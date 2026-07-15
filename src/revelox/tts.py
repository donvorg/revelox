"""Deepgram text-to-speech synthesis for scripted turns."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

from revelox.script import parse_script

MULAW_SILENCE_BYTE = b"\xff"
MULAW_SAMPLE_RATE = 8000
SILENCE_DURATION_SECONDS = 1
SILENCE_BYTES = MULAW_SILENCE_BYTE * (MULAW_SAMPLE_RATE * SILENCE_DURATION_SECONDS)


class TTSError(Exception):
    """Raised when TTS synthesis fails."""


def synthesize_turns(turns: list[str]) -> list[bytes]:
    """Synthesize each turn into raw mulaw 8kHz audio via Deepgram.

    Empty/whitespace-only turns produce 1 second of mulaw silence.

    Args:
        turns: List of turn text strings from :func:`~revelox.script.parse_script`.

    Returns:
        List of raw audio bytes, one entry per turn.

    Raises:
        TTSError: If the Deepgram API key is missing or synthesis fails.
    """
    api_key = os.environ.get("DEEPGRAM_API_KEY")
    if not api_key:
        raise TTSError("DEEPGRAM_API_KEY environment variable is not set")

    try:
        from deepgram import DeepgramClient
    except ImportError:
        raise TTSError(
            "deepgram-sdk is not installed. Install with: pip install 'revelox[deepgram]'"
        ) from None

    client = DeepgramClient(api_key=api_key)
    results: list[bytes] = []

    for turn in turns:
        if not turn.strip():
            results.append(SILENCE_BYTES)
            continue

        try:
            chunks = client.speak.v1.audio.generate(
                text=turn,
                model="aura-2-thalia-en",
                encoding="mulaw",
                sample_rate=MULAW_SAMPLE_RATE,
                container="none",
            )
            audio = b"".join(chunks)
        except Exception as e:
            raise TTSError(f"Deepgram TTS failed for turn: {e}") from None

        results.append(audio)

    return results


def synthesize_script(path: Path) -> list[bytes]:
    """Parse a script file and synthesize all turns to mulaw audio.

    Convenience wrapper combining :func:`~revelox.script.parse_script`
    and :func:`synthesize_turns`.

    Args:
        path: Path to the script ``.txt`` file.

    Returns:
        List of raw mulaw 8kHz audio bytes, one entry per turn.
    """
    turns = parse_script(path)
    return synthesize_turns(turns)
