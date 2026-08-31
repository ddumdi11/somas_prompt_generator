"""S5 — Recherche + Verdikt: ein Call PRO Claim.

Das ist D6a (Spec §3/S5): Der Behauptungs-Blob als ein Request führt zu
thematisch fremden Quellen und pauschalem „nicht überprüfbar"; ein eigener Call
je Claim gibt jedem sein eigenes Token-Budget und einen gezielten Such-Seed.

Zwei Eigenschaften sind hier zentral:
  - **Einzelfehler sind nicht fatal.** Scheitert ein Claim-Call, bekommt genau
    dieser Claim einen sichtbaren „Prüfung fehlgeschlagen"-Vermerk; die übrigen
    laufen weiter.
  - **Abbrechbar zwischen Claims** über ``should_cancel`` — der Worker (PR 4)
    reicht damit den Abbrechen-Button durch, ohne dass dieses Package Qt kennt.

Recherche und Verdikt liegen bewusst noch in EINEM Call (Theorie §6.2 nennt die
Trennung als Zielbild; die Übergangslösung ist für v0.13.0 gesetzt, Spec §8.6).
"""
from __future__ import annotations

import logging
from typing import Callable

from .llm_stage import (
    PromptClient, StageError, extract_json_object, run_json_stage,
)
from .models import ClaimVerdict
from .prompts import build_claim_verification_prompt
from .verdict import (
    FAILED_REASON_PREFIX, check_forbidden_sources, check_verdict_guardrails,
)

logger = logging.getLogger(__name__)

STAGE_NAME = "ClaimVerifier"


def validate_verdict(raw: dict, expected_id: str, source_hint: str = "") -> ClaimVerdict:
    """Validiert einen S5-Rohoutput gegen Schema **und** Taxonomie-Leitplanken.

    Die Leitplanken aus Theorie §6.3 werden hier durchgesetzt, nicht nur im
    Prompt erbeten: kein positives Teilverdikt ohne benannten belegten Teilclaim,
    keine Rechercheerfolg-Behauptung ohne Quelle — und **kein Eigenbeleg**: der
    Unabhängigkeits-Riegel gilt auch dann, wenn das Modell die Prompt-Regel
    ignoriert. Jeder Verstoß ist ein Vertragsbruch und geht in den Reparatur-Retry.

    Args:
        raw: Geparstes JSON-Objekt aus der Modellantwort.
        expected_id: Die claim_id, die zurückkommen muss.
        source_hint: Identität der geprüften Quelle ("Titel URL"). Leer = der
            Eigenbeleg-Riegel kann nicht greifen (keine Referenz zum Vergleichen).

    Returns:
        Das validierte :class:`ClaimVerdict`.

    Raises:
        ValueError: Bei falscher claim_id oder verletzter Leitplanke.
        SchemaError: Bei Schemaverletzung (unbekanntes Verdikt, fehlendes Feld …).
    """
    verdict = ClaimVerdict.from_dict(raw)
    if verdict.claim_id != expected_id:
        raise ValueError(
            f"Falsche claim_id '{verdict.claim_id}' — geprüft werden sollte "
            f"'{expected_id}'. Gib genau diese ID zurück."
        )
    if not verdict.reason.strip():
        raise ValueError(
            f"Verdikt '{verdict.verdict}' ohne Begründung: `reason` ist Pflicht "
            f"(1–2 Sätze, inhaltlich begründet)."
        )
    check_forbidden_sources(verdict.sources, source_hint)
    check_verdict_guardrails(
        verdict.verdict, verdict.supported_subclaim, verdict.sources,
    )
    return verdict


def failed_verdict(claim_id: str, error: str) -> ClaimVerdict:
    """Baut den Ersatz-Verdikt für einen gescheiterten Claim-Call.

    Der Claim verschwindet nicht still und kippt auch nicht den Lauf — er wird
    sichtbar als ungeprüft ausgewiesen (Spec §3/S5).

    ``verdict="unsupported"`` ist hier nur ein **Platzhalter**, damit das Objekt
    schemagültig bleibt: ``failed`` ist keiner der acht internen Werte. Maßgeblich
    ist ``failed=True`` — die Aggregation rendert daraufhin „Prüfung
    fehlgeschlagen" statt des Grundtexts von ``unsupported``. Der wäre falsch:
    hier wurde keine Evidenz gesucht, sondern ein Call ist gescheitert.

    Args:
        claim_id: Die claim_id des gescheiterten Claims.
        error: Die Fehlerursache (geht in die Begründung).

    Returns:
        Ein :class:`ClaimVerdict` mit ``failed=True``.
    """
    return ClaimVerdict(
        claim_id=claim_id,
        verdict="unsupported",
        reason=f"{FAILED_REASON_PREFIX}: {error}",
        sources=[],
        failed=True,
    )


