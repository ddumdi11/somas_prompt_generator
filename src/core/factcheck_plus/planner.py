"""S4 — ResearchPlanner: je selektiertem Claim eine Recherchekarte.

Ein Call für alle selektierten Claims (Spec §3/S4). Der Planner schreibt den
**Rechercheauftrag** statt der offenen Frage „Ist das wahr?" — offene
Wahrheitsfragen erzeugen Bestätigungsfehler, und ein Claim-Blob als Such-Seed
findet bei Nischenthemen nichts Relevantes (Theorie §5.1).

Der Planner **recherchiert nicht und urteilt nicht** (Theorie §8.5).
"""
from __future__ import annotations

from .llm_stage import PromptClient, run_json_stage
from .models import ResearchCard
from .prompts import FORBIDDEN_SHORTCUTS, build_planner_prompt

STAGE_NAME = "ResearchPlanner"


def validate_cards(raw: list, expected_ids: list[str]) -> list[ResearchCard]:
    """Validiert den S4-Rohoutput gegen Schema, ID-Echo und Pflichtinhalte.

    Über das Schema hinaus wird geprüft, dass die beiden Felder, die den
    Rechercheauftrag überhaupt erst zu einem machen, nicht leer sind:
    ``research_questions`` (sonst bleibt es die offene Wahrheitsfrage) und
    ``counter_hypotheses`` (der Riegel gegen Bestätigungsfehler, Theorie §5.1).

    ``canonical_targets`` und ``language_hints`` sind Pflicht**felder**, aber
    zulässigerweise leere Listen — nicht jeder Claim zeigt auf ein Artefakt oder
    einen fremdsprachigen Raum. Das Schema erzwingt ihre Anwesenheit; der Inhalt
    ist claim-abhängig.

    ``forbidden_shortcuts`` wird hier **deterministisch gesetzt**, nicht vom
    Modell erfragt: Die verbotenen Abkürzungen sind Policy-Konstante (Theorie
    §8.4 „nicht dem Modell überlassen"). Ein Echo würde nur Token kosten und
    könnte driften.

    Args:
        raw: Geparste JSON-Liste aus der Modellantwort.
        expected_ids: Die claim_ids der selektierten Claims.

    Returns:
        Die validierten :class:`ResearchCard`-Objekte in Modellreihenfolge.

    Raises:
        ValueError: Bei fehlenden/unbekannten/doppelten IDs oder leeren Pflichtlisten.
        SchemaError: Bei Schemaverletzung.
    """
    if not raw:
        raise ValueError("Leeres Array — erwartet wurde eine Recherchekarte je Claim.")

    cards = [ResearchCard.from_dict(item) for item in raw]

    seen = [c.claim_id for c in cards]
    duplicates = sorted({cid for cid in seen if seen.count(cid) > 1})
    if duplicates:
        raise ValueError(
            f"Diese claim_ids kommen mehrfach vor: {duplicates}. Jede ID genau einmal."
        )
    expected, got = set(expected_ids), set(seen)
    unknown = sorted(got - expected)
    if unknown:
        raise ValueError(
            f"Unbekannte claim_ids: {unknown}. Erlaubt sind ausschließlich die "
            f"vorgelegten IDs: {sorted(expected)}."
        )
    missing = sorted(expected - got)
    if missing:
        raise ValueError(
            f"Für diese claim_ids fehlt die Recherchekarte: {missing}. Gib GENAU "
            f"die vorgelegten IDs zurück — jede genau einmal."
        )

    for card in cards:
        if not [q for q in card.research_questions if q.strip()]:
            raise ValueError(
                f"Karte '{card.claim_id}': `research_questions` ist leer. Ein "
                f"Rechercheauftrag braucht konkrete, einzeln beantwortbare "
                f"Teilfragen — die offene Frage 'Ist das wahr?' ist keiner."
            )
        if not [h for h in card.counter_hypotheses if h.strip()]:
            raise ValueError(
                f"Karte '{card.claim_id}': `counter_hypotheses` ist leer. "
                f"Gegenhypothesen sind Pflicht (Riegel gegen Bestätigungsfehler) — "
                f"was müsste zutreffen, damit die Behauptung NICHT stimmt?"
            )
        # Policy überschreibt, was das Modell hier auch immer geliefert hätte.
        card.forbidden_shortcuts = list(FORBIDDEN_SHORTCUTS)
    return cards


class ResearchPlanner:
    """S4-Stufe: selektierte Claims → Recherchekarten (ein Call für alle).

    Attributes:
        client: LLM-Client (:class:`llm_stage.PromptClient`).
        model: Modell-ID — das Analyse-Modell (kein eigener Picker, Spec §8.3).
    """

    def __init__(self, client: PromptClient, model: str) -> None:
        self.client = client
        self.model = model

    def plan(
        self, claims: list, core_thesis: str = "", anchor_date: str = "",
    ) -> list[ResearchCard]:
        """Schreibt je Claim eine Recherchekarte.

        Args:
            claims: Die selektierten :class:`models.RefinedClaim`-Objekte.
            core_thesis: SOMAS-Kernthese — nur Kontext.
            anchor_date: Optionales Veröffentlichungsdatum (v0.15.0, formatiert)
                als Zeitanker-Kontext; "" → keine Datums-Zeile.

        Returns:
            Die :class:`ResearchCard`-Objekte, eine je Claim.

        Raises:
            ValueError: Wenn ``claims`` leer ist.
            StageError: Bei API-Fehler oder Vertragsbruch nach dem Reparatur-Retry.
        """
        if not claims:
            raise ValueError("Keine selektierten Claims übergeben — S4 hat nichts zu tun.")

        payload = [
            {
                "claim_id": rc.claim_id,
                "normalized_claim": rc.normalized_claim,
                "claim_type": rc.claim_type,
                "entities": rc.entities,
                "timeframe": rc.timeframe,
                "metric": rc.metric,
            }
            for rc in claims
        ]
        expected_ids = [rc.claim_id for rc in claims]
        prompt = build_planner_prompt(payload, core_thesis, anchor_date)
        return run_json_stage(
            client=self.client,
            model=self.model,
            prompt=prompt,
            parse=lambda raw: validate_cards(raw, expected_ids),
            stage_name=STAGE_NAME,
        )
