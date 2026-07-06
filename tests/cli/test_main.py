"""Tests for the top-level CLI group and command registration."""

from click.testing import CliRunner

from revelox.cli.main import cli

runner = CliRunner()


def test_cli_help_exits_zero():
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "Revelox" in result.output


def test_cli_version():
    result = runner.invoke(cli, ["--version"])
    assert result.exit_code == 0
    assert "0.1.0" in result.output


def test_cli_registers_init_command():
    result = runner.invoke(cli, ["init", "--help"])
    assert result.exit_code == 0


def test_cli_registers_run_command():
    result = runner.invoke(cli, ["run", "--help"])
    assert result.exit_code == 0


def test_cli_unknown_command():
    result = runner.invoke(cli, ["nonexistent"])
    assert result.exit_code != 0
