"""The ``revelox run`` command."""

import logging
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
    "--yes",
    is_flag=True,
    default=False,
    help="Skip authorization prompt (for CI/CD).",
)
def run_command(
    config_path: Path | None,
    from_number: str | None,
    target: str | None,
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

    click.echo(f"From:   {run_config.from_number}")
    click.echo(f"Target: {run_config.target}")
    click.echo(f"LLM:    {run_config.llm.provider}/{run_config.llm.model}")
    click.echo("Run not yet implemented.")


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
