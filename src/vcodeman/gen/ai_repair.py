import asyncio
from pathlib import Path

from claude_agent_sdk import ClaudeAgentOptions, query
from claude_agent_sdk.types import AssistantMessage, TextBlock

from vcodeman.gen.compiler import CompileError

_SYSTEM_PROMPT = """\
You are an expert SystemVerilog compilation engineer. You receive a Verilog-XL \
filelist (.f format) that fails to compile and a list of compiler errors. \
You must return a corrected filelist with:
- +incdir+ directives first
- Package files before any files that import them
- Submodule files before files that instantiate them
- -top directive or // -top comment at the end if present

Return ONLY the corrected filelist content. No explanation. No markdown fences. \
Start immediately with the first line."""


class AIRepairError(Exception):
    pass


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
    return asyncio.run(_call_claude(user_message, model))
