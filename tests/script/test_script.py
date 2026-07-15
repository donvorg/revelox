"""Tests for script file parsing."""

import pytest

from revelox.script import parse_script, ScriptError


def test_parse_single_turn(tmp_path):
    script = tmp_path / "single.txt"
    script.write_text("<START_TURN>Hello, how are you?<END_TURN>")
    assert parse_script(script) == ["Hello, how are you?"]


def test_parse_multiple_turns(tmp_path):
    script = tmp_path / "multi.txt"
    script.write_text(
        "<START_TURN>First turn<END_TURN>\n"
        "<START_TURN>Second turn<END_TURN>\n"
        "<START_TURN>Third turn<END_TURN>\n"
    )
    result = parse_script(script)
    assert result == ["First turn", "Second turn", "Third turn"]


def test_strips_whitespace_from_turns(tmp_path):
    script = tmp_path / "whitespace.txt"
    script.write_text("<START_TURN>  padded text  <END_TURN>")
    assert parse_script(script) == ["padded text"]


def test_preserves_empty_turn(tmp_path):
    script = tmp_path / "empty_turn.txt"
    script.write_text(
        "<START_TURN>hello<END_TURN>\n"
        "<START_TURN>   <END_TURN>\n"
        "<START_TURN>goodbye<END_TURN>\n"
    )
    result = parse_script(script)
    assert result == ["hello", "", "goodbye"]


def test_ignores_text_outside_delimiters(tmp_path):
    script = tmp_path / "outside.txt"
    script.write_text(
        "This is ignored\n"
        "<START_TURN>inside<END_TURN>\n"
        "Also ignored\n"
    )
    assert parse_script(script) == ["inside"]


def test_multiline_turn_content(tmp_path):
    script = tmp_path / "multiline.txt"
    script.write_text("<START_TURN>\nline one\nline two\n<END_TURN>")
    result = parse_script(script)
    assert result == ["line one\nline two"]


def test_file_not_found():
    from pathlib import Path

    with pytest.raises(ScriptError, match="Script file not found"):
        parse_script(Path("/nonexistent/script.txt"))


def test_no_turns_found(tmp_path):
    script = tmp_path / "empty.txt"
    script.write_text("just some text with no delimiters")
    with pytest.raises(ScriptError, match="No turns found"):
        parse_script(script)


def test_mismatched_delimiters_extra_start(tmp_path):
    script = tmp_path / "mismatch.txt"
    script.write_text("<START_TURN>hello<END_TURN>\n<START_TURN>orphan")
    with pytest.raises(ScriptError, match="Mismatched delimiters"):
        parse_script(script)


def test_mismatched_delimiters_extra_end(tmp_path):
    script = tmp_path / "mismatch.txt"
    script.write_text("<START_TURN>hello<END_TURN>\n<END_TURN>")
    with pytest.raises(ScriptError, match="without matching"):
        parse_script(script)
