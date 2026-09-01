"""Tests für Faktencheck Plus PR 4: FactcheckPlusWorker (S1–S5-Orchestrierung).

Deckt Spec §5 ab:
- Die fünf Stufen laufen in der richtigen Reihenfolge, mit dem richtigen Modell:
  S1/S2/S4 über das Analyse-Modell, nur S5 über das Web-Modell (PO §8.3).
- Fortschritt je Stufe + je Claim wird gemeldet.
- Abbruch greift zwischen den Stufen UND zwischen den Claims; das Teilergebnis
  bleibt gültig und wird angehängt.
- Ein Stufenfehler beendet den Lauf sauber (nicht fatal für die Analyse), ein
  einzelner Claim-Fehler nicht einmal das.
- Tokens werden über alle Stufen summiert; Debug-Logging läuft je Stufe.

Läuft headless über die Qt-Offscreen-Plattform, alles gemockt — kein Netzwerk.

Lauf (ohne pytest):  QT_QPA_PLATFORM=offscreen python tests/test_factcheck_plus_worker.py
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.core.api_client import APIResponse, APIStatus
from src.core.comparison_item import ModelChoice
from src.core.factcheck_plus_item import FactcheckPlusConfig
import src.core.factcheck_plus_worker as fpw
from src.core.factcheck_plus_worker import FactcheckPlusWorker
from tests.factcheck_plus_helpers import as_json, claim_verdict, load_case, research_card

IRGC = load_case("irgc")

ANALYSIS_MODEL = ModelChoice(
    provider_id="anthropic", model_id="claude-sonnet-4-6",
    model_name="Sonnet 4.6", provider_name="Anthropic",
)
RESEARCH_MODEL = ModelChoice(
    provider_id="perplexity", model_id="sonar-pro",
    model_name="Sonar Pro", provider_name="Perplexity",
)


class ScriptedClient:
    """Client-Doppelgänger, der je Provider ein eigenes Antwortskript abspielt."""

    def __init__(self, provider_id: str, responses: list) -> None:
        self.PROVIDER_ID = provider_id
        self._responses = list(responses)
        self.calls: list[tuple[str, str]] = []

    def send_prompt(
        self, prompt: str, model: str, max_tokens: int | None = None,
        cap_reasoning: bool = False,
    ) -> APIResponse:
        self.calls.append((prompt, model))
        if not self._responses:
            raise AssertionError(
                f"{self.PROVIDER_ID}: unerwarteter Call Nr. {len(self.calls)}"
            )
        nxt = self._responses.pop(0)
        if isinstance(nxt, APIResponse):
            return nxt
        return APIResponse(
            status=APIStatus.RECEIVED, content=nxt, finish_reason="stop",
            tokens_used=100,
        )


def _selected_ids() -> list[str]:
    """Die IDs, die der PolicyScorer beim Default-Budget für IRGC auswählt."""
    return ["c01c", "c01d", "c01b", "c01a"]


def _analysis_script() -> list[str]:
    """S1, S2, S4 — in genau dieser Reihenfolge über das Analyse-Modell."""
    return [
        as_json(IRGC["refiner_response"]),
        as_json(IRGC["mapper_response"]),
        as_json([research_card(cid) for cid in _selected_ids()]),
    ]


def _research_script(ids: list[str] | None = None) -> list:
    """S5 — ein Verdikt je selektiertem Claim."""
    return [as_json(claim_verdict(cid)) for cid in (ids or _selected_ids())]


@pytest.fixture
def clients(monkeypatch):
    """Verdrahtet create_client/get_api_key auf die Doppelgänger."""
    made: dict[str, ScriptedClient] = {}

    def _make(analysis: list, research: list):
        made["anthropic"] = ScriptedClient("anthropic", analysis)
        made["perplexity"] = ScriptedClient("perplexity", research)
        monkeypatch.setattr(fpw, "get_api_key", lambda provider: "key-123")
        monkeypatch.setattr(fpw, "create_client", lambda provider, key: made[provider])
        return made

    return _make


def _config(**over) -> FactcheckPlusConfig:
    cfg = {
        "claims": IRGC["raw_claims"],
        "analysis_model": ANALYSIS_MODEL,
        "research_model": RESEARCH_MODEL,
        "budget": 8,
        "core_thesis": IRGC["core_thesis"],
        "source_title": "IRGC-Beispielvideo",
        "source_url": "https://www.youtube.com/watch?v=2yVJffNplJc",
    }
    cfg.update(over)
    return FactcheckPlusConfig(**cfg)


def _run(worker: FactcheckPlusWorker) -> dict:
    """Führt den Worker synchron aus und sammelt die Signale ein."""
    seen = {"status": [], "stages": [], "claims": [], "finished": [], "errors": []}
    worker.status_changed.connect(lambda s: seen["status"].append(s))
    worker.stage_changed.connect(lambda t, i, n: seen["stages"].append((t, i, n)))
    worker.claim_progress.connect(lambda i, n: seen["claims"].append((i, n)))
    worker.finished_ok.connect(lambda s, r: seen["finished"].append((s, r)))
    worker.error_occurred.connect(lambda m: seen["errors"].append(m))
    worker.run()  # direkt, ohne Event-Loop
    return seen


# --- Happy path -----------------------------------------------------------

def test_full_run_produces_a_rendered_section(clients) -> None:
    made = clients(_analysis_script(), _research_script())
    worker = FactcheckPlusWorker(_config())

    seen = _run(worker)

    assert seen["errors"] == []
    assert seen["status"] == ["running", "done"]
    assert len(seen["finished"]) == 1
    section, result = seen["finished"][0]
    assert "### FAKTENCHECK · VERIFIKATION PLUS" in section
    assert "#### Transparenz" in section
    assert "Policy: relevance-de-v1 · Budget: 8" in section
    assert result.status == "done"
    assert result.refined_count == 4
    assert result.selected_count == 4
    assert result.verified_count == 4
    assert result.failed_count == 0
    assert made["anthropic"].calls, "Analyse-Modell wurde benutzt"


def test_stages_use_the_right_model(clients) -> None:
    """PO §8.3: S1/S2/S4 über das Analyse-Modell, nur S5 über das Web-Modell."""
    made = clients(_analysis_script(), _research_script())
    _run(FactcheckPlusWorker(_config()))

    assert len(made["anthropic"].calls) == 3, "S1, S2, S4 — S3 ist LLM-frei"
    assert all(model == ANALYSIS_MODEL.model_id for _p, model in made["anthropic"].calls)

    assert len(made["perplexity"].calls) == 4, "ein Call PRO selektiertem Claim (D6a)"
    assert all(model == RESEARCH_MODEL.model_id for _p, model in made["perplexity"].calls)


def test_claims_are_researched_in_rank_order(clients) -> None:
    """Wichtigstes zuerst — sonst widerspricht das Modul seinem eigenen Zweck.

    Der PolicyScorer liefert die Auswahl in Rang-Reihenfolge (A vor B, innerhalb
    der Klasse nach priority). Der Worker muss sie so verifizieren und nicht in
    Refiner-Reihenfolge: Sonst stünde im Bericht der schwächste Claim oben, und
    ein Abbruch nach 2 von 8 hätte zwei beliebige statt der zwei wichtigsten
    geprüft.
    """
    made = clients(_analysis_script(), _research_script())
    seen = _run(FactcheckPlusWorker(_config()))

    section, _result = seen["finished"][0]
    # c01c (Quantität, priority 0.70) und c01d (Kausalzurechnung, 0.49) sind die
    # Kernclaims; c01a (Quellenexistenz, 0.20) ist der schwächste.
    order = [
        section.index("Die Analyse nennt eine Spanne"),
        section.index("Die genannten Kosten sind ursaechlich"),
        section.index("Die Methodik dieser Analyse"),
        section.index("Es existiert eine identifizierbare Analyse"),
    ]
    assert order == sorted(order), "Bericht folgt nicht dem Auswahlrang"
    assert "**1. „Die Analyse nennt eine Spanne" in section


def test_progress_is_reported_per_stage_and_per_claim(clients) -> None:
    clients(_analysis_script(), _research_script())
    seen = _run(FactcheckPlusWorker(_config()))

    indices = [i for _t, i, _n in seen["stages"]]
    assert indices[:5] == [1, 2, 3, 4, 5], "fünf Stufen, in Reihenfolge"
    assert all(n == 5 for _t, _i, n in seen["stages"])
    assert seen["claims"] == [(1, 4), (2, 4), (3, 4), (4, 4)]
    assert any("Recherchiere Claim 3/4" in t for t, _i, _n in seen["stages"])


def test_tokens_are_summed_across_all_stages(clients) -> None:
    clients(_analysis_script(), _research_script())
    seen = _run(FactcheckPlusWorker(_config()))
    _section, result = seen["finished"][0]
    # 3 Analyse-Calls + 4 Recherche-Calls, je 100 Tokens.
    assert result.tokens_used == 700


def test_source_hint_reaches_the_verifier(clients) -> None:
    """Der Unabhängigkeits-Riegel braucht die Identität der geprüften Quelle."""
    made = clients(_analysis_script(), _research_script())
    _run(FactcheckPlusWorker(_config()))

    for prompt, _model in made["perplexity"].calls:
        assert "IRGC-Beispielvideo" in prompt
        assert "darf NICHT als Beleg dienen" in prompt


def test_self_citation_is_rejected_end_to_end(clients) -> None:
    """Meldet das Web-Modell das geprüfte Video als Quelle → Retry, nicht durchwinken."""
    ids = _selected_ids()
    research = [
        as_json(claim_verdict(ids[0], sources=["https://youtu.be/2yVJffNplJc"])),
        as_json(claim_verdict(ids[0], sources=["https://www.tagesschau.de/x"])),
    ] + [as_json(claim_verdict(cid)) for cid in ids[1:]]
    made = clients(_analysis_script(), research)

    seen = _run(FactcheckPlusWorker(_config()))

    assert seen["errors"] == []
    assert len(made["perplexity"].calls) == 5, "4 Claims + 1 Reparatur-Retry"
    assert "Eigenbeleg unzulässig" in made["perplexity"].calls[1][0]


# --- Fehler und Abbruch ---------------------------------------------------

def test_no_claims_is_skipped_cleanly(clients) -> None:
    clients([], [])
    seen = _run(FactcheckPlusWorker(_config(claims=[])))

    assert seen["status"] == ["skipped"]
    section, result = seen["finished"][0]
    assert "Keine überprüfbaren Behauptungen gefunden" in section
    assert result.status == "skipped"


def test_missing_api_key_fails_without_calls(clients, monkeypatch) -> None:
    clients(_analysis_script(), _research_script())
    monkeypatch.setattr(fpw, "get_api_key", lambda provider: "")

    seen = _run(FactcheckPlusWorker(_config()))

    assert seen["status"] == ["error"]
    assert "Kein API-Key" in seen["errors"][0]
    assert seen["finished"] == []


def test_stage_error_ends_the_run_without_losing_the_analysis(clients) -> None:
    """S1 bricht den Vertrag zweimal → offener Fehler, aber kein Absturz."""
    broken = as_json([{"claim_id": "c01a", "parent_id": None, "original_text": "o",
                       "normalized_claim": "n", "claim_type": "hard_fact",
                       "entities": []}])  # Suffix ohne parent_id
    clients([broken, broken], [])

    seen = _run(FactcheckPlusWorker(_config()))

    assert seen["status"] == ["running", "error"]
    assert "ClaimRefiner" in seen["errors"][0]
    assert seen["finished"] == []


def test_single_claim_failure_is_not_fatal(clients) -> None:
    ids = _selected_ids()
    research = [
        APIResponse(status=APIStatus.ERROR, error_message="HTTP 503", http_status=503)
        if i == 1 else as_json(claim_verdict(cid))
        for i, cid in enumerate(ids)
    ]
    clients(_analysis_script(), research)

    seen = _run(FactcheckPlusWorker(_config()))

    assert seen["errors"] == []
    section, result = seen["finished"][0]
    assert result.status == "done"
    assert result.failed_count == 1
    assert result.verified_count == 4, "kein Claim verschwindet still"
    assert "Prüfung fehlgeschlagen" in section


def test_cancel_before_start_stops_early(clients) -> None:
    clients(_analysis_script(), _research_script())
    worker = FactcheckPlusWorker(_config())
    worker.cancel()

    seen = _run(worker)

    assert seen["finished"] == []
    assert seen["errors"] == []
    # v0.15.1: Ein Früh-Abbruch (vor/in S1-S4) läuft über die gemeinsame
    # Finalisierung — 'cancelled' wird gemeldet und der Status ist konsistent
    # (früher kehrte run() hier still zurück, result.status blieb 'running').
    assert seen["status"][-1] == "cancelled"
    assert worker.result.status == "cancelled"
    assert "cancelled" not in seen["errors"]  # Abbruch ist kein Fehler


def test_cancel_between_claims_keeps_the_partial_result(clients) -> None:
    """Ein Abbruch ist kein Fehler — das Teilergebnis wird angehängt."""
    made = clients(_analysis_script(), _research_script())
    worker = FactcheckPlusWorker(_config())

    # Nach dem ersten Claim abbrechen.
    worker.claim_progress.connect(
        lambda i, n: worker.cancel() if i == 1 else None
    )
    seen = _run(worker)

    assert seen["status"] == ["running", "cancelled"]
    section, result = seen["finished"][0]
    assert result.status == "cancelled"
    assert result.verified_count == 1
    assert len(made["perplexity"].calls) == 1, "keine weiteren Calls nach Abbruch"
    assert "Lauf vorzeitig abgebrochen" in section


def test_cancel_during_stage_exception_finalizes_cancelled(monkeypatch) -> None:
    """Wirft eine Stufe IM Abbruchmoment eine StageError, wird der Lauf trotzdem
    sauber als 'cancelled' finalisiert (v0.15.1) — nicht als Fehler und nicht
    still auf 'running' hängend. Deckt den Except-Pfad ab (Gegenstück zum
    None-Rückgabe-Pfad)."""
    worker = FactcheckPlusWorker(_config())

    class _CancelThenTruncate:
        """Bricht im S1-Call ab und liefert zugleich eine trunkierte Antwort."""

        PROVIDER_ID = "anthropic"

        def __init__(self) -> None:
            self.calls: list[tuple[str, str]] = []

        def send_prompt(self, prompt, model, max_tokens=None, cap_reasoning=False):
            self.calls.append((prompt, model))
            worker.cancel()  # Nutzer bricht während des laufenden S1-Calls ab
            # …und die Antwort ist trunkiert → run_json_stage wirft StageError,
            # BEVOR der Chunk-Loop should_cancel prüfen kann.
            return APIResponse(
                status=APIStatus.RECEIVED, content='[{"claim_id": "c01"',
                finish_reason="length",
            )

    analysis = _CancelThenTruncate()
    research = ScriptedClient("perplexity", [])
    mapping = {"anthropic": analysis, "perplexity": research}
    monkeypatch.setattr(fpw, "get_api_key", lambda provider: "key-123")
    monkeypatch.setattr(fpw, "create_client", lambda provider, key: mapping[provider])

    seen = _run(worker)

    assert seen["status"] == ["running", "cancelled"]
    assert worker.result.status == "cancelled"
    assert seen["errors"] == []          # Abbruch ist kein Fehler
    assert seen["finished"] == []        # kein renderbarer Abschnitt
    assert len(analysis.calls) == 1      # nach Abbruch keine weitere Stufe
    assert research.calls == []          # S5 läuft nicht mehr an


def test_debug_logger_is_called_per_stage(clients) -> None:
    clients(_analysis_script(), _research_script())

    logged: list[dict] = []

    class FakeLogger:
        def log_request(self, **kwargs):
            logged.append(kwargs["meta"])
            return "dir"

        def log_response(self, **kwargs):
            pass

    _run(FactcheckPlusWorker(_config(), debug_logger=FakeLogger()))

    stages = [m["stage"] for m in logged]
    assert stages[:3] == [
        "factcheck_plus.s1_refiner",
        "factcheck_plus.s2_mapper",
        "factcheck_plus.s4_planner",
    ]
    assert stages[3:] == ["factcheck_plus.s5_verifier"] * 4
    assert all(m["feature"] == "factcheck_plus" for m in logged)


def main() -> None:
    """Hinweis: Diese Suite braucht pytest (Fixtures/monkeypatch)."""
    print("Bitte mit pytest ausführen:  python -m pytest tests/test_factcheck_plus_worker.py")


if __name__ == "__main__":
    main()
