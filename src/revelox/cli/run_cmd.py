import logging

import click

from revelox.utils.e164 import E164

logger = logging.getLogger(__name__)


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
@click.option(
    "--yes",
    is_flag=True,
    default=False,
    help="Skip authorization prompt (for CI/CD).",
)
def run_command(from_number: str, target: str, yes: bool) -> None:
    """Run attack suite against configured target."""
    if yes:
        logger.warning("Authorization assumed via --yes flag.")
    elif not click.confirm(
        "This will place real phone calls. Do you authorize this run?"
    ):
        raise SystemExit("Run aborted by user.")

    click.echo(f"From:   {from_number}")
    click.echo(f"Target: {target}")
    click.echo("Run not yet implemented.")
