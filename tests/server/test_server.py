"""Tests for the FastAPI Twilio media stream server."""

import base64
import json

import pytest
from httpx import ASGITransport, AsyncClient
from httpx_ws import WebSocketDisconnect

from revelox.server import FRAME_SIZE, PLAYBACK_DONE_MARK, create_app


@pytest.fixture
def audio_buffers() -> list[bytes]:
    """Small test audio buffers: 2 frames + 1 frame."""
    return [b"\x80" * 320, b"\xff" * 160]


@pytest.fixture
def app(audio_buffers: list[bytes]) -> object:
    """Create a test app with small audio buffers."""
    return create_app(audio_buffers)


class TestVoiceEndpoint:
    """Tests for the /voice TwiML endpoint."""

    async def test_returns_twiml_with_stream(self, app: object) -> None:
        transport = ASGITransport(app=app)  # type: ignore[arg-type]
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/voice")
        assert resp.status_code == 200
        assert "application/xml" in resp.headers["content-type"]
        body = resp.text
        assert "<Stream" in body
        assert "media-stream" in body


class TestMediaStreamWebSocket:
    """Tests for the /media-stream WebSocket endpoint."""

    async def test_streams_audio_frames(self, app: object) -> None:
        from httpx_ws import aconnect_ws
        from httpx_ws.transport import ASGIWebSocketTransport

        async with (
            AsyncClient(
                transport=ASGIWebSocketTransport(app=app),  # type: ignore[arg-type]
                base_url="http://test",
            ) as client,
            aconnect_ws("/media-stream", client) as ws,
        ):
                start_msg = json.dumps(
                    {
                        "event": "start",
                        "start": {"streamSid": "MZ_test", "callSid": "CA_test"},
                    }
                )
                await ws.send_text(start_msg)

                frames: list[str] = []
                for _ in range(3):
                    raw = await ws.receive_text()
                    data = json.loads(raw)
                    assert data["event"] == "media"
                    assert data["streamSid"] == "MZ_test"
                    frames.append(data["media"]["payload"])

                for payload in frames:
                    decoded = base64.b64decode(payload)
                    assert len(decoded) == FRAME_SIZE

                raw = await ws.receive_text()
                data = json.loads(raw)
                assert data == {
                    "event": "mark",
                    "streamSid": "MZ_test",
                    "mark": {"name": PLAYBACK_DONE_MARK},
                }

                await ws.send_text(
                    json.dumps(
                        {"event": "mark", "mark": {"name": PLAYBACK_DONE_MARK}}
                    )
                )
                with pytest.raises(WebSocketDisconnect):
                    await ws.receive_text()