class ClaimVerifier:
    """S5-Stufe: je Claim ein Recherche-/Verdikt-Call gegen ein Web-Modell.

    Attributes:
        client: LLM-Client (:class:`llm_stage.PromptClient`) — hier das
            Verifikationsmodell mit Web-Zugriff, nicht das Analyse-Modell.
        model: Modell-ID des Verifikationsmodells.
        source_hint: Identität der geprüften Quelle (verbotene Eigenquelle).
        language: Ausgabesprache.
    """

    def __init__(
        self, client: PromptClient, model: str, source_hint: str = "",
        language: str = "Deutsch", anchor_date: str = "",
    ) -> None:
        self.client = client
        self.model = model
        self.source_hint = source_hint
        self.language = language
        self.anchor_date = anchor_date  # v0.15.0: Zeitanker (formatiert, "" = keiner)

    def verify_one(self, claim: dict, card: dict) -> ClaimVerdict:
        """Prüft genau einen Claim (ein Call, eigenes Token-Budget).

        Args:
            claim: Der Claim als Dict.
            card: Seine Recherchekarte als Dict.

        Returns:
            Das :class:`ClaimVerdict`.

        Raises:
            StageError: Bei API-Fehler oder Vertragsbruch nach dem Reparatur-Retry.
        """
        claim_id = claim["claim_id"]
        prompt = build_claim_verification_prompt(
            claim, card, language=self.language, source_hint=self.source_hint,
            anchor_date=self.anchor_date,
        )
        return run_json_stage(
            client=self.client,
            model=self.model,
            prompt=prompt,
            parse=lambda raw: validate_verdict(raw, claim_id, self.source_hint),
            stage_name=f"{STAGE_NAME}[{claim_id}]",
            extract=extract_json_object,
        )

    def verify_all(
        self,
        claims: list,
        cards: list,
        on_progress: Callable[[int, int, str], None] | None = None,
        should_cancel: Callable[[], bool] | None = None,
    ) -> list[ClaimVerdict]:
        """Prüft alle selektierten Claims sequenziell, Einzelfehler nicht fatal.

        Args:
            claims: Die selektierten :class:`models.RefinedClaim`-Objekte.
            cards: Die zugehörigen :class:`models.ResearchCard`-Objekte.
            on_progress: Optionaler Callback ``(index, total, claim_id)``, vor
                jedem Claim aufgerufen (1-basiert) — speist die Fortschrittsanzeige.
            should_cancel: Optionaler Callback; liefert er ``True``, bricht der
                Lauf VOR dem nächsten Claim ab und gibt die bisherigen Verdikte
                zurück (Abbrechen-Button, PR 4).

        Returns:
            Die :class:`ClaimVerdict`-Objekte in Claim-Reihenfolge. Bei Abbruch
            kürzer als ``claims``; gescheiterte Claims tragen ``failed=True``.

        Raises:
            ValueError: Wenn zu einem Claim die Recherchekarte fehlt.
        """
        by_id = {c.claim_id: c for c in cards}
        missing = [rc.claim_id for rc in claims if rc.claim_id not in by_id]
        if missing:
            raise ValueError(f"Recherchekarte fehlt für: {sorted(missing)}")

        results: list[ClaimVerdict] = []
        total = len(claims)
        for index, refined in enumerate(claims, 1):
            if should_cancel is not None and should_cancel():
                logger.info(
                    "%s: Abbruch vor Claim %d/%d (%s).",
                    STAGE_NAME, index, total, refined.claim_id,
                )
                break
            if on_progress is not None:
                on_progress(index, total, refined.claim_id)

            claim_dict = {
                "claim_id": refined.claim_id,
                "normalized_claim": refined.normalized_claim,
                "claim_type": refined.claim_type,
                "entities": refined.entities,
                "timeframe": refined.timeframe,
                "metric": refined.metric,
            }
            card = by_id[refined.claim_id]
            try:
                results.append(self.verify_one(claim_dict, vars(card)))
            except StageError as exc:
                # Einzelfehler ist nicht fatal: Claim sichtbar als ungeprüft
                # ausweisen, Rest weiterlaufen lassen (Spec §3/S5).
                logger.warning(
                    "%s: Claim %s fehlgeschlagen, Lauf geht weiter — %s",
                    STAGE_NAME, refined.claim_id, exc,
                )
                results.append(failed_verdict(refined.claim_id, str(exc)))
        return results
