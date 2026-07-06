from click.testing import CliRunner
import pytest


@pytest.fixture
def cli_runner() -> CliRunner:
    """Shared Click test runner."""
    return CliRunner()
