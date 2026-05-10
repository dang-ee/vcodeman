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

    analyze_ctx = ctx.for_step(label="analyze")
    analyze_step(cfg, analyze_ctx)
    analyze_dir = analyze_ctx.step_dir.path
    run_root = analyze_dir.parent

    render_ctx = ctx.for_step(label="render")
    render_ctx.run_root = run_root
    render_ctx.analyze_dir = analyze_dir
    render_step(cfg, render_ctx)

    if cfg.max_iter == 0:
        return "skipped_compile"

    compile_ctx_0 = ctx.for_step(label="compile_0")
    compile_ctx_0.run_root = run_root
    compile_ctx_0.analyze_dir = analyze_dir
    compile_ctx_0.previous_filelist_dir = render_ctx.step_dir.path
    result = compile_step(cfg, compile_ctx_0)

    if not cfg.use_ai:
        return f"no_ai (success={result['success']})"

    last_compile_dir = compile_ctx_0.step_dir.path
    for i in range(1, cfg.max_iter + 1):
        if result["success"]:
            break
        repair_ctx = ctx.for_step(label=f"repair_{i}")
        repair_ctx.run_root = run_root
        repair_ctx.analyze_dir = analyze_dir
        repair_ctx.previous_compile_dir = last_compile_dir
        repair_step(cfg, repair_ctx)

        compile_ctx = ctx.for_step(label=f"compile_{i}")
        compile_ctx.run_root = run_root
        compile_ctx.analyze_dir = analyze_dir
        compile_ctx.previous_filelist_dir = repair_ctx.step_dir.path
        result = compile_step(cfg, compile_ctx)
        last_compile_dir = compile_ctx.step_dir.path

    return f"final (success={result['success']})"


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


from dw._step_env import resolve_step_env
from dw.claude_agent.config import load_agent
from dw.claude_agent.runner import run_agent

from vcodeman.gen.compiler import resolve_backend, CompileError
from vcodeman.gen.dw_flow.repair import build_user_message, extract_filelist
from vcodeman.gen.writer import render_filelist


def _analyze_dir(ctx: Context) -> Path:
    """Locate the analyze step's directory.

    main() sets ctx.analyze_dir to the exact numbered path (e.g. 01.analyze/).
    Unit tests set ctx.run_root and fall back to run_root/analyze.
    """
    val = getattr(ctx, "analyze_dir", None)
    if isinstance(val, (str, Path)):
        return Path(val)
    return Path(ctx.run_root) / "analyze"


@task(cache_policy=NO_CACHE, task_run_name=step_label)
def render_step(cfg: StepCfg, ctx: Context) -> dict:
    """Read analyze outputs, render initial filelist to step_dir/cpu.f."""
    step_dir = ctx.step_dir.path
    analyze_dir = _analyze_dir(ctx)

    scan_data = json.loads((analyze_dir / "scan_result.json").read_text())
    ordered = json.loads((analyze_dir / "ordered.json").read_text())
    chosen_top = (analyze_dir / "chosen_top.txt").read_text().strip() or None

    backend = resolve_backend(cfg.simulator)()
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


@task(cache_policy=NO_CACHE, task_run_name=step_label)
def compile_step(cfg: StepCfg, ctx: Context) -> dict:
    """Compile the filelist from ctx.previous_filelist_dir/cpu.f.

    Records {success, errors, stderr} as result.json, copies the input
    cpu.f into step_dir for traceability.
    """
    step_dir = ctx.step_dir.path
    src_dir = Path(ctx.previous_filelist_dir)
    src_f = src_dir / "cpu.f"
    target_f = step_dir / "cpu.f"
    target_f.write_text(src_f.read_text())

    chosen_top = ""
    analyze_dir = _analyze_dir(ctx)
    chosen_top_path = analyze_dir / "chosen_top.txt"
    if chosen_top_path.is_file():
        chosen_top = chosen_top_path.read_text().strip()

    backend = resolve_backend(cfg.simulator)()
    result = backend.compile(target_f, top_module=chosen_top or None)

    payload = {
        "success": result.success,
        "errors": [
            {"file": e.file, "line": e.line, "message": e.message, "raw": e.raw}
            for e in result.errors
        ],
        "stderr": result.stderr if hasattr(result, "stderr") else "",
    }
    (step_dir / "result.json").write_text(json.dumps(payload, indent=2))
    if hasattr(result, "stderr"):
        (step_dir / "stderr.log").write_text(result.stderr)

    return {"success": result.success, "n_errors": len(result.errors)}


@task(cache_policy=NO_CACHE, task_run_name=step_label)
def repair_step(cfg: StepCfg, ctx: Context) -> dict:
    """Call repair_filelist agent on the previous compile's failure.

    Reads ctx.previous_compile_dir/{cpu.f, result.json} +
    analyze/file_headers.json, builds a prompt, invokes run_agent,
    post-processes via extract_filelist, and writes corrected cpu.f.
    """
    step_dir = ctx.step_dir.path
    prev = Path(ctx.previous_compile_dir)
    analyze_dir = _analyze_dir(ctx)

    current_filelist = (prev / "cpu.f").read_text()
    result_payload = json.loads((prev / "result.json").read_text())
    errors = [
        CompileError(file=e["file"], line=e["line"],
                     message=e["message"], raw=e["raw"])
        for e in result_payload["errors"]
    ]
    headers_raw = json.loads((analyze_dir / "file_headers.json").read_text())
    file_headers = {Path(k): v for k, v in headers_raw.items()}

    user_message = build_user_message(current_filelist, errors, file_headers)
    (step_dir / "prompt.txt").write_text(user_message)

    pkg = load_agent("agents/repair_filelist", manifest_dir=ctx.manifest_dir)
    se = resolve_step_env(ctx, step=step_dir.name, workdir=str(step_dir))
    raw = run_agent(
        pkg,
        user_prompt=user_message,
        agent_dir=step_dir,
        cwd=step_dir,
        env=se.env,
    )
    corrected = extract_filelist(raw)
    (step_dir / "cpu.f").write_text(corrected)
    return {"step_dir": str(step_dir)}
