import yaml
from pathlib import Path
from vcodeman.gen.analyzer import FileInfo, MacroDef
from vcodeman.gen.macro_extractor import build_macro_report, write_macro_yaml, MacroReport


def _fi(name: str, defs=(), used=()):
    macros = [MacroDef(name=d[0], value=d[1], defined_in=Path(f"/fake/{name}.sv"), line=1)
              for d in defs]
    return FileInfo(path=Path(f"/fake/{name}.sv"),
                    defined_macros=macros,
                    used_macros=list(used))


def test_build_collects_definitions():
    fi = _fi("a", defs=[("WIDTH", "8"), ("SIMULATION", None)])
    report = build_macro_report([fi])
    names = [d.name for d in report.definitions]
    assert "WIDTH" in names
    assert "SIMULATION" in names


def test_build_collects_usages():
    fi_def = _fi("hdr", defs=[("MY_FLAG", None)])
    fi_use = _fi("mod", used=["MY_FLAG"])
    report = build_macro_report([fi_def, fi_use])
    assert Path("/fake/mod.sv") in report.usages.get("MY_FLAG", [])


def test_write_yaml_structure(tmp_path):
    fi = _fi("pkg", defs=[("WIDTH", "8")], used=["WIDTH"])
    report = build_macro_report([fi])
    out = tmp_path / "out.macros.yaml"
    write_macro_yaml(report, out)
    data = yaml.safe_load(out.read_text())
    assert "definitions" in data
    assert "usages" in data
    assert data["definitions"][0]["name"] == "WIDTH"
    assert data["definitions"][0]["value"] == "8"


def test_write_yaml_null_value(tmp_path):
    fi = _fi("h", defs=[("FLAG", None)])
    report = build_macro_report([fi])
    out = tmp_path / "out.macros.yaml"
    write_macro_yaml(report, out)
    data = yaml.safe_load(out.read_text())
    assert data["definitions"][0]["value"] is None
