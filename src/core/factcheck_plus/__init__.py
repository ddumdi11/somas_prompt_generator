"""Faktencheck Plus (v0.13.0) — argumentgewichtete Recherche-Auswahl.

PR 1 liefert das **LLM-freie** Fundament: Datenmodelle + JSON-Verträge (S1/S2)
und den deterministischen ``PolicyScorer`` (S3) inkl. ``relevance_policy_v1.json``.
Refiner (S1), Mapper (S2), ResearchPlanner (S4) und Pro-Claim-Verifikation (S5)
folgen in späteren PRs; hier simulieren Fixtures deren Output.

Kein Qt-Import in diesem Package (extrahierbar als ``factcheck_core``, Spec §2.2).
"""
from .models import (
    ArgumentMapping, ClaimAudit, ClaimClass, MappedClaim, RefinedClaim,
    ROLE_TO_CLASS, SelectionResult, join_claims,
    STATUS_BASISFAKT_SKIPPED, STATUS_EXCLUDED_OPINION, STATUS_NOT_SELECTED_BUDGET,
    STATUS_SELECTED, STATUS_UNDER_SPECIFIED,
)
from .policy_scorer import DEFAULT_POLICY_PATH, PolicyScorer, load_policy
from .schemas import (
    ARGUMENT_MAPPING_SCHEMA, ARGUMENT_ROLES, CLAIM_TYPES, IMPORTANCE_DIMS,
    RATING_DIMS, REFINED_CLAIM_SCHEMA, RESEARCH_VALUE_DIMS, SchemaError, validate,
)

__all__ = [
    # Datenmodelle
    "ArgumentMapping",
    "ClaimAudit",
    "ClaimClass",
    "MappedClaim",
    "RefinedClaim",
    "ROLE_TO_CLASS",
    "SelectionResult",
    "join_claims",
    # Auswahl-/Ausschluss-Status
    "STATUS_SELECTED",
    "STATUS_EXCLUDED_OPINION",
    "STATUS_BASISFAKT_SKIPPED",
    "STATUS_UNDER_SPECIFIED",
    "STATUS_NOT_SELECTED_BUDGET",
    # Scorer
    "PolicyScorer",
    "load_policy",
    "DEFAULT_POLICY_PATH",
    # Verträge / Wertemengen
    "ARGUMENT_MAPPING_SCHEMA",
    "REFINED_CLAIM_SCHEMA",
    "RATING_DIMS",
    "IMPORTANCE_DIMS",
    "RESEARCH_VALUE_DIMS",
    "CLAIM_TYPES",
    "ARGUMENT_ROLES",
    "SchemaError",
    "validate",
]
