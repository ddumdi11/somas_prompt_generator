"""S2 — ArgumentMapper: Argumentrolle, kontrafaktischer Impact, 0–5-Ratings.

Füllt je Prüfeinheit die Felder, aus denen der deterministische PolicyScorer (S3)
seine Auswahl rechnet. Der Mapper **wählt nicht aus und gewichtet nicht**
(Theorie §8.5) — er kennt die Policy-Gewichte gar nicht.
"""
from __future__ import annotations

from typing import Callable, Optional

from .llm_stage import PromptClient, run_json_stage
from .models import ArgumentMapping
from .prompts import build_mapper_prompt

STAGE_NAME = "ArgumentMapper"

# Chunk-Größe fürs S2-Batching (v0.15.1). Bei Claim-Fluten bekommt S2 ~80–100
# Prüfeinheiten und würde als Nächstes das Stage-Budget sprengen (real: 30k Output
# bei 28 Einheiten). Batches à 20 Einheiten; ≤ 20 → genau EIN Call (Regression).
# Offset-frei: der Mapper ECHOT die IDs, er erzeugt sie nicht — Slicing genügt.
S2_CHUNK_SIZE = 20


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


def validate_merged_mappings(
    mappings: list[ArgumentMapping], expected_ids: list[str]
) -> None:
    """Globale Prüfung des GEMERGTEN S2-Ergebnisses über alle Chunks (v0.15.1).

    Schema und Bijektion je Chunk prüft :func:`validate_mappings`; hier wird nach
    dem Merge nur noch die Eindeutigkeit und Vollständigkeit über alle Prüfeinheiten
    gesichert (``join_claims`` bleibt das letzte Netz).

    Args:
        mappings: Die gemergten :class:`ArgumentMapping`-Objekte aller Chunks.
        expected_ids: ALLE erwarteten claim_ids (aus dem vollständigen S1-Ergebnis).

    Raises:
        ValueError: Bei chunk-übergreifendem Duplikat oder fehlender Prüfeinheit.
    """
    seen = [m.claim_id for m in mappings]
    duplicates = sorted({cid for cid in seen if seen.count(cid) > 1})
    if duplicates:
        raise ValueError(
            f"claim_id(s) über Chunk-Grenzen doppelt: {duplicates}. Jede ID einmal."
        )
    missing = sorted(set(expected_ids) - set(seen))
    if missing:
        raise ValueError(
            f"Nach dem Merge fehlen Mappings für: {missing}. "
            f"Jede Prüfeinheit muss über die Chunks hinweg gemappt sein."
        )


class ArgumentMapper:
    """S2-Stufe: Prüfeinheiten → Argumentrolle + Impact + Ratings.

    Attributes:
        client: LLM-Client (``send_prompt(prompt, model) -> APIResponse``).
        model: Modell-ID — das Analyse-Modell (kein eigener Picker, Spec §8.3).
    """

    def __init__(self, client: PromptClient, model: str) -> None:
        self.client = client
        self.model = model

    def map_claims(
        self, refined: list, core_thesis: str = "",
        on_progress: Optional[Callable[[int, int], None]] = None,
        should_cancel: Optional[Callable[[], bool]] = None,
    ) -> list[ArgumentMapping]:
        """Bewertet die Felder je Prüfeinheit (ohne Auswahl, ohne Gewichtung).

        Prüfeinheiten > :data:`S2_CHUNK_SIZE` werden in Batches verarbeitet
        (v0.15.1). Da der Mapper die IDs nur echot (kein ``start_index`` nötig),
        genügt es, ``refined`` zu slicen; die Bijektions-Prüfung läuft PRO Chunk
        (Brüche landen im chunk-lokalen Reparatur-Retry), die Vollständigkeit nach
        dem Merge. ``≤ S2_CHUNK_SIZE`` → genau EIN Call (unverändertes Verhalten).

        Args:
            refined: Die :class:`models.RefinedClaim`-Objekte aus S1.
            core_thesis: SOMAS-Kernthese — Bezugspunkt für `thesis_proximity`.
            on_progress: Optionaler Callback ``(chunk_index, total_chunks)``.
            should_cancel: Optionaler Callback; ``True`` → Abbruch vor dem nächsten
                Chunk, Teilergebnis ohne globale Prüfung (Aufrufer verwirft es).

        Returns:
            Die :class:`ArgumentMapping`-Objekte, eines je Prüfeinheit (gemergt).

        Raises:
            ValueError: Wenn ``refined`` leer ist oder das Merge-Ergebnis unvollständig.
            StageError: Bei API-Fehler oder Vertragsbruch nach dem Reparatur-Retry.
        """
        if not refined:
            raise ValueError("Keine Prüfeinheiten übergeben — S2 hat nichts zu tun.")

        all_expected_ids = [rc.claim_id for rc in refined]
        chunks = [
            refined[i:i + S2_CHUNK_SIZE] for i in range(0, len(refined), S2_CHUNK_SIZE)
        ]
        total = len(chunks)
        merged: list[ArgumentMapping] = []

        for ci, chunk in enumerate(chunks):
            if should_cancel is not None and should_cancel():
                return merged  # Abbruch: Teilergebnis ohne globale Prüfung
            if on_progress is not None:
                on_progress(ci + 1, total)

            payload = [
                {
                    "claim_id": rc.claim_id,
                    "normalized_claim": rc.normalized_claim,
                    "claim_type": rc.claim_type,
                }
                for rc in chunk
            ]
            chunk_ids = [rc.claim_id for rc in chunk]
            prompt = build_mapper_prompt(payload, core_thesis)
            chunk_result = run_json_stage(
                client=self.client,
                model=self.model,
                prompt=prompt,
                parse=lambda raw, ids=chunk_ids: validate_mappings(raw, ids),
                stage_name=STAGE_NAME,
            )
            merged.extend(chunk_result)

        validate_merged_mappings(merged, all_expected_ids)
        return merged
