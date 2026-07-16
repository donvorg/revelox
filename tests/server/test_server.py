"""Tests for the FastAPI Twilio media stream server."""

import asyncio
import base64
import json

import pytest
from httpx import ASGITransport, AsyncClient

from revelox.recording import CallResult
from revelox.server import (
    FRAME_SIZE,
    MIN_RESPONSE_FRAMES,
    SILENCE_THRESHOLD_FRAMES,
    create_app,
)


@pytest.fixture
def audio_buffers() -> list[bytes]:
    """Small test audio buffers: 2 frames + 1 frame."""
    return [b"\x80" * 320, b"\xff" * 160]


@pytest.fixture
def single_turn_buffers() -> list[bytes]:
    """Single turn with 1 frame."""
    return [b"\x80" * 160]


@pytest.fixture
def two_turn_buffers() -> list[bytes]:
    """Two turns, 1 frame each."""
    return [b"\x80" * 160, b"\x80" * 160]


@pytest.fixture
def app(audio_buffers: list[bytes]) -> object:
    """Create a test app with small audio buffers."""
    return create_app(audio_buffers)


def _start_msg(stream_sid: str = "MZ_test", call_sid: str = "CA_test") -> str:
    return json.dumps(
        {
            "event": "start",
            "start": {"streamSid": stream_sid, "callSid": call_sid},
        }
    )


def _mark_msg(name: str, stream_sid: str = "MZ_test") -> str:
    return json.dumps(
        {
            "event": "mark",
            "mark": {"name": name},
        }
    )


def _media_msg(audio: bytes, stream_sid: str = "MZ_test") -> str:
    return json.dumps(
        {
            "event": "media",
            "streamSid": stream_sid,
            "media": {"payload": base64.b64encode(audio).decode("ascii")},
        }
    )


def _stop_msg() -> str:
    return json.dumps({"event": "stop"})


