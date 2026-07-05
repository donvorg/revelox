"""Tests for the `revelox init` command."""

from click.testing import CliRunner

from revelox.cli.main import cli

runner = CliRunner()


def test_init_outputs_not_implemented():
    result = runner.invoke(cli, ["init"])
    assert result.exit_code == 0
    assert "not yet implemented" in result.output
