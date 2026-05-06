"""Tests for CLI commands."""

import pytest
from pathlib import Path

from vcodeman.cli import cli


def test_cli_parse_basic(cli_runner, temp_filelist):
    """Test parse command with simple filelist."""
    filelist = temp_filelist("file1.v\nfile2.v\n")

    result = cli_runner.invoke(cli, ['parse', str(filelist)])

    # Should complete without error
    assert result.exit_code == 0
    assert "file1.v" in result.output
    assert "file2.v" in result.output


def test_cli_parse_nested(cli_runner, test_filelists):
    """Test parse command with nested structure."""
    nested_root = test_filelists / "nested_root.f"

    result = cli_runner.invoke(cli, ['parse', str(nested_root)])

    # Should complete and include files from both filelists
    assert result.exit_code == 0
    assert "root_file.v" in result.output
    assert "level1_file.v" in result.output


def test_cli_parse_with_comments(cli_runner, temp_filelist):
    """Test parse with comment conversion."""
    filelist = temp_filelist("# Comment\nfile.v\n")

    result = cli_runner.invoke(cli, ['parse', str(filelist)])
    assert result.exit_code == 0
    # Should have comment converted to // format
    assert "// # Comment" in result.output
    # File paths should be converted to absolute paths
    assert "file.v" in result.output


def test_cli_output_formats(cli_runner, temp_filelist):
    """Test JSON and text output formats."""
    filelist = temp_filelist("file.v\n")

    # Test text format (default) - preserves original format
    result_text = cli_runner.invoke(cli, ['parse', str(filelist)])
    assert result_text.exit_code == 0
    assert "file.v" in result_text.output

    # Test JSON format
    result_json = cli_runner.invoke(cli, [
        'parse',
        str(filelist),
        '--format', 'json'
    ])
    assert result_json.exit_code == 0
    # JSON output should contain JSON structure
    assert '"root_filepath"' in result_json.output


def test_cli_output_to_file(cli_runner, temp_filelist, tmp_path):
    """Test output to file with -o option."""
    filelist = temp_filelist("file.v\n")
    output_file = tmp_path / "output.f"

    result = cli_runner.invoke(cli, [
        'parse',
        str(filelist),
        '-o', str(output_file)
    ])

    assert result.exit_code == 0
    assert output_file.exists()
    content = output_file.read_text()
    assert "file.v" in content


def test_cli_sqlite_output(cli_runner, temp_filelist, tmp_path):
    """Test SQLite output format."""
    import sqlite3

    filelist = temp_filelist("file1.v\nfile2.v\n")
    output_file = tmp_path / "output.db"

    result = cli_runner.invoke(cli, [
        'parse',
        str(filelist),
        '--format', 'sqlite',
        '-o', str(output_file)
    ])

    assert result.exit_code == 0
    assert output_file.exists()

    # Verify it's a valid SQLite database with expected tables
    conn = sqlite3.connect(output_file)
    cursor = conn.cursor()

    # Check that key tables exist
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = {row[0] for row in cursor.fetchall()}
    assert "filelist" in tables
    assert "file_entry" in tables
    assert "line_item" in tables

    # Verify there's data in the filelist table
    cursor.execute("SELECT COUNT(*) FROM filelist")
    assert cursor.fetchone()[0] >= 1

    conn.close()


def test_cli_sqlite_default_output(cli_runner, temp_filelist):
    """Test SQLite format uses default .db filename when no output specified."""
    filelist = temp_filelist("file.v\n")

    result = cli_runner.invoke(cli, [
        'parse',
        str(filelist),
        '--format', 'sqlite'
    ])

    assert result.exit_code == 0
    # Default output should be the filelist name with .db extension
    expected_db = filelist.with_suffix('.db')
    assert expected_db.exists()

    # Cleanup
    expected_db.unlink()


def test_cli_error_handling(cli_runner, tmp_path):
    """Test error messages for various failure scenarios."""
    # Test with non-existent file
    result = cli_runner.invoke(cli, ['parse', str(tmp_path / 'nonexistent.f')])
    assert result.exit_code != 0


