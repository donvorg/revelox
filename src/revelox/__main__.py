"""Allow running revelox as ``python -m revelox``."""

if __name__ == "__main__":
    from revelox.cli.main import cli

    cli()
