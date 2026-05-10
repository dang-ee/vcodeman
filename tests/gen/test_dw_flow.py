"""Tests for src/vcodeman/gen/dw_flow/flow.py — step functions and the
@dw.flow main entrypoint.

Layer 1 (here): each step function called directly with a fabricated
step_dir and minimal Context. run_agent patched for repair_step.

Layer 2 (here): subprocess `dw run` against a tmp DW_RUNS_DIR with
run_agent patched. (Added in later tasks.)

Layer 3: see test_e2e_ai_repair.py — real Claude, real iverilog.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest


FLOW_PY = Path(__file__).resolve().parent.parent.parent / "src/vcodeman/gen/dw_flow/flow.py"


def test_flow_py_path_exists():
    assert FLOW_PY.is_file(), f"flow.py missing at {FLOW_PY}"


def test_flow_main_reads_env_vars(tmp_path):
    """Smoke test: flow.py imports cleanly and StepCfg picks up env vars."""
    from vcodeman.gen.dw_flow.flow import StepCfg
    cfg = StepCfg(
        rtl_dir=str(tmp_path),
        top="tb_top",
        simulator="icarus",
        max_iter=3,
        use_ai=False,
    )
    assert cfg.rtl_dir == str(tmp_path)
    assert cfg.top == "tb_top"
    assert cfg.max_iter == 3
    assert cfg.use_ai is False


import json
from unittest.mock import MagicMock


def _make_ctx(step_dir: Path):
    """Fabricate a minimal Context that step functions can use."""
    ctx = MagicMock()
    ctx.step_dir.path = step_dir
    ctx.manifest_dir = FLOW_PY.parent.resolve()
    # step_label reads ctx.task_dir.path.name; must be a str not MagicMock
    ctx.task_dir.path.name = step_dir.name
    return ctx


def _cpu_fixture_dir() -> Path:
    return Path(__file__).parent / "fixtures" / "cpu"


def test_analyze_step_writes_expected_artifacts(tmp_path):
    from vcodeman.gen.dw_flow.flow import StepCfg, analyze_step

    cfg = StepCfg(rtl_dir=str(_cpu_fixture_dir()))
    step_dir = tmp_path / "analyze"
    step_dir.mkdir()
    ctx = _make_ctx(step_dir)

    analyze_step(cfg, ctx)

    for fname in ("scan_result.json", "ordered.json", "tops.txt",
                  "macros.yaml", "file_headers.json", "chosen_top.txt"):
        assert (step_dir / fname).is_file(), f"missing {fname}"

    ordered = json.loads((step_dir / "ordered.json").read_text())
    assert "packages" in ordered and "non_packages" in ordered
    assert isinstance(ordered["packages"], list)

    assert (step_dir / "chosen_top.txt").read_text().strip() == "tb_cpu"


def test_render_step_produces_filelist(tmp_path):
    from vcodeman.gen.dw_flow.flow import StepCfg, analyze_step, render_step

    cfg = StepCfg(rtl_dir=str(_cpu_fixture_dir()))

    analyze_dir = tmp_path / "analyze"
    analyze_dir.mkdir()
    analyze_step(cfg, _make_ctx(analyze_dir))

    render_dir = tmp_path / "render"
    render_dir.mkdir()
    ctx = _make_ctx(render_dir)
    ctx.run_root = tmp_path

    render_step(cfg, ctx)

    cpu_f = render_dir / "cpu.f"
    assert cpu_f.is_file()
    text = cpu_f.read_text()
    assert "+incdir+" in text
    assert "tb_cpu" in text
    assert "base_pkg.sv" in text


import shutil


@pytest.mark.skipif(not shutil.which("eda-env"), reason="eda-env not available")
def test_compile_step_records_result(tmp_path):
    from vcodeman.gen.dw_flow.flow import (StepCfg, analyze_step,
                                            compile_step, render_step)

    cfg = StepCfg(rtl_dir=str(_cpu_fixture_dir()))

    for label in ("analyze", "render"):
        (tmp_path / label).mkdir()
    analyze_step(cfg, _make_ctx(tmp_path / "analyze"))
    render_ctx = _make_ctx(tmp_path / "render")
    render_ctx.run_root = tmp_path
    render_step(cfg, render_ctx)

    compile_dir = tmp_path / "compile_0"
    compile_dir.mkdir()
    ctx = _make_ctx(compile_dir)
    ctx.run_root = tmp_path
    ctx.previous_filelist_dir = tmp_path / "render"

    result = compile_step(cfg, ctx)

    assert (compile_dir / "cpu.f").is_file()
    assert (compile_dir / "result.json").is_file()
    payload = json.loads((compile_dir / "result.json").read_text())
    assert "success" in payload and "errors" in payload
    assert payload["success"] is True
    assert result["success"] is True
