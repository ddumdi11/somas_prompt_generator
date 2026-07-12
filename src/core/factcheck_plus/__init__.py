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
)
from .policy_scorer import DEFAULT_POLICY_PATH, PolicyScorer, load_policy
from .schemas import (
    ARGUMENT_MAPPING_SCHEMA, RATING_DIMS, REFINED_CLAIM_SCHEMA, SchemaError,
    validate,
)

__all__ = [
    "ArgumentMapping",
    "ClaimAudit",
    "ClaimClass",
    "MappedClaim",
    "RefinedClaim",
    "ROLE_TO_CLASS",
    "SelectionResult",
    "join_claims",
    "PolicyScorer",
    "load_policy",
    "DEFAULT_POLICY_PATH",
    "ARGUMENT_MAPPING_SCHEMA",
    "REFINED_CLAIM_SCHEMA",
    "RATING_DIMS",
    "SchemaError",
    "validate",
]
