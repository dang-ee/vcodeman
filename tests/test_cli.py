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


def test_cli_parse_no_markers(cli_runner, test_filelists):
    """--no-markers suppresses // RESOLVE START / END around -f/-F includes."""
    nested_root = test_filelists / "nested_root.f"

    result = cli_runner.invoke(cli, ['parse', str(nested_root), '--no-markers'])

    assert result.exit_code == 0
    assert "RESOLVE START" not in result.output
    assert "RESOLVE END" not in result.output
    # Flattening still happens — content from nested filelist is inlined
    assert "level1_file.v" in result.output
    assert "root_file.v" in result.output


def test_cli_parse_comment_missing(cli_runner, temp_filelist):
    """--comment-missing replaces non-existent file lines with // MISSING comments."""
    filelist = temp_filelist("/nonexistent/zzz_missing_file.v\n")

    result = cli_runner.invoke(cli, ['parse', str(filelist), '--comment-missing'])

    assert result.exit_code == 0
    assert "// MISSING:" in result.output
    assert "/nonexistent/zzz_missing_file.v" in result.output
    # Path must appear ONLY inside a comment line, never as a live entry
    for line in result.output.splitlines():
        if "/nonexistent/zzz_missing_file.v" in line:
            assert line.lstrip().startswith("//"), f"missing path leaked as live entry: {line!r}"


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


def test_cli_parse_no_markers_and_comment_missing(cli_runner, tmp_path):
    """Both flags compose: clean output, missing files commented."""
    real_file = tmp_path / "real_file.v"
    real_file.write_text("// dummy\n")

    nested = tmp_path / "nested.f"
    nested.write_text("/nonexistent/inside_nested.v\n")

    root = tmp_path / "root.f"
    root.write_text(f"-f {nested}\n{real_file}\n")

    result = cli_runner.invoke(
        cli, ['parse', str(root), '--no-markers', '--comment-missing']
    )

    assert result.exit_code == 0
    assert "RESOLVE START" not in result.output
    assert "RESOLVE END" not in result.output
    assert "// MISSING:" in result.output
    # Real file appears as a live entry (not commented)
    real_live = [
        ln for ln in result.output.splitlines()
        if str(real_file) in ln and not ln.lstrip().startswith("//")
    ]
    assert len(real_live) == 1, f"expected real file once as live entry, got: {real_live!r}"
