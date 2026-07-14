"""Tests für Faktencheck Plus PR 2: ArgumentMapper (S2) + Kette S1→S2→S3.

Deckt die Architekten-Leitplanken ab:
- Nicht-Zuständigkeiten als explizite Verbote im Prompt (Theorie §8.5): der
  Mapper füllt nur Felder — er wählt nicht aus und gewichtet nicht.
- ID-Echo: exakt die S1-IDs kommen zurück; ein Bruch geht als konkrete Meldung
  in den Reparatur-Retry, bevor `join_claims` als Sicherheitsnetz greift.
- Die Referenzfälle laufen bis in den PolicyScorer durch — der Vertrag zwischen
  den Stufen hält also nicht nur je Stufe, sondern als Kette.

Alles gemockt — kein Netzwerk (Merge-Kriterium PR 2: offline grün).

Lauf (ohne pytest):  python tests/test_argument_mapper_contract.py
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.core.factcheck_plus import (
    ArgumentMapper, ClaimRefiner, PolicyScorer, StageError, build_mapper_prompt,
    join_claims, validate_mappings,
)
from src.core.factcheck_plus.schemas import (
    IMPORTANCE_DIMS, RATING_DIMS, RESEARCH_VALUE_DIMS, SchemaError,
)
from tests.factcheck_plus_helpers import FakeClient, as_json, error_response, load_case

IRGC = load_case("irgc")
KATAR = load_case("katar747")

MODEL = "test-model"


def _mapper(responses: list) -> tuple[ArgumentMapper, FakeClient]:
    client = FakeClient(responses)
    return ArgumentMapper(client, MODEL), client


def _refined(case: dict) -> list:
    """Baut die S1-Objekte des Falls (ohne LLM) für den S2-Eingang."""
    refiner = ClaimRefiner(FakeClient([as_json(case["refiner_response"])]), MODEL)
    return refiner.refine(case["raw_claims"], core_thesis=case["core_thesis"])


def _mapping(cid: str, **over) -> dict:
    item = {
        "claim_id": cid, "argument_role": "core_claim",
        "counterfactual_impact": "high",
        "ratings": {d: 3 for d in RATING_DIMS}, "reason": "r",
    }
    item.update(over)
    return item


# --- Prompt-Vertrag: Nicht-Zuständigkeiten (Theorie §8.5) ------------------

def test_mapper_prompt_forbids_selection_and_weighting() -> None:
    """Auswahl und Gewichtung sind Policy/Code — das Modell darf sie nicht anfassen."""
    prompt = build_mapper_prompt(IRGC["refiner_response"], IRGC["core_thesis"])
    assert "NICHT-ZUSTÄNDIGKEITEN" in prompt
    assert "WÄHLST NICHT AUS" in prompt
    assert "GEWICHTEST NICHT" in prompt
    assert "Rangfolge" in prompt
    assert "Die Gewichte kennst du nicht" in prompt


def test_mapper_prompt_forbids_truth_judgement() -> None:
    prompt = build_mapper_prompt(IRGC["refiner_response"])
    assert "WAHR oder FALSCH" in prompt
    assert "kein Zweifel am Wahrheitsgehalt" in prompt


def test_mapper_prompt_never_leaks_policy_weights() -> None:
    """Gegenprobe: Die konkreten Policy-Gewichte tauchen nirgends im Prompt auf."""
    prompt = build_mapper_prompt(IRGC["refiner_response"])
    for forbidden in ("0.75", "0.6", "0.3", "policy", "priority", "Budget"):
        assert forbidden not in prompt, f"Policy-Interna im Prompt geleakt: {forbidden}"


def test_mapper_prompt_lists_all_rating_dims_and_expected_ids() -> None:
    prompt = build_mapper_prompt(IRGC["refiner_response"])
    for dim in IMPORTANCE_DIMS + RESEARCH_VALUE_DIMS:
        assert dim in prompt, f"Rating-Dimension {dim} fehlt im Prompt"
    assert "Erwartete IDs: 'c01a', 'c01b', 'c01c', 'c01d'" in prompt
    assert "jede genau einmal" in prompt


def test_mapper_context_is_yardstick_not_check_target() -> None:
    """Die Kernthese ist für S2 Bezugspunkt — aber kein Prüfgegenstand."""
    prompt = build_mapper_prompt(IRGC["refiner_response"], IRGC["core_thesis"])
    assert "Bezugspunkt für thesis_proximity — selbst NICHT prüfen" in prompt


# --- Referenzfälle --------------------------------------------------------

@pytest.mark.parametrize("case", [IRGC, KATAR], ids=["irgc", "katar747"])
def test_mapper_returns_one_mapping_per_unit(case) -> None:
    refined = _refined(case)
    mapper, client = _mapper([as_json(case["mapper_response"])])

    mappings = mapper.map_claims(refined, case["core_thesis"])

    assert len(mappings) == len(refined)
    assert [m.claim_id for m in mappings] == [rc.claim_id for rc in refined]
    assert client.call_count == 1


def test_katar_date_is_metadata_and_gift_is_core_claim() -> None:
    """Prüfbar ≠ prüfwürdig: das leicht prüfbare Datum ist kein Kernclaim."""
    refined = _refined(KATAR)
    mapper, _ = _mapper([as_json(KATAR["mapper_response"])])
    mappings = {m.claim_id: m for m in mapper.map_claims(refined, KATAR["core_thesis"])}

    assert mappings["c01a"].argument_role == "metadata"
    assert mappings["c01a"].counterfactual_impact == "low"
    assert mappings["c01b"].argument_role == "core_claim"


# --- ID-Echo (Anker 4) ----------------------------------------------------

def test_missing_id_is_rejected_with_concrete_message() -> None:
    with pytest.raises(ValueError) as exc:
        validate_mappings([_mapping("c01a")], ["c01a", "c01b"])
    assert "fehlen in der Antwort" in str(exc.value)
    assert "c01b" in str(exc.value)


def test_unknown_id_is_rejected() -> None:
    with pytest.raises(ValueError) as exc:
        validate_mappings([_mapping("c01a"), _mapping("c99z")], ["c01a"])
    assert "Unbekannte claim_ids" in str(exc.value)
    assert "c99z" in str(exc.value)


def test_duplicate_id_is_rejected() -> None:
    with pytest.raises(ValueError) as exc:
        validate_mappings([_mapping("c01a"), _mapping("c01a")], ["c01a"])
    assert "mehrfach" in str(exc.value)


def test_empty_mapping_array_is_rejected() -> None:
    with pytest.raises(ValueError) as exc:
        validate_mappings([], ["c01a"])
    assert "Leeres Array" in str(exc.value)


@pytest.mark.parametrize("bad", [
    {"argument_role": "chef_claim"},
    {"counterfactual_impact": "gigantisch"},
    {"ratings": {d: 9 for d in RATING_DIMS}},
    {"ratings": {d: -1 for d in RATING_DIMS}},
    {"ratings": {"thesis_proximity": 3}},
])
def test_schema_violations_are_rejected(bad) -> None:
    with pytest.raises(SchemaError):
        validate_mappings([_mapping("c01a", **bad)], ["c01a"])


def test_empty_refined_list_is_rejected_before_any_call() -> None:
    mapper, client = _mapper([])
    with pytest.raises(ValueError):
        mapper.map_claims([])
    assert client.call_count == 0


# --- Reparatur-Retry ------------------------------------------------------

def test_id_mismatch_triggers_repair_retry_before_join_claims() -> None:
    """Der ID-Bruch fällt in S2 auf — früh genug für den Retry mit Klartext."""
    refined = _refined(IRGC)
    incomplete = as_json([_mapping("c01a"), _mapping("c01b")])  # c01c/c01d fehlen
    mapper, client = _mapper([incomplete, as_json(IRGC["mapper_response"])])

    mappings = mapper.map_claims(refined, IRGC["core_thesis"])

    assert len(mappings) == 4
    assert client.call_count == 2
    repair = client.prompts[1]
    assert "fehlen in der Antwort" in repair
    assert "'c01c', 'c01d'" in repair or "c01c" in repair
    assert "WÄHLST NICHT AUS" in repair, "Ursprungsregeln gelten im Retry weiter"


def test_second_id_mismatch_escalates_openly() -> None:
    refined = _refined(IRGC)
    incomplete = as_json([_mapping("c01a")])
    mapper, client = _mapper([incomplete, incomplete])

    with pytest.raises(StageError) as exc:
        mapper.map_claims(refined)

    assert client.call_count == 2
    assert "ArgumentMapper" in str(exc.value)
    assert "nach Reparatur-Retry" in str(exc.value)


def test_api_error_escalates_without_repair_attempt() -> None:
    refined = _refined(IRGC)
    mapper, client = _mapper([error_response()])

    with pytest.raises(StageError) as exc:
        mapper.map_claims(refined)

    assert client.call_count == 1
    assert "API-Fehler" in str(exc.value)


# --- Kette S1 → S2 → S3 ---------------------------------------------------

@pytest.mark.parametrize("case", [IRGC, KATAR], ids=["irgc", "katar747"])
def test_stages_chain_into_policy_scorer(case) -> None:
    """Der Vertrag hält als Kette: S1-Output + S2-Output → join → Auswahl."""
    refined = _refined(case)
    mapper, _ = _mapper([as_json(case["mapper_response"])])
    mappings = mapper.map_claims(refined, case["core_thesis"])

    mapped = join_claims(refined, mappings)
    result = PolicyScorer.from_file().select(mapped, budget=8)

    assert result.selected_ids, "mindestens ein Claim muss recherchiert werden"
    assert set(result.selected_ids) <= {rc.claim_id for rc in refined}
    assert len(result.audits) == len(refined), "jede Prüfeinheit bekommt eine Auditspur"


def test_katar_metadata_date_never_displaces_the_core_claim() -> None:
    """Regression zur Kernthese des Moduls: prüfbar ≠ prüfwürdig."""
    refined = _refined(KATAR)
    mapper, _ = _mapper([as_json(KATAR["mapper_response"])])
    mappings = mapper.map_claims(refined, KATAR["core_thesis"])

    result = PolicyScorer.from_file().select(join_claims(refined, mappings), budget=1)

    assert result.selected_ids == ["c01b"], (
        "Bei Budget 1 muss der Geschenk-Kernclaim gewinnen, nicht das Flugdatum"
    )


def test_irgc_top_core_claim_wins_and_quota_shares_the_rest() -> None:
    """Dokumentiert die Quotensemantik bei kleinem Budget (Stand PR 1).

    Bei Budget 2 ergibt `core_claims_share: 0.6` genau EINEN A-Platz und
    `supporting_share: 0.3` einen B-Platz. Der stärkste Kernclaim (c01c) gewinnt;
    der zweite Kernclaim c01d wird trotz höherer priority (0.489) vom
    Subclaim c01b (0.433) verdrängt, weil die Klassenkontingente hier als
    Obergrenze wirken.

    Das ist die spezifizierte Auswahl, kein Defekt dieser Stufe — aber ein
    Tuning-Kandidat für den PO (siehe PR-Bericht): der IRGC-Fall ist genau der
    Fall, in dem die Kausalzurechnung nicht rausfallen sollte.
    """
    refined = _refined(IRGC)
    mapper, _ = _mapper([as_json(IRGC["mapper_response"])])
    mappings = mapper.map_claims(refined, IRGC["core_thesis"])

    result = PolicyScorer.from_file().select(join_claims(refined, mappings), budget=2)

    assert result.selected_ids == ["c01c", "c01b"]
    by_id = {a.claim_id: a for a in result.audits}
    assert by_id["c01c"].claim_class == "A", "stärkster Kernclaim ist gesetzt"
    assert by_id["c01d"].priority > by_id["c01b"].priority


def test_irgc_default_budget_covers_all_four_units() -> None:
    """Beim PO-Default-Budget 8 fällt keine der vier Prüfeinheiten hinten runter."""
    refined = _refined(IRGC)
    mapper, _ = _mapper([as_json(IRGC["mapper_response"])])
    mappings = mapper.map_claims(refined, IRGC["core_thesis"])

    result = PolicyScorer.from_file().select(join_claims(refined, mappings), budget=8)

    assert set(result.selected_ids) == {"c01a", "c01b", "c01c", "c01d"}
    # Kernclaims stehen vorn — die Klassenreihenfolge A vor B bleibt gewahrt.
    assert result.selected_ids[:2] == ["c01c", "c01d"]


def main() -> None:
    """Führt alle Tests ohne pytest aus (Parametrize-Fälle explizit)."""
    test_mapper_prompt_forbids_selection_and_weighting()
    test_mapper_prompt_forbids_truth_judgement()
    test_mapper_prompt_never_leaks_policy_weights()
    test_mapper_prompt_lists_all_rating_dims_and_expected_ids()
    test_mapper_context_is_yardstick_not_check_target()
    for case in (IRGC, KATAR):
        test_mapper_returns_one_mapping_per_unit(case)
        test_stages_chain_into_policy_scorer(case)
    test_katar_date_is_metadata_and_gift_is_core_claim()
    test_missing_id_is_rejected_with_concrete_message()
    test_unknown_id_is_rejected()
    test_duplicate_id_is_rejected()
    test_empty_mapping_array_is_rejected()
    for bad in [{"argument_role": "chef_claim"}, {"counterfactual_impact": "gigantisch"},
                {"ratings": {d: 9 for d in RATING_DIMS}},
                {"ratings": {d: -1 for d in RATING_DIMS}},
                {"ratings": {"thesis_proximity": 3}}]:
        test_schema_violations_are_rejected(bad)
    test_empty_refined_list_is_rejected_before_any_call()
    test_id_mismatch_triggers_repair_retry_before_join_claims()
    test_second_id_mismatch_escalates_openly()
    test_api_error_escalates_without_repair_attempt()
    test_katar_metadata_date_never_displaces_the_core_claim()
    test_irgc_top_core_claim_wins_and_quota_shares_the_rest()
    test_irgc_default_budget_covers_all_four_units()
    print("ALLE TESTS OK")


if __name__ == "__main__":
    main()
