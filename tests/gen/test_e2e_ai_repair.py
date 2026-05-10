"""E2E test: vcodeman gen against the cpu fixture, via the dw flow.

The cpu fixture compiles cleanly with static analysis alone, so this is
primarily a smoke test that the full pipeline (CLI wrapper → dw run →
@dw.flow main → analyze/render/compile_0) works end-to-end. The repair
path is exercised by:
  - test_dw_flow.py::test_repair_step_uses_run_agent_and_post_processes
    (Layer 1, mocked Claude)
  - test_dw_flow.py::test_full_flow_via_dw_run_no_ai
    (Layer 2, real subprocess + iverilog, no Claude)

Real-Claude e2e (Layer 3) is captured here when the cpu fixture compiles
on the first try; forcing the repair branch from cmd_gen would require
fixture surgery and is intentionally out of scope.
"""
from __future__ import annotations

import json
import re
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


def test_vcodeman_gen_full_pipeline_succeeds(tmp_path):
    """vcodeman gen on cpu fixture compiles cleanly via static analysis
    (no AI repair needed). Verifies the full dw flow end-to-end."""
    output = tmp_path / "cpu.f"
    runs_dir = tmp_path / "runs"

    runner = CliRunner()
    result = runner.invoke(cli, [
        "gen", str(_cpu_fixture_dir()),
        "--output", str(output),
        "--runs-dir", str(runs_dir),
    ])
    assert result.exit_code == 0, result.output
    assert output.is_file()

    # Verify the run_dir layout: dw names step dirs as NN.label
    run_dir = next(runs_dir.iterdir())
    rx_compile = re.compile(r"\d+\.compile_(\d+)")
    compile_dirs = [(int(m.group(1)), p) for p in run_dir.iterdir()
                    if (m := rx_compile.fullmatch(p.name))]
    assert compile_dirs, f"no compile_N dir under {run_dir}"
    last = max(compile_dirs, key=lambda t: t[0])[1]

    final = json.loads((last / "result.json").read_text())
    assert final["success"] is True


def test_vcodeman_gen_recovers_sidecar_files(tmp_path):
    """tops.txt and macros.yaml should be copied alongside --output."""
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

    tops = (tmp_path / "cpu.f.tops.txt").read_text()
    assert "tb_cpu" in tops

    import yaml
    macros = yaml.safe_load((tmp_path / "cpu.f.macros.yaml").read_text())
    macro_names = {d["name"] for d in macros["definitions"]}
    assert "SIMULATION" in macro_names
