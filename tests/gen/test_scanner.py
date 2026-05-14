from pathlib import Path
from vcodeman.gen.scanner import scan, ScanResult


def test_scan_finds_all_file_types(simple_dir):
    result = scan(simple_dir)
    assert isinstance(result, ScanResult)
    source_names = {f.name for f in result.source_files}
    assert source_names == {"pkg_types.sv", "alu.sv", "core.sv", "top.sv"}


def test_scan_finds_header_files(simple_dir):
    result = scan(simple_dir)
    header_names = {f.name for f in result.header_files}
    assert header_names == {"defines.svh"}


def test_scan_computes_include_dirs(simple_dir):
    result = scan(simple_dir)
    inc_names = {d.name for d in result.include_dirs}
    assert inc_names == {"include"}


def test_scan_returns_absolute_paths(simple_dir):
    result = scan(simple_dir)
    for p in result.source_files + result.header_files + result.include_dirs:
        assert p.is_absolute(), f"Expected absolute path: {p}"


def test_scan_empty_dir(tmp_path):
    result = scan(tmp_path)
    assert result.source_files == []
    assert result.header_files == []
    assert result.include_dirs == []
