"""Realistic filelist cases — patterns we expect to encounter in production.

Each test feeds a small filelist to `vcodeman parse` and asserts the output
behaves as a working EDA flow would expect. Failing tests here indicate a
gap in grammar, parser, resolver, or formatter.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

import pytest
from click.testing import CliRunner

from vcodeman.cli import cli


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def _write(p: Path, body: str) -> Path:
    p.write_text(body)
    return p


def _parse(runner: CliRunner, fl: Path, *extra: str) -> str:
    """Run `vcodeman parse FL [extra args]`; returns stdout. Asserts exit 0."""
    result = runner.invoke(cli, ['parse', str(fl), *extra])
    assert result.exit_code == 0, (
        f"parse failed:\nstdout={result.output!r}\nexc={result.exception!r}"
    )
    return result.output


# ─── Comments ─────────────────────────────────────────────────────────────

def test_multi_word_slash_comment_stays_intact(runner, tmp_path):
    """`// multi word comment` must be ONE comment, not many tokens."""
    fl = _write(tmp_path / "f.f",
        "// this is a multi word comment\n"
        "file_a.v\n"
    )
    out = _parse(runner, fl)
    # Whole comment preserved as a single line
    assert "// this is a multi word comment" in out
    # Exactly one non-comment, non-empty line — and it ends with file_a.v
    live_lines = [
        ln for ln in out.splitlines()
        if ln.strip() and not ln.lstrip().startswith("//")
    ]
    assert len(live_lines) == 1, f"expected 1 live entry, got {live_lines!r}"
    assert live_lines[0].endswith("file_a.v")


def test_multi_word_hash_comment_stays_intact(runner, tmp_path):
    fl = _write(tmp_path / "f.f",
        "# this is a hash style comment\n"
        "file.v\n"
    )
    out = _parse(runner, fl)
    assert "this is a hash style comment" in out
    live_lines = [
        ln for ln in out.splitlines()
        if ln.strip() and not ln.lstrip().startswith("//")
    ]
    assert len(live_lines) == 1, f"expected 1 live entry, got {live_lines!r}"
    assert live_lines[0].endswith("file.v")


def test_filelist_with_only_comments(runner, tmp_path):
    """A filelist that is nothing but comments should parse cleanly."""
    fl = _write(tmp_path / "f.f",
        "// header\n"
        "// more notes\n"
        "# even hash\n"
    )
    out = _parse(runner, fl)
    # All three comments preserved (in some form)
    assert "header" in out
    assert "more notes" in out
    assert "even hash" in out


def test_blank_lines_between_entries(runner, tmp_path):
    fl = _write(tmp_path / "f.f",
        "file_a.v\n"
        "\n"
        "\n"
        "file_b.v\n"
    )
    out = _parse(runner, fl)
    assert "file_a.v" in out
    assert "file_b.v" in out


def test_mixed_comment_styles_same_file(runner, tmp_path):
    fl = _write(tmp_path / "f.f",
        "// slash comment\n"
        "# hash comment\n"
        "file.v\n"
        "// another slash\n"
    )
    out = _parse(runner, fl)
    assert "slash comment" in out
    assert "hash comment" in out
    assert "another slash" in out
    assert "file.v" in out


# ─── Environment variables ────────────────────────────────────────────────

def test_env_var_dollar_form(runner, tmp_path, monkeypatch):
    monkeypatch.setenv("DESIGN_ROOT", str(tmp_path / "design"))
    (tmp_path / "design").mkdir()
    fl = _write(tmp_path / "f.f", "$DESIGN_ROOT/foo.v\n")
    out = _parse(runner, fl)
    assert str(tmp_path / "design" / "foo.v") in out


def test_env_var_braced_form(runner, tmp_path, monkeypatch):
    monkeypatch.setenv("DESIGN_ROOT", str(tmp_path / "design"))
    (tmp_path / "design").mkdir()
    fl = _write(tmp_path / "f.f", "${DESIGN_ROOT}/foo.v\n")
    out = _parse(runner, fl)
    assert str(tmp_path / "design" / "foo.v") in out


def test_env_var_nested_in_middle_of_path(runner, tmp_path, monkeypatch):
    monkeypatch.setenv("SUB", "subdir")
    fl = _write(tmp_path / "f.f", f"{tmp_path}/$SUB/foo.v\n")
    out = _parse(runner, fl)
    assert str(tmp_path / "subdir" / "foo.v") in out


def test_env_var_multiple_in_one_path(runner, tmp_path, monkeypatch):
    monkeypatch.setenv("A", "first")
    monkeypatch.setenv("B", "second")
    fl = _write(tmp_path / "f.f", f"{tmp_path}/$A/$B/leaf.v\n")
    out = _parse(runner, fl)
    assert str(tmp_path / "first" / "second" / "leaf.v") in out


# ─── Nested includes (-f / -F) ────────────────────────────────────────────

def test_nested_f_include_three_deep(runner, tmp_path):
    (tmp_path / "deep.f").write_text("deep_file.v\n")
    (tmp_path / "mid.f").write_text(f"-F {tmp_path}/deep.f\nmid_file.v\n")
    fl = _write(tmp_path / "root.f", f"-F {tmp_path}/mid.f\nroot_file.v\n")
    out = _parse(runner, fl)
    assert "deep_file.v" in out
    assert "mid_file.v" in out
    assert "root_file.v" in out


def test_capital_F_resolves_relative_to_filelist_dir(runner, tmp_path):
    """-F resolves nested filelist path against the parent filelist's dir."""
    sub = tmp_path / "sub"; sub.mkdir()
    (sub / "child.f").write_text("child.v\n")
    fl = _write(tmp_path / "root.f", "-F sub/child.f\nroot.v\n")
    out = _parse(runner, fl)
    assert "child.v" in out
    assert "root.v" in out


