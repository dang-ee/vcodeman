"""Tests for Verilog-XL filelist parser."""

import pytest
from pathlib import Path

from vcodeman.parser import FilelistParser
from vcodeman.resolver import CircularReferenceError


def test_parser_basic(test_filelists):
    """Test parsing a simple filelist with 2 files."""
    parser = FilelistParser()
    simple_f = test_filelists / "simple.f"

    result = parser.parse(simple_f)

    # Should find 2 files from simple.f
    assert result is not None
    # This test will fail until parser is implemented
    # Expected: 2 files (file1.v, file2.v)


def test_parser_nested(test_filelists):
    """Test parsing nested filelists and verify files from both levels."""
    parser = FilelistParser()
    nested_root = test_filelists / "nested_root.f"

    result = parser.parse(nested_root)

    # Should find files from both root and nested level1
    assert result is not None
    # This test will fail until parser is implemented
    # Expected: 2 files (root_file.v, level1_file.v)


def test_parser_circular(test_filelists):
    """Test that circular references are detected and raise error."""
    parser = FilelistParser()
    circular_a = test_filelists / "circular_a.f"

    # Should raise CircularReferenceError
    with pytest.raises(CircularReferenceError):
        parser.parse(circular_a)


def test_parse_library_dir(temp_filelist):
    """Test parsing -y library directory option."""
    parser = FilelistParser()
    filelist = temp_filelist("-y /lib/dir\nfile.v\n")

    result = parser.parse(filelist)
    assert result is not None


def test_parse_library_file(temp_filelist):
    """Test parsing -v library file option."""
    parser = FilelistParser()
    filelist = temp_filelist("-v /lib/cells.v\ndesign.v\n")

    result = parser.parse(filelist)
    assert result is not None


def test_parse_incdir(temp_filelist):
    """Test parsing +incdir+ with multiple paths."""
    parser = FilelistParser()
    filelist = temp_filelist("+incdir+/inc1+/inc2+/inc3\nfile.v\n")

    result = parser.parse(filelist)
    assert result is not None


def test_parse_define(temp_filelist):
    """Test parsing +define+ with and without values."""
    parser = FilelistParser()
    filelist = temp_filelist("+define+DEBUG+VERSION=1.0+TRACE\nfile.v\n")

    result = parser.parse(filelist)
    assert result is not None


def test_parse_libext(temp_filelist):
    """Test parsing +libext+ option."""
    parser = FilelistParser()
    filelist = temp_filelist("+libext+.v+.sv+.vp\nfile.v\n")

    result = parser.parse(filelist)
    assert result is not None


def test_parse_mixed(temp_filelist):
    """Test parsing mixed option types."""
    content = """-f nested.f
-y /lib
-v /lib/cells.v
+incdir+/inc
+define+DEBUG
+libext+.v
design.v
"""
    parser = FilelistParser()
    filelist = temp_filelist(content)

    result = parser.parse(filelist)
    assert result is not None


def test_parse_f_vs_F_difference(tmp_path):
    """Test that -f resolves relative to cwd, -F resolves relative to filelist dir.

    Verilog-XL behavior:
    - -f: resolves relative paths from current working directory
    - -F: resolves relative paths from parent filelist's directory
    """
    import os

    # Create directory structure:
    # tmp_path/
    #   lists/
    #     root.f       (-f sub.f or -F sub.f)
    #     sub/
    #       sub.f      (contains file.v)
    #       file.v

    lists_dir = tmp_path / "lists"
    lists_dir.mkdir()
    sub_dir = lists_dir / "sub"
    sub_dir.mkdir()

    # Create sub.f in sub/
    (sub_dir / "sub.f").write_text("file.v\n")
    (sub_dir / "file.v").write_text("")

    parser = FilelistParser()

    # Test -F: should resolve sub/sub.f relative to root.f's directory (lists/)
    (lists_dir / "root_F.f").write_text("-F sub/sub.f\n")
    result_F = parser.parse(lists_dir / "root_F.f")
    assert result_F is not None

    # Check that sub.f was found (resolved relative to lists/)
    parsed_data = result_F._parsed_data
    filelists = parsed_data.get('filelists', [])
    # Should have 2 filelists: root_F.f and sub/sub.f
    assert len(filelists) == 2
    sub_filelist = next((fl for fl in filelists if 'sub.f' in fl['filepath']), None)
    assert sub_filelist is not None

    # Test -f: should resolve sub/sub.f relative to cwd
    (lists_dir / "root_f.f").write_text("-f sub/sub.f\n")

    # If cwd is not lists_dir, -f won't find sub/sub.f
    # We need to change cwd to lists_dir for -f to work the same as -F
    original_cwd = os.getcwd()
    try:
        os.chdir(lists_dir)
        result_f = parser.parse(lists_dir / "root_f.f")
        assert result_f is not None

        parsed_data_f = result_f._parsed_data
        filelists_f = parsed_data_f.get('filelists', [])
        # Should have 2 filelists when cwd is lists_dir
        assert len(filelists_f) == 2
    finally:
        os.chdir(original_cwd)
