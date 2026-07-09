"""E.164 phone number validation utilities."""

import re

import click

E164_PATTERN = re.compile(r"\+[1-9]\d{6,14}")


def validate_e164(value: str) -> str:
    """Validate that *value* is a valid E.164 phone number, returning it unchanged."""
    if not E164_PATTERN.fullmatch(value):
        msg = f"'{value}' is not valid E.164 (e.g. +15551234567)"
        raise ValueError(msg)
    return value


class E164Type(click.ParamType):
    """Click parameter type that validates E.164 phone numbers."""

    name = "e164"

    def convert(
        self, value: str, param: click.Parameter | None, ctx: click.Context | None
    ) -> str:
        """Convert and validate a CLI argument as an E.164 phone number."""
        try:
            return validate_e164(value)
        except ValueError as e:
            self.fail(str(e), param, ctx)


E164 = E164Type()
