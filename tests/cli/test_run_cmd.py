"""Tests for the `revelox run` command."""

import pytest
from click.testing import CliRunner

from revelox.cli.main import cli

runner = CliRunner()

VALID_FROM = "+15551234567"
VALID_TARGET = "+15559876543"

MINIMAL_CONFIG = f"""\
version: "1"
run:
  target: "{VALID_TARGET}"
  from_number: "{VALID_FROM}"
"""


# --- Happy path ---


def test_run_with_cli_args():
    result = runner.invoke(
        cli, ["run", "--from", VALID_FROM, "--target", VALID_TARGET, "--yes"]
    )
    assert result.exit_code == 0
    assert VALID_FROM in result.output
    assert VALID_TARGET in result.output
    assert "openai/gpt-4o" in result.output


def test_run_cli_args_override_env(tmp_path):
    config = tmp_path / "env_fallback.yaml"
    config.write_text(f"""\
version: "1"
run:
  target: "+19999999999"
  from_number: "+10000000000"
""")
    result = runner.invoke(
        cli, ["run", "--config", str(config), "--from", VALID_FROM, "--target", VALID_TARGET, "--yes"]
    )
    assert result.exit_code == 0
    assert VALID_FROM in result.output
    assert VALID_TARGET in result.output


# --- Config file ---


def test_run_loads_config_file(tmp_path):
    config = tmp_path / "revelox.config.yaml"
    config.write_text(MINIMAL_CONFIG)
    result = runner.invoke(cli, ["run", "--config", str(config), "--yes"])
    assert result.exit_code == 0
    assert VALID_TARGET in result.output
    assert VALID_FROM in result.output


def test_run_cli_overrides_config(tmp_path):
    config = tmp_path / "revelox.config.yaml"
    config.write_text(MINIMAL_CONFIG)
    override = "+19998887777"
    result = runner.invoke(cli, ["run", "--config", str(config), "--target", override, "--yes"])
    assert result.exit_code == 0
    assert override in result.output


def test_run_explicit_config_path(tmp_path):
    config_file = tmp_path / "custom.yaml"
    config_file.write_text(MINIMAL_CONFIG)
    result = runner.invoke(
        cli, ["run", "--config", str(config_file), "--yes"]
    )
    assert result.exit_code == 0
    assert VALID_TARGET in result.output


def test_run_explicit_config_missing_errors(tmp_path):
    result = runner.invoke(
        cli, ["run", "--config", str(tmp_path / "nonexistent.yaml"), "--yes"]
    )
    assert result.exit_code != 0
    assert "not found" in result.output


def test_run_bad_config_file(tmp_path):
    config_file = tmp_path / "bad.yaml"
    config_file.write_text("not: valid: yaml: [")
    result = runner.invoke(cli, ["run", "--config", str(config_file), "--yes"])
    assert result.exit_code != 0


def test_run_partial_config_with_cli_override(tmp_path):
    config = tmp_path / "revelox.config.yaml"
    config.write_text(f"""\
version: "1"
run:
  target: "{VALID_TARGET}"
""")
    result = runner.invoke(
        cli, ["run", "--config", str(config), "--from", VALID_FROM, "--yes"]
    )
    assert result.exit_code == 0
    assert VALID_TARGET in result.output
    assert VALID_FROM in result.output


# --- Authorization gate ---


def test_run_prompt_accepted():
    result = runner.invoke(
        cli,
        ["run", "--from", VALID_FROM, "--target", VALID_TARGET],
        input="y\n",
    )
    assert result.exit_code == 0
    assert VALID_FROM in result.output


def test_run_prompt_declined():
    result = runner.invoke(
        cli,
        ["run", "--from", VALID_FROM, "--target", VALID_TARGET],
        input="n\n",
    )
    assert result.exit_code == 1
    assert "Aborted" in result.output or "aborted" in result.output.lower()


def test_run_yes_flag_skips_prompt():
    result = runner.invoke(
        cli, ["run", "--from", VALID_FROM, "--target", VALID_TARGET, "--yes"]
    )
    assert result.exit_code == 0
    assert "authorize" not in result.output.lower()


def test_run_config_yes_does_not_bypass_prompt(tmp_path):
    config = tmp_path / "revelox.config.yaml"
    config.write_text(f"""\
version: "1"
run:
  target: "{VALID_TARGET}"
  from_number: "{VALID_FROM}"
  yes: true
""")
    result = runner.invoke(cli, ["run", "--config", str(config)], input="y\n")
    assert result.exit_code == 0
    assert "authorize" in result.output.lower()


# --- Missing required values ---


@pytest.mark.parametrize(
    "args",
    [
        ["run", "--target", "+15559876543", "--yes"],
        ["run", "--from", "+15551234567", "--yes"],
        ["run", "--yes"],
    ],
)
def test_run_missing_required_value(args):
    result = runner.invoke(cli, args)
    assert result.exit_code != 0


# --- E.164 wiring (exhaustive validation tested in test_config.py) ---


def test_run_rejects_invalid_e164_from():
    result = runner.invoke(
        cli, ["run", "--from", "not-e164", "--target", VALID_TARGET, "--yes"]
    )
    assert result.exit_code != 0
    assert "not valid E.164" in result.output


def test_run_rejects_invalid_e164_target():
    result = runner.invoke(
        cli, ["run", "--from", VALID_FROM, "--target", "not-e164", "--yes"]
    )
    assert result.exit_code != 0
    assert "not valid E.164" in result.output


def test_run_rejects_invalid_e164_from_in_config(tmp_path):
    config = tmp_path / "bad_e164.yaml"
    config.write_text(f"""\
version: "1"
run:
  target: "{VALID_TARGET}"
  from_number: "not-e164"
""")
    result = runner.invoke(cli, ["run", "--config", str(config), "--yes"])
    assert result.exit_code != 0
