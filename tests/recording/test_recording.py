"""Tests for call recording and report generation."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from revelox.recording import (
    CallResult,
    TranscriptionError,
    save_recording,
    transcribe_audio,
)

MULAW_SAMPLE_RATE = 8000
DEEPGRAM_CLIENT = "deepgram.DeepgramClient"


class TestTranscribeAudio:
    """Tests for the transcribe_audio function."""

    def test_short_audio_returns_empty(self) -> None:
        short = b"\x80" * (MULAW_SAMPLE_RATE // 10 - 1)
        assert transcribe_audio(short) == ""

    def test_missing_api_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("DEEPGRAM_API_KEY", raising=False)
        audio = b"\x80" * MULAW_SAMPLE_RATE
        with pytest.raises(TranscriptionError, match="DEEPGRAM_API_KEY"):
            transcribe_audio(audio)

    @patch(DEEPGRAM_CLIENT)
    def test_returns_transcript(
        self, mock_client_cls: MagicMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("DEEPGRAM_API_KEY", "fake-key")

        alt = MagicMock()
        alt.transcript = "Hello there"
        channel = MagicMock()
        channel.alternatives = [alt]
        response = MagicMock()
        response.results.channels = [channel]

        mock_client_cls.return_value.listen.v1.media.transcribe_file.return_value = response

        audio = b"\x80" * MULAW_SAMPLE_RATE
        assert transcribe_audio(audio) == "Hello there"

    @patch(DEEPGRAM_CLIENT)
    def test_empty_channels_returns_empty(
        self, mock_client_cls: MagicMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("DEEPGRAM_API_KEY", "fake-key")
        response = MagicMock()
        response.results.channels = []
        mock_client_cls.return_value.listen.v1.media.transcribe_file.return_value = response

        assert transcribe_audio(b"\x80" * MULAW_SAMPLE_RATE) == ""

    @patch(DEEPGRAM_CLIENT)
    def test_api_error_raises(
        self, mock_client_cls: MagicMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("DEEPGRAM_API_KEY", "fake-key")
        mock_client_cls.return_value.listen.v1.media.transcribe_file.side_effect = (
            RuntimeError("API down")
        )

        with pytest.raises(TranscriptionError, match="Deepgram STT failed"):
            transcribe_audio(b"\x80" * MULAW_SAMPLE_RATE)

    @patch(DEEPGRAM_CLIENT)
    def test_called_with_correct_params(
        self, mock_client_cls: MagicMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("DEEPGRAM_API_KEY", "fake-key")

        alt = MagicMock()
        alt.transcript = "test"
        channel = MagicMock()
        channel.alternatives = [alt]
        response = MagicMock()
        response.results.channels = [channel]

        transcribe = mock_client_cls.return_value.listen.v1.media.transcribe_file
        transcribe.return_value = response

        audio = b"\x80" * MULAW_SAMPLE_RATE
        transcribe_audio(audio)

        transcribe.assert_called_once_with(
            request=audio,
            encoding="mulaw",
            sample_rate=MULAW_SAMPLE_RATE,
            model="nova-3",
            punctuate=True,
            smart_format=True,
        )


class TestSaveRecording:
    """Tests for the save_recording function."""

    def test_creates_output_directory(self, tmp_path: Path) -> None:
        output = tmp_path / "results" / "CA_test"
        call_result = CallResult(call_sid="CA_test", stream_sid="MZ_test")

        with patch("revelox.recording.transcribe_audio", return_value=""):
            result = save_recording(call_result, [], [], output)

        assert result == output
        assert output.is_dir()

    def test_writes_outbound_wav(self, tmp_path: Path) -> None:
        output = tmp_path / "out"
        call_result = CallResult()
        audio = b"\x80" * 1600

        with patch("revelox.recording.transcribe_audio", return_value=""):
            save_recording(call_result, [audio], ["hello"], output)

        wav_path = output / "outbound.wav"
        assert wav_path.exists()
        assert wav_path.stat().st_size > 0

    def test_writes_inbound_wav(self, tmp_path: Path) -> None:
        output = tmp_path / "out"
        response_audio = b"\x80" * 1600
        call_result = CallResult(turn_responses=[response_audio])

        with patch("revelox.recording.transcribe_audio", return_value=""):
            save_recording(call_result, [b"\x80" * 160], ["hello"], output)

        wav_path = output / "inbound.wav"
        assert wav_path.exists()
        assert wav_path.stat().st_size > 0

    def test_no_wav_when_empty(self, tmp_path: Path) -> None:
        output = tmp_path / "out"
        call_result = CallResult()

        with patch("revelox.recording.transcribe_audio", return_value=""):
            save_recording(call_result, [], [], output)

        assert not (output / "outbound.wav").exists()
        assert not (output / "inbound.wav").exists()

    def test_report_json_structure(self, tmp_path: Path) -> None:
        output = tmp_path / "out"
        call_result = CallResult(
            call_sid="CA_123",
            stream_sid="MZ_456",
            started_at=1720000000.0,
            ended_at=1720000060.0,
            turn_responses=[b"\x80" * MULAW_SAMPLE_RATE],
        )

        with patch("revelox.recording.transcribe_audio", return_value="I can help"):
            save_recording(
                call_result,
                [b"\x80" * 160],
                ["Hello, how are you?"],
                output,
            )

        report = json.loads((output / "report.json").read_text())
        assert report["call_sid"] == "CA_123"
        assert report["stream_sid"] == "MZ_456"
        assert report["started_at"] != ""
        assert report["ended_at"] != ""
        assert len(report["turns"]) == 1
        assert report["turns"][0]["index"] == 0
        assert report["turns"][0]["text"] == "Hello, how are you?"
        assert report["turns"][0]["transcript"] == "I can help"

    def test_transcription_failure_logs_warning(self, tmp_path: Path) -> None:
        output = tmp_path / "out"
        call_result = CallResult(
            turn_responses=[b"\x80" * MULAW_SAMPLE_RATE],
        )

        with patch(
            "revelox.recording.transcribe_audio",
            side_effect=TranscriptionError("fail"),
        ):
            save_recording(call_result, [b"\x80" * 160], ["hi"], output)

        report = json.loads((output / "report.json").read_text())
        assert report["turns"][0]["transcript"] == ""

    def test_more_turns_than_responses(self, tmp_path: Path) -> None:
        output = tmp_path / "out"
        call_result = CallResult(turn_responses=[b"\x80" * 1600])

        with patch("revelox.recording.transcribe_audio", return_value="response"):
            save_recording(
                call_result,
                [b"\x80" * 160, b"\x80" * 160],
                ["turn one", "turn two"],
                output,
            )

        report = json.loads((output / "report.json").read_text())
        assert len(report["turns"]) == 2
        assert report["turns"][0]["transcript"] == "response"
        assert "transcript" not in report["turns"][1]
