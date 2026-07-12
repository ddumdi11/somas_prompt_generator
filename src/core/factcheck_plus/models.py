"""Datenmodelle für Faktencheck Plus (v0.13.0, PR 1).

Bewusst **ohne Qt-Import** — die Stufen kommunizieren nur über diese Dataclasses /
JSON-Verträge, damit das Package später als eigenständiges ``factcheck_core``
extrahierbar bleibt (Intake-Muster, Spec §2.2).

- ``RefinedClaim``   – Output S1 (ClaimRefiner)
- ``ArgumentMapping`` – Output S2 (ArgumentMapper)
- ``MappedClaim``    – S1+S2 je Claim gejoint (Eingabeeinheit des Scorers)
- ``ClaimAudit`` / ``SelectionResult`` – Auswahl + Audit-Spur (Datenquelle des
  späteren Transparenz-Blocks, Spec §3/S3)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .schemas import (
    ARGUMENT_MAPPING_SCHEMA, ARGUMENT_ROLES, REFINED_CLAIM_SCHEMA, validate,
)


class ClaimClass(str, Enum):
    """Arbeitsklassen der Priorisierung (Theorie §2.4)."""
    A = "A"  # Kernclaim – trägt die Hauptthese
    B = "B"  # tragender Subclaim
    C = "C"  # Kontext-/Beispielclaim
    D = "D"  # Basis-/Metadatenclaim (Basisfakt)


# Argumentrolle (S2) → Arbeitsklasse (Theorie §2.4).
ROLE_TO_CLASS: dict[str, ClaimClass] = {
    "core_claim": ClaimClass.A,
    "supporting_premise": ClaimClass.B,
    "context": ClaimClass.C,
    "example": ClaimClass.C,
    "metadata": ClaimClass.D,
}

# Konsistenzriegel zur Importzeit: jede im S2-Vertrag erlaubte Argumentrolle muss
# hier auf eine Klasse abgebildet sein (fängt Drift zwischen Schema und Mapping).
# Der `.get(..., ClaimClass.C)`-Fallback im Scorer bleibt als Laufzeit-Sicherheitsnetz.
assert set(ROLE_TO_CLASS) == set(ARGUMENT_ROLES), (
    "ROLE_TO_CLASS deckt nicht exakt ARGUMENT_ROLES ab: "
    f"{set(ROLE_TO_CLASS) ^ set(ARGUMENT_ROLES)}"
)


@dataclass
class RefinedClaim:
    """Atomisierte, normalisierte Behauptung (S1, ClaimRefiner)."""
    claim_id: str
    original_text: str
    normalized_claim: str
    claim_type: str
    entities: list[str] = field(default_factory=list)
    timeframe: str | None = None
    metric: str | None = None
    parent_id: str | None = None

    @classmethod
    def from_dict(cls, data: dict) -> "RefinedClaim":
        """Validiert gegen ``REFINED_CLAIM_SCHEMA`` und baut die Instanz."""
        validate(data, REFINED_CLAIM_SCHEMA, "$.refined_claim")
        return cls(
            claim_id=data["claim_id"],
            original_text=data["original_text"],
            normalized_claim=data["normalized_claim"],
            claim_type=data["claim_type"],
            entities=list(data.get("entities", [])),
            timeframe=data.get("timeframe"),
            metric=data.get("metric"),
            parent_id=data.get("parent_id"),
        )


@dataclass
class ArgumentMapping:
    """Argumentrolle + kontrafaktischer Impact + 0–5-Ratings (S2, ArgumentMapper)."""
    claim_id: str
    argument_role: str
    counterfactual_impact: str
    ratings: dict[str, int]
    reason: str = ""

    @classmethod
    def from_dict(cls, data: dict) -> "ArgumentMapping":
        """Validiert gegen ``ARGUMENT_MAPPING_SCHEMA`` und baut die Instanz."""
        validate(data, ARGUMENT_MAPPING_SCHEMA, "$.argument_mapping")
        return cls(
            claim_id=data["claim_id"],
            argument_role=data["argument_role"],
            counterfactual_impact=data["counterfactual_impact"],
            ratings=dict(data["ratings"]),
            reason=data.get("reason", ""),
        )


@dataclass
class MappedClaim:
    """S1- und S2-Output eines Claims gejoint — Eingabeeinheit des PolicyScorers."""
    refined: RefinedClaim
    mapping: ArgumentMapping

    @property
    def claim_id(self) -> str:
        return self.refined.claim_id


def join_claims(
    refined: list[RefinedClaim], mappings: list[ArgumentMapping],
) -> list[MappedClaim]:
    """Verbindet Refiner- und Mapper-Output deterministisch über ``claim_id``.

    Die Reihenfolge folgt ``refined`` (stabile Eingabereihenfolge).

    Args:
        refined: RefinedClaims aus S1.
        mappings: ArgumentMappings aus S2.

    Returns:
        Liste gejointer ``MappedClaim`` in ``refined``-Reihenfolge.

    Raises:
        ValueError: Wenn ein Claim kein Gegenstück in der jeweils anderen Liste hat.
    """
    refined_ids = [rc.claim_id for rc in refined]
    if len(set(refined_ids)) != len(refined_ids):
        seen: set[str] = set()
        dupes = sorted({cid for cid in refined_ids if cid in seen or seen.add(cid)})
        raise ValueError(f"Doppelte claim_id in den RefinedClaims: {dupes}")
    by_id = {m.claim_id: m for m in mappings}
    if len(by_id) != len(mappings):
        raise ValueError("Doppelte claim_id in den ArgumentMappings")
    joined: list[MappedClaim] = []
    for rc in refined:
        mapping = by_id.pop(rc.claim_id, None)
        if mapping is None:
            raise ValueError(f"Kein ArgumentMapping für claim_id '{rc.claim_id}'")
        joined.append(MappedClaim(refined=rc, mapping=mapping))
    if by_id:
        raise ValueError(
            f"ArgumentMapping ohne RefinedClaim: {sorted(by_id)}"
        )
    return joined


@dataclass
class ClaimAudit:
    """Auditspur je Claim: Score-Komponenten + Auswahlgrund + Policy-Version.

    Ab Tag eins vollständig (Spec-Leitplanke): Datenquelle des späteren
    Transparenz-Blocks (PR 3/4).
    """
    claim_id: str
    claim_class: str            # "A" | "B" | "C" | "D"
    status: str                 # s. STATUS_* unten
    selected: bool
    importance: float           # 0–1
    research_value: float       # 0–1
    checkability: float         # 0–1
    priority: float             # importance × research_value × checkability
    policy_version: str
    reason: str


# Auswahl-/Ausschluss-Status (Route eines Claims durch die Gates + Quotenauswahl).
STATUS_SELECTED = "selected"                    # in die Deep-Research-Auswahl
STATUS_EXCLUDED_OPINION = "excluded_opinion"    # Gate 1: Meinung/Deutung
STATUS_BASISFAKT_SKIPPED = "basisfakt_skipped"  # Gate 3: Basisfakt/trivial – nur gelistet
STATUS_UNDER_SPECIFIED = "under_specified"      # Gate 5: zu vage – flag, nicht recherchiert
STATUS_NOT_SELECTED_BUDGET = "not_selected_budget"  # eligible, aber Budget/Quote erschöpft


@dataclass
class SelectionResult:
    """Ergebnis eines PolicyScorer-Laufs: Auswahl + vollständige Auditspur."""
    policy_version: str
    budget: int
    selected_ids: list[str]
    audits: list[ClaimAudit]
    counts: dict[str, int]

    def selected_audits(self) -> list[ClaimAudit]:
        """Audits der selektierten Claims, in Auswahlreihenfolge (Rang)."""
        by_id = {a.claim_id: a for a in self.audits}
        return [by_id[cid] for cid in self.selected_ids]