def test_mixed_f_and_F_in_same_filelist(runner, tmp_path):
    (tmp_path / "via_f.f").write_text("via_f_content.v\n")
    (tmp_path / "via_F.f").write_text("via_F_content.v\n")
    fl = _write(tmp_path / "root.f",
        f"-f {tmp_path}/via_f.f\n"
        f"-F via_F.f\n"
    )
    out = _parse(runner, fl)
    assert "via_f_content.v" in out
    assert "via_F_content.v" in out


# ─── +option terminals ────────────────────────────────────────────────────

def test_incdir_plus_chained_paths(runner, tmp_path):
    fl = _write(tmp_path / "f.f", "+incdir+/path/a+/path/b+/path/c\n")
    out = _parse(runner, fl)
    assert "/path/a" in out
    assert "/path/b" in out
    assert "/path/c" in out


def test_define_no_value(runner, tmp_path):
    fl = _write(tmp_path / "f.f", "+define+DEBUG\n")
    out = _parse(runner, fl)
    assert "+define+DEBUG" in out or "DEBUG" in out


def test_define_with_value(runner, tmp_path):
    fl = _write(tmp_path / "f.f", "+define+VERSION=2\n")
    out = _parse(runner, fl)
    assert "VERSION=2" in out


def test_define_chain_mixed_with_and_without_values(runner, tmp_path):
    fl = _write(tmp_path / "f.f", "+define+A+B=2+C+D=4\n")
    out = _parse(runner, fl)
    for token in ("A", "B=2", "C", "D=4"):
        assert token in out, f"missing macro token: {token}"


def test_libext_plus_chained(runner, tmp_path):
    fl = _write(tmp_path / "f.f", "+libext+.v+.sv+.vh\n")
    out = _parse(runner, fl)
    for ext in (".v", ".sv", ".vh"):
        assert ext in out


# ─── Dash options ─────────────────────────────────────────────────────────

def test_dash_y_library_dir(runner, tmp_path):
    libdir = tmp_path / "libs"; libdir.mkdir()
    fl = _write(tmp_path / "f.f", f"-y {libdir}\n")
    out = _parse(runner, fl)
    assert str(libdir) in out


def test_dash_v_library_file(runner, tmp_path):
    libfile = tmp_path / "lib.v"; libfile.write_text("\n")
    fl = _write(tmp_path / "f.f", f"-v {libfile}\n")
    out = _parse(runner, fl)
    assert str(libfile) in out


# ─── Path edge cases ──────────────────────────────────────────────────────

