"""FastAPI server for Twilio media stream WebSocket."""

from __future__ import annotations

import asyncio
import base64
import json
import logging
from typing import Any

from fastapi import FastAPI, Request, WebSocket
from fastapi.responses import Response

logger = logging.getLogger(__name__)

FRAME_SIZE = 160
FRAME_DURATION_S = 0.02


def create_app(audio_buffers: list[bytes], call_done: asyncio.Event | None = None) -> FastAPI:
    """Build a FastAPI app that streams pre-synthesized audio to Twilio.

    Args:
        audio_buffers: List of raw mulaw 8kHz audio byte buffers to stream.
        call_done: Optional event set when the call ends.
    """
    app = FastAPI()
    app.state.audio_buffers = audio_buffers
    app.state.call_done = call_done

    @app.post("/voice")
    async def voice(request: Request) -> Response:
        """Return TwiML that opens a media stream WebSocket."""
        from twilio.twiml.voice_response import Connect, VoiceResponse

        host = request.headers.get("host", "localhost")
        scheme = "wss" if request.url.scheme == "https" else "ws"

        resp = VoiceResponse()
        connect: Connect = resp.connect()  # type: ignore[assignment]
        connect.stream(url=f"{scheme}://{host}/media-stream")
        return Response(content=str(resp), media_type="application/xml")

    @app.websocket("/media-stream")
    async def media_stream(ws: WebSocket) -> None:
        """Handle the Twilio media stream WebSocket."""
        await ws.accept()
        ws_lock = asyncio.Lock()
        stream_task: asyncio.Task[None] | None = None

        async def _stream_audio(stream_sid: str) -> None:
            buffers: list[bytes] = app.state.audio_buffers
            for buf in buffers:
                for offset in range(0, len(buf), FRAME_SIZE):
                    frame = buf[offset : offset + FRAME_SIZE]
                    payload = base64.b64encode(frame).decode("ascii")
                    msg = json.dumps(
                        {
                            "event": "media",
                            "streamSid": stream_sid,
                            "media": {"payload": payload},
                        }
                    )
                    async with ws_lock:
                        await ws.send_text(msg)
                    await asyncio.sleep(FRAME_DURATION_S)

        try:
            while True:
                raw = await ws.receive_text()
                data: dict[str, Any] = json.loads(raw)
                event = data.get("event")

                if event == "start":
                    stream_sid = data["start"]["streamSid"]
                    logger.info("Stream started: %s", stream_sid)
                    stream_task = asyncio.create_task(_stream_audio(stream_sid))

                elif event == "stop":
                    logger.info("Stream stopped")
                    break

        except Exception:
            logger.debug("WebSocket closed")
        finally:
            if stream_task and not stream_task.done():
                stream_task.cancel()
            if app.state.call_done:
                app.state.call_done.set()

    return app
