"""Tests for config models and loader."""

import pytest
from pydantic import ValidationError

from revelox.config import (
    ConfigError,
    LLMConfig,
    ReveloxConfig,
    RunConfig,
    load_config,
)

VALID_FROM = "+15551234567"
VALID_TARGET = "+15559876543"


# --- Model defaults ---


def test_llm_config_defaults():
    cfg = LLMConfig()
    assert cfg.provider == "openai"
    assert cfg.model == "gpt-4o"


def test_run_config_defaults():
    cfg = RunConfig(target=VALID_TARGET, from_number=VALID_FROM)
    assert cfg.llm.provider == "openai"
    assert cfg.modules == ["all"]
    assert cfg.output_formats == ["json", "md"]
    assert cfg.yes is False


def test_revelox_config_wraps_run():
    cfg = ReveloxConfig(run=RunConfig(target=VALID_TARGET, from_number=VALID_FROM))
    assert cfg.version == "1"
    assert cfg.run.target == VALID_TARGET


# --- E.164 validation ---


def test_valid_phone_numbers():
    cfg = RunConfig(target=VALID_TARGET, from_number=VALID_FROM)
    assert cfg.target == VALID_TARGET
    assert cfg.from_number == VALID_FROM


@pytest.mark.parametrize(
    "bad_number",
    [
        "5551234567",
        "+abcdefghij",
        "+",
        "+123",
        "+0123456789",
    ],
)
def test_invalid_target_rejected(bad_number: str):
    with pytest.raises(ValidationError, match="not valid E.164"):
        RunConfig(target=bad_number, from_number=VALID_FROM)


@pytest.mark.parametrize(
    "bad_number",
    [
        "not-a-number",
        "+",
        "+123",
    ],
)
def test_invalid_from_number_rejected(bad_number: str):
    with pytest.raises(ValidationError, match="not valid E.164"):
        RunConfig(target=VALID_TARGET, from_number=bad_number)


# --- Missing fields ---


def test_missing_target_raises():
    with pytest.raises(ValidationError):
        RunConfig(from_number=VALID_FROM)  # type: ignore[call-arg]


def test_missing_from_number_raises():
    with pytest.raises(ValidationError):
        RunConfig(target=VALID_TARGET)  # type: ignore[call-arg]


# --- Loader ---


def test_load_valid_config(tmp_path):
    config_file = tmp_path / "revelox.config.yaml"
    config_file.write_text(f"""\
version: "1"
run:
  target: "{VALID_TARGET}"
  from_number: "{VALID_FROM}"
  llm:
    provider: openai
    model: gpt-4o
""")
    cfg = load_config(config_file)
    assert cfg.run.target == VALID_TARGET
    assert cfg.run.from_number == VALID_FROM
    assert cfg.run.llm.model == "gpt-4o"


def test_load_minimal_config(tmp_path):
    config_file = tmp_path / "revelox.config.yaml"
    config_file.write_text(f"""\
version: "1"
run:
  target: "{VALID_TARGET}"
  from_number: "{VALID_FROM}"
""")
    cfg = load_config(config_file)
    assert cfg.run.llm.provider == "openai"
    assert cfg.run.modules == ["all"]


def test_load_missing_file(tmp_path):
    with pytest.raises(ConfigError, match="not found"):
        load_config(tmp_path / "nonexistent.yaml")


def test_load_malformed_yaml(tmp_path):
    config_file = tmp_path / "bad.yaml"
    config_file.write_text(":\n  :\n  - [invalid")
    with pytest.raises(ConfigError, match="Invalid YAML"):
        load_config(config_file)


def test_load_non_mapping_yaml(tmp_path):
    config_file = tmp_path / "list.yaml"
    config_file.write_text("- item1\n- item2\n")
    with pytest.raises(ConfigError, match="YAML mapping"):
        load_config(config_file)


def test_load_invalid_phone_in_yaml(tmp_path):
    config_file = tmp_path / "bad_phone.yaml"
    config_file.write_text("""\
version: "1"
run:
  target: "not-a-number"
  from_number: "+15551234567"
""")
    with pytest.raises(ConfigError, match="validation failed"):
        load_config(config_file)