def test_cli_parse_env_injects_variable(cli_runner, tmp_path, monkeypatch):
    """--env KEY=VALUE injects the var so $KEY in the filelist resolves."""
    # Make sure PROJ is NOT in the inherited env
    monkeypatch.delenv("MY_INJECTED_PROJ", raising=False)

    proj_dir = tmp_path / "proj_root"
    proj_dir.mkdir()
    (proj_dir / "real.v").write_text("// real\n")

    fl = tmp_path / "list.f"
    fl.write_text("$MY_INJECTED_PROJ/real.v\n")

    result = cli_runner.invoke(
        cli, ['parse', str(fl), '--env', f'MY_INJECTED_PROJ={proj_dir}']
    )

    assert result.exit_code == 0, result.output
    assert str(proj_dir / "real.v") in result.output


def test_cli_parse_env_multiple_pairs(cli_runner, tmp_path, monkeypatch):
    """Multiple --env flags accumulate; each KEY=VALUE applied independently."""
    monkeypatch.delenv("INJ_A", raising=False)
    monkeypatch.delenv("INJ_B", raising=False)

    a_dir = tmp_path / "a"; a_dir.mkdir(); (a_dir / "x.v").write_text("\n")
    b_dir = tmp_path / "b"; b_dir.mkdir(); (b_dir / "y.v").write_text("\n")

    fl = tmp_path / "list.f"
    fl.write_text("$INJ_A/x.v\n$INJ_B/y.v\n")

    result = cli_runner.invoke(
        cli,
        ['parse', str(fl), '--env', f'INJ_A={a_dir}', '--env', f'INJ_B={b_dir}'],
    )
    assert result.exit_code == 0, result.output
    assert str(a_dir / "x.v") in result.output
    assert str(b_dir / "y.v") in result.output


def test_cli_parse_env_rejects_bad_format(cli_runner, tmp_path):
    """--env without `=` is rejected with exit code 2."""
    fl = tmp_path / "list.f"
    fl.write_text("file.v\n")

    result = cli_runner.invoke(cli, ['parse', str(fl), '--env', 'NO_EQUALS'])
    assert result.exit_code == 2
    assert "must be KEY=VALUE" in result.output


def test_cli_parse_env_rejects_empty_key(cli_runner, tmp_path):
    """--env =value (empty key) is rejected."""
    fl = tmp_path / "list.f"
    fl.write_text("file.v\n")

    result = cli_runner.invoke(cli, ['parse', str(fl), '--env', '=value_only'])
    assert result.exit_code == 2
    assert "may not be empty" in result.output


# ---------------------------------------------------------------------------
# --incdir-first
# ---------------------------------------------------------------------------

def test_incdir_first_moves_to_top(cli_runner, temp_filelist):
    """All +incdir+ lines appear before any file paths."""
    fl = temp_filelist(
        "file_a.v\n"
        "+incdir+/inc/shared\n"
        "file_b.v\n"
        "+incdir+/inc/ip\n"
        "file_c.v\n"
    )

    result = cli_runner.invoke(cli, ['parse', str(fl), '--incdir-first'])

    assert result.exit_code == 0
    lines = [l for l in result.output.splitlines() if l.strip()]
    incdir_lines = [i for i, l in enumerate(lines) if l.startswith('+incdir+')]
    file_lines   = [i for i, l in enumerate(lines) if l.endswith('.v')]

    assert len(incdir_lines) == 2
    assert len(file_lines) == 3
    assert max(incdir_lines) < min(file_lines), "all incdir must precede all file paths"


def test_incdir_first_collects_from_nested(cli_runner, tmp_path):
    """--incdir-first hoists +incdir+ entries from inside nested -F includes."""
    sub = tmp_path / "sub.f"
    sub.write_text("+incdir+/inc/sub\nsub/mod.v\n")

    root = tmp_path / "root.f"
    root.write_text("-F sub.f\n+incdir+/inc/root\nroot/top.v\n")

    result = cli_runner.invoke(cli, ['parse', str(root), '--incdir-first'])

    assert result.exit_code == 0
    lines = [l for l in result.output.splitlines() if l.strip()]
    incdir_indices = [i for i, l in enumerate(lines) if l.startswith('+incdir+')]
    file_indices   = [i for i, l in enumerate(lines) if l.endswith('.v')]

    assert len(incdir_indices) == 2
    assert '+incdir+/inc/sub'  in result.output
    assert '+incdir+/inc/root' in result.output
    assert max(incdir_indices) < min(file_indices), "nested incdir must also be hoisted"


