"""Faktencheck Plus (v0.13.0) — argumentgewichtete Recherche-Auswahl.

PR 1 lieferte das **LLM-freie** Fundament: Datenmodelle + JSON-Verträge (S1/S2)
und den deterministischen ``PolicyScorer`` (S3) inkl. ``relevance_policy_v1.json``.
PR 2 ergänzt die beiden LLM-Stufen ``ClaimRefiner`` (S1) und ``ArgumentMapper``
(S2) samt Prompt-Verträgen und Reparatur-Retry. ResearchPlanner (S4) und
Pro-Claim-Verifikation (S5) folgen in späteren PRs.

Kein Qt-Import in diesem Package (extrahierbar als ``factcheck_core``, Spec §2.2);
einziger Berührungspunkt zum SOMAS-Client ist ``llm_stage``.
"""
from .llm_stage import MAX_REPAIR_ATTEMPTS, StageError, extract_json_array, run_json_stage
from .mapper import ArgumentMapper, validate_mappings
from .models import (
    ArgumentMapping, ClaimAudit, ClaimClass, MappedClaim, RefinedClaim,
    ROLE_TO_CLASS, SelectionResult, join_claims,
    STATUS_BASISFAKT_SKIPPED, STATUS_EXCLUDED_OPINION, STATUS_NOT_SELECTED_BUDGET,
    STATUS_SELECTED, STATUS_UNDER_SPECIFIED,
)
from .policy_scorer import DEFAULT_POLICY_PATH, PolicyScorer, load_policy
from .prompts import (
    REFINER_CLAIM_TYPES, build_mapper_prompt, build_refiner_prompt,
    build_repair_prompt, make_claim_id, sanitize_context,
)
from .refiner import CLAIM_ID_RE, ClaimRefiner, validate_refined
from .schemas import (
    ARGUMENT_MAPPING_SCHEMA, ARGUMENT_ROLES, CLAIM_TYPES, COUNTERFACTUAL_IMPACT,
    IMPORTANCE_DIMS, RATING_DIMS, REFINED_CLAIM_SCHEMA, RESEARCH_VALUE_DIMS,
    SchemaError, validate,
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
    # LLM-Stufen (S1/S2)
    "ClaimRefiner",
    "ArgumentMapper",
    "validate_refined",
    "validate_mappings",
    "CLAIM_ID_RE",
    # Stufen-Mechanik
    "StageError",
    "run_json_stage",
    "extract_json_array",
    "MAX_REPAIR_ATTEMPTS",
    # Prompt-Verträge
    "build_refiner_prompt",
    "build_mapper_prompt",
    "build_repair_prompt",
    "make_claim_id",
    "sanitize_context",
    "REFINER_CLAIM_TYPES",
    # Verträge / Wertemengen
    "ARGUMENT_MAPPING_SCHEMA",
    "REFINED_CLAIM_SCHEMA",
    "RATING_DIMS",
    "IMPORTANCE_DIMS",
    "RESEARCH_VALUE_DIMS",
    "CLAIM_TYPES",
    "ARGUMENT_ROLES",
    "COUNTERFACTUAL_IMPACT",
    "SchemaError",
    "validate",
]
