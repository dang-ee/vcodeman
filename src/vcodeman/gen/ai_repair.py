from pathlib import Path

import anthropic

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


def repair_filelist(
    client: anthropic.Anthropic,
    current_filelist: str,
    errors: list[CompileError],
    file_headers: dict[Path, str],
    model: str = "claude-sonnet-4-6",
) -> str:
    """Call Claude API once to get a corrected filelist.

    Args:
        client: Anthropic client instance.
        current_filelist: current .f file content.
        errors: structured compiler errors from this iteration.
        file_headers: mapping of file path -> first 30 lines of source.
        model: Claude model to use.

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

    response = client.messages.create(
        model=model,
        max_tokens=4096,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )
    first_block = response.content[0]
    if hasattr(first_block, 'text'):
        return first_block.text  # type: ignore[attr-defined]
    raise AIRepairError(f"Unexpected response type: {type(first_block)}")
