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
