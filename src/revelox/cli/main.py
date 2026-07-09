"""CLI group and command registration."""

import click

from revelox.cli.init_cmd import init_command
from revelox.cli.run_cmd import run_command


@click.group()
@click.version_option(package_name="revelox")
def cli() -> None:
    """Revelox — adversarial security testing for voice AI agents."""


cli.add_command(init_command, "init")
cli.add_command(run_command, "run")
