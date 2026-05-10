"""Integration tests for `vcodeman gen` CLI (the dw wrapper).

Each test invokes the click command via CliRunner, runs the full pipeline
(static analysis + render + compile via dw subprocess), and asserts on the
recovered artifact files. eda-env required.
"""
import json
import shutil
from pathlib import Path

import pytest
from click.testing import CliRunner

from vcodeman.cli import cli


pytestmark = [
    pytest.mark.skipif(not shutil.which("eda-env"), reason="eda-env not available"),
]


def _cpu_fixture_dir() -> Path:
    return Path(__file__).parent / "fixtures" / "cpu"


def test_cmd_gen_creates_output_files(tmp_path):
    output = tmp_path / "cpu.f"
    runs_dir = tmp_path / "runs"

    runner = CliRunner()
    result = runner.invoke(cli, [
        "gen", str(_cpu_fixture_dir()),
        "--output", str(output),
        "--runs-dir", str(runs_dir),
        "--no-ai",
    ])
    assert result.exit_code == 0, result.output
    assert output.is_file()
    assert (tmp_path / "cpu.f.tops.txt").is_file()
    assert (tmp_path / "cpu.f.macros.yaml").is_file()


def test_cmd_gen_no_compile_skips_compile_dir(tmp_path):
    output = tmp_path / "cpu.f"
    runs_dir = tmp_path / "runs"

    runner = CliRunner()
    result = runner.invoke(cli, [
        "gen", str(_cpu_fixture_dir()),
        "--output", str(output),
        "--runs-dir", str(runs_dir),
        "--no-compile",
    ])
    assert result.exit_code == 0, result.output
    assert output.is_file()

    # Verify no compile_N dir exists in the run_dir
    import re
    run_dir = next(runs_dir.iterdir())
    rx = re.compile(r"\d+\.compile_\d+")
    compile_dirs = [p for p in run_dir.iterdir() if rx.fullmatch(p.name)]
    assert not compile_dirs, f"--no-compile must not produce compile dirs, got {compile_dirs}"


def test_cmd_gen_filelist_has_correct_order(tmp_path):
    """Verify the produced filelist has +incdir+ before sources, packages
    before non-packages."""
    output = tmp_path / "cpu.f"
    runs_dir = tmp_path / "runs"

    runner = CliRunner()
    result = runner.invoke(cli, [
        "gen", str(_cpu_fixture_dir()),
        "--output", str(output),
        "--runs-dir", str(runs_dir),
        "--no-ai",
    ])
    assert result.exit_code == 0

    text = output.read_text()
    incdir_idx = text.find("+incdir+")
    base_pkg_idx = text.find("base_pkg.sv")
    cpu_idx = text.find("rtl/cpu.sv")
    assert 0 <= incdir_idx < base_pkg_idx < cpu_idx, (
        f"order broken: incdir={incdir_idx}, base_pkg={base_pkg_idx}, cpu={cpu_idx}"
    )


def test_cmd_gen_tops_file_contains_top(tmp_path):
    output = tmp_path / "cpu.f"
    runs_dir = tmp_path / "runs"

    runner = CliRunner()
    result = runner.invoke(cli, [
        "gen", str(_cpu_fixture_dir()),
        "--output", str(output),
        "--runs-dir", str(runs_dir),
        "--no-ai",
    ])
    assert result.exit_code == 0

    tops = (tmp_path / "cpu.f.tops.txt").read_text()
    assert "tb_cpu" in tops


def test_cmd_gen_macros_file_has_simulation(tmp_path):
    output = tmp_path / "cpu.f"
    runs_dir = tmp_path / "runs"

    runner = CliRunner()
    result = runner.invoke(cli, [
        "gen", str(_cpu_fixture_dir()),
        "--output", str(output),
        "--runs-dir", str(runs_dir),
        "--no-ai",
    ])
    assert result.exit_code == 0

    import yaml
    macros = yaml.safe_load((tmp_path / "cpu.f.macros.yaml").read_text())
    macro_names = {d["name"] for d in macros["definitions"]}
    assert "SIMULATION" in macro_names
