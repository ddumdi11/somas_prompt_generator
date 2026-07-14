"""Tests für Faktencheck Plus PR 3: ResearchPlanner (S4).

Deckt Theorie §5.1 und Spec §3/S4 ab:
- Nicht-Zuständigkeiten im Prompt (Theorie §8.5): der Planner recherchiert nicht,
  urteilt nicht, erfindet keine Quellen.
- Rechercheauftrag statt „Ist das wahr?" — `research_questions` und
  `counter_hypotheses` dürfen nie leer sein (Riegel gegen Bestätigungsfehler).
- Die zwei Pflichtfelder aus Theorie §5.1 (v0.2/v0.3): `canonical_targets`
  (direktes Prüfziel statt Suchbegriffen) und `language_hints` (Originalsprache).
- Quellenhierarchie (§5.2) und verbotene Abkürzungen stehen als Policy im Prompt.

Alles gemockt — kein Netzwerk.

Lauf (ohne pytest):  python tests/test_research_planner_contract.py
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.core.factcheck_plus import (
    ClaimRefiner, ResearchPlanner, StageError, build_planner_prompt,
    validate_cards,
)
from src.core.factcheck_plus.schemas import SchemaError
from tests.factcheck_plus_helpers import (
    FakeClient, as_json, error_response, load_case, research_card,
)

IRGC = load_case("irgc")
MODEL = "test-model"


def _refined(case: dict) -> list:
    refiner = ClaimRefiner(FakeClient([as_json(case["refiner_response"])]), MODEL)
    return refiner.refine(case["raw_claims"], core_thesis=case["core_thesis"])


def _planner(responses: list) -> tuple[ResearchPlanner, FakeClient]:
    client = FakeClient(responses)
    return ResearchPlanner(client, MODEL), client


def _payload(case: dict) -> list[dict]:
    return case["refiner_response"]


# --- Prompt-Vertrag -------------------------------------------------------

def test_planner_prompt_forbids_research_and_verdict():
    prompt = build_planner_prompt(_payload(IRGC))
    assert "NICHT-ZUSTÄNDIGKEITEN" in prompt
    assert "RECHERCHIERST NICHT" in prompt
    assert "nimmst kein Verdikt vorweg" in prompt
    assert "erfindest KEINE Quellen" in prompt


def test_planner_prompt_states_the_core_rule_against_open_truth_questions():
    """Theorie §5.1: „Ist das wahr?" erzeugt Bestätigungsfehler."""
    prompt = build_planner_prompt(_payload(IRGC))
    assert "Ist das wahr?" in prompt
    assert "Bestätigungsfehler" in prompt


def test_planner_prompt_carries_source_hierarchy_and_forbidden_shortcuts():
    prompt = build_planner_prompt(_payload(IRGC))
    assert "Primärquellen" in prompt
    assert "NICHT als alleiniger Beweis" in prompt
    assert "Such-Snippets nur zur Hypothesenbildung" in prompt
    assert "Snippet als Beleg" in prompt


def test_planner_prompt_demands_both_mandatory_fields():
    """canonical_targets und language_hints sind Pflichtfelder (Theorie §5.1)."""
    prompt = build_planner_prompt(_payload(IRGC))
    assert "canonical_targets" in prompt
    assert "arXiv-ID" in prompt
    assert "generische Suchen verfehlen solche Belege" in prompt
    assert "language_hints" in prompt
    assert "ORIGINALSPRACHE" in prompt
    assert "Transliteration" in prompt


def test_planner_prompt_lists_claims_with_their_anchors():
    prompt = build_planner_prompt(_payload(IRGC))
    assert "c01c [quantitative]" in prompt
    assert "Entitäten: IRGC, Europa" in prompt
    assert "Erwartete IDs: 'c01a', 'c01b', 'c01c', 'c01d'" in prompt


# --- Validierung ----------------------------------------------------------

def test_valid_cards_pass():
    cards = validate_cards([research_card("c01a")], ["c01a"])
    assert cards[0].claim_id == "c01a"
    assert cards[0].canonical_targets == []
    assert cards[0].language_hints == []


def test_empty_research_questions_are_rejected():
    with pytest.raises(ValueError) as exc:
        validate_cards([research_card("c01a", research_questions=[])], ["c01a"])
    assert "research_questions" in str(exc.value)
    assert "Ist das wahr?" in str(exc.value)


def test_empty_counter_hypotheses_are_rejected():
    """Gegenhypothesen sind der Riegel gegen Bestätigungsfehler — nie leer."""
    with pytest.raises(ValueError) as exc:
        validate_cards([research_card("c01a", counter_hypotheses=[])], ["c01a"])
    assert "counter_hypotheses" in str(exc.value)
    assert "Bestätigungsfehler" in str(exc.value)


def test_whitespace_only_entries_do_not_satisfy_mandatory_lists():
    with pytest.raises(ValueError):
        validate_cards([research_card("c01a", counter_hypotheses=["   "])], ["c01a"])


