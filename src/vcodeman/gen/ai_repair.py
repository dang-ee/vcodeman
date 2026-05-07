import asyncio
import re
from pathlib import Path

from claude_agent_sdk import ClaudeAgentOptions, query
from claude_agent_sdk.types import AssistantMessage, TextBlock

from vcodeman.gen.compiler import CompileError

_SYSTEM_PROMPT = """\
You are an expert SystemVerilog compilation engineer. You receive a Verilog-XL \
filelist (.f format) that fails to compile and a list of compiler errors. \
You must return a corrected filelist with:
- +incdir+ directives first (before any source files)
- Package files before any files that import them
- Submodule files before files that instantiate them
- -top directive or // -top comment at the end if present

CRITICAL OUTPUT FORMAT RULES:
1. Output ONLY the corrected filelist. Nothing else.
2. NO markdown code fences (no ``` or ```systemverilog).
3. NO explanation text before or after the filelist.
4. NO introductory phrases like "Here is..." or "The corrected filelist:".
5. The very first character of your response must be the first character of the filelist.
6. Use the exact absolute file paths from the input — do not change or shorten them."""


class AIRepairError(Exception):
    pass


def _extract_filelist(raw: str) -> str:
    """Strip markdown fences and prose from a Claude response, leaving only .f content."""
    lines = raw.splitlines()

    # If response is wrapped in a code fence, extract just the inner content
    if lines and lines[0].strip().startswith("```"):
        inner: list[str] = []
        for line in lines[1:]:
            if line.strip().startswith("```"):
                break
            inner.append(line)
        if inner:
            lines = inner

    # Keep only lines that look like valid .f file content:
    # - absolute paths (start with /)
    # - +incdir+, +define+, -f, -v, -y, -top directives
    # - // comments
    # - blank lines
    # Discard: prose sentences, markdown, etc.
    _VALID_LINE = re.compile(
        r"""^\s*(?:
            /           # absolute paths or // comments
          | \+incdir\+  # incdir directive
          | \+define\+  # define directive
          | -(?:f|v|y|top|s)(?:\s|$)  # common flags (may be at end of line)
          | //          # comment
          |$            # blank line
        )""",
        re.VERBOSE,
    )
    kept = [ln for ln in lines if _VALID_LINE.match(ln)]
    return "\n".join(kept) + "\n" if kept else raw


async def _call_claude(user_message: str, model: str | None) -> str:
    options = ClaudeAgentOptions(
        system_prompt=_SYSTEM_PROMPT,
        allowed_tools=[],
        permission_mode="bypassPermissions",
        model=model,
    )
    parts: list[str] = []
    async for message in query(prompt=user_message, options=options):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    parts.append(block.text)
    if not parts:
        raise AIRepairError("No text response received from Claude")
    return "".join(parts)


def repair_filelist(
    current_filelist: str,
    errors: list[CompileError],
    file_headers: dict[Path, str],
    model: str | None = None,
) -> str:
    """Call Claude (via Claude Agent SDK) once to get a corrected filelist.

    Uses the local Claude Code session — no API key required.

    Args:
        current_filelist: current .f file content.
        errors: structured compiler errors from this iteration.
        file_headers: mapping of file path -> first 30 lines of source.
        model: Claude model override (None = use Claude Code's configured model).

    Returns:
        Corrected .f file content as a string.
    """
    error_block = "\n".join(
        f"  {e.file}:{e.line}: {e.message}" if e.file else f"  {e.message}"
        for e in errors
    )
    headers_block = "\n\n".join(
        f"=== {path.name} ===\n{content}"
        for path, content in file_headers.items()
    )
    user_message = (
        f"Compilation failed with the following errors:\n{error_block}\n\n"
        f"Current filelist:\n{current_filelist}\n\n"
        f"File headers (first 30 lines each):\n{headers_block}"
    )
    raw = asyncio.run(_call_claude(user_message, model))
    return _extract_filelist(raw)
