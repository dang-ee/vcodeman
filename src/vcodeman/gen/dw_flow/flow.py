"""dw flow for vcodeman gen.

Steps:
  analyze   — scan + analyze + topo-sort + top-detect + macro-extract
  render    — produce initial filelist
  compile_N — invoke simulator backend; record success/errors
  repair_N  — call repair_filelist agent; post-process response

The compile/repair pair iterates while result.success is false, up to
cfg.max_iter. --no-compile (max_iter=0) stops after render.
--no-ai (use_ai=false) stops after compile_0.
"""
from __future__ import annotations

import os
from pathlib import Path

from prefect import task
from prefect.cache_policies import NO_CACHE
from pydantic_settings import BaseSettings, SettingsConfigDict
from taskpipe.context import Context

import dw
from dw._task_run_name import step_label


class StepCfg(BaseSettings):
    model_config = SettingsConfigDict(extra="forbid")
    rtl_dir: str
    top: str | None = None
    simulator: str = "icarus"
    max_iter: int = 5
    use_ai: bool = True


@dw.flow
def main(ctx: dw.Context) -> str:
    cfg = StepCfg(
        rtl_dir=os.environ["VCM_RTL_DIR"],
        top=os.environ.get("VCM_TOP") or None,
        simulator=os.environ.get("VCM_SIMULATOR", "icarus"),
        max_iter=int(os.environ.get("VCM_MAX_ITER", "5")),
        use_ai=os.environ.get("VCM_USE_AI", "1") == "1",
    )
    return f"cfg={cfg.model_dump()}"
