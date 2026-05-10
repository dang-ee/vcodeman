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


def test_resolve_backend_builtin_icarus():
    from vcodeman.gen.compiler import IcarusBackend, resolve_backend
    assert resolve_backend("icarus") is IcarusBackend


def test_resolve_backend_unknown_name_raises():
    from vcodeman.gen.compiler import resolve_backend
    with pytest.raises(KeyError, match="Unknown backend"):
        resolve_backend("nonexistent")


def test_resolve_backend_from_file_auto_class(tmp_path):
    from vcodeman.gen.compiler import resolve_backend, SimulatorBackend
    backend_py = tmp_path / "my_backend.py"
    backend_py.write_text("""
from vcodeman.gen.compiler import SimulatorBackend

class MyBackend(SimulatorBackend):
    name = "my"

    def compile_cmd(self, filelist, top_module=None):
        return ["echo", str(filelist)]

    def parse_errors(self, stdout, stderr, rc):
        return []
""")
    cls = resolve_backend(str(backend_py))
    assert issubclass(cls, SimulatorBackend)
    assert cls.name == "my"


def test_resolve_backend_from_file_explicit_class(tmp_path):
    from vcodeman.gen.compiler import resolve_backend
    backend_py = tmp_path / "two_backends.py"
    backend_py.write_text("""
from vcodeman.gen.compiler import SimulatorBackend

class FirstBackend(SimulatorBackend):
    name = "first"
    def compile_cmd(self, filelist, top_module=None): return []
    def parse_errors(self, stdout, stderr, rc): return []

class SecondBackend(SimulatorBackend):
    name = "second"
    def compile_cmd(self, filelist, top_module=None): return []
    def parse_errors(self, stdout, stderr, rc): return []
""")
    cls = resolve_backend(f"{backend_py}:SecondBackend")
    assert cls.name == "second"


def test_resolve_backend_from_file_no_subclass_raises(tmp_path):
    from vcodeman.gen.compiler import resolve_backend
    backend_py = tmp_path / "empty.py"
    backend_py.write_text("# no SimulatorBackend subclass\n")
    with pytest.raises(ValueError, match="No SimulatorBackend subclass"):
        resolve_backend(str(backend_py))


def test_resolve_backend_from_file_multiple_no_class_raises(tmp_path):
    from vcodeman.gen.compiler import resolve_backend
    backend_py = tmp_path / "two.py"
    backend_py.write_text("""
from vcodeman.gen.compiler import SimulatorBackend

class A(SimulatorBackend):
    name = "a"
    def compile_cmd(self, filelist, top_module=None): return []
    def parse_errors(self, stdout, stderr, rc): return []

class B(SimulatorBackend):
    name = "b"
    def compile_cmd(self, filelist, top_module=None): return []
    def parse_errors(self, stdout, stderr, rc): return []
""")
    with pytest.raises(ValueError, match="multiple"):
        resolve_backend(str(backend_py))


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
