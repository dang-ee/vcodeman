"""E2E test: AI repair loop using real Claude (claude-agent-sdk, no API key needed).

Strategy:
1. Scan the cpu fixture (multi-package RISC-V-subset CPU design)
2. Generate a *deliberately broken* filelist (all files in reverse dependency
   order, +incdir+ at the end instead of the top)
3. Verify it fails compilation
4. Run repair_filelist() against real Claude
5. Verify the repaired filelist compiles cleanly
"""

import shutil
from pathlib import Path

import pytest

from vcodeman.gen.compiler import IcarusBackend
from vcodeman.gen.scanner import scan

pytestmark = [
    pytest.mark.skipif(
        not shutil.which("eda-env"),
        reason="eda-env not available",
    ),
]


def _make_broken_filelist(cpu_dir: Path) -> tuple[str, dict[Path, str]]:
    """Build a deliberately bad filelist: sources in reverse filesystem order,
    +incdir+ at the end (wrong position), packages mixed in with sources."""
    result = scan(cpu_dir)
    all_sv = result.source_files  # filesystem order (alphabetical by rglob)

    # Reverse the file order so dependencies appear after their dependents
    broken_lines = [str(p) for p in reversed(all_sv)]

    # Put +incdir+ at the END (wrong — it must come before any sources)
    if result.include_dirs:
        broken_lines.append("+incdir+" + str(result.include_dirs[0]))

    broken_content = "\n".join(broken_lines) + "\n"

    # Collect first-30-line headers for AI context
    file_headers: dict[Path, str] = {
        p: "\n".join(p.read_text(errors="replace").splitlines()[:30])
        for p in all_sv
    }
    return broken_content, file_headers


def test_broken_filelist_actually_fails(cpu_dir, tmp_path):
    """Sanity check: the broken filelist must fail compilation before we repair it."""
    broken_content, _ = _make_broken_filelist(cpu_dir)
    broken_f = tmp_path / "broken.f"
    broken_f.write_text(broken_content)

    backend = IcarusBackend()
    result = backend.compile(broken_f)
    assert not result.success, (
        "Expected broken filelist to fail compilation — "
        "if it passes, the test premise is wrong"
    )
    print(f"\n[broken] {len(result.errors)} compile errors, first: {result.errors[0].message!r}")


@pytest.mark.skip(reason="Migrated to dw flow — see Task 12")
def test_ai_repair_fixes_broken_cpu_filelist(cpu_dir, tmp_path):
    """E2E: real Claude repairs a broken CPU filelist until it compiles.

    DEPRECATED: This test was for the old ai_repair.py module.
    The repair flow is now integrated into the dw flow at gen/dw_flow/flow.py.
    Migration is tracked in Task 12.
    """
    broken_content, file_headers = _make_broken_filelist(cpu_dir)

    # Compile broken version to get real error messages
    broken_f = tmp_path / "broken.f"
    broken_f.write_text(broken_content)
    backend = IcarusBackend()
    compile_result = backend.compile(broken_f)

    assert not compile_result.success, "Broken filelist must fail first"

    print(f"\n[broken filelist]:\n{broken_content}")
    print(f"\n[broken] {len(compile_result.errors)} errors:")
    for e in compile_result.errors[:5]:
        print(f"  {e.raw}")
    print("\n[OK] AI repair succeeded - filelist compiles cleanly")


def test_vcodeman_gen_e2e_full_pipeline(cpu_dir, tmp_path):
    """E2E: full dw flow pipeline on the CPU fixture with compile check."""
    import subprocess
    import sys

    out = tmp_path / "cpu.f"
    result = subprocess.run(
        [sys.executable, "-m", "vcodeman.cli", "gen",
         str(cpu_dir), "-o", str(out), "--no-ai"],
        check=False,
    )

    assert result.returncode == 0, f"dw flow failed with return code {result.returncode}"
    assert out.exists(), f"Output filelist not created at {out}"
    assert Path(str(out) + ".tops.txt").exists(), "tops.txt sidecar not created"
    assert Path(str(out) + ".macros.yaml").exists(), "macros.yaml sidecar not created"

    tops = Path(str(out) + ".tops.txt").read_text()
    assert "tb_cpu" in tops
    print(f"\n[tops]:\n{tops}")

    import yaml
    macros = yaml.safe_load(Path(str(out) + ".macros.yaml").read_text())
    macro_names = {d["name"] for d in macros["definitions"]}
    assert "SIMULATION" in macro_names
    assert "CPU_ARCH" in macro_names
    print(f"\n[macros]: {macro_names}")
