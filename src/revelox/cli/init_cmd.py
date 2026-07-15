"""The ``revelox init`` command."""

from pathlib import Path

import click

from revelox.config import CONFIG_FILENAME, DEFAULT_CONFIG_YAML


@click.command()
@click.option("--force", is_flag=True, default=False, help="Overwrite existing config file.")
@click.option(
    "--output-dir",
    type=click.Path(file_okay=False, path_type=Path),
    default=Path("./out"),
    help="Directory to write config file into (default: ./out).",
)
def init_command(force: bool, output_dir: Path) -> None:
    """Create a revelox.config.yaml in the given output directory."""
    output_dir.mkdir(parents=True, exist_ok=True)
    dest = output_dir / CONFIG_FILENAME
    if dest.exists() and not force:
        raise click.ClickException(
            f"{CONFIG_FILENAME} already exists. Use --force to overwrite."
        )

    dest.write_text(DEFAULT_CONFIG_YAML)
    click.echo(f"Created {CONFIG_FILENAME}")
