import click

from revelox.cli.init_cmd import init_command
from revelox.cli.run_cmd import run_command


@click.group()
@click.version_option(version="0.1.0")
def cli() -> None:
    """Revelox — adversarial security testing for voice AI agents."""


cli.add_command(init_command, "init")
cli.add_command(run_command, "run")
