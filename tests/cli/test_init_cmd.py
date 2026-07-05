"""Tests for the `revelox init` command."""

from click.testing import CliRunner

from revelox.cli.main import cli

runner = CliRunner()


def test_init_outputs_confirmation():
    result = runner.invoke(cli, ["init"])
    assert result.exit_code == 0
    assert "revelox.config.yaml created" in result.output
