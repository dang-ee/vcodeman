from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from vcodeman.gen.ai_repair import AIRepairError, repair_filelist
from vcodeman.gen.compiler import CompileError

_ERRORS = [CompileError(file="/rtl/mod.sv", line=5,
                        message="undeclared identifier 'foo'", raw="...")]
_FILE_HEADERS = {Path("/rtl/pkg.sv"): "package pkg;\nendpackage",
                 Path("/rtl/mod.sv"): "module mod;\nendmodule"}


def _make_mock_query(response_text: str):
    """Return an async generator that yields one AssistantMessage with response_text."""
    from claude_agent_sdk.types import AssistantMessage, TextBlock

    async def _mock_query(*, prompt, options=None, **kwargs):
        yield AssistantMessage(content=[TextBlock(text=response_text)], model="mock")

    return _mock_query


def test_repair_returns_corrected_filelist():
    corrected = "/rtl/pkg.sv\n/rtl/mod.sv\n"
    with patch("vcodeman.gen.ai_repair.query", _make_mock_query(corrected)):
        result = repair_filelist(
            current_filelist="/rtl/pkg.sv\n",
            errors=_ERRORS,
            file_headers=_FILE_HEADERS,
        )
    assert result == corrected


def test_repair_prompt_contains_errors():
    captured: list[str] = []

    async def _capturing_query(*, prompt, options=None, **kwargs):
        from claude_agent_sdk.types import AssistantMessage, TextBlock
        captured.append(prompt)
        yield AssistantMessage(content=[TextBlock(text="/rtl/mod.sv\n")], model="mock")

    with patch("vcodeman.gen.ai_repair.query", _capturing_query):
        repair_filelist(
            current_filelist="/rtl/pkg.sv\n",
            errors=_ERRORS,
            file_headers=_FILE_HEADERS,
        )
    assert "undeclared identifier" in captured[0]


def test_repair_raises_when_no_text_returned():
    async def _empty_query(*, prompt, options=None, **kwargs):
        from claude_agent_sdk.types import ResultMessage
        yield ResultMessage(
            subtype="success", duration_ms=0, duration_api_ms=0,
            is_error=False, num_turns=1, session_id="x", stop_reason="end_turn",
        )

    with patch("vcodeman.gen.ai_repair.query", _empty_query):
        with pytest.raises(AIRepairError):
            repair_filelist(
                current_filelist="/rtl/pkg.sv\n",
                errors=_ERRORS,
                file_headers=_FILE_HEADERS,
            )


def test_ai_repair_module_importable():
    from vcodeman.gen.ai_repair import AIRepairError, repair_filelist
    assert callable(repair_filelist)
    assert issubclass(AIRepairError, Exception)