def test_missing_mandatory_field_is_a_schema_error():
    """canonical_targets/language_hints müssen ANWESEND sein (leer ist ok)."""
    card = research_card("c01a")
    del card["canonical_targets"]
    with pytest.raises(SchemaError) as exc:
        validate_cards([card], ["c01a"])
    assert "canonical_targets" in str(exc.value)


def test_mandatory_fields_may_be_empty_lists():
    """Nicht jeder Claim zeigt auf ein Artefakt oder einen fremdsprachigen Raum."""
    cards = validate_cards(
        [research_card("c01a", canonical_targets=[], language_hints=[])], ["c01a"],
    )
    assert cards[0].canonical_targets == []


def test_canonical_targets_are_carried_through():
    cards = validate_cards(
        [research_card("c01a", canonical_targets=["arXiv:2108.11896"],
                       language_hints=["فارسی: مثال", "Transliteration: mesal"])],
        ["c01a"],
    )
    assert cards[0].canonical_targets == ["arXiv:2108.11896"]
    assert len(cards[0].language_hints) == 2


@pytest.mark.parametrize("raw, ids, needle", [
    ([], ["c01a"], "Leeres Array"),
    ([research_card("c01a")], ["c01a", "c01b"], "fehlt die Recherchekarte"),
    ([research_card("c01a"), research_card("c99")], ["c01a"], "Unbekannte claim_ids"),
    ([research_card("c01a"), research_card("c01a")], ["c01a"], "mehrfach"),
])
def test_id_violations_are_rejected(raw, ids, needle):
    with pytest.raises(ValueError) as exc:
        validate_cards(raw, ids)
    assert needle in str(exc.value)


# --- Stufe ----------------------------------------------------------------

def test_planner_returns_one_card_per_claim():
    refined = _refined(IRGC)
    cards_json = as_json([research_card(rc.claim_id) for rc in refined])
    planner, client = _planner([cards_json])

    cards = planner.plan(refined, IRGC["core_thesis"])

    assert [c.claim_id for c in cards] == [rc.claim_id for rc in refined]
    assert client.call_count == 1


def test_missing_counter_hypotheses_trigger_repair_retry():
    refined = _refined(IRGC)
    broken = as_json([research_card(rc.claim_id, counter_hypotheses=[]) for rc in refined])
    good = as_json([research_card(rc.claim_id) for rc in refined])
    planner, client = _planner([broken, good])

    cards = planner.plan(refined)

    assert len(cards) == 4
    assert client.call_count == 2
    assert "Bestätigungsfehler" in client.prompts[1]
    assert "RECHERCHIERST NICHT" in client.prompts[1], "Ursprungsregeln gelten weiter"


def test_second_violation_escalates_openly():
    refined = _refined(IRGC)
    broken = as_json([research_card(rc.claim_id, research_questions=[]) for rc in refined])
    planner, client = _planner([broken, broken])

    with pytest.raises(StageError) as exc:
        planner.plan(refined)

    assert client.call_count == 2
    assert "ResearchPlanner" in str(exc.value)


def test_api_error_escalates_without_repair():
    refined = _refined(IRGC)
    planner, client = _planner([error_response()])
    with pytest.raises(StageError) as exc:
        planner.plan(refined)
    assert client.call_count == 1
    assert "API-Fehler" in str(exc.value)


def test_empty_claims_rejected_before_any_call():
    planner, client = _planner([])
    with pytest.raises(ValueError):
        planner.plan([])
    assert client.call_count == 0


def main():
    """Führt alle Tests ohne pytest aus (Parametrize-Fälle explizit)."""
    test_planner_prompt_forbids_research_and_verdict()
    test_planner_prompt_states_the_core_rule_against_open_truth_questions()
    test_planner_prompt_carries_source_hierarchy_and_forbidden_shortcuts()
    test_planner_prompt_demands_both_mandatory_fields()
    test_planner_prompt_lists_claims_with_their_anchors()
    test_valid_cards_pass()
    test_empty_research_questions_are_rejected()
    test_empty_counter_hypotheses_are_rejected()
    test_whitespace_only_entries_do_not_satisfy_mandatory_lists()
    test_missing_mandatory_field_is_a_schema_error()
    test_mandatory_fields_may_be_empty_lists()
    test_canonical_targets_are_carried_through()
    for raw, ids, needle in [
        ([], ["c01a"], "Leeres Array"),
        ([research_card("c01a")], ["c01a", "c01b"], "fehlt die Recherchekarte"),
        ([research_card("c01a"), research_card("c99")], ["c01a"], "Unbekannte claim_ids"),
        ([research_card("c01a"), research_card("c01a")], ["c01a"], "mehrfach"),
    ]:
        test_id_violations_are_rejected(raw, ids, needle)
    test_planner_returns_one_card_per_claim()
    test_missing_counter_hypotheses_trigger_repair_retry()
    test_second_violation_escalates_openly()
    test_api_error_escalates_without_repair()
    test_empty_claims_rejected_before_any_call()
    print("ALLE TESTS OK")


if __name__ == "__main__":
    main()
