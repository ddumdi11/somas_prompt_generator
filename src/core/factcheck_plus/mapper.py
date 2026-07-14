"""S2 — ArgumentMapper: Argumentrolle, kontrafaktischer Impact, 0–5-Ratings.

Füllt je Prüfeinheit die Felder, aus denen der deterministische PolicyScorer (S3)
seine Auswahl rechnet. Der Mapper **wählt nicht aus und gewichtet nicht**
(Theorie §8.5) — er kennt die Policy-Gewichte gar nicht.
"""
from __future__ import annotations

from .llm_stage import run_json_stage
from .models import ArgumentMapping
from .prompts import build_mapper_prompt

STAGE_NAME = "ArgumentMapper"


def validate_mappings(raw: list, expected_ids: list[str]) -> list[ArgumentMapping]:
    """Validiert den S2-Rohoutput gegen Schema **und** ID-Echo.

    Die ID-Bijektion prüft :func:`models.join_claims` später ohnehin hart — aber
    dort erst NACH der Stufe, mit einem nackten ``ValueError``. Hier fällt der
    Bruch früh genug auf, um den Reparatur-Retry mit einer konkreten Meldung zu
    füttern; ``join_claims`` bleibt das letzte Sicherheitsnetz.

    Args:
        raw: Geparste JSON-Liste aus der Modellantwort.
        expected_ids: Die claim_ids aus S1 — exakt diese müssen zurückkommen.

    Returns:
        Die validierten :class:`ArgumentMapping`-Objekte in Modellreihenfolge.

    Raises:
        ValueError: Bei fehlenden, unbekannten oder doppelten IDs.
        SchemaError: Bei Schemaverletzung (Rolle, Impact, Rating-Bereich …).
    """
    if not raw:
        raise ValueError("Leeres Array — erwartet wurde ein Mapping je Prüfeinheit.")

    mappings = [ArgumentMapping.from_dict(item) for item in raw]

    seen: list[str] = [m.claim_id for m in mappings]
    duplicates = sorted({cid for cid in seen if seen.count(cid) > 1})
    if duplicates:
        raise ValueError(
            f"Diese claim_ids kommen mehrfach vor: {duplicates}. Jede ID genau einmal."
        )

    expected = set(expected_ids)
    got = set(seen)
    unknown = sorted(got - expected)
    if unknown:
        raise ValueError(
            f"Unbekannte claim_ids: {unknown}. Erlaubt sind ausschließlich die "
            f"vorgelegten IDs: {sorted(expected)}."
        )
    missing = sorted(expected - got)
    if missing:
        raise ValueError(
            f"Diese claim_ids fehlen in der Antwort: {missing}. Gib GENAU die "
            f"vorgelegten IDs zurück — jede genau einmal."
        )
    return mappings


class ArgumentMapper:
    """S2-Stufe: Prüfeinheiten → Argumentrolle + Impact + Ratings.

    Attributes:
        client: LLM-Client (``send_prompt(prompt, model) -> APIResponse``).
        model: Modell-ID — das Analyse-Modell (kein eigener Picker, Spec §8.3).
    """

    def __init__(self, client, model: str) -> None:
        self.client = client
        self.model = model

    def map_claims(self, refined: list, core_thesis: str = "") -> list[ArgumentMapping]:
        """Bewertet die Felder je Prüfeinheit (ohne Auswahl, ohne Gewichtung).

        Args:
            refined: Die :class:`models.RefinedClaim`-Objekte aus S1.
            core_thesis: SOMAS-Kernthese — Bezugspunkt für `thesis_proximity`.

        Returns:
            Die :class:`ArgumentMapping`-Objekte, eines je Prüfeinheit.

        Raises:
            ValueError: Wenn ``refined`` leer ist.
            StageError: Bei API-Fehler oder Vertragsbruch nach dem Reparatur-Retry.
        """
        if not refined:
            raise ValueError("Keine Prüfeinheiten übergeben — S2 hat nichts zu tun.")

        payload = [
            {
                "claim_id": rc.claim_id,
                "normalized_claim": rc.normalized_claim,
                "claim_type": rc.claim_type,
            }
            for rc in refined
        ]
        expected_ids = [rc.claim_id for rc in refined]
        prompt = build_mapper_prompt(payload, core_thesis)
        return run_json_stage(
            client=self.client,
            model=self.model,
            prompt=prompt,
            parse=lambda raw: validate_mappings(raw, expected_ids),
            stage_name=STAGE_NAME,
        )