async def _receive_until_mark(ws: object) -> tuple[list[dict], dict]:
    """Receive messages until a mark is found. Returns (media_frames, mark_data)."""
    frames: list[dict] = []
    while True:
        raw = await ws.receive_text()
        data = json.loads(raw)
        if data["event"] == "mark":
            return frames, data
        assert data["event"] == "media"
        frames.append(data)


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

    async def test_streams_audio_frames_and_mark(self, single_turn_buffers: list[bytes]) -> None:
        """Single turn: sends 1 frame then a mark."""
        app = create_app(single_turn_buffers)

        from httpx_ws import aconnect_ws
        from httpx_ws.transport import ASGIWebSocketTransport

        async with (
            AsyncClient(
                transport=ASGIWebSocketTransport(app=app),  # type: ignore[arg-type]
                base_url="http://test",
            ) as client,
            aconnect_ws("/media-stream", client) as ws,
        ):
            await ws.send_text(_start_msg())

            frames, mark = await _receive_until_mark(ws)
            assert len(frames) == 1
            assert mark["mark"]["name"] == "turn-0"

            decoded = base64.b64decode(frames[0]["media"]["payload"])
            assert len(decoded) == FRAME_SIZE

            await ws.send_text(_mark_msg("turn-0"))
            await asyncio.sleep(0.05)
            await ws.send_text(_stop_msg())

    async def test_call_result_populated(self, single_turn_buffers: list[bytes]) -> None:
        """CallResult gets call_sid, stream_sid, and timestamps."""
        call_result = CallResult()
        app = create_app(single_turn_buffers, call_result=call_result)

        from httpx_ws import aconnect_ws
        from httpx_ws.transport import ASGIWebSocketTransport

        async with (
            AsyncClient(
                transport=ASGIWebSocketTransport(app=app),  # type: ignore[arg-type]
                base_url="http://test",
            ) as client,
            aconnect_ws("/media-stream", client) as ws,
        ):
            await ws.send_text(_start_msg("MZ_abc", "CA_abc"))

            await _receive_until_mark(ws)

            await ws.send_text(_mark_msg("turn-0"))
            await asyncio.sleep(0.05)
            await ws.send_text(_stop_msg())

        assert call_result.call_sid == "CA_abc"
        assert call_result.stream_sid == "MZ_abc"
        assert call_result.started_at > 0
        assert call_result.ended_at >= call_result.started_at

    async def test_incoming_media_captured(self, single_turn_buffers: list[bytes]) -> None:
        """Response audio from inbound media events is captured."""
        call_result = CallResult()
        app = create_app(single_turn_buffers, call_result=call_result)

        from httpx_ws import aconnect_ws
        from httpx_ws.transport import ASGIWebSocketTransport

        async with (
            AsyncClient(
                transport=ASGIWebSocketTransport(app=app),  # type: ignore[arg-type]
                base_url="http://test",
            ) as client,
            aconnect_ws("/media-stream", client) as ws,
        ):
            await ws.send_text(_start_msg())
            await _receive_until_mark(ws)

            await ws.send_text(_mark_msg("turn-0"))

            await asyncio.sleep(0.05)

            for _ in range(MIN_RESPONSE_FRAMES):
                await ws.send_text(_media_msg(b"\x80" * FRAME_SIZE))

            for _ in range(SILENCE_THRESHOLD_FRAMES):
                await ws.send_text(_media_msg(b"\xff" * FRAME_SIZE))

            await asyncio.sleep(0.1)
            await ws.send_text(_stop_msg())

        assert len(call_result.turn_responses) == 1
        expected_len = (MIN_RESPONSE_FRAMES + SILENCE_THRESHOLD_FRAMES) * FRAME_SIZE
        assert len(call_result.turn_responses[0]) == expected_len

    async def test_turn_taking_two_turns(self, two_turn_buffers: list[bytes]) -> None:
        """Two-turn script: turn 0 plays, response captured, turn 1 plays."""
        call_result = CallResult()
        app = create_app(two_turn_buffers, call_result=call_result)

        from httpx_ws import aconnect_ws
        from httpx_ws.transport import ASGIWebSocketTransport

        async with (
            AsyncClient(
                transport=ASGIWebSocketTransport(app=app),  # type: ignore[arg-type]
                base_url="http://test",
            ) as client,
            aconnect_ws("/media-stream", client) as ws,
        ):
            await ws.send_text(_start_msg())

            frames_0, mark_0 = await _receive_until_mark(ws)
            assert mark_0["mark"]["name"] == "turn-0"
            assert len(frames_0) == 1

            await ws.send_text(_mark_msg("turn-0"))
            await asyncio.sleep(0.05)

            for _ in range(MIN_RESPONSE_FRAMES):
                await ws.send_text(_media_msg(b"\x80" * FRAME_SIZE))
            for _ in range(SILENCE_THRESHOLD_FRAMES):
                await ws.send_text(_media_msg(b"\xff" * FRAME_SIZE))

            frames_1, mark_1 = await _receive_until_mark(ws)
            assert mark_1["mark"]["name"] == "turn-1"
            assert len(frames_1) == 1

            await ws.send_text(_mark_msg("turn-1"))
            await asyncio.sleep(0.05)

            for _ in range(SILENCE_THRESHOLD_FRAMES):
                await ws.send_text(_media_msg(b"\xff" * FRAME_SIZE))

            await asyncio.sleep(0.1)
            await ws.send_text(_stop_msg())

        assert len(call_result.turn_responses) == 2
        expected = (MIN_RESPONSE_FRAMES + SILENCE_THRESHOLD_FRAMES) * FRAME_SIZE
        assert len(call_result.turn_responses[0]) == expected

    async def test_response_timeout_advances_to_next_turn(
        self, two_turn_buffers: list[bytes]
    ) -> None:
        """If no response after mark, sender times out and sends next turn."""
        call_result = CallResult()
        app = create_app(two_turn_buffers, call_result=call_result)

        from httpx_ws import aconnect_ws
        from httpx_ws.transport import ASGIWebSocketTransport

        import revelox.server as server_module

        original_timeout = server_module.RESPONSE_TIMEOUT_S
        server_module.RESPONSE_TIMEOUT_S = 0.1
        try:
            async with (
                AsyncClient(
                    transport=ASGIWebSocketTransport(app=app),  # type: ignore[arg-type]
                    base_url="http://test",
                ) as client,
                aconnect_ws("/media-stream", client) as ws,
            ):
                await ws.send_text(_start_msg())

                _, mark_0 = await _receive_until_mark(ws)
                assert mark_0["mark"]["name"] == "turn-0"

                await ws.send_text(_mark_msg("turn-0"))

                _, mark_1 = await _receive_until_mark(ws)
                assert mark_1["mark"]["name"] == "turn-1"

                await ws.send_text(_mark_msg("turn-1"))
                await asyncio.sleep(0.15)
                await ws.send_text(_stop_msg())
        finally:
            server_module.RESPONSE_TIMEOUT_S = original_timeout

        assert len(call_result.turn_responses) == 2
        assert call_result.turn_responses[0] == b""
