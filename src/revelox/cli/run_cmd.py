"""The ``revelox run`` command."""

from __future__ import annotations

import logging
import os
import threading
from pathlib import Path

import click
from pydantic import ValidationError

from revelox.config import CONFIG_FILENAME, ConfigError, RunConfig, load_config
from revelox.utils.e164 import E164

logger = logging.getLogger(__name__)

DEFAULT_CONFIG_PATH = Path(CONFIG_FILENAME)


@click.command()
@click.option(
    "--config",
    "config_path",
    type=click.Path(dir_okay=False, path_type=Path),
    default=None,
    help="Path to config file (default: ./revelox.config.yaml).",
)
@click.option(
    "--from",
    "from_number",
    type=E164,
    envvar="TWILIO_PHONE_NUMBER",
    default=None,
    help="Phone number to call from (E.164 format).",
)
@click.option(
    "--target",
    type=E164,
    envvar="REVELOX_TARGET_NUMBER",
    default=None,
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
    config_path: Path | None,
    from_number: str | None,
    target: str | None,
    script: Path,
    port: int,
    yes: bool,
) -> None:
    """Run attack suite against configured target."""
    run_config = _resolve_config(config_path, from_number, target, yes)

    if run_config.yes:
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

    click.echo(f"From:   {run_config.from_number}")
    click.echo(f"Target: {run_config.target}")

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
    click.echo(f"Dialing {run_config.target}...")
    call_sid = dial(run_config.from_number, run_config.target, voice_url)
    click.echo(f"Call placed: {call_sid}")

    call_done.wait()
    server.should_exit = True
    server_thread.join()


def _resolve_config(
    config_path: Path | None,
    from_number: str | None,
    target: str | None,
    yes: bool,
) -> RunConfig:
    """Build RunConfig from config file + CLI overrides."""
    config_file = config_path or DEFAULT_CONFIG_PATH

    if config_path is not None and not config_file.exists():
        raise click.ClickException(f"Config file not found: {config_file}")

    base: dict[str, object] = {}
    if config_file.exists():
        try:
            data = load_config(config_file)
        except ConfigError as e:
            raise click.ClickException(str(e)) from None
        run_section = data.get("run")
        if isinstance(run_section, dict):
            base = run_section

    if from_number is not None:
        base["from_number"] = from_number
    if target is not None:
        base["target"] = target
    base["yes"] = yes

    if not base.get("from_number"):
        raise click.UsageError(
            "No from-number provided. Pass --from, set TWILIO_PHONE_NUMBER, or add to config."
        )
    if not base.get("target"):
        raise click.UsageError(
            "No target provided. Pass --target, set REVELOX_TARGET_NUMBER, or add to config."
        )

    try:
        return RunConfig.model_validate(base)
    except ValidationError as e:
        raise click.ClickException(f"Invalid configuration: {e}") from None
