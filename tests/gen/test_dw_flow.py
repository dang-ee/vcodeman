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


import os
import shutil
import subprocess


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


def test_repair_step_uses_run_agent_and_post_processes(tmp_path, monkeypatch):
    from vcodeman.gen.dw_flow import flow as flow_mod

    cfg = flow_mod.StepCfg(rtl_dir=str(_cpu_fixture_dir()))
    (tmp_path / "analyze").mkdir()
    flow_mod.analyze_step(cfg, _make_ctx(tmp_path / "analyze"))

    compile_dir = tmp_path / "compile_0"
    compile_dir.mkdir()
    (compile_dir / "cpu.f").write_text("/some/wrong.sv\n")
    (compile_dir / "result.json").write_text(json.dumps({
        "success": False,
        "errors": [{"file": "/some/wrong.sv", "line": 1,
                    "message": "syntax error", "raw": "..."}],
        "stderr": "",
    }))

    def fake_run_agent(pkg, *, user_prompt, agent_dir, cwd, env):
        return "```\n+incdir+/x/inc\n/x/pkg.sv\n/x/mod.sv\n```\n"

    monkeypatch.setattr(flow_mod, "run_agent", fake_run_agent)

    repair_dir = tmp_path / "repair_1"
    repair_dir.mkdir()
    ctx = _make_ctx(repair_dir)
    ctx.run_root = tmp_path
    ctx.previous_compile_dir = compile_dir

    flow_mod.repair_step(cfg, ctx)

    assert (repair_dir / "prompt.txt").is_file()
    assert "syntax error" in (repair_dir / "prompt.txt").read_text()

    cpu_f = (repair_dir / "cpu.f").read_text()
    assert "```" not in cpu_f, "markdown fence must be stripped"
    assert "+incdir+/x/inc" in cpu_f
    assert "/x/pkg.sv" in cpu_f


def _find_step_dir(run_dir: Path, label: str) -> Path | None:
    """Find a numbered step dir like '03.compile_0' by its label suffix."""
    matches = [d for d in run_dir.iterdir() if d.is_dir() and d.name.endswith(f".{label}")]
    return matches[0] if matches else None


@pytest.mark.skipif(not shutil.which("eda-env"), reason="eda-env not available")
def test_full_flow_via_dw_run_no_ai(tmp_path):
    """Layer 2: real dw subprocess, --no-ai (no Claude needed)."""
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()

    env = {
        **os.environ,
        "VCM_RTL_DIR": str(_cpu_fixture_dir()),
        "VCM_TOP": "",
        "VCM_SIMULATOR": "icarus",
        "VCM_MAX_ITER": "5",
        "VCM_USE_AI": "0",
        "DW_RUNS_DIR": str(runs_dir),
    }
    completed = subprocess.run(
        ["uv", "run", "dw", "run", str(FLOW_PY)],
        env=env, capture_output=True, text=True,
    )
    assert completed.returncode == 0, (
        f"dw run failed:\nstdout:{completed.stdout}\nstderr:{completed.stderr}"
    )

    run_dirs = list(runs_dir.iterdir())
    assert len(run_dirs) == 1, f"expected 1 run_dir, got {run_dirs}"
    run_dir = run_dirs[0]

    analyze_d = _find_step_dir(run_dir, "analyze")
    render_d = _find_step_dir(run_dir, "render")
    compile_0_d = _find_step_dir(run_dir, "compile_0")
    repair_1_d = _find_step_dir(run_dir, "repair_1")

    assert analyze_d is not None and analyze_d.is_dir(), "missing analyze step dir"
    assert render_d is not None and render_d.is_dir(), "missing render step dir"
    assert compile_0_d is not None and compile_0_d.is_dir(), "missing compile_0 step dir"
    assert repair_1_d is None, "use_ai=False must skip repair"

    final = json.loads((compile_0_d / "result.json").read_text())
    assert final["success"] is True


def test_resolve_backend_in_render_step_uses_custom_file(tmp_path, monkeypatch):
    """render_step should accept a backend specified as a file path."""
    from vcodeman.gen.dw_flow.flow import StepCfg, analyze_step, render_step

    backend_py = tmp_path / "stub_backend.py"
    backend_py.write_text("""
from vcodeman.gen.compiler import SimulatorBackend

class StubBackend(SimulatorBackend):
    name = "stub"
    def compile_cmd(self, filelist, top_module=None):
        return ["true"]  # always succeeds, ignores top
    def parse_errors(self, stdout, stderr, rc):
        return []
    def top_directive(self, module):
        return f"// -top {module}"
""")

    cfg = StepCfg(rtl_dir=str(_cpu_fixture_dir()), simulator=str(backend_py))
    (tmp_path / "analyze").mkdir()
    analyze_step(cfg, _make_ctx(tmp_path / "analyze"))

    render_dir = tmp_path / "render"
    render_dir.mkdir()
    ctx = _make_ctx(render_dir)
    ctx.run_root = tmp_path
    render_step(cfg, ctx)

    cpu_f = render_dir / "cpu.f"
    assert cpu_f.is_file()
    assert "// -top tb_cpu" in cpu_f.read_text()
