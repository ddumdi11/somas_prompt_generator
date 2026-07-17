"""32k-Stage-Budget für OpenRouter + Token-Split im Debug-Log (v0.13.3).

Teil A — OpenRouter-Stage-Calls bekommen an der Qt↔Package-Naht
(``_TokenCountingClient``) das größere Budget ``STAGE_MAX_TOKENS_OPENROUTER``
(32768), weil DeepSeek-Hosts den Reasoning-Cap aus v0.13.2 nicht zuverlässig
respektieren. Andere Provider bleiben bei ``STAGE_MAX_TOKENS`` (16384); der
Reasoning-Cap bleibt aktiv.

Teil B — Alle 4 Clients füllen ``tokens_input``/``tokens_output`` aus dem
``usage``-Objekt; OpenRouter/OpenAI zusätzlich ``reasoning_tokens``. Das
Debug-Log persistiert den Split (bisher standen ``tokens_input/output`` immer 0).

Alles offline, gemockt — kein Netzwerk.

Lauf (ohne pytest):  QT_QPA_PLATFORM=offscreen python tests/test_stage_budget_and_tokens.py
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import sys
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.core.api_client import DEFAULT_MAX_TOKENS, APIResponse, APIStatus
from src.core.debug_logger import DebugLogger
from src.core.openrouter_client import OpenRouterClient
from src.core.perplexity_client import PerplexityClient
from src.core.factcheck_plus.llm_stage import STAGE_MAX_TOKENS
from src.core.factcheck_plus_worker import STAGE_MAX_TOKENS_OPENROUTER, _TokenCountingClient


class _Resp:
    """Minimaler requests-Response-Doppelgänger."""

    status_code: int = 200
    text: str = ""

    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def json(self) -> dict:
        return self._payload


def _ok_payload(usage: dict | None = None) -> dict:
    """Baut einen erfolgreichen chat/completions-Payload (optional mit usage)."""
    return {
        "choices": [{"message": {"content": "Antwort"}, "finish_reason": "stop"}],
        "usage": usage if usage is not None else {"total_tokens": 3},
    }


def _capture(module_path: str) -> tuple[dict, Any]:
    """Patch-Kontext, der den gesendeten JSON-Payload einsammelt.

    Returns:
        Tuple aus dem (nach dem Call gefüllten) ``captured``-Dict und dem
        ``patch``-Kontextmanager, der ``requests.post`` ersetzt.
    """
    captured: dict = {}

    def fake_post(url: str, headers: dict | None = None,
                  json: dict | None = None, timeout: float | None = None) -> _Resp:
        captured["json"] = json
        return _Resp(_ok_payload())

    return captured, patch(f"{module_path}.requests.post", side_effect=fake_post)


class _RecordingStub:
    """Client-Doppelgänger mit PROVIDER_ID, der die Aufrufe protokolliert."""

    def __init__(self, provider_id: str) -> None:
        self.PROVIDER_ID: str = provider_id
        self.seen_max_tokens: list[int | None] = []

    def send_prompt(self, prompt: str, model: str, max_tokens: int | None = None,
                    cap_reasoning: bool = False) -> APIResponse:
        self.seen_max_tokens.append(max_tokens)
        return APIResponse(status=APIStatus.RECEIVED, content="[]", tokens_used=1)


# === Teil A: 32k-Budget für OpenRouter-Stage-Calls ========================

def test_openrouter_stage_call_uses_32k() -> None:
    """Durch die Naht: OpenRouter-Stage-Call → Payload max_tokens=32768 + Cap."""
    captured, ctx = _capture("src.core.openrouter_client")
    wrapped = _TokenCountingClient(OpenRouterClient("k"), "s1_refiner")
    with ctx:
        # llm_stage fordert 16384 an; die Naht hebt es für OpenRouter auf 32768.
        r = wrapped.send_prompt("p", "deepseek/deepseek-v4-pro",
                                max_tokens=STAGE_MAX_TOKENS, cap_reasoning=True)
    assert r.status == APIStatus.RECEIVED, r.error_message
    assert STAGE_MAX_TOKENS_OPENROUTER == 32768
    assert captured["json"]["max_tokens"] == 32768, captured["json"]["max_tokens"]
    # Reasoning-Cap bleibt unverändert aktiv.
    assert captured["json"]["reasoning"] == {"exclude": True, "effort": "low"}
    print("  openrouter_stage_call_uses_32k OK")


def test_perplexity_stage_call_stays_16k() -> None:
    """Nicht-OpenRouter-Stage-Call bleibt bei 16384, kein reasoning-Feld."""
    captured, ctx = _capture("src.core.perplexity_client")
    wrapped = _TokenCountingClient(PerplexityClient("k"), "s5_verifier")
    with ctx:
        r = wrapped.send_prompt("p", "sonar-pro",
                                max_tokens=STAGE_MAX_TOKENS, cap_reasoning=True)
    assert r.status == APIStatus.RECEIVED, r.error_message
    assert captured["json"]["max_tokens"] == STAGE_MAX_TOKENS == 16384
    assert "reasoning" not in captured["json"], captured["json"]
    print("  perplexity_stage_call_stays_16k OK")


def test_non_openrouter_budget_unchanged_at_seam() -> None:
    """Die Naht hebt nur für OpenRouter an — Anthropic bleibt bei 16384."""
    stub = _RecordingStub("anthropic")
    _TokenCountingClient(stub, "s1_refiner").send_prompt(
        "p", "claude-sonnet-4-6", max_tokens=STAGE_MAX_TOKENS, cap_reasoning=True,
    )
    assert stub.seen_max_tokens == [STAGE_MAX_TOKENS]
    # Gegenprobe: OpenRouter-Stub bekommt 32768.
    orb = _RecordingStub("openrouter")
    _TokenCountingClient(orb, "s1_refiner").send_prompt(
        "p", "x", max_tokens=STAGE_MAX_TOKENS, cap_reasoning=True,
    )
    assert orb.seen_max_tokens == [STAGE_MAX_TOKENS_OPENROUTER]
    print("  non_openrouter_budget_unchanged_at_seam OK")


def test_normal_openrouter_call_unchanged() -> None:
    """Normaler (nicht durch die Naht laufender) OpenRouter-Call: DEFAULT + nur exclude."""
    captured, ctx = _capture("src.core.openrouter_client")
    with ctx:
        OpenRouterClient("k").send_prompt("p", "some/model")
    assert captured["json"]["max_tokens"] == DEFAULT_MAX_TOKENS
    assert captured["json"]["reasoning"] == {"exclude": True}
    print("  normal_openrouter_call_unchanged OK")


# === Teil B: Token-Split im Debug-Log =====================================

def test_openrouter_token_split_and_reasoning() -> None:
    """OpenRouter füllt input/output + reasoning_tokens aus usage."""
    usage = {
        "prompt_tokens": 1960, "completion_tokens": 16384, "total_tokens": 18344,
        "completion_tokens_details": {"reasoning_tokens": 11400},
    }
    captured: dict = {}

    def fake_post(url: str, headers: dict | None = None,
                  json: dict | None = None, timeout: float | None = None) -> _Resp:
        captured["json"] = json
        return _Resp(_ok_payload(usage))

    with patch("src.core.openrouter_client.requests.post", side_effect=fake_post):
        r = OpenRouterClient("k").send_prompt("p", "deepseek/deepseek-v4-pro")
    assert r.tokens_input == 1960 and r.tokens_output == 16384
    assert r.tokens_used == 18344
    assert r.reasoning_tokens == 11400
    print("  openrouter_token_split_and_reasoning OK")


def test_openrouter_missing_usage_no_crash() -> None:
    """Fehlt usage, bleiben die Felder 0/None — kein Crash."""
    def fake_post(url: str, headers: dict | None = None,
                  json: dict | None = None, timeout: float | None = None) -> _Resp:
        return _Resp({"choices": [{"message": {"content": "Antwort"},
                                   "finish_reason": "stop"}]})  # kein usage

    with patch("src.core.openrouter_client.requests.post", side_effect=fake_post):
        r = OpenRouterClient("k").send_prompt("p", "some/model")
    assert r.status == APIStatus.RECEIVED
    assert r.tokens_input == 0 and r.tokens_output == 0
    assert r.reasoning_tokens is None
    print("  openrouter_missing_usage_no_crash OK")


def test_perplexity_token_split_no_reasoning() -> None:
    """Perplexity füllt input/output, aber kein reasoning_tokens."""
    usage = {"prompt_tokens": 50, "completion_tokens": 200, "total_tokens": 250}

    def fake_post(url: str, headers: dict | None = None,
                  json: dict | None = None, timeout: float | None = None) -> _Resp:
        return _Resp({"choices": [{"message": {"content": "A"},
                                   "finish_reason": "stop"}], "usage": usage})

    with patch("src.core.perplexity_client.requests.post", side_effect=fake_post):
        r = PerplexityClient("k").send_prompt("p", "sonar-pro")
    assert r.tokens_input == 50 and r.tokens_output == 200
    assert r.reasoning_tokens is None
    print("  perplexity_token_split_no_reasoning OK")


def test_anthropic_token_split() -> None:
    """Anthropic füllt input/output aus usage; kein separates reasoning."""
    try:
        import anthropic  # noqa: F401
    except ImportError:
        print("  anthropic_token_split: SDK nicht installiert -> uebersprungen")
        return
    from src.core.anthropic_client import AnthropicClient

    block = MagicMock()
    block.text = "Hallo"
    msg = MagicMock()
    msg.content = [block]
    msg.stop_reason = "end_turn"
    msg.usage.input_tokens = 120
    msg.usage.output_tokens = 40
    with patch("anthropic.Anthropic") as M:
        M.return_value.messages.create.return_value = msg
        r = AnthropicClient("k").send_prompt("p", "claude-sonnet-4-6")
    assert r.tokens_input == 120 and r.tokens_output == 40 and r.tokens_used == 160
    assert r.reasoning_tokens is None
    print("  anthropic_token_split OK")


def test_openai_token_split_with_reasoning() -> None:
    """OpenAI füllt input/output + reasoning_tokens (o-Series)."""
    try:
        import openai  # noqa: F401
    except ImportError:
        print("  openai_token_split: SDK nicht installiert -> uebersprungen")
        return
    from src.core.openai_client import OpenAIClient

    resp = MagicMock()
    resp.choices[0].message.content = "Antwort"
    resp.choices[0].finish_reason = "stop"
    resp.usage.total_tokens = 300
    resp.usage.prompt_tokens = 100
    resp.usage.completion_tokens = 200
    resp.usage.completion_tokens_details.reasoning_tokens = 150
    with patch("openai.OpenAI") as M:
        M.return_value.chat.completions.create.return_value = resp
        r = OpenAIClient("k").send_prompt("p", "o3")
    assert r.tokens_input == 100 and r.tokens_output == 200
    assert r.reasoning_tokens == 150
    print("  openai_token_split_with_reasoning OK")


class _RecordingLogger:
    """DebugLogger-Doppelgänger, der die log_response-Kwargs einsammelt."""

    def __init__(self) -> None:
        self.enabled: bool = True
        self.kwargs: dict | None = None

    def log_request(self, **kwargs: object) -> str:
        return "logdir"

    def log_response(self, **kwargs: object) -> None:
        self.kwargs = kwargs


def test_token_counting_client_forwards_split_to_log() -> None:
    """_TokenCountingClient reicht token_log_dict + reasoning_tokens ans Log."""
    resp = APIResponse(
        status=APIStatus.RECEIVED, content="[]",
        tokens_used=250, tokens_input=50, tokens_output=200, reasoning_tokens=42,
    )
    client = _RecordingStub("openrouter")
    client.send_prompt = (  # type: ignore[method-assign]
        lambda p, m, max_tokens=None, cap_reasoning=False: resp
    )
    logger = _RecordingLogger()
    _TokenCountingClient(client, "s1_refiner", logger).send_prompt("p", "m")
    assert logger.kwargs is not None
    assert logger.kwargs["tokens"] == {"input": 50, "output": 200, "total": 250}
    assert logger.kwargs["reasoning_tokens"] == 42
    print("  token_counting_client_forwards_split_to_log OK")


def test_debug_log_persists_token_split() -> None:
    """log_response schreibt tokens_input/output/tokens_reasoning in response.json."""
    import json

    dbg = DebugLogger(enabled=True)
    with tempfile.TemporaryDirectory() as tmp:
        log_dir = Path(tmp)
        dbg.log_response(
            log_dir=log_dir, status_code=200, content="x",
            tokens={"input": 50, "output": 200, "total": 250},
            duration=1.0, reasoning_tokens=42,
        )
        data = json.loads((log_dir / "response.json").read_text(encoding="utf-8"))
    assert data["tokens_input"] == 50 and data["tokens_output"] == 200
    assert data["tokens_total"] == 250 and data["tokens_reasoning"] == 42
    print("  debug_log_persists_token_split OK")


def main() -> None:
    print("32k-Stage-Budget + Token-Split (v0.13.3):")
    test_openrouter_stage_call_uses_32k()
    test_perplexity_stage_call_stays_16k()
    test_non_openrouter_budget_unchanged_at_seam()
    test_normal_openrouter_call_unchanged()
    test_openrouter_token_split_and_reasoning()
    test_openrouter_missing_usage_no_crash()
    test_perplexity_token_split_no_reasoning()
    test_anthropic_token_split()
    test_openai_token_split_with_reasoning()
    test_token_counting_client_forwards_split_to_log()
    test_debug_log_persists_token_split()
    print("ALLE TESTS OK")


if __name__ == "__main__":
    main()
