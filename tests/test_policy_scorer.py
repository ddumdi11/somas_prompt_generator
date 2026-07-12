"""Tests für Faktencheck Plus PR 1: PolicyScorer + Verträge (v0.13.0).

Deckt die Spec-/Architekten-Leitplanken ab:
- Gates VOR Scores, in semantischer Reihenfolge (Theorie §4.2).
- Quotenauswahl klassenweise (A vor B vor C) statt globaler Top-N.
- Strikt deterministisch: gleicher (auch umsortierter) Input → gleiche Auswahl.
- Basisfakten fallen aus der Auswahl und verdrängen nie einen Kernclaim.
- Audit ab Tag eins: Score-Komponenten + Policy-Version + Begründung.

Lauf (ohne pytest):  python tests/test_policy_scorer.py
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.core.factcheck_plus import (
    ArgumentMapping, MappedClaim, PolicyScorer, RefinedClaim, SchemaError,
    SelectionResult, join_claims, load_policy,
)
from src.core.factcheck_plus.schemas import IMPORTANCE_DIMS, RESEARCH_VALUE_DIMS


# --- Fixture-Helfer (simulieren S1/S2, LLM-frei) --------------------------

def _claim(
    cid: str, role: str = "core_claim", claim_type: str = "quantitative",
    entities: tuple[str, ...] = ("Entität",), timeframe: str | None = "2025",
    metric: str | None = "Prozent", importance: int = 4, research: int = 4,
    parent_id: str | None = None, **rating_overrides: int,
) -> MappedClaim:
    refined = RefinedClaim(
        claim_id=cid, original_text=f"o-{cid}", normalized_claim=f"n-{cid}",
        claim_type=claim_type, entities=list(entities), timeframe=timeframe,
        metric=metric, parent_id=parent_id,
    )
    ratings = {d: importance for d in IMPORTANCE_DIMS}
    ratings.update({d: research for d in RESEARCH_VALUE_DIMS})
    ratings.update(rating_overrides)
    mapping = ArgumentMapping(
        claim_id=cid, argument_role=role, counterfactual_impact="high",
        ratings=ratings, reason="",
    )
    return MappedClaim(refined=refined, mapping=mapping)


def _scorer() -> PolicyScorer:
    return PolicyScorer.from_file()


def _classes(result: SelectionResult, ids: list[str]) -> list[str]:
    by_id = {a.claim_id: a for a in result.audits}
    return [by_id[i].claim_class for i in ids]


# --- Gates ----------------------------------------------------------------

def test_gate_excludes_opinion_and_interpretation():
    claims = [
        _claim("op", claim_type="opinion"),
        _claim("ip", claim_type="interpretation"),
        _claim("ok", claim_type="quantitative"),
    ]
    res = _scorer().select(claims, budget=8)
    status = {a.claim_id: a.status for a in res.audits}
    assert status["op"] == "excluded_opinion"
    assert status["ip"] == "excluded_opinion"
    assert "op" not in res.selected_ids and "ip" not in res.selected_ids
    assert "ok" in res.selected_ids
    print("  gate_excludes_opinion_and_interpretation OK")


def test_gate_basisfakt_metadata_skipped():
    # Perfekter Basisfakt (max Ratings, volle Checkability) darf NICHT recherchiert werden.
    claims = [_claim("meta", role="metadata", importance=5, research=5)]
    res = _scorer().select(claims, budget=8)
    assert res.audits[0].status == "basisfakt_skipped"
    assert res.selected_ids == []
    print("  gate_basisfakt_metadata_skipped OK")


def test_gate_triviality_threshold():
    # triviality = 5 - non_triviality; skip ab >= 4  →  non_triviality <= 1.
    skipped = _claim("triv", non_triviality=1)      # triviality 4 → skip
    eligible = _claim("keep", non_triviality=2)     # triviality 3 → eligible
    res = _scorer().select([skipped, eligible], budget=8)
    status = {a.claim_id: a.status for a in res.audits}
    assert status["triv"] == "basisfakt_skipped"
    assert "keep" in res.selected_ids
    print("  gate_triviality_threshold OK")


def test_gate_under_specified_when_no_anchor():
    vague = _claim("vague", entities=(), timeframe=None, metric=None)
    res = _scorer().select([vague], budget=8)
    assert res.audits[0].status == "under_specified"
    assert res.audits[0].checkability == 0.0
    assert res.selected_ids == []
    print("  gate_under_specified_when_no_anchor OK")


# --- Quoten & Klassen-Priorität ------------------------------------------

def test_quota_is_class_wise_not_global_top_n():
    # B-Claims scoren HÖHER als A-Claims. Globales Top-N würde B bevorzugen;
    # klassenweise Quote muss trotzdem zuerst die Kernclaims (A) füllen.
    a_claims = [_claim(f"a{i}", role="core_claim", importance=2, research=2) for i in range(4)]
    b_claims = [_claim(f"b{i}", role="supporting_premise", importance=5, research=5) for i in range(4)]
    res = _scorer().select(a_claims + b_claims, budget=5)
    # budget 5: core_cap=round(3.0)=3, supp_cap=round(1.5)=2 → 3 A + 2 B
    classes = _classes(res, res.selected_ids)
    assert classes.count("A") == 3, classes
    assert classes.count("B") == 2, classes
    assert len(res.selected_ids) == 5
    print("  quota_is_class_wise_not_global_top_n OK")


def test_context_quota_capped():
    context = [_claim(f"c{i}", role="context", importance=5, research=5) for i in range(5)]
    res = _scorer().select(context, budget=8)
    # context_max_claims = 2 → nur 2 Kontextclaims, Rest not_selected_budget
    assert len(res.selected_ids) == 2
    assert all(a.claim_class == "C" for a in res.selected_audits())
    print("  context_quota_capped OK")


def test_basisfakt_never_displaces_core():
    # Regression: "Das ZDF ist öffentlich-rechtlich" (Basisfakt, perfekt prüfbar)
    # darf keinen Kernclaim aus der Auswahl drängen.
    basisfakt = _claim("zdf", role="metadata", importance=5, research=5)
    core = _claim("kern", role="core_claim", importance=3, research=3)
    res = _scorer().select([basisfakt, core], budget=1)
    assert res.selected_ids == ["kern"]
    status = {a.claim_id: a.status for a in res.audits}
    assert status["zdf"] == "basisfakt_skipped"
    print("  basisfakt_never_displaces_core OK")


def test_budget_default_from_policy():
    # Genügend eligible Kernclaims → Auswahl exakt auf Policy-Default (8) gekappt.
    claims = [_claim(f"a{i}", role="core_claim") for i in range(20)]
    res = _scorer().select(claims)  # kein budget → Default 8
    assert res.budget == 8
    assert len(res.selected_ids) == 8
    print("  budget_default_from_policy OK")


# --- Determinismus --------------------------------------------------------

def test_deterministic_same_and_shuffled_input():
    claims = (
        [_claim(f"a{i}", role="core_claim", importance=5 - (i % 3), research=4) for i in range(5)]
        + [_claim(f"b{i}", role="supporting_premise", importance=3, research=3) for i in range(3)]
        + [_claim(f"c{i}", role="context") for i in range(3)]
    )
    scorer = _scorer()
    first = scorer.select(list(claims), budget=6).selected_ids
    again = scorer.select(list(claims), budget=6).selected_ids
    reversed_in = scorer.select(list(reversed(claims)), budget=6).selected_ids
    assert first == again, (first, again)
    assert first == reversed_in, (first, reversed_in)  # unabhängig von Eingabereihenfolge
    print("  deterministic_same_and_shuffled_input OK")


# --- Audit ----------------------------------------------------------------

def test_audit_completeness_and_priority_math():
    res = _scorer().select([_claim("x", importance=4, research=2)], budget=8)
    a = res.audits[0]
    assert a.policy_version == "relevance-de-v1"
    # priority = importance × research_value × checkability (alle 0–1)
    assert abs(a.priority - a.importance * a.research_value * a.checkability) < 1e-9
    assert 0.0 <= a.importance <= 1.0 and 0.0 <= a.research_value <= 1.0
    assert a.checkability == 1.0  # Entität + Zeitraum + Metrik vorhanden
    assert a.selected and a.status == "selected" and "Auswahlrang 1/1" in a.reason
    # counts summieren auf extracted
    assert res.counts["extracted"] == 1 and res.counts["selected"] == 1
    print("  audit_completeness_and_priority_math OK")


def test_counts_sum_to_extracted():
    claims = [
        _claim("sel", role="core_claim"),
        _claim("op", claim_type="opinion"),
        _claim("meta", role="metadata"),
        _claim("vague", entities=(), timeframe=None, metric=None),
    ]
    res = _scorer().select(claims, budget=8)
    total = (res.counts["selected"] + res.counts["excluded_opinion"]
             + res.counts["basisfakt_skipped"] + res.counts["under_specified"]
             + res.counts["not_selected_budget"])
    assert total == res.counts["extracted"] == 4
    print("  counts_sum_to_extracted OK")


# --- Verträge (Schema-Validierung) ----------------------------------------

def _valid_refined_dict():
    return {
        "claim_id": "c1", "parent_id": None,
        "original_text": "o", "normalized_claim": "n",
        "claim_type": "quantitative", "entities": ["X"],
        "timeframe": "2025", "metric": "Prozent",
    }


def _valid_mapping_dict():
    ratings = {d: 3 for d in (IMPORTANCE_DIMS + RESEARCH_VALUE_DIMS)}
    return {
        "claim_id": "c1", "argument_role": "core_claim",
        "counterfactual_impact": "high", "ratings": ratings, "reason": "r",
    }


def test_refined_claim_from_dict_valid_and_invalid():
    rc = RefinedClaim.from_dict(_valid_refined_dict())
    assert rc.claim_id == "c1" and rc.entities == ["X"]
    # ungültiger claim_type
    bad = _valid_refined_dict()
    bad["claim_type"] = "banana"
    with pytest.raises(SchemaError):
        RefinedClaim.from_dict(bad)
    # Pflichtfeld fehlt
    missing = _valid_refined_dict()
    del missing["normalized_claim"]
    with pytest.raises(SchemaError):
        RefinedClaim.from_dict(missing)
    print("  refined_claim_from_dict_valid_and_invalid OK")


def test_argument_mapping_from_dict_validates_ratings():
    am = ArgumentMapping.from_dict(_valid_mapping_dict())
    assert am.argument_role == "core_claim"
    # Rating außerhalb 0–5
    bad = _valid_mapping_dict()
    bad["ratings"]["recency"] = 9
    with pytest.raises(SchemaError):
        ArgumentMapping.from_dict(bad)
    # Rating-Dimension fehlt
    missing = _valid_mapping_dict()
    del missing["ratings"]["harm_potential"]
    with pytest.raises(SchemaError):
        ArgumentMapping.from_dict(missing)
    # ungültige Rolle
    role = _valid_mapping_dict()
    role["argument_role"] = "boss"
    with pytest.raises(SchemaError):
        ArgumentMapping.from_dict(role)
    print("  argument_mapping_from_dict_validates_ratings OK")


def test_join_claims_matches_and_reports_mismatch():
    refined = [RefinedClaim.from_dict(_valid_refined_dict())]
    mapping = [ArgumentMapping.from_dict(_valid_mapping_dict())]
    joined = join_claims(refined, mapping)
    assert len(joined) == 1 and joined[0].claim_id == "c1"
    # fehlendes Mapping
    orphan = RefinedClaim.from_dict({**_valid_refined_dict(), "claim_id": "c2"})
    with pytest.raises(ValueError):
        join_claims([orphan], mapping)
    print("  join_claims_matches_and_reports_mismatch OK")


# --- Policy-Datei ---------------------------------------------------------

def test_unsupported_gate_route_raises():
    import copy
    base = load_policy()
    bad_basis = copy.deepcopy(base)
    bad_basis["gates"]["basisfakt_route"] = "delete_everything"
    with pytest.raises(ValueError):
        PolicyScorer(bad_basis)
    bad_us = copy.deepcopy(base)
    bad_us["gates"]["under_specified_route"] = "yolo"
    with pytest.raises(ValueError):
        PolicyScorer(bad_us)
    print("  unsupported_gate_route_raises OK")


def test_rating_scale_mismatch_raises():
    import copy
    base = load_policy()
    bad = copy.deepcopy(base)
    bad["rating_scale"] = [0, 4]  # passt nicht zu den Schema-Grenzen [0, 5]
    with pytest.raises(ValueError):
        PolicyScorer(bad)
    print("  rating_scale_mismatch_raises OK")


def test_join_duplicate_refined_raises():
    a = RefinedClaim.from_dict(_valid_refined_dict())
    b = RefinedClaim.from_dict(_valid_refined_dict())  # gleiche claim_id 'c1'
    mapping = ArgumentMapping.from_dict(_valid_mapping_dict())
    with pytest.raises(ValueError):
        join_claims([a, b], [mapping])
    print("  join_duplicate_refined_raises OK")


def test_policy_file_encodes_po_decisions():
    policy = load_policy()
    assert policy["policy_version"] == "relevance-de-v1"
    assert policy["budget"]["deep_research_default"] == 8  # PO §8.1
    assert policy["gates"]["basisfakt_route"] == "skip_listed_only"  # PO §8.2
    assert policy["gates"]["exclude_claim_types"] == ["opinion", "interpretation"]
    # Alle Rating-Dimensionen haben ein Gewicht
    weighted = set(policy["weights"]["importance"]) | set(policy["weights"]["research_value"])
    assert weighted == set(IMPORTANCE_DIMS) | set(RESEARCH_VALUE_DIMS)
    print("  policy_file_encodes_po_decisions OK")


def main():
    print("Faktencheck Plus PR 1 — PolicyScorer & Verträge:")
    test_gate_excludes_opinion_and_interpretation()
    test_gate_basisfakt_metadata_skipped()
    test_gate_triviality_threshold()
    test_gate_under_specified_when_no_anchor()
    test_quota_is_class_wise_not_global_top_n()
    test_context_quota_capped()
    test_basisfakt_never_displaces_core()
    test_budget_default_from_policy()
    test_deterministic_same_and_shuffled_input()
    test_audit_completeness_and_priority_math()
    test_counts_sum_to_extracted()
    test_refined_claim_from_dict_valid_and_invalid()
    test_argument_mapping_from_dict_validates_ratings()
    test_join_claims_matches_and_reports_mismatch()
    test_unsupported_gate_route_raises()
    test_rating_scale_mismatch_raises()
    test_join_duplicate_refined_raises()
    test_policy_file_encodes_po_decisions()
    print("ALLE TESTS OK")


if __name__ == "__main__":
    main()
