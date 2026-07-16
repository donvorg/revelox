"""FastAPI server for Twilio media stream WebSocket with turn-taking."""

from __future__ import annotations

import asyncio
import base64
import contextlib
import json
import logging
import time
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import threading

    from revelox.recording import CallResult

from fastapi import FastAPI, Request, WebSocket
from fastapi.responses import Response

from revelox.tts import MULAW_SILENCE_BYTE

logger = logging.getLogger(__name__)

FRAME_SIZE = 160
FRAME_DURATION_S = 0.02
SILENCE_THRESHOLD_FRAMES = 40
MIN_RESPONSE_FRAMES = 10
RESPONSE_TIMEOUT_S = 10.0
SILENCE_FRAME = MULAW_SILENCE_BYTE * FRAME_SIZE


def create_app(
    audio_buffers: list[bytes],
    call_done: threading.Event | None = None,
    call_result: CallResult | None = None,
) -> FastAPI:
    """Build a FastAPI app that streams pre-synthesized audio to Twilio.

    Args:
        audio_buffers: List of raw mulaw 8kHz audio byte buffers to stream.
        call_done: Optional event set when the call ends.
        call_result: Optional object to accumulate call state and response audio.
    """
    app = FastAPI()
    app.state.audio_buffers = audio_buffers
    app.state.call_done = call_done
    app.state.call_result = call_result

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
        """Handle the Twilio media stream WebSocket with turn-taking."""
        await ws.accept()

        state = _StreamState(
            audio_buffers=app.state.audio_buffers,
            call_result=app.state.call_result,
        )

        sender_task: asyncio.Task[None] | None = None

        try:
            while True:
                raw = await ws.receive_text()
                data: dict[str, Any] = json.loads(raw)
                event = data.get("event")

                if event == "start":
                    state.stream_sid = data["start"]["streamSid"]
                    call_sid = data["start"].get("callSid", "")
                    logger.info("Stream started: %s", state.stream_sid)

                    if state.call_result is not None:
                        state.call_result.stream_sid = state.stream_sid
                        state.call_result.call_sid = call_sid
                        state.call_result.started_at = time.time()

                    sender_task = asyncio.create_task(
                        _sender(ws, state)
                    )

                elif event == "media":
                    payload = data["media"]["payload"]
                    audio = base64.b64decode(payload)
                    state.response_buffer.extend(audio)
                    state.total_response_frames += 1

                    if _is_silence_frame(audio):
                        state.consecutive_silence += 1
                    else:
                        state.consecutive_silence = 0

                    if (
                        not state.response_done.is_set()
                        and state.total_response_frames >= MIN_RESPONSE_FRAMES
                        and state.consecutive_silence >= SILENCE_THRESHOLD_FRAMES
                    ):
                        state.response_done.set()

                elif event == "mark":
                    mark_name = data.get("mark", {}).get("name", "")
                    logger.debug("Mark received: %s", mark_name)
                    state.mark_received.set()

                elif event == "stop":
                    logger.info("Stream stopped")
                    break

        except Exception:
            logger.debug("WebSocket closed")
        finally:
            if sender_task and not sender_task.done():
                sender_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await sender_task
            if state.call_result is not None:
                state.call_result.ended_at = time.time()
            if app.state.call_done:
                app.state.call_done.set()

    return app


class _StreamState:
    """Mutable shared state between the receiver loop and sender task."""

    def __init__(
        self,
        audio_buffers: list[bytes],
        call_result: CallResult | None,
    ) -> None:
        self.audio_buffers = audio_buffers
        self.call_result = call_result
        self.stream_sid = ""

        self.mark_received = asyncio.Event()
        self.response_done = asyncio.Event()

        self.response_buffer = bytearray()
        self.consecutive_silence = 0
        self.total_response_frames = 0


def _is_silence_frame(frame: bytes) -> bool:
    """Check if a frame is all mulaw silence bytes."""
    return frame == SILENCE_FRAME


async def _sender(ws: WebSocket, state: _StreamState) -> None:
    """Send audio turns with mark-based turn-taking."""
    for i, buf in enumerate(state.audio_buffers):
        for offset in range(0, len(buf), FRAME_SIZE):
            frame = buf[offset : offset + FRAME_SIZE]
            payload = base64.b64encode(frame).decode("ascii")
            msg = json.dumps(
                {
                    "event": "media",
                    "streamSid": state.stream_sid,
                    "media": {"payload": payload},
                }
            )
            await ws.send_text(msg)
            await asyncio.sleep(FRAME_DURATION_S)

        state.mark_received.clear()

        mark_msg = json.dumps(
            {
                "event": "mark",
                "streamSid": state.stream_sid,
                "mark": {"name": f"turn-{i}"},
            }
        )
        await ws.send_text(mark_msg)

        await _await_response(state, i)


MARK_TIMEOUT_S = 5.0


async def _await_response(state: _StreamState, turn_index: int) -> None:
    """Wait for the mark echo, then listen for the target's response."""
    try:
        await asyncio.wait_for(state.mark_received.wait(), timeout=MARK_TIMEOUT_S)
    except TimeoutError:
        logger.warning("Mark echo timeout after turn %d", turn_index)

    state.response_buffer.clear()
    state.consecutive_silence = 0
    state.total_response_frames = 0
    state.response_done.clear()

    try:
        await asyncio.wait_for(
            state.response_done.wait(),
            timeout=RESPONSE_TIMEOUT_S,
        )
    except TimeoutError:
        logger.debug("Response timeout after turn %d", turn_index)

    if state.call_result is not None:
        state.call_result.turn_responses.append(bytes(state.response_buffer))
