"""PolicyScorer — deterministische Claim-Auswahl (v0.13.0, PR 1).

**Streng deterministisch, KEIN LLM, keine Zufälle** (Spec §6): gleicher Input →
gleiche Auswahl. Der Scorer konsumiert nur Felder, die in PR 2 der Refiner (S1)
und Mapper (S2) liefern; hier simulieren Fixtures diese.

Ablauf pro Claim (Spec §3/S3, Theorie §4):
  1. **Gates vor Scores** (Reihenfolge aus Theorie §4.2 ist semantisch):
     Gate 1 Meinung/Deutung raus · Gate 2 Kontext = eigene (kleine) Quote ·
     Gate 3 Basisfakt/trivial nur listen · Gate 4 Attribution (kommt aus S1 bereits
     gesplittet) · Gate 5 zu vage → flaggen, nicht recherchieren.
  2. **Scores:** importance × research_value × checkability (alle 0–1).
  3. **Quotenauswahl klassenweise** (A vor B vor C) statt globaler Top-N.

Gewichte/Schwellen/Quoten kommen aus ``relevance_policy_v1.json`` — Konfiguration,
kein Code. Jede Auswahl trägt eine vollständige Auditspur (``ClaimAudit``).
"""
from __future__ import annotations

import json
from pathlib import Path

from .models import (
    ClaimAudit, ClaimClass, MappedClaim, ROLE_TO_CLASS, SelectionResult,
    STATUS_BASISFAKT_SKIPPED, STATUS_EXCLUDED_OPINION, STATUS_NOT_SELECTED_BUDGET,
    STATUS_SELECTED, STATUS_UNDER_SPECIFIED,
)
from .schemas import IMPORTANCE_DIMS, RATING_MAX, RATING_MIN, RESEARCH_VALUE_DIMS

DEFAULT_POLICY_PATH = (
    Path(__file__).resolve().parent.parent.parent / "config" / "relevance_policy_v1.json"
)

# Unterstützte Gate-Routen → Audit-Status. Die Policy-Felder `basisfakt_route` /
# `under_specified_route` sind damit wirksam (nicht dekorativ): ein unbekannter
# Wert schlägt bei der Konstruktion fehl, statt still ignoriert zu werden. Weitere
# Routen (z.B. eigene Schnellprüfung) hängen sich hier an.
_BASISFAKT_ROUTE_STATUS = {"skip_listed_only": STATUS_BASISFAKT_SKIPPED}
_UNDER_SPECIFIED_ROUTE_STATUS = {"flag_not_research": STATUS_UNDER_SPECIFIED}


def _resolve_route(route_map: dict, value: str | None, field: str) -> str:
    """Löst einen konfigurierten Gate-Routen-Wert in seinen Audit-Status auf.

    Args:
        route_map: Zulässige Routen → Status.
        value: Der in der Policy konfigurierte Routen-Wert.
        field: Feldname (für die Fehlermeldung).

    Returns:
        Der Audit-Status für diese Route.

    Raises:
        ValueError: Wenn ``value`` keine unterstützte Route ist.
    """
    if value not in route_map:
        raise ValueError(
            f"Unbekannte {field}={value!r}; unterstützt: {sorted(route_map)}"
        )
    return route_map[value]


def load_policy(path: str | Path | None = None) -> dict:
    """Lädt eine Policy-Datei.

    Args:
        path: Pfad zur Policy-JSON (``str`` oder ``Path``). ``None`` (Default) nutzt
            ``src/config/relevance_policy_v1.json`` (``DEFAULT_POLICY_PATH``).

    Returns:
        Die geparste Policy als ``dict``.
    """
    p = Path(path) if path is not None else DEFAULT_POLICY_PATH
    return json.loads(p.read_text(encoding="utf-8"))


