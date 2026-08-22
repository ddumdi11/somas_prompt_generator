"""32k-Analyse-Budget für OpenRouter + Usage im Leer-Inhalt-Fehlerpfad (v0.14.2).

Spiegel-Stück zu v0.13.3 für den **Analyse-Call** (statt der Stage-Calls).

Teil A — Der normale OpenRouter-Call (``max_tokens is None``: Analyse UND
klassische Verifikation) bekommt einen OpenRouter-eigenen 32768-Default statt
``DEFAULT_MAX_TOKENS`` (8192). Explizit übergebene Werte (Stage-Calls) bleiben
1:1; alle anderen Provider bleiben bei 8192.

Teil B — Auch die Leer-Inhalt-``APIResponse`` trägt jetzt den Token-Split aus
``usage`` (v0.13.3 füllte ihn nur im Erfolgspfad). Genau dort braucht die
Diagnose den Beleg, WOHIN das Budget ging (Reasoning). Alle 4 Clients.

Alles offline, gemockt — kein Netzwerk.

Lauf (ohne pytest):
    QT_QPA_PLATFORM=offscreen python tests/test_openrouter_analysis_budget.py
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.core.api_client import (
    DEFAULT_MAX_TOKENS,
    APIStatus,
    is_empty_content_error,
)
from src.core.openrouter_client import OPENROUTER_DEFAULT_MAX_TOKENS, OpenRouterClient
from src.core.perplexity_client import PerplexityClient


class _Resp:
    """Minimaler requests-Response-Doppelgänger."""

    status_code: int = 200
    text: str = ""

    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def json(self) -> dict:
        return self._payload


def _capture(module_path: str, payload: dict) -> tuple[dict, object]:
    """Patch-Kontext, der den gesendeten JSON-Payload einsammelt."""
    captured: dict = {}

    def fake_post(url: str, headers: dict | None = None,
                  json: dict | None = None, timeout: float | None = None) -> _Resp:
        captured["json"] = json
        return _Resp(payload)

    return captured, patch(f"{module_path}.requests.post", side_effect=fake_post)


_OK = {"choices": [{"message": {"content": "Antwort"}, "finish_reason": "stop"}],
       "usage": {"total_tokens": 3}}


# === Teil A: 32k-Analyse-Budget ==========================================

def test_normal_openrouter_call_uses_32k() -> None:
    """Analyse-Call ohne explizites max_tokens → Payload 32768 (nicht 8192)."""
    captured, ctx = _capture("src.core.openrouter_client", _OK)
    with ctx:
        r = OpenRouterClient("k").send_prompt("p", "deepseek/deepseek-v4-pro-0813")
    assert r.status == APIStatus.RECEIVED, r.error_message
    assert OPENROUTER_DEFAULT_MAX_TOKENS == 32768
    assert captured["json"]["max_tokens"] == 32768
    assert captured["json"]["max_tokens"] != DEFAULT_MAX_TOKENS
    # Analyse-Reasoning bleibt ungecappt (nur exclude, kein effort).
    assert captured["json"]["reasoning"] == {"exclude": True}
    print("  normal_openrouter_call_uses_32k OK")


def test_explicit_max_tokens_respected() -> None:
    """Explizit übergebene max_tokens (Stage-Calls) werden 1:1 respektiert."""
    for explicit in (16384, 32768, 4096):
        captured, ctx = _capture("src.core.openrouter_client", _OK)
        with ctx:
            OpenRouterClient("k").send_prompt("p", "m", max_tokens=explicit)
        assert captured["json"]["max_tokens"] == explicit, explicit
    print("  explicit_max_tokens_respected OK")


def test_perplexity_normal_call_stays_8192() -> None:
    """Andere Provider bleiben unverändert bei DEFAULT_MAX_TOKENS (8192)."""
    captured, ctx = _capture("src.core.perplexity_client", _OK)
    with ctx:
        PerplexityClient("k").send_prompt("p", "sonar-pro")
    assert captured["json"]["max_tokens"] == DEFAULT_MAX_TOKENS == 8192
    print("  perplexity_normal_call_stays_8192 OK")


def test_anthropic_normal_call_stays_8192() -> None:
    """Anthropic-Normal-Call: weiterhin 8192 (nicht vom OpenRouter-Default berührt)."""
    # SDK ist Pflicht-Dependency (requirements.txt); fehlt sie doch, honest SKIP
    # statt assertion-freiem Durchlauf (der als PASS bzw. „ALL OK" durchginge).
    pytest.importorskip("anthropic")
    from src.core.anthropic_client import AnthropicClient

    block = MagicMock()
    block.text = "Hallo"
    msg = MagicMock()
    msg.content = [block]
    msg.stop_reason = "end_turn"
    msg.usage.input_tokens = 10
    msg.usage.output_tokens = 5
    with patch("anthropic.Anthropic") as M:
        M.return_value.messages.create.return_value = msg
        AnthropicClient("k").send_prompt("p", "claude-sonnet-4-6")
        _, kwargs = M.return_value.messages.create.call_args
    assert kwargs["max_tokens"] == DEFAULT_MAX_TOKENS == 8192
    print("  anthropic_normal_call_stays_8192 OK")


def test_openai_normal_call_stays_8192() -> None:
    """OpenAI-Normal-Call: weiterhin 8192."""
    pytest.importorskip("openai")
    from src.core.openai_client import OpenAIClient

    resp = MagicMock()
    resp.choices[0].message.content = "Antwort"
    resp.choices[0].finish_reason = "stop"
    resp.usage.total_tokens = 3
    resp.usage.prompt_tokens = 1
    resp.usage.completion_tokens = 2
    resp.usage.completion_tokens_details.reasoning_tokens = None
    with patch("openai.OpenAI") as M:
        M.return_value.chat.completions.create.return_value = resp
        OpenAIClient("k").send_prompt("p", "gpt-4o")
        _, kwargs = M.return_value.chat.completions.create.call_args
    assert kwargs["max_tokens"] == DEFAULT_MAX_TOKENS == 8192
    print("  openai_normal_call_stays_8192 OK")


# === Teil B: Usage im Leer-Inhalt-Fehlerpfad =============================

def _empty_payload(usage: dict | None) -> dict:
    """Leer-Inhalt-Payload (finish_reason=length), optional mit usage."""
    p: dict = {"choices": [{"message": {"content": ""}, "finish_reason": "length"}]}
    if usage is not None:
        p["usage"] = usage
    return p


def test_openrouter_empty_content_carries_usage() -> None:
    """OpenRouter-Leer-Inhalt trägt input/output/total + reasoning aus usage."""
    usage = {
        "prompt_tokens": 1960, "completion_tokens": 16384, "total_tokens": 18344,
        "completion_tokens_details": {"reasoning_tokens": 14700},
    }
    _, ctx = _capture("src.core.openrouter_client", _empty_payload(usage))
    with ctx:
        r = OpenRouterClient("k").send_prompt("p", "deepseek/deepseek-v4-pro-0813")
    assert r.status == APIStatus.ERROR
    assert is_empty_content_error(r.error_message)
    assert r.http_status == 200 and r.finish_reason == "length"
    assert r.tokens_input == 1960 and r.tokens_output == 16384
    assert r.tokens_used == 18344 and r.reasoning_tokens == 14700
    print("  openrouter_empty_content_carries_usage OK")


def test_openrouter_empty_content_without_usage_no_crash() -> None:
    """Ohne usage bleiben die Token-Felder 0/None — kein Crash."""
    _, ctx = _capture("src.core.openrouter_client", _empty_payload(None))
    with ctx:
        r = OpenRouterClient("k").send_prompt("p", "some/model")
    assert r.status == APIStatus.ERROR and is_empty_content_error(r.error_message)
    assert r.tokens_input == 0 and r.tokens_output == 0
    assert r.tokens_used == 0 and r.reasoning_tokens is None
    print("  openrouter_empty_content_without_usage_no_crash OK")


def test_perplexity_empty_content_carries_usage() -> None:
    """Perplexity-Leer-Inhalt trägt input/output/total (kein reasoning)."""
    usage = {"prompt_tokens": 40, "completion_tokens": 8192, "total_tokens": 8232}
    _, ctx = _capture("src.core.perplexity_client", _empty_payload(usage))
    with ctx:
        r = PerplexityClient("k").send_prompt("p", "sonar-pro")
    assert r.status == APIStatus.ERROR and is_empty_content_error(r.error_message)
    assert r.tokens_input == 40 and r.tokens_output == 8192 and r.tokens_used == 8232
    assert r.reasoning_tokens is None
    print("  perplexity_empty_content_carries_usage OK")


def test_anthropic_empty_content_carries_usage() -> None:
    """Anthropic-Leer-Inhalt trägt input/output aus usage."""
    pytest.importorskip("anthropic")
    from src.core.anthropic_client import AnthropicClient

    msg = MagicMock()
    msg.content = []  # leer → Leer-Inhalt-Pfad
    msg.stop_reason = "max_tokens"
    msg.usage.input_tokens = 120
    msg.usage.output_tokens = 8192
    with patch("anthropic.Anthropic") as M:
        M.return_value.messages.create.return_value = msg
        r = AnthropicClient("k").send_prompt("p", "claude-sonnet-4-6")
    assert r.status == APIStatus.ERROR and is_empty_content_error(r.error_message)
    # max_tokens → length normalisiert.
    assert r.finish_reason == "length"
    assert r.tokens_input == 120 and r.tokens_output == 8192 and r.tokens_used == 8312
    assert r.reasoning_tokens is None
    print("  anthropic_empty_content_carries_usage OK")


def test_openai_empty_content_carries_usage() -> None:
    """OpenAI-Leer-Inhalt trägt input/output + reasoning (o-Series)."""
    pytest.importorskip("openai")
    from src.core.openai_client import OpenAIClient

    resp = MagicMock()
    resp.choices[0].message.content = ""  # leer → Leer-Inhalt-Pfad
    resp.choices[0].finish_reason = "length"
    resp.usage.total_tokens = 8292
    resp.usage.prompt_tokens = 100
    resp.usage.completion_tokens = 8192
    resp.usage.completion_tokens_details.reasoning_tokens = 8000
    with patch("openai.OpenAI") as M:
        M.return_value.chat.completions.create.return_value = resp
        r = OpenAIClient("k").send_prompt("p", "o3")
    assert r.status == APIStatus.ERROR and is_empty_content_error(r.error_message)
    assert r.tokens_input == 100 and r.tokens_output == 8192
    assert r.tokens_used == 8292 and r.reasoning_tokens == 8000
    print("  openai_empty_content_carries_usage OK")


def main() -> None:
    """Führt alle Prüfungen ohne pytest nacheinander aus.

    Deckt Teil A (Analyse-Budget: Normal-Call 32k, explizite Werte 1:1, andere
    Provider 8192) und Teil B (Token-Split im Leer-Inhalt-Fehlerpfad je Provider)
    ab und meldet am Ende „ALLE TESTS OK". Fehlt ein Pflicht-SDK
    (anthropic/openai), bricht der jeweilige Test per ``importorskip`` sichtbar ab
    statt still als Erfolg durchzulaufen.
    """
    print("32k-Analyse-Budget + Usage im Leer-Pfad (v0.14.2):")
    test_normal_openrouter_call_uses_32k()
    test_explicit_max_tokens_respected()
    test_perplexity_normal_call_stays_8192()
    test_anthropic_normal_call_stays_8192()
    test_openai_normal_call_stays_8192()
    test_openrouter_empty_content_carries_usage()
    test_openrouter_empty_content_without_usage_no_crash()
    test_perplexity_empty_content_carries_usage()
    test_anthropic_empty_content_carries_usage()
    test_openai_empty_content_carries_usage()
    print("ALLE TESTS OK")


if __name__ == "__main__":
    main()
