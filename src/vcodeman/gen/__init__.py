"""RTL filelist auto-generator."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from vcodeman.gen.analyzer import analyze_file
from vcodeman.gen.compiler import BACKENDS, CompileResult, SimulatorBackend
from vcodeman.gen.graph import build_order
from vcodeman.gen.macro_extractor import build_macro_report, write_macro_yaml
from vcodeman.gen.scanner import scan
from vcodeman.gen.top_detector import detect_tops
from vcodeman.gen.writer import render_filelist


@dataclass
class GenResult:
    filelist_path: Path
    tops_path: Path
    macros_path: Path
    top_module: str | None
    iterations: int
    success: bool
    final_errors: list = field(default_factory=list)


def generate(
    rtl_dir: Path,
    output: Path,
    top: str | None = None,
    simulator: str = "icarus",
    max_iter: int = 5,
    do_compile: bool = True,
    use_ai: bool = True,
    no_comments: bool = False,
) -> GenResult:
    tops_path = Path(str(output) + ".tops.txt")
    macros_path = Path(str(output) + ".macros.yaml")

    # 1. Scan
    scan_result = scan(rtl_dir)
    all_files = scan_result.source_files + scan_result.header_files

    # 2. Analyze
    infos = [analyze_file(f) for f in all_files]
    src_infos = [fi for fi in infos if fi.path in set(scan_result.source_files)]

    # 3. Build order
    ordered = build_order(src_infos)
    pkg_path_set = {fi.path for fi in src_infos if fi.declared_packages}
    pkg_files = [p for p in ordered if p in pkg_path_set]
    non_pkg_ordered = [p for p in ordered if p not in pkg_path_set]

    # 4. Detect tops
    candidates = detect_tops(src_infos)
    best_top = top or (candidates[0].module_name if candidates else None)

    # Write tops sidecar
    tops_lines = ["# Top module candidates (best first)\n"]
    for c in candidates:
        marker = " <- best" if c.module_name == best_top else ""
        tops_lines.append(
            f"{c.module_name:30s}  score={c.score:.2f}  "
            f"transitive={c.transitive_instance_count}  "
            f"file={c.file_path.name}{marker}\n"
        )
    tops_path.write_text("".join(tops_lines))

    # 5. Macro report
    write_macro_yaml(build_macro_report(infos), macros_path)

    # 6. Determine backend top_directive
    backend: SimulatorBackend = BACKENDS[simulator]()
    top_dir = backend.top_directive(best_top) if best_top else None

    # 7. Render initial filelist
    def _render(iterations: int) -> str:
        return render_filelist(
            scan_result.include_dirs,
            pkg_files,
            non_pkg_ordered,
            top_module=best_top,
            top_directive=top_dir,
            simulator=simulator,
            iterations=iterations,
            no_comments=no_comments,
        )

    filelist_text = _render(0)
    output.write_text(filelist_text)

    if not do_compile:
        return GenResult(filelist_path=output, tops_path=tops_path,
                         macros_path=macros_path, top_module=best_top,
                         iterations=0, success=True)

    # 8. Compile + AI repair loop
    result: CompileResult = backend.compile(output, top_module=best_top)
    if result.success:
        return GenResult(filelist_path=output, tops_path=tops_path,
                         macros_path=macros_path, top_module=best_top,
                         iterations=0, success=True)

    if not use_ai:
        return GenResult(filelist_path=output, tops_path=tops_path,
                         macros_path=macros_path, top_module=best_top,
                         iterations=0, success=False,
                         final_errors=result.errors)

    file_headers: dict = {
        fi.path: "\n".join(fi.path.read_text(errors="replace").splitlines()[:30])
        for fi in src_infos
    }

    from vcodeman.gen.ai_repair import repair_filelist
    for iteration in range(1, max_iter + 1):
        corrected = repair_filelist(
            current_filelist=output.read_text(),
            errors=result.errors,
            file_headers=file_headers,
        )
        output.write_text(corrected)
        result = backend.compile(output, top_module=best_top)
        if result.success:
            return GenResult(filelist_path=output, tops_path=tops_path,
                             macros_path=macros_path, top_module=best_top,
                             iterations=iteration, success=True)

    return GenResult(filelist_path=output, tops_path=tops_path,
                     macros_path=macros_path, top_module=best_top,
                     iterations=max_iter, success=False,
                     final_errors=result.errors)
