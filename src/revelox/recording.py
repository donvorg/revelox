"""Call recording, transcription, and report generation."""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

from pydub import AudioSegment

from revelox.tts import MULAW_SAMPLE_RATE

logger = logging.getLogger(__name__)


@dataclass
class CallResult:
    """Accumulated state from a single call."""

    call_sid: str = ""
    stream_sid: str = ""
    started_at: float = 0.0
    ended_at: float = 0.0
    turn_responses: list[bytes] = field(default_factory=list)


class TranscriptionError(Exception):
    """Raised when STT transcription fails."""


def transcribe_audio(audio: bytes) -> str:
    """Transcribe raw mulaw 8kHz audio bytes via Deepgram STT.

    Returns an empty string if the audio is too short to contain speech.
    """
    if len(audio) < MULAW_SAMPLE_RATE // 10:
        return ""

    api_key = os.environ.get("DEEPGRAM_API_KEY")
    if not api_key:
        raise TranscriptionError("DEEPGRAM_API_KEY environment variable is not set")

    try:
        from deepgram import DeepgramClient
    except ImportError:
        raise TranscriptionError(
            "deepgram-sdk is not installed. Install with: pip install 'revelox[deepgram]'"
        ) from None

    client = DeepgramClient(api_key=api_key)

    try:
        response = client.listen.v1.media.transcribe_file(
            request=audio,
            encoding="mulaw",
            model="nova-3",
            punctuate=True,
            smart_format=True,
        )
    except Exception as e:
        raise TranscriptionError(f"Deepgram STT failed: {e}") from None

    channels = response.results.channels
    if not channels:
        return ""
    alternatives = channels[0].alternatives
    if not alternatives:
        return ""
    return alternatives[0].transcript or ""


def _mulaw_to_segment(raw: bytes) -> AudioSegment:
    """Convert raw mulaw 8kHz bytes to a pydub AudioSegment."""
    return AudioSegment(
        data=raw,
        sample_width=1,
        frame_rate=MULAW_SAMPLE_RATE,
        channels=1,
    )


def save_recording(
    call_result: CallResult,
    audio_buffers: list[bytes],
    script_turns: list[str],
    output_dir: Path,
) -> Path:
    """Save call recordings and a JSON report to disk.

    Args:
        call_result: Accumulated call state with response audio.
        audio_buffers: Outbound audio buffers (one per script turn).
        script_turns: Original script text for each turn.
        output_dir: Directory to write output files to.

    Returns:
        The output directory path.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    outbound_audio = b"".join(audio_buffers)
    if outbound_audio:
        seg = _mulaw_to_segment(outbound_audio)
        seg.export(str(output_dir / "outbound.wav"), format="wav")

    inbound_audio = b"".join(call_result.turn_responses)
    if inbound_audio:
        seg = _mulaw_to_segment(inbound_audio)
        seg.export(str(output_dir / "inbound.wav"), format="wav")

    turns = []
    for i, text in enumerate(script_turns):
        entry: dict[str, object] = {"index": i, "text": text}
        if i < len(call_result.turn_responses):
            response_audio = call_result.turn_responses[i]
            if response_audio:
                try:
                    entry["transcript"] = transcribe_audio(response_audio)
                except TranscriptionError:
                    logger.warning("Transcription failed for turn %d, skipping", i)
                    entry["transcript"] = ""
            else:
                entry["transcript"] = ""
        turns.append(entry)

    report = {
        "call_sid": call_result.call_sid,
        "stream_sid": call_result.stream_sid,
        "started_at": _iso_timestamp(call_result.started_at),
        "ended_at": _iso_timestamp(call_result.ended_at),
        "turns": turns,
    }

    report_path = output_dir / "report.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n")

    return output_dir


def _iso_timestamp(epoch: float) -> str:
    """Convert an epoch float to an ISO 8601 string."""
    if epoch == 0.0:
        return ""
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(epoch))
