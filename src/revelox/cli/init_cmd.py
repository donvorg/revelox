"""The ``revelox init`` command."""

from pathlib import Path

import click

from revelox.config import DEFAULT_CONFIG_YAML

CONFIG_FILENAME = "revelox.config.yaml"


@click.command()
@click.option("--force", is_flag=True, default=False, help="Overwrite existing config file.")
def init_command(force: bool) -> None:
    """Create a revelox.config.yaml in the current directory."""
    dest = Path.cwd() / CONFIG_FILENAME
    if dest.exists() and not force:
        raise click.ClickException(
            f"{CONFIG_FILENAME} already exists. Use --force to overwrite."
        )

    dest.write_text(DEFAULT_CONFIG_YAML)
    click.echo(f"Created {CONFIG_FILENAME}")
