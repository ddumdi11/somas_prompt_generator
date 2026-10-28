"""OpenRouter: HTTP 200 ohne ``choices`` — Fehlerbody sichtbar machen (v0.16.1).

Realfall (27.10., S5 mit ``gpt-5.1-codex-max:online``): Nach bis zu ~29 min
Upstream-Hänger kam HTTP 200 mit einem Body ohne ``choices``. Der Client fing
den ``KeyError`` und warf den Body weg — übrig blieb „Unerwartete API-Antwort:
'choices'" und im Debug-Log ein synthetischer ``status_code: 500``.

Jetzt: ``error``-Objekt → code + message in der Meldung; sonst die vorhandenen
Top-Level-Felder; in beiden Fällen ein gekürzter Rohbody-Auszug (Log +
``error_message`` → response.json) und ``http_status=200``. Verhalten sonst
unverändert: ``APIStatus.ERROR``, kein Reparatur-Retry, kein Leer-Inhalt-Retry.

Alles offline, gemockt — kein Netzwerk.
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import json
import logging
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import src.core.factcheck_plus_worker as fpw
from src.core.api_client import APIStatus, is_empty_content_error
from src.core.factcheck_plus.llm_stage import StageError, run_json_stage
from src.core.openrouter_client import RAW_BODY_EXCERPT_CHARS, OpenRouterClient

_UPSTREAM_ERROR = {
    "id": "gen-123",
    "error": {"message": "Upstream search provider timed out", "code": 502},
}
_NO_CHOICES = {"id": "gen-456", "object": "chat.completion", "usage": {}}


class _Resp:
    """requests-Response-Doppelgänger mit echtem Rohtext."""

    def __init__(self, payload: object, status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code
        self.text = json.dumps(payload)

    def json(self) -> object:
        return self._payload


def _send(payload: object, status_code: int = 200):
    with patch("src.core.openrouter_client.requests.post",
               return_value=_Resp(payload, status_code)) as post:
        response = OpenRouterClient("k").send_prompt("p", "openai/gpt-5.1-codex-max:online")
    assert post.call_count == 1  # kein Client-seitiger Retry
    return response


# --- 1. error-Objekt im 200er-Body ----------------------------------------

def test_error_object_reaches_error_message() -> None:
    """code + message des Upstream-Fehlers stehen in der Meldung; Status echt 200."""
    response = _send(_UPSTREAM_ERROR)
    assert response.status == APIStatus.ERROR
    assert response.http_status == 200
    assert ("OpenRouter-Fehlerantwort statt Completion: 502: "
            "Upstream search provider timed out") in response.error_message
    assert "Rohbody-Auszug (Daten)" in response.error_message
    assert '"id": "gen-123"' in response.error_message
    # Kein Leer-Inhalt → der Analyse-Pfad startet keinen Auto-Retry (Phase 17).
    assert not is_empty_content_error(response.error_message)


def test_multiline_and_overlong_upstream_message_is_cleaned() -> None:
    """Umbrüche in ``error.message`` → einzeilig; überlange Texte gekürzt."""
    response = _send({"error": {"message": "Zeile eins\nZeile zwei\r\n\tdrei",
                                "code": "upstream\nerror"}})
    assert "\n" not in response.error_message and "\r" not in response.error_message
    assert ("OpenRouter-Fehlerantwort statt Completion: upstream error: "
            "Zeile eins Zeile zwei drei") in response.error_message

    response = _send({"error": {"message": "x" * 5000, "code": 502}})
    reason = response.error_message.split(" [Rohbody-Auszug", 1)[0]
    assert len(reason) < 400 and reason.endswith("…")


def test_error_as_plain_string() -> None:
    """Manche Upstreams liefern ``error`` als String statt Objekt."""
    response = _send({"error": "rate limited"})
    assert "OpenRouter-Fehlerantwort statt Completion: rate limited" in response.error_message
    assert response.http_status == 200


# --- 2. weder choices noch error ------------------------------------------

def test_missing_choices_names_top_level_fields(caplog) -> None:
    """Generische Meldung nennt die vorhandenen Felder; Rohbody-Auszug im Log."""
    with caplog.at_level(logging.ERROR, logger="src.core.openrouter_client"):
        response = _send(_NO_CHOICES)
    assert response.status == APIStatus.ERROR
    assert response.http_status == 200
    assert ("Unerwartete API-Antwort ohne 'choices'; Felder: id, object, usage"
            in response.error_message)
    assert any("Rohbody (Auszug, Daten)" in r.getMessage() and "gen-456" in r.getMessage()
               for r in caplog.records)


@pytest.mark.parametrize("payload", [{"choices": []}, {"choices": None}, ["kein", "Objekt"]])
def test_other_malformed_bodies_do_not_crash(payload) -> None:
    """Leere/None-choices und Nicht-Objekt-Bodies → sauberer Fehler, kein Crash."""
    response = _send(payload)
    assert response.status == APIStatus.ERROR
    assert response.http_status == 200
    assert "Unerwartete API-Antwort ohne 'choices'" in response.error_message


def test_raw_excerpt_is_capped_and_single_line() -> None:
    """Auszug gekürzt und einzeilig — die Meldung landet auch in der Berichts-Begründung."""
    big = {"error": {"message": "x", "code": 500},
           "detail": "zeile\n" * 1000}
    response = _send(big)
    excerpt = response.error_message.split("Rohbody-Auszug (Daten): ", 1)[1]
    assert len(excerpt.rstrip("]")) <= RAW_BODY_EXCERPT_CHARS
    assert "\n" not in response.error_message


# --- Kette: Stufe + Debug-Log ---------------------------------------------

def test_stage_fails_once_with_upstream_reason() -> None:
    """S5-Kette: genau ein Call, kein Reparatur-Retry, Grund im StageError."""
    with patch("src.core.openrouter_client.requests.post",
               return_value=_Resp(_UPSTREAM_ERROR)) as post:
        with pytest.raises(StageError) as exc:
            run_json_stage(OpenRouterClient("k"), "m", "p",
                           parse=lambda raw: raw, stage_name="ClaimVerifier[c01]")
    assert post.call_count == 1
    assert "API-Fehler — OpenRouter-Fehlerantwort statt Completion: 502" in str(exc.value)


class _RecordingDebugLogger:
    enabled = True

    def __init__(self) -> None:
        self.responses: list[dict] = []

    def log_request(self, **kwargs) -> str:
        return "logdir"

    def log_response(self, **kwargs) -> None:
        self.responses.append(kwargs)


def test_debug_log_gets_real_status_and_body_excerpt() -> None:
    """response.json bekommt 200 statt 500 und den Upstream-Grund samt Auszug."""
    dbg = _RecordingDebugLogger()
    with patch("src.core.openrouter_client.requests.post",
               return_value=_Resp(_UPSTREAM_ERROR)):
        wrapper = fpw._TokenCountingClient(
            OpenRouterClient("k"), "factcheck_plus.s5_verifier", dbg)
        wrapper.send_prompt("p", "m", max_tokens=16384)
    logged = dbg.responses[-1]
    assert logged["status_code"] == 200
    assert "Upstream search provider timed out" in logged["error"]
    assert "gen-123" in logged["error"]


# --- 3. Non-200-Pfad: Meldung unverändert, Status jetzt echt ----------------

def test_non_200_path_keeps_message_and_logs_real_status() -> None:
    """HTTP 402: Meldungsform wie bisher, aber http_status=402 statt Default 500."""
    response = _send({"error": {"message": "Insufficient credits", "code": 402}}, 402)
    assert response.status == APIStatus.ERROR
    assert response.error_message.startswith("HTTP 402: ")
    assert response.http_status == 402
    dbg = _RecordingDebugLogger()
    with patch("src.core.openrouter_client.requests.post",
               return_value=_Resp({"error": "x"}, 402)):
        fpw._TokenCountingClient(OpenRouterClient("k"), "s", dbg).send_prompt("p", "m")
    assert dbg.responses[-1]["status_code"] == 402


# --- 4. Bericht: Fehler-Begründung gekürzt, Log behält alles ----------------

def test_report_shortens_failed_reason_but_keeps_short_cause() -> None:
    """Die Berichtszeile trägt den Kurzgrund (≤ 160, „…“), nicht den Rohbody-Dump."""
    from src.core.factcheck_plus import build_verdict_rows, failed_verdict
    from src.core.factcheck_plus.models import RefinedClaim
    from src.core.factcheck_plus.verdict import FAILED_REASON_MAX_CHARS

    response = _send(_UPSTREAM_ERROR)
    error = f"ClaimVerifier[c01]: API-Fehler — {response.error_message}"
    claim = RefinedClaim(claim_id="c01", parent_id=None, original_text="x",
                         normalized_claim="Behauptung", claim_type="factual")
    row = build_verdict_rows([claim], [failed_verdict("c01", error)])[0]
    line = row["reason_line"]
    assert len(line) <= FAILED_REASON_MAX_CHARS and line.endswith("…")
    assert line.startswith("Prüfung fehlgeschlagen: ClaimVerifier[c01]: API-Fehler — "
                           "OpenRouter-Fehlerantwort statt Completion: 502")
    assert "gen-123" not in line  # Rohbody bleibt draußen …
    assert "gen-123" in error     # … steht aber weiter in der vollen Meldung (Log)


def test_short_failed_reason_is_untouched() -> None:
    """Kurze Gründe (z. B. „HTTP 503“) bleiben unverändert, ohne „…“."""
    from src.core.factcheck_plus.aggregate import shorten_failed_reason
    assert shorten_failed_reason("Prüfung fehlgeschlagen: HTTP 503") == \
        "Prüfung fehlgeschlagen: HTTP 503"