class PolicyScorer:
    """Wählt aus gejointen Claims (S1+S2) deterministisch die Deep-Research-Menge."""

    def __init__(self, policy: dict) -> None:
        """Initialisiert den Scorer aus einer geladenen Policy.

        Args:
            policy: Policy-Konfiguration (s. :func:`load_policy`) mit
                ``rating_scale``, ``weights``, ``gates``, ``quotas`` und ``budget``.

        Raises:
            ValueError: Wenn ``rating_scale`` nicht zu den Schema-Grenzen
                (``RATING_MIN``/``RATING_MAX``) passt oder eine Gate-Route
                (``basisfakt_route`` / ``under_specified_route``) unbekannt ist.
        """
        self._policy = policy
        # Rating-Skala EINE Quelle: muss zu den Schema-Grenzen passen, damit
        # Validierung (Schema) und Scoring dieselben Min/Max nutzen.
        scale = [int(policy["rating_scale"][0]), int(policy["rating_scale"][1])]
        if scale != [RATING_MIN, RATING_MAX]:
            raise ValueError(
                f"rating_scale {scale} passt nicht zu Schema-Grenzen "
                f"[{RATING_MIN}, {RATING_MAX}]"
            )
        self._scale_max = float(RATING_MAX)
        self._w_importance = policy["weights"]["importance"]
        self._w_research = policy["weights"]["research_value"]
        self._gates = policy["gates"]
        self._quotas = policy["quotas"]
        # Gate-Routen aus der Config auflösen (unbekannter Wert → sofortiger Fehler).
        self._basisfakt_status = _resolve_route(
            _BASISFAKT_ROUTE_STATUS, self._gates.get("basisfakt_route"), "basisfakt_route"
        )
        self._under_specified_status = _resolve_route(
            _UNDER_SPECIFIED_ROUTE_STATUS,
            self._gates.get("under_specified_route"), "under_specified_route",
        )

    @classmethod
    def from_file(cls, path: str | Path | None = None) -> "PolicyScorer":
        """Bequemer Konstruktor aus einer Policy-Datei."""
        return cls(load_policy(path))

    @property
    def policy_version(self) -> str:
        """Gibt die Versionskennung der aktiven Policy zurück (z.B. ``relevance-de-v1``)."""
        return self._policy["policy_version"]

    # --- Scores ------------------------------------------------------------

    def _weighted_norm(self, ratings: dict, weights: dict, dims: tuple) -> float:
        """Gewichtete Summe der 0–5-Ratings, normiert auf 0–1."""
        max_sum = sum(weights[d] for d in dims) * self._scale_max
        if max_sum <= 0:
            return 0.0
        got = sum(weights[d] * float(ratings.get(d, 0)) for d in dims)
        return got / max_sum

    def _checkability(self, claim: MappedClaim) -> float:
        """0–1 aus S1-Feldern: Entität / Zeitraum / Metrik vorhanden? (Anteil von 3)."""
        rc = claim.refined
        present = sum((
            bool(rc.entities),
            bool(rc.timeframe),
            bool(rc.metric),
        ))
        return present / 3.0

    # --- Gates (Reihenfolge semantisch, Theorie §4.2) ----------------------

    def _gate_status(
        self, claim: MappedClaim, claim_class: ClaimClass, checkability: float,
    ) -> str | None:
        """Wendet die harten Gates an; gibt einen Ausschluss-Status oder ``None``
        (= eligible) zurück. ``None`` bedeutet: geht ins Scoring/Quotenauswahl.

        Args:
            claim: Der gejointe Claim (S1+S2).
            claim_class: Bereits im Aufrufer bestimmte Arbeitsklasse (A/B/C/D).
            checkability: Vorab berechnete Checkability (0–1).
        """
        claim_type = claim.refined.claim_type

        # Gate 1 — Meinung/Deutung: gar nicht recherchieren.
        if claim_type in self._gates.get("exclude_claim_types", []):
            return STATUS_EXCLUDED_OPINION

        # Gate 3 — Basisfakt (Metadaten-Rolle) ODER trivial: gemäß `basisfakt_route`
        # nur listen, nicht recherchieren. Trivialität = (Skalenmax − non_triviality);
        # ab `triviality_skip_at` gilt der Claim als trivial. (Gate 2 = Kontext hat
        # keinen Drop, sondern eine eigene kleine Quote in der Auswahl.)
        if claim_class == ClaimClass.D:
            return self._basisfakt_status
        triviality = self._scale_max - float(claim.mapping.ratings.get("non_triviality", 0))
        if triviality >= self._gates.get("triviality_skip_at", self._scale_max + 1):
            return self._basisfakt_status

        # Gate 4 — Attribution: kommt aus S1 bereits als eigener Claim gesplittet;
        # hier keine Sonderbehandlung nötig.

        # Gate 5 — zu vage: keinerlei prüfbare Anker (Entität/Zeitraum/Metrik) →
        # gemäß `under_specified_route` flaggen, nicht recherchieren.
        if checkability <= 0.0:
            return self._under_specified_status

        return None

    # --- Hauptlogik --------------------------------------------------------

    def select(
        self, claims: list[MappedClaim], budget: int | None = None,
    ) -> SelectionResult:
        """Wählt deterministisch die zu recherchierenden Claims aus.

        Args:
            claims: Gejointe S1+S2-Claims (``join_claims``).
            budget: Deep-Research-Budget; Default aus der Policy
                (``budget.deep_research_default``).

        Returns:
            ``SelectionResult`` mit Auswahl, vollständiger Auditspur und Zählwerten
            für den späteren Transparenz-Block.
        """
        if budget is None:
            budget = int(self._policy["budget"]["deep_research_default"])

        version = self.policy_version
        audit_by_id: dict[str, ClaimAudit] = {}
        # eligible-Claims je Klasse, jeweils (priority, claim_id, claim) — Sortierung
        # deterministisch: priority absteigend, dann claim_id aufsteigend.
        eligible: dict[ClaimClass, list[tuple[float, str, MappedClaim]]] = {
            ClaimClass.A: [], ClaimClass.B: [], ClaimClass.C: [],
        }

        for claim in claims:
            importance = self._weighted_norm(
                claim.mapping.ratings, self._w_importance, IMPORTANCE_DIMS
            )
            research_value = self._weighted_norm(
                claim.mapping.ratings, self._w_research, RESEARCH_VALUE_DIMS
            )
            checkability = self._checkability(claim)
            priority = importance * research_value * checkability
            claim_class = ROLE_TO_CLASS.get(
                claim.mapping.argument_role, ClaimClass.C
            )

            status = self._gate_status(claim, claim_class, checkability)
            audit_by_id[claim.claim_id] = ClaimAudit(
                claim_id=claim.claim_id,
                claim_class=claim_class.value,
                status=status or STATUS_NOT_SELECTED_BUDGET,  # vorläufig; ggf. selected
                selected=False,
                importance=importance,
                research_value=research_value,
                checkability=checkability,
                priority=priority,
                policy_version=version,
                reason="",
            )
            if status is None:
                eligible[claim_class].append((priority, claim.claim_id, claim))

        for bucket in eligible.values():
            bucket.sort(key=lambda t: (-t[0], t[1]))

        selected_ids = self._apply_quotas(eligible, budget)

        # Audits finalisieren (Status + Begründung).
        for rank, cid in enumerate(selected_ids, 1):
            a = audit_by_id[cid]
            a.selected = True
            a.status = STATUS_SELECTED
            a.reason = (
                f"Klasse {a.claim_class}, priority {a.priority:.3f}, "
                f"Auswahlrang {rank}/{len(selected_ids)} (Budget {budget})"
            )
        for a in audit_by_id.values():
            if not a.reason:
                a.reason = self._reason_for(a.status, a)

        counts = self._counts(audit_by_id.values())
        # Auditspur in Eingabereihenfolge der Claims (stabil).
        audits = [audit_by_id[c.claim_id] for c in claims]
        return SelectionResult(
            policy_version=version,
            budget=budget,
            selected_ids=selected_ids,
            audits=audits,
            counts=counts,
        )

    def _apply_quotas(
        self,
        eligible: dict[ClaimClass, list[tuple[float, str, MappedClaim]]],
        budget: int,
    ) -> list[str]:
        """Klassenweise Quotenauswahl (A vor B vor C), Budget als harte Obergrenze.

        Erst werden die Klassenkontingente gefüllt (core/supporting-Anteil, Kontext-
        Cap); bleibt danach Budget übrig, füllen die stärksten übrigen eligible
        Claims in Klassenreihenfolge auf (Spill), damit Budget nicht verfällt.
        """
        core_cap = round(budget * self._quotas["core_claims_share"])
        supp_cap = round(budget * self._quotas["supporting_share"])
        ctx_cap = int(self._quotas["context_max_claims"])
        caps = {ClaimClass.A: core_cap, ClaimClass.B: supp_cap, ClaimClass.C: ctx_cap}

        selected: list[str] = []
        taken: dict[ClaimClass, int] = {ClaimClass.A: 0, ClaimClass.B: 0, ClaimClass.C: 0}

        # 1) Primärauswahl nach Klassenkontingent, in Klassenreihenfolge.
        for cls in (ClaimClass.A, ClaimClass.B, ClaimClass.C):
            for priority, cid, _claim in eligible[cls]:
                if len(selected) >= budget or taken[cls] >= caps[cls]:
                    break
                selected.append(cid)
                taken[cls] += 1

        # 2) Spill: Restbudget mit stärksten übrigen eligible Claims füllen —
        #    NUR Kern- (A) und tragende Subclaims (B). core/supporting-Anteile sind
        #    weiche Shares (dürfen ineinander spillen), damit knappe Kontingente kein
        #    Budget verschenken. `context_max_claims` ist dagegen ein HARTER Cap
        #    (Theorie §4.3: Kontext ≤ wenige Claims) und wird beim Spill NICHT erhöht.
        if len(selected) < budget:
            chosen = set(selected)
            for cls in (ClaimClass.A, ClaimClass.B):
                for priority, cid, _claim in eligible[cls]:
                    if len(selected) >= budget:
                        break
                    if cid not in chosen:
                        selected.append(cid)
                        chosen.add(cid)
                if len(selected) >= budget:
                    break

        return selected

    def _reason_for(self, status: str, audit: ClaimAudit) -> str:
        """Menschlich lesbare Begründung je Nicht-Auswahl-Status."""
        if status == STATUS_EXCLUDED_OPINION:
            return "Gate 1: Meinung/Interpretation — nicht recherchiert"
        if status == STATUS_BASISFAKT_SKIPPED:
            return "Gate 3: Basisfakt/trivial — nur gelistet, nicht recherchiert"
        if status == STATUS_UNDER_SPECIFIED:
            return "Gate 5: zu vage (kein prüfbarer Anker) — flag, nicht recherchiert"
        return (
            f"Klasse {audit.claim_class}, priority {audit.priority:.3f} — "
            "eligible, aber Budget/Quote erschöpft"
        )

    @staticmethod
    def _counts(audits) -> dict[str, int]:
        """Zählwerte für den späteren Transparenz-Block."""
        counts = {
            "extracted": 0,
            STATUS_SELECTED: 0,
            STATUS_BASISFAKT_SKIPPED: 0,
            STATUS_EXCLUDED_OPINION: 0,
            STATUS_UNDER_SPECIFIED: 0,
            STATUS_NOT_SELECTED_BUDGET: 0,
        }
        for a in audits:
            counts["extracted"] += 1
            counts[a.status] = counts.get(a.status, 0) + 1
        return counts
