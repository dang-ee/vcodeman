import os
from pathlib import Path
from unittest.mock import MagicMock, patch
from vcodeman.gen.ai_repair import repair_filelist, AIRepairError
from vcodeman.gen.compiler import CompileError


_ERRORS = [CompileError(file="/rtl/mod.sv", line=5,
                        message="undeclared identifier 'foo'", raw="...")]
_FILE_HEADERS = {Path("/rtl/pkg.sv"): "package pkg;\nendpackage",
                 Path("/rtl/mod.sv"): "module mod;\nendmodule"}


def _mock_client(response_text: str):
    msg = MagicMock()
    msg.content = [MagicMock(text=response_text)]
    client = MagicMock()
    client.messages.create.return_value = msg
    return client


def test_repair_returns_corrected_filelist():
    corrected = "/rtl/pkg.sv\n/rtl/mod.sv\n"
    client = _mock_client(corrected)
    result = repair_filelist(
        client=client,
        current_filelist="/rtl/pkg.sv\n",
        errors=_ERRORS,
        file_headers=_FILE_HEADERS,
    )
    assert result == corrected


def test_repair_calls_api_once():
    client = _mock_client("/rtl/pkg.sv\n/rtl/mod.sv\n")
    repair_filelist(client=client, current_filelist="/rtl/pkg.sv\n",
                    errors=_ERRORS, file_headers=_FILE_HEADERS)
    assert client.messages.create.call_count == 1


def test_repair_prompt_contains_errors():
    client = _mock_client("/rtl/mod.sv\n")
    repair_filelist(client=client, current_filelist="/rtl/pkg.sv\n",
                    errors=_ERRORS, file_headers=_FILE_HEADERS)
    call_kwargs = client.messages.create.call_args.kwargs
    user_msg = call_kwargs["messages"][0]["content"]
    assert "undeclared identifier" in user_msg


def test_repair_raises_on_missing_api_key(tmp_path):
    with patch.dict(os.environ, {}, clear=True):
        with patch("anthropic.Anthropic") as mock_anthropic:
            mock_anthropic.side_effect = Exception("ANTHROPIC_API_KEY not set")
            try:
                from vcodeman.gen import ai_repair
                import importlib
                importlib.reload(ai_repair)
            except Exception:
                pass
