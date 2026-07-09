"""Tests for the `revelox init` command."""

from click.testing import CliRunner

from revelox.cli.main import cli

runner = CliRunner()


def test_init_creates_config_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(cli, ["init"])
    assert result.exit_code == 0
    assert "Created" in result.output
    config = tmp_path / "revelox.config.yaml"
    assert config.exists()
    content = config.read_text()
    assert "target:" in content
    assert "from_number:" in content
    assert "llm:" in content


def test_init_refuses_overwrite(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "revelox.config.yaml").write_text("existing")
    result = runner.invoke(cli, ["init"])
    assert result.exit_code != 0
    assert "already exists" in result.output


def test_init_force_overwrites(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "revelox.config.yaml").write_text("existing")
    result = runner.invoke(cli, ["init", "--force"])
    assert result.exit_code == 0
    content = (tmp_path / "revelox.config.yaml").read_text()
    assert content != "existing"
    assert "target:" in content
