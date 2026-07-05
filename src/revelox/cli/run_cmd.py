import os

import click


@click.command()
@click.option(
    "--from",
    "from_number",
    default=None,
    help="Phone number to call from (E.164 format). Falls back to TWILIO_PHONE_NUMBER env var.",
)
@click.option(
    "--target",
    default=None,
    help="Phone number to call (E.164 format). Falls back to REVELOX_TARGET_NUMBER env var.",
)
def run_command(from_number: str | None, target: str | None) -> None:
    """Run attack suite against configured target."""
    from_number = from_number or os.environ.get("TWILIO_PHONE_NUMBER")
    if not from_number:
        raise click.UsageError(
            "No from-number provided. Pass --from or set TWILIO_PHONE_NUMBER."
        )

    target = target or os.environ.get("REVELOX_TARGET_NUMBER")
    if not target:
        raise click.UsageError(
            "No target provided. Pass --target or set REVELOX_TARGET_NUMBER."
        )

    if not from_number.startswith("+") or not from_number[1:].isdigit():
        raise click.BadParameter(
            f"Invalid from-number '{from_number}'. Must be E.164 format (e.g. +15551234567).",
            param_hint="'--from'",
        )

    if not target.startswith("+") or not target[1:].isdigit():
        raise click.BadParameter(
            f"Invalid target '{target}'. Must be E.164 format (e.g. +15551234567).",
            param_hint="'--target'",
        )

    click.echo(f"From:   {from_number}")
    click.echo(f"Target: {target}")
    click.echo("Run not yet implemented.")

