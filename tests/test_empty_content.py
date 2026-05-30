"""Regressionstest: leerer/None-Content der Provider -> APIResponse(ERROR) statt Crash.

Hintergrund (v0.9.0): OpenRouter-Modell `tencent/hy3-preview` lieferte HTTP 200
mit `choices[0].message.content == None`. Das alte `len(content)` warf
`object of type 'NoneType' has no len()` und wurde nur vom generischen except
als "unerwarteter Fehler" gefangen. Erwartet wird stattdessen eine klare
APIResponse(status=ERROR) mit finish_reason in der Meldung.

Lauf (ohne pytest):  python tests/test_empty_content.py
"""
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

# Projekt-Root auf den Importpfad legen (Lauf ohne Installation/pytest)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.core.api_client import APIStatus
from src.core.openrouter_client import OpenRouterClient
from src.core.perplexity_client import PerplexityClient


class FakeResp:
    status_code = 200
    def __init__(self, payload): self._p = payload
    def json(self): return self._p


def _run_requests_client(cls, module_path, payload):
    with patch(f"{module_path}.requests.post", return_value=FakeResp(payload)):
        return cls("dummy-key").send_prompt("prompt", "some/model")


def test_requests_based(name, cls, module_path):
    # 1) content == None -> ERROR (kein Crash), finish_reason in Meldung
    r = _run_requests_client(cls, module_path,
        {"choices": [{"message": {"content": None}, "finish_reason": "error"}],
         "usage": {"total_tokens": 0}})
    assert r.status == APIStatus.ERROR, f"{name}: None sollte ERROR sein"
    assert "leeren Inhalt" in r.error_message and "finish_reason=error" in r.error_message
    # 2) content == "" + reasoning gesetzt -> RECEIVED mit reasoning-Text
    r = _run_requests_client(cls, module_path,
        {"choices": [{"message": {"content": "", "reasoning": "Denkprozess"}, "finish_reason": "stop"}]})
    assert r.status == APIStatus.RECEIVED and r.content == "Denkprozess", f"{name}: reasoning-Fallback"
    # 3) content nur Whitespace, kein reasoning -> ERROR
    r = _run_requests_client(cls, module_path,
        {"choices": [{"message": {"content": "   "}, "finish_reason": "length"}]})
    assert r.status == APIStatus.ERROR, f"{name}: leer ohne reasoning -> ERROR"
    # 4) Normalfall -> RECEIVED
    r = _run_requests_client(cls, module_path,
        {"choices": [{"message": {"content": "Hallo Welt"}}], "usage": {"total_tokens": 5}})
    assert r.status == APIStatus.RECEIVED and r.content == "Hallo Welt", f"{name}: Normalfall"
    # 5) message fehlt -> ERROR (kein Crash)
    r = _run_requests_client(cls, module_path, {"choices": [{}]})
    assert r.status == APIStatus.ERROR, f"{name}: fehlende message -> ERROR"
    print(f"  {name}: OK (None/reasoning/leer/normal/fehlend)")


def test_openai():
    try:
        import openai  # noqa: F401
    except ImportError:
        print("  OpenAI: SDK nicht installiert -> uebersprungen")
        return
    from src.core.openai_client import OpenAIClient
    def fake_response(content):
        resp = MagicMock()
        resp.choices[0].message.content = content
        resp.choices[0].finish_reason = "stop"
        resp.usage.total_tokens = 3
        return resp
    with patch("openai.OpenAI") as M:
        M.return_value.chat.completions.create.return_value = fake_response(None)
        assert OpenAIClient("k").send_prompt("p", "gpt-4o").status == APIStatus.ERROR
        M.return_value.chat.completions.create.return_value = fake_response("Antwort")
        r = OpenAIClient("k").send_prompt("p", "gpt-4o")
        assert r.status == APIStatus.RECEIVED and r.content == "Antwort"
    print("  OpenAI: OK (None -> ERROR, Text -> RECEIVED)")


def test_anthropic():
    try:
        import anthropic  # noqa: F401
    except ImportError:
        print("  Anthropic: SDK nicht installiert -> uebersprungen")
        return
    from src.core.anthropic_client import AnthropicClient
    def block(text):
        b = MagicMock(); b.text = text; return b
    def fake_message(blocks):
        msg = MagicMock()
        msg.content = blocks
        msg.stop_reason = "end_turn"
        msg.usage.input_tokens = 1
        msg.usage.output_tokens = 2
        return msg
    with patch("anthropic.Anthropic") as M:
        M.return_value.messages.create.return_value = fake_message([])
        assert AnthropicClient("k").send_prompt("p", "claude-sonnet-4-6").status == APIStatus.ERROR
        M.return_value.messages.create.return_value = fake_message([block(None)])
        assert AnthropicClient("k").send_prompt("p", "claude-sonnet-4-6").status == APIStatus.ERROR
        M.return_value.messages.create.return_value = fake_message([block("Hallo")])
        r = AnthropicClient("k").send_prompt("p", "claude-sonnet-4-6")
        assert r.status == APIStatus.RECEIVED and r.content == "Hallo"
    print("  Anthropic: OK (leer/None-Block -> ERROR, Text -> RECEIVED)")


def main():
    print("Tests leerer/None-Content:")
    test_requests_based("OpenRouter", OpenRouterClient, "src.core.openrouter_client")
    test_requests_based("Perplexity", PerplexityClient, "src.core.perplexity_client")
    test_openai()
    test_anthropic()
    print("ALLE TESTS OK")


if __name__ == "__main__":
    main()
