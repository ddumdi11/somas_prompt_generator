"""Tests für die v0.11-Prüfkette im ComparisonWorker (Teil A, v0.14.3).

Der Vergleichspfad (v0.9.0) hatte weder Struktur-Validator noch finish_reason-Gate
noch Auto-Retry — er übernahm degenerierten Modell-Output ungeprüft ins Dokument.
Teil A verdrahtet dieselbe Kette wie die Einzelanalyse (inkl.
``strip_reasoning_preamble``) in beide Analyse-Stufen.

Getestet wird ``ComparisonWorker.run()`` DIREKT aufgerufen (kein QThread-Start,
keine Netzwerk-Calls): ``get_api_key``/``create_client`` gemockt, Transkript-Modus
(umgeht ``resolve_video_info``/Thumbnails). Signale werden synchron eingesammelt.

Lauf (ohne pytest):
    QT_QPA_PLATFORM=offscreen python tests/test_comparison_validator.py
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.core.api_client import APIResponse, APIStatus
from src.core.comparison_item import ComparisonConfig, ModelChoice
from src.core.comparison_worker import ComparisonWorker

FIXTURES = Path(__file__).resolve().parent / "fixtures"

# Strukturell gültige, rein lateinische Analyse (passt validate_analysis_structure).
VALID_ANALYSIS = (
    "### FRAMING\nEinleitender Satz zum Beitrag.\n"
    "### KERNTHESE\nDie zentrale These ist klar benannt.\n"
    "### ELABORATION\nVertiefung mit konkreten Belegen im Text.\n"
    "### IMPLIKATION\nDas Fazit für die Praxis.\n"
    "### KRITIK\nEine kritische Einordnung der Grenzen.\n"
)


def _received(content: str, finish_reason: str = "stop") -> APIResponse:
    return APIResponse(
        status=APIStatus.RECEIVED, content=content, tokens_used=42,
        finish_reason=finish_reason,
    )


def _error(msg: str = "HTTP 500") -> APIResponse:
    return APIResponse(status=APIStatus.ERROR, error_message=msg)


class _FakeClient:
    """Gibt vorbestimmte Antworten der Reihe nach zurück."""

    PROVIDER_ID = "fake"
    BASE_URL = ""

    def __init__(self, responses: list[APIResponse]) -> None:
        self._responses = list(responses)
        self.calls = 0

    def send_prompt(self, prompt, model, max_tokens=None, cap_reasoning=False):
        self.calls += 1
        return self._responses.pop(0)


def _degenerate_content() -> str:
    return (FIXTURES / "comparison_degenerate_flash.txt").read_text(encoding="utf-8")


def _run_worker(resp_a, resp_b, resp_synth):
    """Baut Worker + Fake-Clients, ruft run() direkt auf, sammelt die Signale."""
    client_a = _FakeClient(resp_a)
    client_b = _FakeClient(resp_b)
    client_synth = _FakeClient(resp_synth)
    clients = {"pa": client_a, "pb": client_b, "ps": client_synth}

    config = ComparisonConfig(
        input_mode="transcript",
        transcript_title="Testquelle",
        transcript_author="Autor",
        transcript_text="Ein hinreichend langer Transkript-Text für die Analyse.",
        preset_name="Standard",
        model_a=ModelChoice(provider_id="pa", model_id="ma", model_name="Model A"),
        model_b=ModelChoice(provider_id="pb", model_id="mb", model_name="Model B"),
        model_synth=ModelChoice(provider_id="ps", model_id="ms", model_name="Synth"),
    )

    events = {"steps": [], "errors": [], "finished": [], "analyses": []}
    worker = ComparisonWorker(config)
    worker.step_status_changed.connect(lambda s: events["steps"].append(s))
    worker.error_occurred.connect(lambda step, msg: events["errors"].append((step, msg)))
    worker.comparison_finished.connect(lambda md: events["finished"].append(md))
    worker.analysis_completed.connect(
        lambda step, text, resp: events["analyses"].append(step)
    )

    with patch("src.core.comparison_worker.get_api_key", return_value="k"), \
         patch("src.core.comparison_worker.create_client",
               side_effect=lambda pid, key: clients[pid]):
        worker.run()

    return worker, events, clients


# --- Test 3: ungültige B → 1× Retry → erneut ungültig → offener Fehlschlag --

def test_invalid_b_retries_then_open_failure() -> None:
    """Degenerierte B (Schriftmix) zweimal → Retry, dann offener Fehlschlag, kein Doc."""
    degen = _degenerate_content()
    worker, events, clients = _run_worker(
        resp_a=[_received(VALID_ANALYSIS)],
        resp_b=[_received(degen), _received(degen)],  # beide Versuche ungültig
        resp_synth=[_received("Kurzbeschreibung")],
    )
    assert clients["pb"].calls == 2, "B müsste genau einmal wiederholt werden"
    assert "b_retry" in events["steps"], events["steps"]
    assert not events["finished"], "Kein Dokument bei kaputter Analyse"
    assert worker.result.status == "error"
    assert any(step == "b" for step, _ in events["errors"]), events["errors"]
    # Synthese darf gar nicht erst gestartet worden sein.
    assert clients["ps"].calls == 0
    print("  invalid_b_retries_then_open_failure OK")


# --- Test 4: A gültig, B im Retry gültig → Dokument entsteht ----------------

def test_b_valid_on_retry_produces_document() -> None:
    """Erst ungültige, dann gültige B → Retry, danach normales Dokument."""
    degen = _degenerate_content()
    worker, events, clients = _run_worker(
        resp_a=[_received(VALID_ANALYSIS)],
        resp_b=[_received(degen), _received(VALID_ANALYSIS)],
        resp_synth=[_received("Kurzbeschreibung")],
    )
    assert clients["pb"].calls == 2
    assert "b_retry" in events["steps"]
    assert events["finished"], "Dokument müsste entstehen"
    assert worker.result.status == "done"
    assert set(events["analyses"]) == {"a", "b"}
    print("  b_valid_on_retry_produces_document OK")


# --- Test 5: B finish_reason=length → gleicher Pfad wie Test 3 --------------

def test_b_truncated_finish_reason_open_failure() -> None:
    """B mit finish_reason=length (Trunkierung) → Retry, dann offener Fehlschlag."""
    worker, events, clients = _run_worker(
        resp_a=[_received(VALID_ANALYSIS)],
        resp_b=[
            _received(VALID_ANALYSIS, finish_reason="length"),
            _received(VALID_ANALYSIS, finish_reason="length"),
        ],
        resp_synth=[_received("Kurzbeschreibung")],
    )
    assert clients["pb"].calls == 2
    assert not events["finished"]
    assert worker.result.status == "error"
    assert any("abgeschnitten" in msg.lower() for _, msg in events["errors"]), events["errors"]
    print("  b_truncated_finish_reason_open_failure OK")


# --- Test 6: beide gültig → unverändert; Synthese-Fehler → Platzhalter ------

def test_both_valid_document_and_synthesis_error_nonfatal() -> None:
    """Beide Analysen gültig → Dokument; Synthese-Fehler bleibt nicht-fatal."""
    worker, events, clients = _run_worker(
        resp_a=[_received(VALID_ANALYSIS)],
        resp_b=[_received(VALID_ANALYSIS)],
        resp_synth=[_error("Synthese-Modell down")],  # nicht-fatal
    )
    assert clients["pa"].calls == 1 and clients["pb"].calls == 1, "kein Retry nötig"
    assert not any(s in events["steps"] for s in ("a_retry", "b_retry"))
    assert events["finished"], "Dokument müsste trotz Synthese-Fehler entstehen"
    assert worker.result.status == "done"
    # Synthese-Fehler wird als (nicht-fataler) Hinweis gemeldet.
    assert any(step == "synth" for step, _ in events["errors"]), events["errors"]
    # Platzhalter steht im Dokument.
    from src.core.comparison_worker import SYNTHESIS_PLACEHOLDER
    assert SYNTHESIS_PLACEHOLDER in worker.result.final_markdown
    print("  both_valid_document_and_synthesis_error_nonfatal OK")


# --- Regression: A-Transport-Fehler → sofortiger Fehlschlag, kein Retry -----

def test_transport_error_no_retry() -> None:
    """Transport-/API-Fehler in A → sofortiger Fehlschlag, kein Auto-Retry."""
    worker, events, clients = _run_worker(
        resp_a=[_error("HTTP 500")],
        resp_b=[_received(VALID_ANALYSIS)],
        resp_synth=[_received("Kurzbeschreibung")],
    )
    assert clients["pa"].calls == 1, "Transport-Fehler darf keinen Retry auslösen"
    assert not events["finished"]
    assert worker.result.status == "error"
    assert clients["pb"].calls == 0, "B darf nach A-Fehler nicht mehr laufen"
    print("  transport_error_no_retry OK")


def main() -> None:
    """Führt alle ComparisonWorker-Prüfketten-Tests aus."""
    print("ComparisonWorker-Prüfkette (Teil A, v0.14.3):")
    test_invalid_b_retries_then_open_failure()
    test_b_valid_on_retry_produces_document()
    test_b_truncated_finish_reason_open_failure()
    test_both_valid_document_and_synthesis_error_nonfatal()
    test_transport_error_no_retry()
    print("ALLE TESTS OK")


if __name__ == "__main__":
    main()