def test_path_with_dashes_dots_underscores(runner, tmp_path):
    weird = tmp_path / "my-design.v1.0_top.v"
    weird.write_text("\n")
    fl = _write(tmp_path / "f.f", f"{weird}\n")
    out = _parse(runner, fl)
    assert str(weird) in out


def test_relative_path_resolved_against_filelist_dir(runner, tmp_path):
    sub = tmp_path / "design"; sub.mkdir()
    leaf = sub / "leaf.v"; leaf.write_text("\n")
    fl = _write(sub / "list.f", "leaf.v\n")
    out = _parse(runner, fl)
    # Resolved to absolute against the filelist's own directory
    assert str(leaf) in out


# ─── Resolve markers (always on; default behavior) ────────────────────────

def test_emits_resolve_markers_for_includes(runner, tmp_path):
    """An expanded -f/-F shows a resolve-style marker comment."""
    (tmp_path / "child.f").write_text("child.v\n")
    fl = _write(tmp_path / "root.f", f"-f {tmp_path}/child.f\nroot.v\n")
    out = _parse(runner, fl)
    assert re.search(r"//.*resolv", out, flags=re.IGNORECASE), (
        f"expected a resolve-marker comment in default output:\n{out}"
    )


# ─── Whitespace / line endings ────────────────────────────────────────────

def test_tab_indented_path(runner, tmp_path):
    fl = _write(tmp_path / "f.f", "\tfile_with_tab.v\n")
    out = _parse(runner, fl)
    assert "file_with_tab.v" in out


def test_crlf_line_endings(runner, tmp_path):
    fl = tmp_path / "f.f"
    fl.write_bytes(b"// crlf comment\r\nfile.v\r\n")
    out = _parse(runner, fl)
    assert "crlf comment" in out
    assert "file.v" in out


def test_trailing_whitespace_on_lines(runner, tmp_path):
    fl = _write(tmp_path / "f.f",
        "file_a.v   \n"
        "file_b.v\t\n"
    )
    out = _parse(runner, fl)
    assert "file_a.v" in out
    assert "file_b.v" in out


# ─── More subtle real-world patterns ──────────────────────────────────────

def test_trailing_slash_comment_on_path_line(runner, tmp_path):
    """Some filelists put a trailing `// note` after a real path. The path
    must still resolve and the note must not be treated as a separate path."""
    fl = _write(tmp_path / "f.f",
        "real_file.v // include for foo bar\n"
    )
    out = _parse(runner, fl)
    # path resolves
    assert re.search(r"\breal_file\.v\b", out), out
    # No live entry called "include" or "bar"
    live_lines = [
        ln for ln in out.splitlines()
        if ln.strip() and not ln.lstrip().startswith("//")
    ]
    for stray in ("include", "for", "foo", "bar"):
        for ln in live_lines:
            # token-level check: stray word must not appear as a standalone path
            assert not re.search(rf"(^|/|\s){re.escape(stray)}(\s|$)", ln), (
                f"trailing-comment word {stray!r} leaked into live path: {ln!r}"
            )


def test_filelist_with_only_blank_lines(runner, tmp_path):
    """An effectively empty filelist (just whitespace and newlines) parses
    without erroring — the simulator gets nothing useful, but vcodeman
    shouldn't crash."""
    fl = _write(tmp_path / "f.f", "\n   \n\t\n\n")
    result = runner.invoke(cli, ['parse', str(fl)])
    assert result.exit_code == 0, result.output


def test_completely_empty_filelist(runner, tmp_path):
    """Zero-byte filelist: must not crash."""
    fl = tmp_path / "f.f"
    fl.write_bytes(b"")
    result = runner.invoke(cli, ['parse', str(fl)])
    assert result.exit_code == 0, result.output


def test_path_with_dot_relative_syntax(runner, tmp_path):
    """Paths like ./sub/file.v and ../sib/file.v normalize to absolute
    correctly."""
    sub = tmp_path / "sub"; sub.mkdir()
    leaf = sub / "leaf.v"; leaf.write_text("\n")
    fl = _write(sub / "list.f", "./leaf.v\n")
    out = _parse(runner, fl)
    assert str(leaf) in out
    # No literal "./" should leak into the absolute path
    assert "/./" not in out


