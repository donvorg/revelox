import click


@click.command()
def init_command() -> None:
    """Create a revelox.config.yaml in the current directory."""
    click.echo("revelox.config.yaml created.")
