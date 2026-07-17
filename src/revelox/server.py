"""FastAPI server for Twilio media stream WebSocket."""

from __future__ import annotations

import asyncio
import base64
import contextlib
import json
import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import threading

from fastapi import FastAPI, Request, WebSocket
from fastapi.responses import Response

logger = logging.getLogger(__name__)

FRAME_SIZE = 160
FRAME_DURATION_S = 0.02
PLAYBACK_DONE_MARK = "playback-done"


def create_app(audio_buffers: list[bytes], call_done: threading.Event | None = None) -> FastAPI:
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

        resp = VoiceResponse()
        connect: Connect = resp.connect()  # type: ignore[assignment]
        connect.stream(url=f"wss://{host}/media-stream")
        return Response(content=str(resp), media_type="application/xml")

    @app.websocket("/media-stream")
    async def media_stream(ws: WebSocket) -> None:
        """Handle the Twilio media stream WebSocket."""
        await ws.accept()
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
                    await ws.send_text(msg)
                    await asyncio.sleep(FRAME_DURATION_S)

            await ws.send_text(
                json.dumps(
                    {
                        "event": "mark",
                        "streamSid": stream_sid,
                        "mark": {"name": PLAYBACK_DONE_MARK},
                    }
                )
            )

        try:
            while True:
                raw = await ws.receive_text()
                data: dict[str, Any] = json.loads(raw)
                event = data.get("event")

                if event == "start":
                    stream_sid = data["start"]["streamSid"]
                    logger.info("Stream started: %s", stream_sid)
                    stream_task = asyncio.create_task(_stream_audio(stream_sid))

                elif event == "mark":
                    mark_name = data.get("mark", {}).get("name", "")
                    if mark_name == PLAYBACK_DONE_MARK:
                        logger.info("Playback complete, closing stream")
                        break

                elif event == "stop":
                    logger.info("Stream stopped")
                    break

        except Exception:
            logger.debug("WebSocket closed")
        finally:
            if stream_task and not stream_task.done():
                stream_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await stream_task
            if app.state.call_done:
                app.state.call_done.set()
            with contextlib.suppress(RuntimeError):
                await ws.close()

    return app
