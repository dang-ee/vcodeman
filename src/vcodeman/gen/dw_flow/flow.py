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


import json

from vcodeman.gen.analyzer import analyze_file
from vcodeman.gen.graph import build_order
from vcodeman.gen.macro_extractor import build_macro_report, write_macro_yaml
from vcodeman.gen.scanner import scan
from vcodeman.gen.top_detector import detect_tops


@task(cache_policy=NO_CACHE, task_run_name=step_label)
def analyze_step(cfg: StepCfg, ctx: Context) -> dict:
    """Static analysis: scan + analyze + topo + top-detect + macros.

    Outputs (in step_dir):
      scan_result.json, ordered.json, tops.txt, macros.yaml,
      file_headers.json, chosen_top.txt
    """
    step_dir = ctx.step_dir.path
    rtl_dir = Path(cfg.rtl_dir)

    scan_result = scan(rtl_dir)
    all_files = scan_result.source_files + scan_result.header_files
    infos = [analyze_file(f) for f in all_files]
    src_set = set(scan_result.source_files)
    src_infos = [fi for fi in infos if fi.path in src_set]

    ordered = build_order(src_infos)
    pkg_set = {fi.path for fi in src_infos if fi.declared_packages}
    pkg_files = [p for p in ordered if p in pkg_set]
    non_pkg = [p for p in ordered if p not in pkg_set]

    candidates = detect_tops(src_infos)
    best_top = cfg.top or (candidates[0].module_name if candidates else "")

    (step_dir / "scan_result.json").write_text(json.dumps({
        "source_files": [str(p) for p in scan_result.source_files],
        "header_files": [str(p) for p in scan_result.header_files],
        "include_dirs": [str(p) for p in scan_result.include_dirs],
    }, indent=2))

    (step_dir / "ordered.json").write_text(json.dumps({
        "packages": [str(p) for p in pkg_files],
        "non_packages": [str(p) for p in non_pkg],
    }, indent=2))

    tops_lines = ["# Top module candidates (best first)\n"]
    for c in candidates:
        marker = " <- best" if c.module_name == best_top else ""
        tops_lines.append(
            f"{c.module_name:30s}  score={c.score:.2f}  "
            f"transitive={c.transitive_instance_count}  "
            f"file={c.file_path.name}{marker}\n"
        )
    (step_dir / "tops.txt").write_text("".join(tops_lines))

    write_macro_yaml(build_macro_report(infos), step_dir / "macros.yaml")

    file_headers = {
        str(fi.path): "\n".join(fi.path.read_text(errors="replace").splitlines()[:30])
        for fi in src_infos
    }
    (step_dir / "file_headers.json").write_text(json.dumps(file_headers, indent=2))

    (step_dir / "chosen_top.txt").write_text(best_top + "\n" if best_top else "")

    return {"top": best_top, "n_files": len(src_infos)}


from vcodeman.gen.compiler import BACKENDS
from vcodeman.gen.writer import render_filelist


def _analyze_dir(ctx: Context) -> Path:
    """Locate the analyze step's directory under the run_root.

    By dw convention, ctx.run_root is the parent of all step dirs, and
    each step dir is named after its label. analyze_step's label is
    'analyze'. Tests set ctx.run_root directly; in real flow runs it's
    attached to each step's Context by main().
    """
    return Path(ctx.run_root) / "analyze"


@task(cache_policy=NO_CACHE, task_run_name=step_label)
def render_step(cfg: StepCfg, ctx: Context) -> dict:
    """Read analyze outputs, render initial filelist to step_dir/cpu.f."""
    step_dir = ctx.step_dir.path
    analyze_dir = _analyze_dir(ctx)

    scan_data = json.loads((analyze_dir / "scan_result.json").read_text())
    ordered = json.loads((analyze_dir / "ordered.json").read_text())
    chosen_top = (analyze_dir / "chosen_top.txt").read_text().strip() or None

    backend = BACKENDS[cfg.simulator]()
    top_dir = backend.top_directive(chosen_top) if chosen_top else None

    text = render_filelist(
        [Path(p) for p in scan_data["include_dirs"]],
        [Path(p) for p in ordered["packages"]],
        [Path(p) for p in ordered["non_packages"]],
        top_module=chosen_top,
        top_directive=top_dir,
        simulator=cfg.simulator,
        iterations=0,
        no_comments=False,
    )
    (step_dir / "cpu.f").write_text(text)
    return {"top": chosen_top}
