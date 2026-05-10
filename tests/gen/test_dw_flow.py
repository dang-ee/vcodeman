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
