"""Tests for the `revelox run` command."""

import pytest
from click.testing import CliRunner

from revelox.cli.main import cli

runner = CliRunner()

VALID_FROM = "+15551234567"
VALID_TARGET = "+15559876543"


# --- Happy path ---


def test_run_with_cli_args():
    result = runner.invoke(cli, ["run", "--from", VALID_FROM, "--target", VALID_TARGET])
    assert result.exit_code == 0
    assert VALID_FROM in result.output
    assert VALID_TARGET in result.output


def test_run_with_env_vars(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("TWILIO_PHONE_NUMBER", VALID_FROM)
    monkeypatch.setenv("REVELOX_TARGET_NUMBER", VALID_TARGET)
    result = runner.invoke(cli, ["run"])
    assert result.exit_code == 0
    assert VALID_FROM in result.output


def test_run_cli_args_override_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("TWILIO_PHONE_NUMBER", "+10000000000")
    monkeypatch.setenv("REVELOX_TARGET_NUMBER", "+19999999999")
    result = runner.invoke(cli, ["run", "--from", VALID_FROM, "--target", VALID_TARGET])
    assert result.exit_code == 0
    assert VALID_FROM in result.output
    assert VALID_TARGET in result.output


# --- Missing required values ---


def test_run_missing_from_number():
    result = runner.invoke(cli, ["run", "--target", VALID_TARGET])
    assert result.exit_code != 0


def test_run_missing_target():
    result = runner.invoke(cli, ["run", "--from", VALID_FROM])
    assert result.exit_code != 0


def test_run_missing_both():
    result = runner.invoke(cli, ["run"])
    assert result.exit_code != 0


# --- E.164 validation ---


@pytest.mark.parametrize(
    "bad_number",
    [
        "5551234567",       # missing +
        "+abcdefghij",      # non-digit after +
        "+",                # just a plus
        "++15551234567",    # double plus
        "+1555 123 4567",   # spaces
        "+123",             # too short (< 7 digits)
        "+0123456789",      # leading zero after +
    ],
)
def test_run_rejects_invalid_e164_from(bad_number: str):
    result = runner.invoke(cli, ["run", "--from", bad_number, "--target", VALID_TARGET])
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
def test_run_rejects_invalid_e164_target(bad_number: str):
    result = runner.invoke(cli, ["run", "--from", VALID_FROM, "--target", bad_number])
    assert result.exit_code != 0
    assert "not valid E.164" in result.output


def test_run_rejects_empty_string_from():
    result = runner.invoke(cli, ["run", "--from", "", "--target", VALID_TARGET])
    assert result.exit_code != 0


def test_run_env_var_with_invalid_format(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("TWILIO_PHONE_NUMBER", "not-e164")
    monkeypatch.setenv("REVELOX_TARGET_NUMBER", VALID_TARGET)
    result = runner.invoke(cli, ["run"])
    assert result.exit_code != 0
    assert "not valid E.164" in result.output
