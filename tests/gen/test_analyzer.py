from pathlib import Path
from vcodeman.gen.analyzer import analyze_file, FileInfo, MacroDef


def test_analyze_package_file(simple_dir):
    info = analyze_file(simple_dir / "pkg_types.sv")
    assert info.declared_packages == ["pkg_types"]
    assert info.declared_modules == []
    assert info.imported_packages == []
    assert info.instantiated_modules == []


def test_analyze_module_with_import_and_include(simple_dir):
    info = analyze_file(simple_dir / "alu.sv")
    assert "alu" in info.declared_modules
    assert "pkg_types" in info.imported_packages
    assert "defines.svh" in info.included_files


def test_analyze_module_instantiation(simple_dir):
    info = analyze_file(simple_dir / "core.sv")
    assert "core" in info.declared_modules
    assert "alu" in info.instantiated_modules


def test_analyze_top_module(simple_dir):
    info = analyze_file(simple_dir / "top.sv")
    assert "top" in info.declared_modules
    assert "core" in info.instantiated_modules


def test_analyze_header_macros(simple_dir):
    info = analyze_file(simple_dir / "include" / "defines.svh")
    macro_names = [m.name for m in info.defined_macros]
    assert "SIMULATION" in macro_names
    assert "DATA_WIDTH" in macro_names


def test_analyze_ifdef_usage(simple_dir):
    info = analyze_file(simple_dir / "alu.sv")
    assert "SIMULATION" in info.used_macros


def test_analyze_path_is_absolute(simple_dir):
    info = analyze_file(simple_dir / "top.sv")
    assert info.path.is_absolute()


def test_gate_primitive_not_in_instantiated_modules(tmp_path):
    """gate_instantiation must NOT appear as a module dependency."""
    sv = tmp_path / "gates.sv"
    sv.write_text("module gates (output o, input a, b);\n  and g1 (o, a, b);\nendmodule\n")
    info = analyze_file(sv)
    assert "and" not in info.instantiated_modules


def test_analyze_nonansi_module(tmp_path):
    """Legacy Verilog-1995 non-ANSI port style must be recognized."""
    sv = tmp_path / "nonansi.v"
    sv.write_text("module legacy(a, b);\n  input a;\n  output b;\n  assign b = a;\nendmodule\n")
    info = analyze_file(sv)
    assert "legacy" in info.declared_modules
