"""Gemeinsame Helfer für die Faktencheck-Plus-Stufentests (S1/S2, PR 2).

Bewusst ohne ``test_``-Präfix — pytest sammelt das Modul nicht als Testdatei ein.
Die Referenzfälle liegen als JSON in ``tests/fixtures/`` und sind damit
eigenständiger Bestandteil der Testsuite (kein Verweis auf unversionierte
Arbeitsnotizen).
"""
import json
from pathlib import Path

from src.core.api_client import APIResponse, APIStatus

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"


def load_case(name: str) -> dict:
    """Lädt einen Atomisierungs-Referenzfall aus ``tests/fixtures/``.

    Args:
        name: Fall-Kürzel, z.B. "irgc" oder "katar747".

    Returns:
        Das geparste Fixture-Dict (raw_claims, refiner_response, mapper_response …).
    """
    path = FIXTURE_DIR / f"factcheck_plus_{name}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def as_json(payload: object) -> str:
    """Serialisiert eine Fixture-Antwort so, wie ein Modell sie liefern würde."""
    return json.dumps(payload, ensure_ascii=False)


class FakeClient:
    """Skript-gesteuerter LLM-Client-Doppelgänger (kein Netzwerk).

    Gibt die vorgegebenen Antworten der Reihe nach zurück und protokolliert
    jeden gesendeten Prompt — so lässt sich prüfen, ob der Reparatur-Retry
    überhaupt und mit welchem Inhalt rausging.

    Attributes:
        prompts: Alle gesendeten Prompts in Aufrufreihenfolge.
        models: Alle verwendeten Modell-IDs in Aufrufreihenfolge.
    """

    def __init__(self, responses: list) -> None:
        """Initialisiert den Doppelgänger.

        Args:
            responses: Liste aus ``str`` (wird zu einer RECEIVED-Antwort mit
                diesem Inhalt) oder fertigen :class:`APIResponse`-Objekten.
        """
        self._responses = list(responses)
        self.prompts: list[str] = []
        self.models: list[str] = []

    def send_prompt(self, prompt: str, model: str) -> APIResponse:
        """Liefert die nächste skriptierte Antwort und protokolliert den Aufruf."""
        self.prompts.append(prompt)
        self.models.append(model)
        if not self._responses:
            raise AssertionError(
                f"FakeClient: unerwarteter {len(self.prompts)}. Aufruf — "
                f"keine Antwort mehr im Skript."
            )
        nxt = self._responses.pop(0)
        if isinstance(nxt, APIResponse):
            return nxt
        return APIResponse(status=APIStatus.RECEIVED, content=nxt, finish_reason="stop")

    @property
    def call_count(self) -> int:
        """Anzahl der bisher erfolgten Aufrufe."""
        return len(self.prompts)


def error_response(message: str = "HTTP 500 — Provider nicht erreichbar") -> APIResponse:
    """Baut eine Transport-/API-Fehlerantwort (löst KEINEN Reparatur-Retry aus)."""
    return APIResponse(status=APIStatus.ERROR, error_message=message, http_status=500)


def research_card(cid: str, **over) -> dict:
    """Baut eine schema-gültige Recherchekarte (S4-Output) für Tests.

    Args:
        cid: Die claim_id.
        **over: Felder, die überschrieben werden sollen.

    Returns:
        Das Karten-Dict.
    """
    card = {
        "claim_id": cid,
        "research_questions": [f"Welche Quelle belegt {cid}?"],
        "counter_hypotheses": [f"{cid} beruht auf einer Fehlzuschreibung."],
        "source_priorities": ["Primärquellen", "Fachinstitutionen"],
        "required_evidence": ["unabhängige Bestätigung"],
        "forbidden_shortcuts": ["Snippet als Beleg werten"],
        "canonical_targets": [],
        "language_hints": [],
    }
    card.update(over)
    return card


def claim_verdict(cid: str, **over) -> dict:
    """Baut ein schema- und leitplanken-gültiges Verdikt (S5-Output) für Tests.

    Args:
        cid: Die claim_id.
        **over: Felder, die überschrieben werden sollen.

    Returns:
        Das Verdikt-Dict.
    """
    verdict = {
        "claim_id": cid,
        "verdict": "supported",
        "reason": "Zwei unabhängige Primärquellen stützen die Angabe.",
        "supported_subclaim": None,
        "sources": ["https://example.org/primaerquelle"],
        "open_questions": None,
    }
    verdict.update(over)
    return verdict
