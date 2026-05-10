# vcodeman gen — dw flow Refactor Design

**Date:** 2026-05-10
**Status:** Draft, awaiting user review

## Goal

Reimplement `vcodeman gen` on top of [dw (design-workflow)](https://github.com/.../design-workflow) so that:

1. The AI repair loop is no longer driven by a hardcoded Python loop calling `claude_agent_sdk` directly. Instead it uses dw's `run_agent` infrastructure.
2. System prompts, model selection, and budget caps move out of source code into a dw agent package (`agents/repair_filelist/`).
3. Each step (static analysis, render, compile, every repair iteration) leaves a permanent on-disk artifact under a `runs/<run_id>/` directory, enabling per-step re-execution and post-mortem debugging via `dw step` and `dw resume`.
4. The user-facing CLI (`vcodeman gen <dir> ...`) is unchanged.

## Non-Goals

- Replacing the static analysis modules (scanner, analyzer, graph, top_detector, macro_extractor, writer). They remain pure Python libraries; only the orchestration and AI invocation layers change.
- Adding new simulator backends, top-detection heuristics, or repair strategies.
- Changing the user-visible CLI surface.
- Adding `--runs-dir` CLI option to dw itself (only the `DW_RUNS_DIR` env var is added — CLI option can come later).

## Architecture

```
vcodeman gen <RTL_DIR>  --output ... --simulator ... --max-iter ... --runs-dir ./runs
        │
        ▼  subprocess.run(["dw", "run", flow.py], env={VCM_*, DW_RUNS_DIR})
        │
   ┌────┴───────────────────────────────────────────────────────┐
   │ flow.py  (@dw.flow main)                                   │
   │                                                            │
   │  analyze_step  →  render_step  →  compile_0                │
   │       │              │               │                     │
   │       ▼              ▼               ▼                     │
   │  for i in 1..max_iter:                                     │
   │     if result.success: break                               │
   │     repair_i  →  compile_i                                 │
   │                                                            │
   └────────────────────────────────────────────────────────────┘
        │
        ▼  flow returns; runs/<run_id>/ has all step artifacts
   vcodeman wrapper finds last compile_N, copies cpu.f + sidecars
   to user --output path, prints success / pointer to run_dir.
```

**Responsibility split**

| Layer | Owns |
|-------|------|
| `vcodeman` CLI wrapper | Parse args, build env, invoke `dw run`, recover artifacts to `--output`, print result. |
| `flow.py` | Orchestrate steps. Knows nothing about the user's `--output` path; writes everything under run_dir. |
| Static-analysis modules (scanner/analyzer/etc.) | Unchanged Python libraries called from `analyze_step`. |
| `agents/repair_filelist/` | System prompt, model selection (or none), turn/budget limits — no Python code. |
| dw infrastructure | `run_agent`, transcript capture, run_dir creation, step re-execution. |

## Step Structure

### analyze_step

**Inputs (env):** `VCM_RTL_DIR`, `VCM_TOP` (optional)
**Outputs (in step_dir):**
- `scan_result.json` — `{source_files: [...], header_files: [...], include_dirs: [...]}`
- `ordered.json` — topologically sorted source files: `{packages: [...], non_packages: [...]}`
- `tops.txt` — top candidates with scores (sidecar format)
- `macros.yaml` — macro report
- `file_headers.json` — `{path: first_30_lines}` for AI repair context
- `chosen_top.txt` — single line: best top module name (or empty)

**Body:** calls `scan()`, `analyze_file()` per file, `build_order()`, `detect_tops()`, `build_macro_report()`, `write_macro_yaml()`. All current static-analysis logic, just dumping intermediate state to disk.

### render_step

**Inputs:** `analyze_step` outputs (read from `run_dir/analyze/`)
**Outputs (in step_dir):** `cpu.f` — initial filelist text (renderer applied to ordered packages + non-packages + include_dirs + chosen_top)

### compile_N (N = 0, 1, 2, ...)

**Inputs:** previous `cpu.f` (from render_step for N=0, or from `repair_N` for N>0)
**Outputs (in step_dir):**
- `cpu.f` — the filelist that was compiled (copy of input for traceability)
- `result.json` — `{success: bool, errors: [{file, line, message, raw}, ...], stderr: str}`

**Body:** invoke the configured `SimulatorBackend` (default `IcarusBackend`) on the input filelist; serialize the `CompileResult` to JSON.

### repair_N (N = 1, 2, ...)

**Inputs:** previous `compile_{N-1}/cpu.f` and `result.json`, plus `analyze/file_headers.json`
**Outputs (in step_dir):**
- `prompt.txt` — the assembled user message (compiler errors + current filelist + file headers) for debugging
- `transcript.jsonl` — automatically captured by dw `run_agent`
- `cpu.f` — Claude's response after `_extract_filelist()` post-processing

**Body:**
```python
pkg = load_agent("repair_filelist", manifest_dir=ctx.manifest_dir)
se = resolve_step_env(ctx, step=step_dir.name, workdir=str(step_dir))
raw = run_agent(pkg, user_prompt=user_message, agent_dir=step_dir, cwd=step_dir, env=se.env)
corrected = _extract_filelist(raw)  # markdown/prose stripping stays in code
(step_dir / "cpu.f").write_text(corrected)
```

### Flow body

```python
@dw.flow
def main(ctx: dw.Context) -> str:
    cfg = StepCfg(
        rtl_dir=os.environ["VCM_RTL_DIR"],
        top=os.environ.get("VCM_TOP") or None,
        simulator=os.environ.get("VCM_SIMULATOR", "icarus"),
        max_iter=int(os.environ.get("VCM_MAX_ITER", "5")),
        use_ai=os.environ.get("VCM_USE_AI", "1") == "1",
    )

    analyze_step(cfg, ctx.for_step(label="analyze"))
    render_step(cfg, ctx.for_step(label="render"))

    if cfg.max_iter == 0:
        # --no-compile: stop after render. No compile_*, no repair_*.
        return "skipped_compile"

    result = compile_step(cfg, ctx.for_step(label="compile_0"))
    if not cfg.use_ai:
        # --no-ai: compile once and stop, regardless of success.
        return f"no_ai (success={result['success']})"

    for i in range(1, cfg.max_iter + 1):
        if result["success"]:
            break
        repair_step(cfg, ctx.for_step(label=f"repair_{i}"))
        result = compile_step(cfg, ctx.for_step(label=f"compile_{i}"))

    return f"final (success={result['success']})"
```

`--no-compile` and `--no-ai` produce different run_dir contents:

| Mode | run_dir contains |
|------|------------------|
| Default | `analyze/`, `render/`, `compile_0/`, optionally `repair_*/`, `compile_*/` |
| `--no-ai` | `analyze/`, `render/`, `compile_0/` only |
| `--no-compile` | `analyze/`, `render/` only |

The wrapper's artifact-recovery logic must handle each:
- `--no-compile` → copy `render/cpu.f` to `--output`; success = true (no compile attempted).
- `--no-ai` → copy `compile_0/cpu.f` to `--output`; success = `compile_0/result.json["success"]`.
- Default → copy last `compile_N/cpu.f`; success per its `result.json`.

## Agent Package: `agents/repair_filelist/`

```
agents/repair_filelist/
  CLAUDE.md           # system prompt (current _SYSTEM_PROMPT moved here)
  settings.json       # permissions only (no model key → Claude Code's active model)
  dw.toml             # max_turns=1, max_budget_usd=0.10
  agent.toml          # name + description for `dw list`
```

### `CLAUDE.md`

The current `_SYSTEM_PROMPT` from `src/vcodeman/gen/ai_repair.py` (lines 10–25), unchanged in content, formatted as markdown.

### `settings.json`

```json
{
  "permissions": {
    "defaultMode": "bypassPermissions"
  }
}
```

No `model` key. Claude Code's active model (whatever the user has via `/model`) is used. Users who want to pin a specific model add `"model": "claude-sonnet-4-6"`.

### `dw.toml`

```toml
max_turns = 1
max_budget_usd = 0.10
```

`max_turns = 1` matches current behavior (one shot per iteration). `max_budget_usd` is a new safety guard — if a single repair attempt exceeds $0.10, dw aborts. Selected as ~10x current expected per-call cost.

### `agent.toml`

```toml
name = "repair_filelist"
description = "Reorder a SystemVerilog filelist (.f) so it compiles cleanly."
```

Cosmetic — used by `dw list`. Does not affect runtime.

## CLI Wrapper

`src/vcodeman/cli.py:cmd_gen()` becomes a thin wrapper around `dw run`:

```python
def cmd_gen(rtl_dir, output, top, simulator, max_iter, runs_dir,
            no_compile, no_ai):
    flow_py = Path(__file__).parent / "gen" / "dw_flow" / "flow.py"
    runs_dir = Path(runs_dir).resolve()
    runs_dir.mkdir(parents=True, exist_ok=True)

    env = {
        **os.environ,
        "VCM_RTL_DIR": str(Path(rtl_dir).resolve()),
        "VCM_TOP": top or "",
        "VCM_SIMULATOR": simulator,
        "VCM_MAX_ITER": "0" if no_compile else str(max_iter),
        "VCM_USE_AI": "0" if no_ai else "1",
        "DW_RUNS_DIR": str(runs_dir),
    }
    completed = subprocess.run(["dw", "run", str(flow_py)], env=env, check=False)

    # Find the run_dir that was just created (most recent under runs_dir).
    run_dir = max(runs_dir.iterdir(), key=lambda p: p.stat().st_mtime)
    final_compile = _find_last_compile_dir(run_dir)
    final = json.loads((final_compile / "result.json").read_text())

    # Recover artifacts to user-visible paths.
    shutil.copy(final_compile / "cpu.f", output)
    shutil.copy(run_dir / "analyze" / "tops.txt", f"{output}.tops.txt")
    shutil.copy(run_dir / "analyze" / "macros.yaml", f"{output}.macros.yaml")

    if final["success"]:
        click.echo(f"Generated: {output}  (debug: {run_dir})")
    else:
        click.secho(f"Compile still failing after {max_iter} iterations.",
                    fg="red", err=True)
        click.echo(f"  resume: dw resume {run_dir}", err=True)
        sys.exit(1)
```

### CLI options

| Option | Default | Maps to |
|--------|---------|---------|
| `<RTL_DIR>` (positional) | required | `VCM_RTL_DIR` |
| `-o, --output PATH` | `./out.f` | (wrapper-only, not passed to flow) |
| `-t, --top TEXT` | `""` (auto-detect) | `VCM_TOP` |
| `--simulator TEXT` | `icarus` | `VCM_SIMULATOR` |
| `--max-iter INT` | `5` | `VCM_MAX_ITER` |
| `--runs-dir PATH` | `./runs` | `DW_RUNS_DIR` |
| `--no-compile` | off | sets `VCM_MAX_ITER=0`, `VCM_USE_AI=0` |
| `--no-ai` | off | `VCM_USE_AI=0` (compile once, no repair) |

## dw Side Change

`src/dw/cli.py:_runs_root()` modified to honor `DW_RUNS_DIR`:

```python
def _runs_root(toml_path: Path) -> Path:
    env = os.environ.get("DW_RUNS_DIR")
    if env:
        return Path(env).expanduser().resolve()
    return toml_path.resolve().parent / "runs"
```

When `DW_RUNS_DIR` is set, dw creates the run_dir under it; otherwise the current behavior (next to flow/toml) is preserved. Backwards compatible.

A `--runs-dir` CLI option can be added later but is not required for this refactor.

## Run Directory Layout

```
./runs/<timestamp>-<id>/
├── analyze/
│   ├── scan_result.json
│   ├── ordered.json
│   ├── tops.txt
│   ├── macros.yaml
│   ├── file_headers.json
│   └── chosen_top.txt
├── render/
│   └── cpu.f                  # initial filelist
├── compile_0/
│   ├── cpu.f                  # input filelist (= render/cpu.f)
│   ├── result.json            # {success, errors, stderr}
│   └── stderr.log
├── repair_1/
│   ├── prompt.txt             # assembled user message
│   ├── transcript.jsonl       # dw-captured Claude conversation
│   └── cpu.f                  # post-_extract_filelist
├── compile_1/
│   ├── cpu.f                  # = repair_1/cpu.f
│   └── result.json
├── repair_2/  ...
└── compile_N/                 # last one — wrapper reads result.json from here
    └── result.json            # success=true → wrapper copies cpu.f to --output
```

## Testing Strategy

Three layers, in increasing fidelity:

### Layer 1 — Step unit tests

`tests/gen/test_dw_flow.py` (new). Each step function (`analyze_step`, `render_step`, `compile_step`, `repair_step`) called directly with a fabricated step_dir + minimal Context; assertions on the files written.

For `repair_step`, patch `dw.claude_agent.runner.run_agent` to return a canned response; verify `_extract_filelist` is applied and `cpu.f` is written.

### Layer 2 — Flow integration

Run `dw run flow.py` as a subprocess against a tmp `DW_RUNS_DIR`, with `run_agent` patched via a conftest fixture. Verify the full `analyze/render/compile_0/repair_*/compile_*/` directory tree is produced and the final compile succeeds (using a known-good filelist response from the mock).

### Layer 3 — End-to-end with real Claude

The current `tests/gen/test_e2e_ai_repair.py::test_ai_repair_fixes_broken_cpu_filelist` adapted to call `vcodeman gen` directly (or `dw run` with the real flow). Skipped when `eda-env` or `claude` CLI are unavailable. Same CPU fixture, same broken-filelist construction.

### Tests removed

| Test | Reason |
|------|--------|
| `test_ai_repair.py::test_repair_returns_corrected_filelist` | `repair_filelist()` function deleted. |
| `test_ai_repair.py::test_repair_prompt_contains_errors` | Same. |
| `test_ai_repair.py::test_repair_raises_when_no_text_returned` | Same; equivalent coverage now in `test_dw_flow.py` layer-1 `repair_step` test. |

### Tests retained verbatim

- All `_extract_filelist` unit tests in `test_ai_repair.py` (10 tests). The post-processor stays in code; tests stay.
- All static-analysis module tests (scanner, analyzer, graph, top_detector, macro_extractor, writer, compiler).

## Migration Plan

1. Add `DW_RUNS_DIR` support to dw (`src/dw/cli.py`). Verify with a unit test in the dw repo.
2. Create `agents/repair_filelist/` directory with `CLAUDE.md`, `settings.json`, `dw.toml`, `agent.toml`.
3. Create `src/vcodeman/gen/dw_flow/flow.py` with the four step functions and `@dw.flow main`. Move `_extract_filelist` and helper `build_user_message` into a new `src/vcodeman/gen/dw_flow/repair.py` module.
4. Rewrite `src/vcodeman/cli.py:cmd_gen` to invoke `dw run` and recover artifacts.
5. Delete `src/vcodeman/gen/ai_repair.py`. Delete `src/vcodeman/gen/__init__.py:generate()` (the orchestrator) and `GenResult` dataclass — wrapper now does this work.
6. Move/delete tests per the table above.
7. Verify `tests/gen/test_e2e_ai_repair.py` (Layer 3) still passes against real Claude on the CPU fixture.

## Risks & Open Questions

- **dw subprocess overhead.** Each `vcodeman gen` invocation spawns a `dw run` subprocess. For interactive use this is fine (~1s startup). If integration tests run hundreds of these, suite time grows. Mitigation: Layer 2 tests can call `dw.flow` Python API directly if it exposes one, bypassing subprocess.
- **`run_agent` API stability.** dw's `run_agent` signature is taken from reference workflows; if dw changes the contract, our `repair_step` breaks. Mitigation: pin dw version in `pyproject.toml` until dw declares 1.0.
- **Transcript file location.** dw is expected to write `transcript.jsonl` under `agent_dir` (the step_dir). If dw writes it somewhere else, our debugging story changes. Verify against reference flows during implementation.
- **`DW_RUNS_DIR` env var name.** Could conflict with future dw CLI option naming. Acceptable risk — env var is internal to vcodeman→dw handoff.

## Test Plan (manual verification)

After implementation:

1. `vcodeman gen tests/gen/fixtures/cpu/ --output /tmp/cpu.f` — passes, produces `/tmp/cpu.f` + sidecars, `./runs/<id>/` exists with all step dirs.
2. Inspect `./runs/<id>/repair_1/transcript.jsonl` — should contain Claude's prompt and response.
3. `dw step compile_0 ./runs/<id>` — re-runs only the initial compile.
4. `dw resume ./runs/<id>` — picks up from where it left off.
5. Edit `agents/repair_filelist/CLAUDE.md` (e.g., add a new rule), re-run `vcodeman gen` — new behavior takes effect without code changes.
