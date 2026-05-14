from pathlib import Path

import pytest

from vcodeman.gen.compiler import CompileError
from vcodeman.gen.dw_flow.repair import (
    AIRepairError,
    build_user_message,
    extract_filelist,
)


# --- extract_filelist tests (10) ---

def test_extract_clean_input_passes_through():
    raw = "+incdir+/a/inc\n/a/pkg.sv\n/a/mod.sv\n"
    assert extract_filelist(raw) == raw


def test_extract_strips_markdown_fence():
    raw = "```\n+incdir+/a/inc\n/a/mod.sv\n```\n"
    assert extract_filelist(raw) == "+incdir+/a/inc\n/a/mod.sv\n"


def test_extract_strips_fenced_with_language():
    raw = "```systemverilog\n/a/pkg.sv\n/a/mod.sv\n```"
    assert extract_filelist(raw) == "/a/pkg.sv\n/a/mod.sv\n"


def test_extract_drops_leading_prose():
    raw = "Here is the corrected filelist:\n\n+incdir+/a/inc\n/a/mod.sv\n"
    out = extract_filelist(raw)
    assert "Here is" not in out
    assert "+incdir+/a/inc" in out
    assert "/a/mod.sv" in out


def test_extract_drops_trailing_prose():
    raw = "/a/mod.sv\nThis filelist is now fixed.\n"
    out = extract_filelist(raw)
    assert "/a/mod.sv" in out
    assert "fixed" not in out


def test_extract_keeps_comments_and_blanks():
    raw = "// header\n\n/a/pkg.sv\n// section\n/a/mod.sv\n"
    out = extract_filelist(raw)
    assert "// header" in out
    assert "// section" in out
    assert "/a/pkg.sv" in out


def test_extract_keeps_top_flag():
    raw = "/a/mod.sv\n-top tb_top\n"
    assert extract_filelist(raw) == "/a/mod.sv\n-top tb_top\n"


def test_extract_raises_on_pure_prose():
    raw = "I cannot help with that request.\nPlease provide more context.\n"
    with pytest.raises(AIRepairError, match="no recognizable filelist content"):
        extract_filelist(raw)


def test_extract_raises_on_comments_only():
    raw = "// just a comment\n// another comment\n"
    with pytest.raises(AIRepairError):
        extract_filelist(raw)


def test_extract_handles_unclosed_fence():
    raw = "```\n/a/pkg.sv\n/a/mod.sv\n"
    out = extract_filelist(raw)
    assert "/a/pkg.sv" in out
    assert "/a/mod.sv" in out


# --- build_user_message tests (2) ---

def test_build_user_message_contains_errors_and_filelist():
    errors = [
        CompileError(file="/rtl/mod.sv", line=5,
                     message="undeclared identifier 'foo'", raw="..."),
    ]
    headers = {Path("/rtl/pkg.sv"): "package pkg;\nendpackage"}
    msg = build_user_message("/rtl/pkg.sv\n", errors, headers)

    assert "undeclared identifier" in msg
    assert "/rtl/mod.sv:5" in msg
    assert "/rtl/pkg.sv" in msg
    assert "package pkg;" in msg


def test_build_user_message_handles_error_without_file():
    errors = [CompileError(file=None, line=None, message="No top modules", raw="...")]
    headers = {}
    msg = build_user_message("\n", errors, headers)

    assert "No top modules" in msg
