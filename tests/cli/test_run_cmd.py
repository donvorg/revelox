"""Tests for the `revelox run` command."""

from pathlib import Path
from threading import Event
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from revelox.cli.main import cli

runner = CliRunner()

VALID_FROM = "+15551234567"
VALID_TARGET = "+15559876543"
SCRIPT_CONTENT = "<START_TURN>\nHello\n<END_TURN>\n"

MINIMAL_CONFIG = f"""\
version: "1"
run:
  target: "{VALID_TARGET}"
  from_number: "{VALID_FROM}"
"""


@pytest.fixture
def script_file(tmp_path: Path) -> str:
    """Create a minimal script file and return its path."""
    p = tmp_path / "test.txt"
    p.write_text(SCRIPT_CONTENT)
    return str(p)


def _base_args(script_file: str) -> list[str]:
    return ["run", "--from", VALID_FROM, "--target", VALID_TARGET, "--script", script_file, "--yes"]


def _mock_create_app(audio_buffers, call_done: Event, call_result=None):
    call_done.set()
    return MagicMock()


def _make_server_class():
    mock_cls = MagicMock()
    mock_cls.return_value.started = True
    return mock_cls


@pytest.fixture
def pipeline_mocks(monkeypatch: pytest.MonkeyPatch):
    """Patch the full Twilio pipeline so run_command completes without blocking."""
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://test.ngrok.io")
    with (
        patch("revelox.tts.synthesize_script", return_value=[b"\xff" * 160]),
        patch("revelox.server.create_app", side_effect=_mock_create_app),
        patch("uvicorn.Config"),
        patch("uvicorn.Server", new_callable=_make_server_class),
        patch("revelox.dialer.dial", return_value="CA_test"),
        patch("revelox.recording.save_recording"),
    ):
        yield


# --- Happy path (mocked pipeline) ---


def test_run_with_cli_args(pipeline_mocks, script_file: str) -> None:
    result = runner.invoke(cli, _base_args(script_file))
    assert result.exit_code == 0, result.output
    assert VALID_FROM in result.output
    assert VALID_TARGET in result.output
    assert "CA_test" in result.output


def test_run_with_env_vars(pipeline_mocks, script_file: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TWILIO_PHONE_NUMBER", VALID_FROM)
    monkeypatch.setenv("REVELOX_TARGET_NUMBER", VALID_TARGET)
    result = runner.invoke(cli, ["run", "--script", script_file, "--yes"])
    assert result.exit_code == 0, result.output


def test_run_cli_args_override_config(pipeline_mocks, tmp_path: Path, script_file: str) -> None:
    config = tmp_path / "env_fallback.yaml"
    config.write_text(f"""\
version: "1"
run:
  target: "+19999999999"
  from_number: "+10000000000"
""")
    result = runner.invoke(
        cli, ["run", "--config", str(config), "--from", VALID_FROM, "--target", VALID_TARGET, "--script", script_file, "--yes"]
    )
    assert result.exit_code == 0
    assert VALID_FROM in result.output
    assert VALID_TARGET in result.output


# --- Config file ---


def test_run_loads_config_file(pipeline_mocks, tmp_path: Path, script_file: str) -> None:
    config = tmp_path / "revelox.config.yaml"
    config.write_text(MINIMAL_CONFIG)
    result = runner.invoke(cli, ["run", "--config", str(config), "--script", script_file, "--yes"])
    assert result.exit_code == 0
    assert VALID_TARGET in result.output
    assert VALID_FROM in result.output


def test_run_cli_overrides_config(pipeline_mocks, tmp_path: Path, script_file: str) -> None:
    config = tmp_path / "revelox.config.yaml"
    config.write_text(MINIMAL_CONFIG)
    override = "+19998887777"
    result = runner.invoke(cli, ["run", "--config", str(config), "--target", override, "--script", script_file, "--yes"])
    assert result.exit_code == 0
    assert override in result.output


def test_run_explicit_config_path(pipeline_mocks, tmp_path: Path, script_file: str) -> None:
    config_file = tmp_path / "custom.yaml"
    config_file.write_text(MINIMAL_CONFIG)
    result = runner.invoke(
        cli, ["run", "--config", str(config_file), "--script", script_file, "--yes"]
    )
    assert result.exit_code == 0
    assert VALID_TARGET in result.output


def test_run_explicit_config_missing_errors(tmp_path: Path, script_file: str) -> None:
    result = runner.invoke(
        cli, ["run", "--config", str(tmp_path / "nonexistent.yaml"), "--script", script_file, "--yes"]
    )
    assert result.exit_code != 0
    assert "not found" in result.output


def test_run_bad_config_file(tmp_path: Path, script_file: str) -> None:
    config_file = tmp_path / "bad.yaml"
    config_file.write_text("not: valid: yaml: [")
    result = runner.invoke(cli, ["run", "--config", str(config_file), "--script", script_file, "--yes"])
    assert result.exit_code != 0


def test_run_partial_config_with_cli_override(pipeline_mocks, tmp_path: Path, script_file: str) -> None:
    config = tmp_path / "revelox.config.yaml"
    config.write_text(f"""\
version: "1"
run:
  target: "{VALID_TARGET}"
""")
    result = runner.invoke(
        cli, ["run", "--config", str(config), "--from", VALID_FROM, "--script", script_file, "--yes"]
    )
    assert result.exit_code == 0
    assert VALID_TARGET in result.output
    assert VALID_FROM in result.output


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


def test_run_rejects_invalid_e164_from(script_file: str) -> None:
    result = runner.invoke(
        cli, ["run", "--from", "not-e164", "--target", VALID_TARGET, "--script", script_file, "--yes"]
    )
    assert result.exit_code != 0
    assert "not valid E.164" in result.output


def test_run_rejects_invalid_e164_target(script_file: str) -> None:
    result = runner.invoke(
        cli, ["run", "--from", VALID_FROM, "--target", "not-e164", "--script", script_file, "--yes"]
    )
    assert result.exit_code != 0
    assert "not valid E.164" in result.output


def test_run_rejects_invalid_e164_from_in_config(tmp_path: Path, script_file: str) -> None:
    config = tmp_path / "bad_e164.yaml"
    config.write_text(f"""\
version: "1"
run:
  target: "{VALID_TARGET}"
  from_number: "not-e164"
""")
    result = runner.invoke(cli, ["run", "--config", str(config), "--script", script_file, "--yes"])
    assert result.exit_code != 0
