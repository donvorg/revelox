import re

import click

E164_PATTERN = re.compile(r"\+[1-9]\d{6,14}")


class E164Type(click.ParamType):
    """Click parameter type that validates E.164 phone numbers."""

    name = "e164"

    def convert(
        self, value: str, param: click.Parameter | None, ctx: click.Context | None
    ) -> str:
        if not E164_PATTERN.fullmatch(value):
            self.fail(
                f"'{value}' is not valid E.164 (e.g. +15551234567)", param, ctx
            )
        return value


E164 = E164Type()
