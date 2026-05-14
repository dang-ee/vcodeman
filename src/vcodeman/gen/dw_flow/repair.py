"""Helpers used by repair_step: response post-processing and prompt assembly.

The system prompt itself lives in agents/repair_filelist/CLAUDE.md.
This module only handles the deterministic Python plumbing: turning
compiler errors + file headers into a user message, and stripping
markdown/prose from the model's response.
"""
from __future__ import annotations

import re
from pathlib import Path

from vcodeman.gen.compiler import CompileError


class AIRepairError(Exception):
    pass


# Lines that look like valid .f file content: absolute paths, directives,
# // comments, or blank lines. Anything else (prose, markdown, etc.) is dropped.
_VALID_LINE = re.compile(
    r"""^\s*(?:
        /                        # absolute paths or // comments
      | \+incdir\+               # incdir directive
      | \+define\+               # define directive
      | -(?:f|v|y|top|s)(?:\s|$) # common flags (may be at end of line)
      | //                       # comment
      |$                         # blank line
    )""",
    re.VERBOSE,
)


def extract_filelist(raw: str) -> str:
    """Strip markdown fences and prose from a Claude response.

    Raises:
        AIRepairError: when no recognizable filelist content remains.
    """
    lines = raw.splitlines()

    if lines and lines[0].strip().startswith("```"):
        inner: list[str] = []
        for line in lines[1:]:
            if line.strip().startswith("```"):
                break
            inner.append(line)
        lines = inner

    kept = [ln for ln in lines if _VALID_LINE.match(ln)]

    has_content = any(ln.strip() and not ln.lstrip().startswith("//") for ln in kept)
    if not has_content:
        raise AIRepairError(
            "Claude response contained no recognizable filelist content. "
            f"Raw response:\n{raw[:500]}"
        )

    return "\n".join(kept) + "\n"


def build_user_message(
    current_filelist: str,
    errors: list[CompileError],
    file_headers: dict[Path, str],
) -> str:
    """Assemble the prompt body sent to the repair_filelist agent."""
    error_block = "\n".join(
        f"  {e.file}:{e.line}: {e.message}" if e.file else f"  {e.message}"
        for e in errors
    )
    headers_block = "\n\n".join(
        f"=== {path.name} ===\n{content}"
        for path, content in file_headers.items()
    )
    return (
        f"Compilation failed with the following errors:\n{error_block}\n\n"
        f"File headers (first 30 lines each):\n{headers_block}\n\n"
        f"Current filelist:\n{current_filelist}"
    )
