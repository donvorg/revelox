"""Script file parser for turn-delimited attack scripts."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

START_TURN = "<START_TURN>"
END_TURN = "<END_TURN>"

_TURN_PATTERN = re.compile(
    re.escape(START_TURN) + r"(.*?)" + re.escape(END_TURN),
    re.DOTALL,
)


class ScriptError(Exception):
    """Raised when script parsing fails."""


def parse_script(path: Path) -> list[str]:
    """Parse a script file and return the text of each turn.

    Extracts text between ``<START_TURN>`` / ``<END_TURN>`` delimiter pairs.
    Whitespace is stripped from each turn but empty strings are preserved.
    Text outside delimiters is ignored.

    Args:
        path: Path to the script ``.txt`` file.

    Returns:
        List of turn strings (may include empty strings for silence turns).

    Raises:
        ScriptError: If the file cannot be read, contains mismatched
            delimiters, or has no turns.
    """
    try:
        content = path.read_text()
    except FileNotFoundError:
        raise ScriptError(f"Script file not found: {path}") from None
    except OSError as e:
        raise ScriptError(f"Cannot read script file: {e}") from None

    _check_mismatched_delimiters(content)

    turns = [match.group(1).strip() for match in _TURN_PATTERN.finditer(content)]

    if not turns:
        raise ScriptError(f"No turns found in {path}")

    return turns


def _check_mismatched_delimiters(content: str) -> None:
    """Raise ScriptError if delimiters are mismatched or misordered."""
    pattern = re.compile(re.escape(START_TURN) + "|" + re.escape(END_TURN))
    starts = 0
    ends = 0
    depth = 0
    for m in pattern.finditer(content):
        if m.group() == START_TURN:
            starts += 1
            depth += 1
            if depth > 1:
                raise ScriptError(f"Nested {START_TURN} found")
        else:
            ends += 1
            depth -= 1
            if depth < 0:
                raise ScriptError(f"{END_TURN} without matching {START_TURN}")
    if starts != ends:
        raise ScriptError(
            f"Mismatched delimiters: {starts} {START_TURN} vs {ends} {END_TURN}"
        )
