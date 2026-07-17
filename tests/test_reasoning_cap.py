"""Reasoning-Cap für OpenRouter-Stage-Calls (v0.13.2).

Anlass (Realtest 2026-07-17, DeepSeek V4 Pro via OpenRouter): S1 scheiterte trotz
``STAGE_MAX_TOKENS = 16384`` — ~14,7k Tokens gingen ins (durch ``exclude`` unsicht-
bare) Reasoning, nur ~1,6k in den sichtbaren JSON-Output → ``finish_reason=length``.

Der Fix cappt das Reasoning für strukturierte Stage-Calls per Effort-Cap. Bewusst
``effort`` statt ``max_tokens``: DeepSeek V4 ist auf OpenRouter effort-gesteuert;
``effort`` wird nativ verstanden statt über die vage ``max_tokens``→effort-
Rückabbildung zu laufen.

Deckt die vier Testpunkte des Startprompts ab:
1. OpenRouter-Stage-Call: Payload enthält den Effort-Cap + weiterhin ``exclude``.
2. Normaler OpenRouter-Analyse-Call: Payload unverändert (nur ``exclude``).
3. Andere Provider (Anthropic/OpenAI/Perplexity): Parameter ignoriert, kein
   Payload-Feld, kein Fehler.
+ Verdrahtung: ``run_json_stage`` fordert ``cap_reasoning=True`` an.

Alles offline, gemockt — kein Netzwerk.

Lauf (ohne pytest):  python tests/test_reasoning_cap.py
"""
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.core.api_client import APIStatus
from src.core.openrouter_client import OpenRouterClient
from src.core.perplexity_client import PerplexityClient
from src.core.factcheck_plus.llm_stage import run_json_stage
from tests.factcheck_plus_helpers import FakeClient


class _Resp:
    status_code = 200
    text = ""

    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


_OK_PAYLOAD = {
    "choices": [{"message": {"content": "Antwort"}, "finish_reason": "stop"}],
    "usage": {"total_tokens": 3},
}


def _capture_openrouter(cap_reasoning: bool) -> dict:
    """Ruft OpenRouter.send_prompt und gibt den gesendeten JSON-Payload zurück."""
    captured = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["json"] = json
        return _Resp(_OK_PAYLOAD)

    with patch("src.core.openrouter_client.requests.post", side_effect=fake_post):
        r = OpenRouterClient("k").send_prompt(
            "p", "deepseek/deepseek-v4-pro", max_tokens=16384,
            cap_reasoning=cap_reasoning,
        )
    assert r.status == APIStatus.RECEIVED, r.error_message
    return captured["json"]


# --- Punkt 1: Stage-Call bekommt den Effort-Cap ---------------------------

def test_stage_call_sends_effort_cap():
    """cap_reasoning=True → reasoning enthält effort-Cap UND weiterhin exclude."""
    payload = _capture_openrouter(cap_reasoning=True)
    assert payload["reasoning"] == {
        "exclude": True, "effort": OpenRouterClient.REASONING_CAP_EFFORT,
    }, payload["reasoning"]
    assert OpenRouterClient.REASONING_CAP_EFFORT == "low"
    print("  stage_call_sends_effort_cap OK")


# --- Punkt 2: Normaler Analyse-Call unverändert ---------------------------

def test_normal_call_has_no_cap():
    """Default cap_reasoning=False → reasoning bleibt nur {exclude: True}."""
    payload = _capture_openrouter(cap_reasoning=False)
    assert payload["reasoning"] == {"exclude": True}, payload["reasoning"]
    assert "effort" not in payload["reasoning"]
    print("  normal_call_has_no_cap OK")


def test_default_is_no_cap():
    """Ohne das Argument bleibt das Verhalten unverändert (nur exclude)."""
    captured = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["json"] = json
        return _Resp(_OK_PAYLOAD)

    with patch("src.core.openrouter_client.requests.post", side_effect=fake_post):
        OpenRouterClient("k").send_prompt("p", "some/model")  # kein cap_reasoning
    assert captured["json"]["reasoning"] == {"exclude": True}
    print("  default_is_no_cap OK")


# --- Punkt 3: Andere Provider ignorieren das Flag -------------------------

def test_perplexity_ignores_cap():
    """Perplexity-Payload bekommt KEIN reasoning-Feld, auch mit cap_reasoning."""
    captured = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["json"] = json
        return _Resp(_OK_PAYLOAD)

    with patch("src.core.perplexity_client.requests.post", side_effect=fake_post):
        r = PerplexityClient("k").send_prompt(
            "p", "sonar-pro", max_tokens=16384, cap_reasoning=True,
        )
    assert r.status == APIStatus.RECEIVED, r.error_message
    assert "reasoning" not in captured["json"], captured["json"]
    print("  perplexity_ignores_cap OK")


def test_openai_ignores_cap():
    """OpenAI: cap_reasoning=True bricht nicht und setzt kein reasoning-kwarg."""
    try:
        import openai  # noqa: F401
    except ImportError:
        print("  openai_ignores_cap: SDK nicht installiert -> uebersprungen")
        return
    from src.core.openai_client import OpenAIClient

    resp = MagicMock()
    resp.choices[0].message.content = "Antwort"
    resp.choices[0].finish_reason = "stop"
    resp.usage.total_tokens = 3

    with patch("openai.OpenAI") as M:
        create = M.return_value.chat.completions.create
        create.return_value = resp
        r = OpenAIClient("k").send_prompt("p", "gpt-4o", cap_reasoning=True)
    assert r.status == APIStatus.RECEIVED
    assert "reasoning" not in create.call_args.kwargs, create.call_args.kwargs
    print("  openai_ignores_cap OK")


def test_anthropic_ignores_cap():
    """Anthropic: cap_reasoning=True bricht nicht und setzt kein reasoning-kwarg."""
    try:
        import anthropic  # noqa: F401
    except ImportError:
        print("  anthropic_ignores_cap: SDK nicht installiert -> uebersprungen")
        return
    from src.core.anthropic_client import AnthropicClient

    block = MagicMock()
    block.text = "Hallo"
    msg = MagicMock()
    msg.content = [block]
    msg.stop_reason = "end_turn"
    msg.usage.input_tokens = 1
    msg.usage.output_tokens = 2

    with patch("anthropic.Anthropic") as M:
        create = M.return_value.messages.create
        create.return_value = msg
        r = AnthropicClient("k").send_prompt(
            "p", "claude-sonnet-4-6", cap_reasoning=True,
        )
    assert r.status == APIStatus.RECEIVED and r.content == "Hallo"
    assert "reasoning" not in create.call_args.kwargs, create.call_args.kwargs
    print("  anthropic_ignores_cap OK")


# --- Verdrahtung: die Stufe fordert den Cap an ----------------------------

def test_run_json_stage_requests_cap():
    """run_json_stage reicht cap_reasoning=True an den Client durch (alle Stufen)."""
    client = FakeClient(["[]"])
    result = run_json_stage(client, "m", "p", parse=lambda raw: raw, stage_name="S")
    assert result == []
    assert client.cap_reasoning == [True], client.cap_reasoning
    print("  run_json_stage_requests_cap OK")


def main():
    print("Reasoning-Cap für OpenRouter-Stage-Calls (v0.13.2):")
    test_stage_call_sends_effort_cap()
    test_normal_call_has_no_cap()
    test_default_is_no_cap()
    test_perplexity_ignores_cap()
    test_openai_ignores_cap()
    test_anthropic_ignores_cap()
    test_run_json_stage_requests_cap()
    print("ALLE TESTS OK")


if __name__ == "__main__":
    main()
