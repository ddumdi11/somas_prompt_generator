"""S1 — ClaimRefiner: Atomisierung, Attribution-Split, Normalisierung, Typ.

Zerlegt die Roh-Behauptungen aus Stufe 1 in **atomare Prüfeinheiten** (Theorie
§2.2), trennt Attributions- von Objekt-Claims (§2.3) und normalisiert sie zu
eigenständig prüfbaren Sätzen. Der Refiner **bewertet nicht** — weder Relevanz
noch Wahrheit (Theorie §8.5); das übernehmen S2/S3 bzw. S5.
"""
from __future__ import annotations

import re
from typing import Callable, Optional

from .llm_stage import PromptClient, run_json_stage
from .models import RefinedClaim
from .prompts import build_refiner_prompt, make_claim_id

STAGE_NAME = "ClaimRefiner"

# Chunk-Größe fürs S1-Batching (v0.15.1). Der Ein-Call-Refiner skaliert nicht über
# ~40 Roh-Claims (jede Prüfeinheit echot original_text + normalized_claim → Output
# sprengt das Stage-Budget). Batches à 15 Roh-Claims halten den Output je Call klein;
# ≤ 15 Claims → genau EIN Call, unverändertes Verhalten (wichtigste Regression).
S1_CHUNK_SIZE = 15

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


def validate_merged_refined(
    claims: list[RefinedClaim], input_ids: list[str]
) -> None:
    """Globale Prüfung des GEMERGTEN S1-Ergebnisses über alle Chunks (v0.15.1).

    Läuft NACH dem Merge auf den bereits geparsten Objekten (Schema, ID-Form und
    parent_id-Konvention sind je Chunk in :func:`validate_refined` geprüft). Deckt
    das Chunk-übergreifende Sicherheitsnetz ab:

      - **Eindeutigkeit** aller claim_ids über Chunk-Grenzen (strukturell durch
        disjunkte Eingangs-Mengen schon ausgeschlossen — hier als Riegel).
      - **Vollständigkeit**: jede Eingangs-ID kommt vor (unverändert oder als
        parent_id ihrer Teile), auch chunk-übergreifend kein stiller Verlust.

    Args:
        claims: Die gemergten :class:`RefinedClaim`-Objekte aller Chunks.
        input_ids: ALLE vorgelegten Eingangs-IDs (global, 'c01'…'cNN').

    Raises:
        ValueError: Bei chunk-übergreifendem Duplikat oder fehlender Behauptung.
    """
    seen = [c.claim_id for c in claims]
    duplicates = sorted({cid for cid in seen if seen.count(cid) > 1})
    if duplicates:
        raise ValueError(
            f"claim_id(s) über Chunk-Grenzen doppelt: {duplicates}. "
            f"Jede ID darf nur einmal vorkommen."
        )
    covered = {(c.parent_id or c.claim_id) for c in claims}
    missing = sorted(set(input_ids) - covered)
    if missing:
        raise ValueError(
            f"Nach dem Merge fehlen Behauptungen: {missing}. "
            f"Jede vorgelegte ID muss über die Chunks hinweg vorkommen."
        )


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
        anchor_date: str = "",
        on_progress: Optional[Callable[[int, int], None]] = None,
        should_cancel: Optional[Callable[[], bool]] = None,
    ) -> list[RefinedClaim]:
        """Zerlegt und normalisiert die vorgelegten Behauptungen (chunk-fähig).

        Roh-Claims > :data:`S1_CHUNK_SIZE` werden in Batches aufgeteilt und je Batch
        mit einem eigenen ``run_json_stage``-Call verarbeitet (v0.15.1). Die
        globalen IDs ``cNN`` bleiben über die Chunks stabil (``start_index``); jeder
        Chunk trägt DENSELBEN Kontext (Kernthese, Zeitanker). Reparatur-Retry und
        Trunkierungs-Gate gelten PRO Chunk (unveränderte ``llm_stage``-Semantik).
        ``≤ S1_CHUNK_SIZE`` Claims → genau EIN Call, unverändertes Verhalten.

        Args:
            claims: Roh-Behauptungen aus Stufe 1 (Basisfakt-bereinigt, ungekappt).
            core_thesis: SOMAS-Kernthese/Framing — nur Kontext, wird nicht bewertet.
            source_hint: Titel/URL der geprüften Quelle, nur zur Einordnung.
            anchor_date: Optionales Veröffentlichungsdatum (v0.15.0, formatiert).
            on_progress: Optionaler Callback ``(chunk_index, total_chunks)``, vor
                jedem Chunk (1-basiert) — speist die Fortschrittsanzeige.
            should_cancel: Optionaler Callback; liefert er ``True``, bricht der Lauf
                VOR dem nächsten Chunk ab und gibt das bisherige Teilergebnis OHNE
                globale Merge-Prüfung zurück (der Aufrufer verwirft es bei Abbruch).

        Returns:
            Die atomisierten :class:`RefinedClaim`-Objekte (über alle Chunks gemergt).

        Raises:
            ValueError: Wenn ``claims`` leer ist oder das Merge-Ergebnis unvollständig.
            StageError: Bei API-Fehler oder Vertragsbruch nach dem Reparatur-Retry.
        """
        if not claims:
            raise ValueError("Keine Behauptungen übergeben — S1 hat nichts zu tun.")

        all_input_ids = [make_claim_id(i) for i in range(1, len(claims) + 1)]
        chunks = [
            claims[i:i + S1_CHUNK_SIZE] for i in range(0, len(claims), S1_CHUNK_SIZE)
        ]
        total = len(chunks)
        merged: list[RefinedClaim] = []

        for ci, chunk in enumerate(chunks):
            if should_cancel is not None and should_cancel():
                return merged  # Abbruch: Teilergebnis ohne globale Prüfung (Aufrufer verwirft)
            if on_progress is not None:
                on_progress(ci + 1, total)

            offset = ci * S1_CHUNK_SIZE
            chunk_ids = all_input_ids[offset:offset + len(chunk)]
            prompt = build_refiner_prompt(
                chunk, core_thesis, source_hint, anchor_date,
                start_index=offset + 1,
            )
            chunk_result = run_json_stage(
                client=self.client,
                model=self.model,
                prompt=prompt,
                parse=lambda raw, ids=chunk_ids: validate_refined(raw, ids),
                stage_name=STAGE_NAME,
            )
            merged.extend(chunk_result)

        validate_merged_refined(merged, all_input_ids)
        return merged
