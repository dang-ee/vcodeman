import pytest
import shutil
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch
from vcodeman.gen.compiler import (
    IcarusBackend, CompileError, CompileResult, BACKENDS
)


def test_icarus_compile_cmd_structure():
    backend = IcarusBackend()
    cmd = backend.compile_cmd(Path("/some/out.f"))
    assert cmd[0] == "eda-env"
    assert "iverilog" in cmd
    assert "-g2012" in cmd
    assert "/some/out.f" in " ".join(cmd)


def test_icarus_compile_cmd_with_top():
    backend = IcarusBackend()
    cmd = backend.compile_cmd(Path("/some/out.f"), top_module="my_top")
    assert "-s" in cmd
    assert "my_top" in cmd


def test_icarus_top_directive_returns_none():
    assert IcarusBackend().top_directive("any_top") is None


def test_parse_errors_extracts_file_and_line():
    backend = IcarusBackend()
    stderr = "/path/to/file.sv:42: error: undeclared identifier 'foo'"
    errors = backend.parse_errors("", stderr, 1)
    assert len(errors) == 1
    assert errors[0].file == "/path/to/file.sv"
    assert errors[0].line == 42
    assert "undeclared identifier" in errors[0].message


def test_parse_errors_empty_on_success():
    backend = IcarusBackend()
    errors = backend.parse_errors("", "", 0)
    assert errors == []


def test_backends_registry_contains_icarus():
    assert "icarus" in BACKENDS
    assert isinstance(BACKENDS["icarus"](), IcarusBackend)


@pytest.mark.skipif(not shutil.which("eda-env"), reason="eda-env not available")
def test_compile_success(tmp_path, simple_dir):
    """Integration: compile the simple fixture and expect success."""
    from vcodeman.gen.scanner import scan
    from vcodeman.gen.analyzer import analyze_file
    from vcodeman.gen.graph import build_order
    from vcodeman.gen.writer import render_filelist

    result = scan(simple_dir)
    infos = [analyze_file(f) for f in result.source_files]

    pkg_files = [fi.path for fi in infos if fi.declared_packages]
    src_files = [p for p in build_order(infos) if p not in pkg_files]

    content = render_filelist(result.include_dirs, pkg_files, src_files,
                              top_module="top", simulator="icarus")
    filelist = tmp_path / "out.f"
    filelist.write_text(content)

    backend = IcarusBackend()
    compile_result = backend.compile(filelist, top_module="top")
    assert compile_result.success, f"Errors: {compile_result.errors}"
