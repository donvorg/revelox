import click

from revelox.utils.e164 import E164


@click.command()
@click.option(
    "--from",
    "from_number",
    type=E164,
    envvar="TWILIO_PHONE_NUMBER",
    required=True,
    help="Phone number to call from (E.164 format).",
)
@click.option(
    "--target",
    type=E164,
    envvar="REVELOX_TARGET_NUMBER",
    required=True,
    help="Phone number to call (E.164 format).",
)
def run_command(from_number: str, target: str) -> None:
    """Run attack suite against configured target."""
    click.echo(f"From:   {from_number}")
    click.echo(f"Target: {target}")
    click.echo("Run not yet implemented.")