def test_incdir_first_no_incdir_is_noop(cli_runner, temp_filelist):
    """--incdir-first on a filelist with no +incdir+ produces identical output."""
    fl = temp_filelist("file_a.v\nfile_b.v\n")

    plain  = cli_runner.invoke(cli, ['parse', str(fl)])
    hoisted = cli_runner.invoke(cli, ['parse', str(fl), '--incdir-first'])

    assert plain.exit_code == 0
    assert hoisted.exit_code == 0
    assert plain.output == hoisted.output


# ---------------------------------------------------------------------------
# --no-comments
# ---------------------------------------------------------------------------

def test_no_comments_strips_hash_and_slash(cli_runner, temp_filelist):
    """Both # and // comment lines are removed."""
    fl = temp_filelist(
        "// top header\n"
        "file_a.v\n"
        "# mid comment\n"
        "file_b.v\n"
    )

    result = cli_runner.invoke(cli, ['parse', str(fl), '--no-comments'])

    assert result.exit_code == 0
    assert '//' not in result.output
    assert '#'  not in result.output
    assert 'file_a.v' in result.output
    assert 'file_b.v' in result.output


def test_no_comments_strips_resolver_markers(cli_runner, tmp_path):
    """--no-comments also removes the // resolved start: / end: markers."""
    sub = tmp_path / "sub.f"
    sub.write_text("sub/mod.v\n")

    root = tmp_path / "root.f"
    root.write_text("-F sub.f\nroot/top.v\n")

    result = cli_runner.invoke(cli, ['parse', str(root), '--no-comments'])

    assert result.exit_code == 0
    assert 'resolved start' not in result.output
    assert 'resolved end'   not in result.output
    assert 'mod.v'  in result.output
    assert 'top.v'  in result.output


def test_no_comments_hides_skip_ext_lines(cli_runner, temp_filelist):
    """When --no-comments is combined with --skip-ext, skipped files vanish entirely."""
    fl = temp_filelist("core.v\npackage.vhd\ntop.v\n")

    result = cli_runner.invoke(
        cli, ['parse', str(fl), '--skip-ext', 'vhd', '--no-comments']
    )

    assert result.exit_code == 0
    assert 'skipped' not in result.output
    assert '.vhd'    not in result.output
    assert 'core.v'  in result.output
    assert 'top.v'   in result.output


# ---------------------------------------------------------------------------
# --incdir-first + --no-comments combined
# ---------------------------------------------------------------------------

def test_incdir_first_and_no_comments_combined(cli_runner, tmp_path):
    """Combined flags: incdir at top, zero comment lines in output."""
    sub = tmp_path / "sub.f"
    sub.write_text("// sub header\n+incdir+/inc/sub\nsub/mod.v\n")

    root = tmp_path / "root.f"
    root.write_text(
        "# root header\n"
        "-F sub.f\n"
        "+incdir+/inc/root\n"
        "root/top.v\n"
    )

    result = cli_runner.invoke(
        cli, ['parse', str(root), '--incdir-first', '--no-comments']
    )

    assert result.exit_code == 0

    lines = [l for l in result.output.splitlines() if l.strip()]
    comment_lines = [l for l in lines if l.startswith('//') or l.startswith('#')]
    incdir_lines  = [i for i, l in enumerate(lines) if l.startswith('+incdir+')]
    file_lines    = [i for i, l in enumerate(lines) if l.endswith('.v')]

    assert comment_lines == [], f"unexpected comment lines: {comment_lines}"
    assert len(incdir_lines) == 2
    assert max(incdir_lines) < min(file_lines)


