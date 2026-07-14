"""S1 — ClaimRefiner: Atomisierung, Attribution-Split, Normalisierung, Typ.

Zerlegt die Roh-Behauptungen aus Stufe 1 in **atomare Prüfeinheiten** (Theorie
§2.2), trennt Attributions- von Objekt-Claims (§2.3) und normalisiert sie zu
eigenständig prüfbaren Sätzen. Der Refiner **bewertet nicht** — weder Relevanz
noch Wahrheit (Theorie §8.5); das übernehmen S2/S3 bzw. S5.
"""
from __future__ import annotations

import re

from .llm_stage import PromptClient, run_json_stage
from .models import RefinedClaim
from .prompts import build_refiner_prompt, make_claim_id

STAGE_NAME = "ClaimRefiner"

# Gültige Claim-ID: 'c01' (ungeteilt) oder 'c01a'/'c01ab' (Teil einer Zerlegung).
CLAIM_ID_RE = re.compile(r"^c\d{2,}([a-z]{1,2})?$")


def _split_suffix(claim_id: str) -> str:
    """Gibt den Buchstaben-Suffix einer Claim-ID zurück ('' bei ungeteilt)."""
    match = CLAIM_ID_RE.match(claim_id)
    return match.group(1) or "" if match else ""


def validate_refined(raw: list, input_ids: list[str]) -> list[RefinedClaim]:
    """Validiert den S1-Rohoutput gegen Schema **und** ID-Konvention.

    Die Fehlermeldungen sind bewusst konkret — sie gehen bei einem Vertragsbruch
    wörtlich in den Reparatur-Prompt (:func:`llm_stage.run_json_stage`).

    Geprüft wird:
      1. Schema je Element (:class:`RefinedClaim.from_dict`).
      2. ID-Form ('c01' bzw. 'c01a') und Eindeutigkeit.
      3. ID-Konvention: Suffix ⇔ `parent_id` gesetzt und Präfix-treu.
      4. Vollständigkeit: jede Eingangs-ID kommt vor — unverändert oder als
         `parent_id` ihrer Teile (kein Claim geht still verloren).

    Nicht geprüft wird, ob `claim_type` faktisch ist: rutscht doch eine Meinung
    durch, fängt sie Gate 1 des PolicyScorers ab (deshalb kennt der Vertrag
    `opinion`/`interpretation` überhaupt).

    Args:
        raw: Geparste JSON-Liste aus der Modellantwort.
        input_ids: Die vorgelegten Eingangs-IDs ('c01', 'c02', …).

    Returns:
        Die validierten :class:`RefinedClaim`-Objekte in Modellreihenfolge.

    Raises:
        ValueError: Bei Verletzung von ID-Form, Eindeutigkeit oder Vollständigkeit.
        SchemaError: Bei Schemaverletzung eines Elements (Subklasse von ValueError).
    """
    if not raw:
        raise ValueError("Leeres Array — erwartet wurde mindestens eine Prüfeinheit.")

    claims = [RefinedClaim.from_dict(item) for item in raw]
    known = set(input_ids)
    seen: set[str] = set()
    covered: set[str] = set()

    for claim in claims:
        cid = claim.claim_id
        if not CLAIM_ID_RE.match(cid):
            raise ValueError(
                f"claim_id '{cid}' verletzt die ID-Konvention: erlaubt sind die "
                f"vorgelegte ID (z.B. 'c01') oder sie mit Kleinbuchstaben-Suffix "
                f"(z.B. 'c01a')."
            )
        if cid in seen:
            raise ValueError(f"claim_id '{cid}' kommt mehrfach vor — IDs müssen eindeutig sein.")
        seen.add(cid)

        suffix = _split_suffix(cid)
        base = cid[:len(cid) - len(suffix)] if suffix else cid

        if suffix:
            if not claim.parent_id:
                raise ValueError(
                    f"claim_id '{cid}' ist eine Zerlegung, aber parent_id fehlt — "
                    f"erwartet: parent_id '{base}'."
                )
            if claim.parent_id != base:
                raise ValueError(
                    f"claim_id '{cid}' hat parent_id '{claim.parent_id}', erwartet "
                    f"wurde '{base}' (die ID vor dem Buchstaben-Suffix)."
                )
        elif claim.parent_id:
            raise ValueError(
                f"claim_id '{cid}' ist ungeteilt, trägt aber parent_id "
                f"'{claim.parent_id}' — ungeteilte Claims haben parent_id null."
            )

        if base not in known:
            raise ValueError(
                f"claim_id '{cid}' verweist auf die unbekannte Ursprungs-ID '{base}'. "
                f"Erlaubt sind nur die vorgelegten IDs: {sorted(known)}."
            )
        covered.add(base)

    missing = sorted(known - covered)
    if missing:
        raise ValueError(
            f"Diese vorgelegten Behauptungen fehlen in der Antwort: {missing}. "
            f"Jede ID muss vorkommen — unverändert oder als parent_id ihrer Teile."
        )
    return claims


class ClaimRefiner:
    """S1-Stufe: Roh-Behauptungen → atomare, normalisierte Prüfeinheiten.

    Attributes:
        client: LLM-Client (``send_prompt(prompt, model) -> APIResponse``).
        model: Modell-ID — das Analyse-Modell (kein eigener Picker, Spec §8.3).
    """

    def __init__(self, client: PromptClient, model: str) -> None:
        self.client = client
        self.model = model

    def refine(
        self, claims: list[str], core_thesis: str = "", source_hint: str = "",
    ) -> list[RefinedClaim]:
        """Zerlegt und normalisiert die vorgelegten Behauptungen.

        Args:
            claims: Roh-Behauptungen aus Stufe 1 (Basisfakt-bereinigt, gekappt).
            core_thesis: SOMAS-Kernthese/Framing — nur Kontext, wird nicht bewertet.
            source_hint: Titel/URL der geprüften Quelle, nur zur Einordnung.

        Returns:
            Die atomisierten :class:`RefinedClaim`-Objekte.

        Raises:
            ValueError: Wenn ``claims`` leer ist.
            StageError: Bei API-Fehler oder Vertragsbruch nach dem Reparatur-Retry.
        """
        if not claims:
            raise ValueError("Keine Behauptungen übergeben — S1 hat nichts zu tun.")

        input_ids = [make_claim_id(i) for i in range(1, len(claims) + 1)]
        prompt = build_refiner_prompt(claims, core_thesis, source_hint)
        return run_json_stage(
            client=self.client,
            model=self.model,
            prompt=prompt,
            parse=lambda raw: validate_refined(raw, input_ids),
            stage_name=STAGE_NAME,
        )
