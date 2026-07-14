"""Tests for the `revelox run` command."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from revelox.cli.main import cli

runner = CliRunner()

VALID_FROM = "+15551234567"
VALID_TARGET = "+15559876543"
SCRIPT_CONTENT = "<START_TURN>\nHello\n<END_TURN>\n"


@pytest.fixture
def script_file(tmp_path: Path) -> str:
    """Create a minimal script file and return its path."""
    p = tmp_path / "test.txt"
    p.write_text(SCRIPT_CONTENT)
    return str(p)


def _base_args(script_file: str) -> list[str]:
    return ["run", "--from", VALID_FROM, "--target", VALID_TARGET, "--script", script_file, "--yes"]


# --- Happy path (mocked pipeline) ---


@patch("revelox.dialer.dial", return_value="CA_test")
@patch("uvicorn.Config")
@patch("uvicorn.Server")
@patch("revelox.tts.synthesize_script", return_value=[b"\xff" * 160])
def test_run_with_cli_args(
    mock_synth: MagicMock,
    mock_server: MagicMock,
    mock_config: MagicMock,
    mock_dial: MagicMock,
    script_file: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://test.ngrok.io")
    result = runner.invoke(cli, _base_args(script_file))
    assert result.exit_code == 0, result.output
    assert VALID_FROM in result.output
    assert VALID_TARGET in result.output
    assert "CA_test" in result.output


@patch("revelox.dialer.dial", return_value="CA_test")
@patch("uvicorn.Config")
@patch("uvicorn.Server")
@patch("revelox.tts.synthesize_script", return_value=[b"\xff" * 160])
def test_run_with_env_vars(
    mock_synth: MagicMock,
    mock_server: MagicMock,
    mock_config: MagicMock,
    mock_dial: MagicMock,
    script_file: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TWILIO_PHONE_NUMBER", VALID_FROM)
    monkeypatch.setenv("REVELOX_TARGET_NUMBER", VALID_TARGET)
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://test.ngrok.io")
    result = runner.invoke(cli, ["run", "--script", script_file, "--yes"])
    assert result.exit_code == 0, result.output


# --- Authorization gate ---


def test_run_prompt_declined(script_file: str) -> None:
    result = runner.invoke(
        cli,
        ["run", "--from", VALID_FROM, "--target", VALID_TARGET, "--script", script_file],
        input="n\n",
    )
    assert result.exit_code == 1
    assert "Aborted" in result.output or "aborted" in result.output.lower()


# --- Missing required values ---


def test_run_missing_script() -> None:
    result = runner.invoke(cli, ["run", "--from", VALID_FROM, "--target", VALID_TARGET, "--yes"])
    assert result.exit_code != 0


def test_run_missing_from_number(script_file: str) -> None:
    result = runner.invoke(cli, ["run", "--target", VALID_TARGET, "--script", script_file, "--yes"])
    assert result.exit_code != 0


def test_run_missing_target(script_file: str) -> None:
    result = runner.invoke(cli, ["run", "--from", VALID_FROM, "--script", script_file, "--yes"])
    assert result.exit_code != 0


def test_run_missing_public_base_url(script_file: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PUBLIC_BASE_URL", raising=False)
    result = runner.invoke(cli, _base_args(script_file))
    assert result.exit_code != 0
    assert "PUBLIC_BASE_URL" in result.output


# --- E.164 validation ---


@pytest.mark.parametrize(
    "bad_number",
    [
        "5551234567",
        "+abcdefghij",
        "+",
        "++15551234567",
        "+1555 123 4567",
        "+123",
        "+0123456789",
    ],
)
def test_run_rejects_invalid_e164_from(bad_number: str, script_file: str) -> None:
    result = runner.invoke(
        cli,
        ["run", "--from", bad_number, "--target", VALID_TARGET, "--script", script_file, "--yes"],
    )
    assert result.exit_code != 0
    assert "not valid E.164" in result.output


@pytest.mark.parametrize(
    "bad_number",
    [
        "5559876543",
        "+notanumber",
        "+",
        "+123",
    ],
)
def test_run_rejects_invalid_e164_target(bad_number: str, script_file: str) -> None:
    result = runner.invoke(
        cli, ["run", "--from", VALID_FROM, "--target", bad_number, "--script", script_file, "--yes"]
    )
    assert result.exit_code != 0
    assert "not valid E.164" in result.output
