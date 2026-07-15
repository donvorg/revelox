"""The ``revelox run`` command."""

from __future__ import annotations

import logging
import os
import threading
from pathlib import Path

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
    "--script",
    type=click.Path(exists=True, path_type=Path),
    required=True,
    help="Path to the script file.",
)
@click.option(
    "--port",
    type=int,
    default=8765,
    show_default=True,
    help="Local server port.",
)
@click.option(
    "--yes",
    is_flag=True,
    default=False,
    help="Skip authorization prompt (for CI/CD).",
)
def run_command(
    from_number: str, target: str, script: Path, port: int, yes: bool
) -> None:
    """Run attack suite against configured target."""
    if yes:
        logger.warning("Authorization assumed via --yes flag.")
    elif not click.confirm(
        "This will place real phone calls. Do you authorize this run?"
    ):
        raise click.Abort()

    public_base_url = os.environ.get("PUBLIC_BASE_URL")
    if not public_base_url:
        raise click.UsageError("PUBLIC_BASE_URL environment variable is required.")

    import time

    import uvicorn

    from revelox.dialer import dial
    from revelox.server import create_app
    from revelox.tts import synthesize_script

    click.echo(f"From:   {from_number}")
    click.echo(f"Target: {target}")

    click.echo("Synthesizing script...")
    audio_buffers = synthesize_script(script)
    click.echo(f"Synthesized {len(audio_buffers)} turn(s).")

    call_done = threading.Event()
    app = create_app(audio_buffers, call_done=call_done)

    config = uvicorn.Config(app, host="0.0.0.0", port=port, log_level="warning")
    server = uvicorn.Server(config)
    server_thread = threading.Thread(target=server.run, daemon=True)
    server_thread.start()

    while not server.started:
        time.sleep(0.05)

    voice_url = f"{public_base_url}/voice"
    click.echo(f"Dialing {target}...")
    call_sid = dial(from_number, target, voice_url)
    click.echo(f"Call placed: {call_sid}")

    call_done.wait()
    server.should_exit = True
    server_thread.join()
