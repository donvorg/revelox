"""Tests for Deepgram TTS synthesis."""

from unittest.mock import patch

import pytest

from revelox.tts import MULAW_SAMPLE_RATE, SILENCE_BYTES, TTSError, synthesize_turns

DEEPGRAM_CLIENT = "deepgram.DeepgramClient"


def test_missing_api_key(monkeypatch):
    monkeypatch.delenv("DEEPGRAM_API_KEY", raising=False)
    with pytest.raises(TTSError, match="DEEPGRAM_API_KEY"):
        synthesize_turns(["hello"])


@patch(DEEPGRAM_CLIENT)
def test_empty_turn_produces_silence(mock_client_cls, monkeypatch):
    monkeypatch.setenv("DEEPGRAM_API_KEY", "fake-key")
    result = synthesize_turns([""])
    assert result == [SILENCE_BYTES]
    assert len(result[0]) == MULAW_SAMPLE_RATE


@patch(DEEPGRAM_CLIENT)
def test_whitespace_only_turn_produces_silence(mock_client_cls, monkeypatch):
    monkeypatch.setenv("DEEPGRAM_API_KEY", "fake-key")
    result = synthesize_turns(["   \n\t  "])
    assert result == [SILENCE_BYTES]


@patch(DEEPGRAM_CLIENT)
def test_synthesizes_each_turn(mock_client_cls, monkeypatch):
    monkeypatch.setenv("DEEPGRAM_API_KEY", "fake-key")
    mock_generate = mock_client_cls.return_value.speak.v1.audio.generate
    mock_generate.return_value = iter([b"\x00\x01", b"\x02\x03"])

    result = synthesize_turns(["hello", "world"])
    assert len(result) == 2
    assert all(isinstance(chunk, bytes) for chunk in result)
    assert mock_generate.call_count == 2


@patch(DEEPGRAM_CLIENT)
def test_deepgram_called_with_correct_params(mock_client_cls, monkeypatch):
    monkeypatch.setenv("DEEPGRAM_API_KEY", "fake-key")
    mock_generate = mock_client_cls.return_value.speak.v1.audio.generate
    mock_generate.return_value = iter([b"\x00"])

    synthesize_turns(["test text"])

    mock_generate.assert_called_once_with(
        text="test text",
        model="aura-2-thalia-en",
        encoding="mulaw",
        sample_rate=MULAW_SAMPLE_RATE,
        container="none",
    )


@patch(DEEPGRAM_CLIENT)
def test_mixed_empty_and_text_turns(mock_client_cls, monkeypatch):
    monkeypatch.setenv("DEEPGRAM_API_KEY", "fake-key")
    mock_generate = mock_client_cls.return_value.speak.v1.audio.generate
    mock_generate.return_value = iter([b"\xaa\xbb"])

    result = synthesize_turns(["hello", "", "goodbye"])
    assert len(result) == 3
    assert result[1] == SILENCE_BYTES
    assert mock_generate.call_count == 2


@patch(DEEPGRAM_CLIENT)
def test_deepgram_error_raises_tts_error(mock_client_cls, monkeypatch):
    monkeypatch.setenv("DEEPGRAM_API_KEY", "fake-key")
    mock_generate = mock_client_cls.return_value.speak.v1.audio.generate
    mock_generate.side_effect = RuntimeError("API down")

    with pytest.raises(TTSError, match="Deepgram TTS failed"):
        synthesize_turns(["hello"])