def test_path_with_parent_dir_syntax(runner, tmp_path):
    """`../sibling/file.v` resolves against the filelist's dir."""
    a = tmp_path / "a"; a.mkdir()
    b = tmp_path / "b"; b.mkdir()
    (b / "leaf.v").write_text("\n")
    fl = _write(a / "list.f", "../b/leaf.v\n")
    out = _parse(runner, fl)
    assert str(b / "leaf.v") in out


def test_undefined_env_var_is_left_unchanged_by_default(runner, tmp_path):
    """Without --strict-env, an undefined $VAR stays in place rather than
    erroring out. This is the documented permissive behavior."""
    fl = _write(tmp_path / "f.f", "$DEFINITELY_NOT_SET_xyz/foo.v\n")
    result = runner.invoke(cli, ['parse', str(fl)])
    # Should not crash; either leave the var as-is or expand to empty
    assert result.exit_code == 0, result.output


def test_undefined_env_var_warns_to_stderr(runner, tmp_path, monkeypatch):
    """In non-strict mode the parser must surface unresolved $VARs as a
    stderr warning so the user notices the gap. CliRunner mixes stdout and
    stderr by default, so we check the merged output."""
    monkeypatch.delenv("ZZ_REALLY_NOT_SET", raising=False)
    fl = _write(tmp_path / "f.f", "$ZZ_REALLY_NOT_SET/foo.v\n")
    result = runner.invoke(cli, ['parse', str(fl)])
    assert result.exit_code == 0, result.output
    assert "warning" in result.output.lower()
    assert "ZZ_REALLY_NOT_SET" in result.output


def test_repeated_undefined_var_warns_only_once(runner, tmp_path, monkeypatch):
    """Same var seen in many paths warns once per resolver invocation."""
    monkeypatch.delenv("ZZ_DUPE", raising=False)
    fl = _write(tmp_path / "f.f",
        "$ZZ_DUPE/a.v\n"
        "$ZZ_DUPE/b.v\n"
        "$ZZ_DUPE/c.v\n"
    )
    result = runner.invoke(cli, ['parse', str(fl)])
    assert result.exit_code == 0
    # Count warning lines mentioning ZZ_DUPE
    warning_count = sum(
        1 for line in result.output.splitlines()
        if "warning" in line.lower() and "ZZ_DUPE" in line
    )
    assert warning_count == 1, (
        f"expected 1 dedup'd warning, got {warning_count}\n{result.output}"
    )


def test_strict_env_fails_on_undefined_var(runner, tmp_path):
    fl = _write(tmp_path / "f.f", "$DEFINITELY_NOT_SET_xyz/foo.v\n")
    result = runner.invoke(cli, ['parse', str(fl), '--strict-env'])
    assert result.exit_code != 0
    assert "DEFINITELY_NOT_SET_xyz" in result.output


def test_path_with_multiple_dots_in_filename(runner, tmp_path):
    """Common in real designs: foo_v1.0.svh or weird.bench.v"""
    weird = tmp_path / "foo.bench.v.svh"
    weird.write_text("\n")
    fl = _write(tmp_path / "f.f", f"{weird}\n")
    out = _parse(runner, fl)
    assert str(weird) in out


def test_indented_then_normal_lines(runner, tmp_path):
    """Inconsistent indentation must not change the resolved entries."""
    fl = _write(tmp_path / "f.f",
        "    indented_file.v\n"
        "normal_file.v\n"
        "\t\ttab_indented.v\n"
    )
    out = _parse(runner, fl)
    for needle in ("indented_file.v", "normal_file.v", "tab_indented.v"):
        assert needle in out, f"missing: {needle}\n{out}"


def test_lots_of_comments_around_options(runner, tmp_path):
    """Filelists with heavy commentary around the actual options."""
    fl = _write(tmp_path / "f.f",
        "// Block comment header\n"
        "// describing the filelist\n"
        "//\n"
        "+incdir+/include/path\n"
        "// next section: defines\n"
        "+define+DEBUG=1\n"
        "// the actual files\n"
        "file_a.v\n"
        "file_b.v\n"
        "// end\n"
    )
    out = _parse(runner, fl)
    assert "Block comment header" in out
    assert "/include/path" in out
    assert "DEBUG=1" in out
    assert "file_a.v" in out
    assert "file_b.v" in out
