"""Configuration models and loader for revelox."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from pathlib import Path

import yaml
from pydantic import BaseModel, field_validator

from revelox.utils.e164 import validate_e164

CONFIG_FILENAME = "revelox.config.yaml"

DEFAULT_CONFIG_YAML = """\
# revelox configuration
# Docs: https://github.com/drdonv/revelox

version: "1"

run:
  # Phone number to call (E.164 format, e.g. +15551234567)
  target: "+1XXXXXXXXXX"

  # Phone number to call from (E.164). Falls back to TWILIO_PHONE_NUMBER env var.
  from_number: "+1XXXXXXXXXX"

  # LLM settings (used for attack generation and judging)
  llm:
    provider: openai    # only openai supported currently
    model: gpt-4o

  # Attack modules to run ("all" runs every available module)
  modules:
    - all

  # Output formats
  output_formats:
    - json
    - md

  # Set to true to skip the authorization prompt (for CI/CD)
  yes: false
"""


class LLMConfig(BaseModel):
    """LLM provider configuration."""

    provider: Literal["openai"] = "openai"
    model: str = "gpt-4o"


class RunConfig(BaseModel):
    """Configuration for a single revelox run."""

    target: str
    from_number: str
    llm: LLMConfig = LLMConfig()
    modules: list[str] = ["all"]
    output_formats: list[Literal["json", "md"]] = ["json", "md"]
    yes: bool = False

    @field_validator("target", "from_number")
    @classmethod
    def check_e164(cls, v: str) -> str:
        """Validate phone numbers are E.164 format."""
        return validate_e164(v)


class ReveloxConfig(BaseModel):
    """Top-level configuration file model."""

    version: str = "1"
    run: RunConfig


class ConfigError(Exception):
    """Raised when config loading or validation fails."""


def load_config(path: Path) -> dict[str, Any]:
    """Load and parse a revelox config file, returning the raw data dict."""
    try:
        raw = path.read_text()
    except FileNotFoundError:
        raise ConfigError(f"Config file not found: {path}") from None
    except OSError as e:
        raise ConfigError(f"Cannot read config file: {e}") from None

    try:
        data: Any = yaml.safe_load(raw)
    except yaml.YAMLError as e:
        raise ConfigError(f"Invalid YAML in {path}: {e}") from None

    if not isinstance(data, dict):
        raise ConfigError(f"Config file must be a YAML mapping, got {type(data).__name__}")

    return data
