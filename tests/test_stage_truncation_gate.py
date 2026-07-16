"""Trunkierungs-Härtung der Faktencheck-Plus-Stufen (v0.13.1).

Deckt die drei Teile des Fixes ab (Realtest 2026-07-16: S1 scheiterte bei 21
Roh-Claims an einem abgeschnittenen JSON-Array):

- **Teil A** — Trunkierungs-Gate in ``llm_stage.run_json_stage``: eine bei der
  Token-Grenze abgeschnittene Antwort (``finish_reason`` ∈ length/max_tokens/
  truncated) bricht SOFORT mit ``StageError`` ab — **kein** Reparatur-Retry
  (gleiches Budget schnitte erneut ab). Regression: kaputtes JSON OHNE
  Trunkierung bekommt weiterhin genau einen Reparatur-Retry; ein Transport-
  Fehler weiterhin keinen.
- **Teil B** — ``_TokenCountingClient`` reicht ``finish_reason`` an
  ``debug_logger.log_response`` durch (stand zuvor immer ``""``).
- **Teil C** — Stufen-Calls setzen ``max_tokens = STAGE_MAX_TOKENS`` (16384);
  ein normaler Client-Call bleibt bei ``DEFAULT_MAX_TOKENS``.

Alles offline, gemockt — kein Netzwerk.

Lauf (ohne pytest):  QT_QPA_PLATFORM=offscreen python tests/test_stage_truncation_gate.py
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.core.api_client import (
    DEFAULT_MAX_TOKENS, APIResponse, APIStatus,
)
from src.core.factcheck_plus.llm_stage import (
    STAGE_MAX_TOKENS, StageError, run_json_stage,
)
from src.core.openrouter_client import OpenRouterClient
import src.core.factcheck_plus_worker as fpw
from tests.factcheck_plus_helpers import FakeClient, error_response


def _received(content: str, finish_reason: str) -> APIResponse:
    """Baut eine RECEIVED-Antwort mit gesetztem finish_reason."""
    return APIResponse(
        status=APIStatus.RECEIVED, content=content, finish_reason=finish_reason,
    )


# --- Teil A: Trunkierungs-Gate --------------------------------------------

def test_truncated_array_raises_without_repair():
    """Valides-aber-abgeschnittenes JSON + length → StageError, genau 1 Call."""
    # Für sich (bis zum Abbruch) valides Array, das mitten im String endet.
    truncated = _received('[{"claim_id": "c01", "normalized_claim": "Die Zahl', "length")
    client = FakeClient([truncated])

    with pytest.raises(StageError) as exc:
        run_json_stage(client, "m", "prompt", parse=lambda raw: raw,
                       stage_name="ClaimRefiner")

    msg = str(exc.value)
    assert "abgeschnitten" in msg, msg
    assert "finish_reason=length" in msg, msg
    assert client.call_count == 1, "Trunkierung darf KEINEN Reparatur-Retry auslösen"
    print("  truncated_array_raises_without_repair OK")


def test_all_truncation_reasons_gate():
    """Alle drei Trunkierungs-Werte greifen (max_tokens/truncated/length)."""
    for reason in ("max_tokens", "truncated", "LENGTH"):
        client = FakeClient([_received("[teilweise", reason)])
        with pytest.raises(StageError):
            run_json_stage(client, "m", "p", parse=lambda raw: raw, stage_name="S")
        assert client.call_count == 1, reason
    print("  all_truncation_reasons_gate OK")


def test_broken_json_without_truncation_triggers_one_repair():
    """Regression: kaputtes JSON + end_turn → weiterhin genau 1 Reparatur-Retry."""
    broken = _received("das ist gar kein JSON", "end_turn")
    client = FakeClient([broken, broken])

    with pytest.raises(StageError) as exc:
        run_json_stage(client, "m", "prompt", parse=lambda raw: raw, stage_name="S")

    assert "Reparatur-Retry" in str(exc.value)
    assert client.call_count == 2, "genau ein Reparatur-Retry (2 Calls insgesamt)"
    print("  broken_json_without_truncation_triggers_one_repair OK")


def test_transport_error_no_repair():
    """Regression: Transport-/API-Fehler → weiterhin kein Reparatur-Retry."""
    client = FakeClient([error_response()])

    with pytest.raises(StageError) as exc:
        run_json_stage(client, "m", "prompt", parse=lambda raw: raw, stage_name="S")

    assert "API-Fehler" in str(exc.value)
    assert client.call_count == 1
    print("  transport_error_no_repair OK")


def test_empty_finish_reason_still_parses():
    """Kontrolle: leerer finish_reason ist keine Trunkierung — normal geparst."""
    client = FakeClient([_received("[]", "")])
    result = run_json_stage(client, "m", "p", parse=lambda raw: raw, stage_name="S")
    assert result == []
    assert client.call_count == 1
    print("  empty_finish_reason_still_parses OK")


# --- Teil C: Stufen-Budget -------------------------------------------------

def test_stage_call_uses_stage_max_tokens():
    """Der Stufen-Call reicht STAGE_MAX_TOKENS (16384) an den Client durch."""
    client = FakeClient([_received("[]", "stop")])
    result = run_json_stage(client, "m", "p", parse=lambda raw: raw, stage_name="S")
    assert result == []
    assert STAGE_MAX_TOKENS == 16384
    assert client.max_tokens == [STAGE_MAX_TOKENS], client.max_tokens
    print("  stage_call_uses_stage_max_tokens OK")


def test_normal_client_call_uses_default_budget():
    """Ein normaler Client-Call ohne Override bleibt bei DEFAULT_MAX_TOKENS,
    ein expliziter Override (wie aus der Stufe) landet 1:1 im Payload."""
    captured = []

    class _Resp:
        status_code = 200
        text = ""

        @staticmethod
        def json():
            return {
                "choices": [{"message": {"content": "Antwort"},
                             "finish_reason": "stop"}],
                "usage": {"total_tokens": 3},
            }

    def fake_post(url, headers=None, json=None, timeout=None):
        captured.append(json)
        return _Resp()

    with patch("src.core.openrouter_client.requests.post", side_effect=fake_post):
        client = OpenRouterClient("k")
        assert client.send_prompt("p", "some/model").status == APIStatus.RECEIVED
        client.send_prompt("p", "some/model", max_tokens=STAGE_MAX_TOKENS)

    assert captured[0]["max_tokens"] == DEFAULT_MAX_TOKENS, captured[0]["max_tokens"]
    assert captured[1]["max_tokens"] == STAGE_MAX_TOKENS, captured[1]["max_tokens"]
    print("  normal_client_call_uses_default_budget OK")


# --- Teil B: finish_reason im Stage-Log -----------------------------------

class _RecordingDebugLogger:
    """Fake-DebugLogger, der die log_response-Kwargs einsammelt."""

    def __init__(self):
        self.enabled = True
        self.responses = []

    def log_request(self, **kwargs):
        return "logdir"

    def log_response(self, **kwargs):
        self.responses.append(kwargs)


class _StubClient:
    """Client-Doppelgänger für den _TokenCountingClient-Test."""

    PROVIDER_ID = "anthropic"

    def __init__(self, response: APIResponse):
        self._response = response
        self.seen_max_tokens = []

    def send_prompt(self, prompt, model, max_tokens=None):
        self.seen_max_tokens.append(max_tokens)
        return self._response


def test_finish_reason_reaches_debug_log():
    """Teil B: der finish_reason der Stufen-Antwort erreicht log_response —
    und der Wrapper reicht max_tokens an den echten Client durch (Teil C)."""
    resp = _received("[]", "length")
    resp.tokens_used = 42
    client = _StubClient(resp)
    dbg = _RecordingDebugLogger()

    wrapper = fpw._TokenCountingClient(client, "factcheck_plus.s1_refiner", dbg)
    wrapper.send_prompt("p", "m", max_tokens=STAGE_MAX_TOKENS)

    assert dbg.responses, "log_response wurde nicht aufgerufen"
    assert dbg.responses[-1]["finish_reason"] == "length", dbg.responses[-1]
    assert client.seen_max_tokens == [STAGE_MAX_TOKENS], client.seen_max_tokens
    print("  finish_reason_reaches_debug_log OK")


def main():
    print("Trunkierungs-Härtung der Plus-Stufen (v0.13.1):")
    test_truncated_array_raises_without_repair()
    test_all_truncation_reasons_gate()
    test_broken_json_without_truncation_triggers_one_repair()
    test_transport_error_no_repair()
    test_empty_finish_reason_still_parses()
    test_stage_call_uses_stage_max_tokens()
    test_normal_client_call_uses_default_budget()
    test_finish_reason_reaches_debug_log()
    print("ALLE TESTS OK")


if __name__ == "__main__":
    main()
