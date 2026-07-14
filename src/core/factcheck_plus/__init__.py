"""Faktencheck Plus (v0.13.0) — argumentgewichtete Recherche-Auswahl.

PR 1 lieferte das **LLM-freie** Fundament: Datenmodelle + JSON-Verträge (S1/S2)
und den deterministischen ``PolicyScorer`` (S3) inkl. ``relevance_policy_v1.json``.
PR 2 ergänzt die beiden LLM-Stufen ``ClaimRefiner`` (S1) und ``ArgumentMapper``
(S2) samt Prompt-Verträgen und Reparatur-Retry. ResearchPlanner (S4) und
Pro-Claim-Verifikation (S5) folgen in späteren PRs.

Kein Qt-Import in diesem Package (extrahierbar als ``factcheck_core``, Spec §2.2);
einziger Berührungspunkt zum SOMAS-Client ist ``llm_stage``.
"""
from .aggregate import (
    build_render_context, build_skipped_rows, build_transparency, build_verdict_rows,
)
from .llm_stage import (
    MAX_REPAIR_ATTEMPTS, PromptClient, StageError, extract_json_array,
    extract_json_object, run_json_stage, strip_code_fences,
)
from .mapper import ArgumentMapper, validate_mappings
from .models import (
    ArgumentMapping, ClaimAudit, ClaimClass, ClaimVerdict, MappedClaim,
    RefinedClaim, ResearchCard, ROLE_TO_CLASS, SelectionResult, join_claims,
    STATUS_BASISFAKT_SKIPPED, STATUS_EXCLUDED_OPINION, STATUS_NOT_SELECTED_BUDGET,
    STATUS_SELECTED, STATUS_UNDER_SPECIFIED,
)
from .planner import ResearchPlanner, validate_cards
from .policy_scorer import DEFAULT_POLICY_PATH, PolicyScorer, load_policy
from .prompts import (
    FORBIDDEN_SHORTCUTS, REFINER_CLAIM_TYPES, SOURCE_HIERARCHY,
    build_claim_verification_prompt, build_mapper_prompt, build_planner_prompt,
    build_refiner_prompt, build_repair_prompt, make_claim_id, sanitize_context,
)
from .refiner import CLAIM_ID_RE, ClaimRefiner, validate_refined
from .schemas import (
    ARGUMENT_MAPPING_SCHEMA, ARGUMENT_ROLES, CLAIM_TYPES, CLAIM_VERDICT_SCHEMA,
    COUNTERFACTUAL_IMPACT, IMPORTANCE_DIMS, INTERNAL_VERDICTS, RATING_DIMS,
    REFINED_CLAIM_SCHEMA, RESEARCH_CARD_SCHEMA, RESEARCH_VALUE_DIMS,
    VERDICTS_REQUIRING_SOURCE, VERDICTS_REQUIRING_SUBCLAIM, SchemaError, validate,
)
from .verdict import (
    FAILED_REASON_PREFIX, FAILED_UI_VERDICT, UI_VERDICTS, VERDICT_MAP,
    VerdictError, check_verdict_guardrails, format_reason_line, map_verdict,
)
from .verifier import ClaimVerifier, failed_verdict, validate_verdict

__all__ = [
    # Datenmodelle
    "ArgumentMapping",
    "ClaimAudit",
    "ClaimClass",
    "ClaimVerdict",
    "MappedClaim",
    "RefinedClaim",
    "ResearchCard",
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
    # LLM-Stufen (S1/S2/S4/S5)
    "ClaimRefiner",
    "ArgumentMapper",
    "ResearchPlanner",
    "ClaimVerifier",
    "validate_refined",
    "validate_mappings",
    "validate_cards",
    "validate_verdict",
    "failed_verdict",
    "CLAIM_ID_RE",
    # Verdikt-Taxonomie (8→4)
    "VERDICT_MAP",
    "UI_VERDICTS",
    "INTERNAL_VERDICTS",
    "VerdictError",
    "map_verdict",
    "check_verdict_guardrails",
    "format_reason_line",
    "FAILED_UI_VERDICT",
    "FAILED_REASON_PREFIX",
    "VERDICTS_REQUIRING_SOURCE",
    "VERDICTS_REQUIRING_SUBCLAIM",
    # Aggregation
    "build_render_context",
    "build_verdict_rows",
    "build_skipped_rows",
    "build_transparency",
    # Stufen-Mechanik
    "PromptClient",
    "StageError",
    "run_json_stage",
    "extract_json_array",
    "extract_json_object",
    "strip_code_fences",
    "MAX_REPAIR_ATTEMPTS",
    # Prompt-Verträge
    "build_refiner_prompt",
    "build_mapper_prompt",
    "build_planner_prompt",
    "build_claim_verification_prompt",
    "build_repair_prompt",
    "make_claim_id",
    "sanitize_context",
    "REFINER_CLAIM_TYPES",
    "SOURCE_HIERARCHY",
    "FORBIDDEN_SHORTCUTS",
    # Verträge / Wertemengen
    "ARGUMENT_MAPPING_SCHEMA",
    "REFINED_CLAIM_SCHEMA",
    "RESEARCH_CARD_SCHEMA",
    "CLAIM_VERDICT_SCHEMA",
    "RATING_DIMS",
    "IMPORTANCE_DIMS",
    "RESEARCH_VALUE_DIMS",
    "CLAIM_TYPES",
    "ARGUMENT_ROLES",
    "COUNTERFACTUAL_IMPACT",
    "SchemaError",
    "validate",
]
