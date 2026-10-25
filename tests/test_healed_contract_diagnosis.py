"""Doppel-Diagnose im Reparatur-Retry + S2-Rollen-Klarstellung (v0.15.3).

Realtest 2026-10-24 abends (Bündel-Probe 5, GLM 5.3 Flash): S2-Chunk 1 hatte
ZWEI Defekte gleichzeitig — ein unescaptes ``"`` UND 2× die erfundene Rolle
``source_attribution_placeholder``. v0.15.2 heilte den Quote, die Schema-Prüfung
fand danach den Enum-Fehler, die Heilung wurde korrekt verworfen — aber in den
Reparatur-Prompt ging NUR die JSON-Diagnose. Der Retry escapte den Quote
korrekt, steigerte den Placeholder jedoch von 2 auf 5 Vorkommen.

- **Teil A** — Heilung parsebar, aber Vertragsbruch → die Meldung trägt BEIDE
  Diagnosen, den Vertragsbruch zuerst (im Wortlaut direkter Schema-Fehler).
- **Teil B** — Der Mapper-Prompt stellt klar, dass ``claim_type`` keine
  ``argument_role`` ist.

Fixture ``tests/fixtures/s2_glm_quote_plus_invalid_role.json``: Erstversuch
(21-49-10) + Reparatur-Retry (21-49-33), unverändert aus den Debug-Logs.

Alles offline, gemockt — kein Netzwerk.

Lauf (ohne pytest):  python tests/test_healed_contract_diagnosis.py
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.core.factcheck_plus import build_mapper_prompt
from src.core.factcheck_plus.llm_stage import (
    JSONSyntaxError, StageError, extract_json_array, heal_unescaped_quotes,
    run_json_stage,
)
from src.core.factcheck_plus.mapper import validate_mappings
from src.core.factcheck_plus.schemas import ARGUMENT_ROLES, RATING_DIMS
from tests.factcheck_plus_helpers import FIXTURE_DIR, FakeClient, as_json, load_case

ROLE_ERROR = (
    "$.argument_mapping.argument_role: 'source_attribution_placeholder' nicht in"
)
HEALED_PREFIX = "Nach automatischer Korrektur der Anführungszeichen bleibt"


def _fixture(name: str) -> dict:
    """Lädt eine reale S2-Fehl-Antwort-Fixture aus ``tests/fixtures/``."""
    return json.loads((FIXTURE_DIR / f"{name}.json").read_text(encoding="utf-8"))


COMBINED = _fixture("s2_glm_quote_plus_invalid_role")
QUOTE_ONLY = _fixture("s2_glm_unescaped_quote")


def _mapping(cid: str, role: str = "context") -> dict:
    """Ein (bis auf die Rolle) schema-valides S2-Mapping."""
    return {
        "claim_id": cid, "argument_role": role, "counterfactual_impact": "low",
        "ratings": {d: 2 for d in RATING_DIMS}, "reason": "r",
    }


def _run(responses: list, ids: list[str]) -> FakeClient:
    """Lässt S2-Validierung über ``run_json_stage`` laufen; Fehler werden geschluckt."""
    client = FakeClient(responses)
    try:
        run_json_stage(
            client, "m", "p", parse=lambda raw: validate_mappings(raw, ids),
            stage_name="ArgumentMapper",
        )
    except StageError:
        pass
    return client


# --- Fixture-Befund -----------------------------------------------------------

def test_fixture_has_both_defects() -> None:
    """Roh unparsebar; nach Heilung parsebar, aber mit erfundener Rolle."""
    raw = COMBINED["first_attempt"]
    with pytest.raises(JSONSyntaxError):
        extract_json_array(raw)
    healed, count = heal_unescaped_quotes(raw)
    assert count == 1
    roles = [m["argument_role"] for m in extract_json_array(healed)]
    assert roles.count("source_attribution_placeholder") == 2
    assert COMBINED["repair_attempt"].count("source_attribution_placeholder") == 5


# --- Teil A: Doppel-Diagnose ------------------------------------------------

def test_combined_fixture_repair_names_both_problems_schema_first() -> None:
    """Heilung verworfen → Reparatur-Prompt trägt Schema-Fehler UND JSON-Diagnose."""
    client = _run(
        [COMBINED["first_attempt"], COMBINED["repair_attempt"]],
        COMBINED["expected_claim_ids"],
    )
    assert len(client.prompts) == 2
    error_block = client.prompts[1].split("KONKRETER FEHLER:\n")[1].split(
        "\nDEINE VORIGE ANTWORT")[0]
    assert HEALED_PREFIX in error_block
    assert ROLE_ERROR in error_block
    assert "JSON-Syntaxfehler: Expecting ',' delimiter" in error_block
    assert "⟦HIER⟧" in error_block
    assert "Prüfe unescapte Anführungszeichen" in error_block
    assert error_block.index(ROLE_ERROR) < error_block.index("JSON-Syntaxfehler")


def test_final_stage_error_still_names_the_role_problem() -> None:
    """Scheitert auch der Retry, nennt die Abschlussmeldung den Enum-Fehler."""
    client = FakeClient([COMBINED["first_attempt"], COMBINED["repair_attempt"]])
    with pytest.raises(StageError) as exc:
        run_json_stage(
            client, "m", "p",
            parse=lambda raw: validate_mappings(raw, COMBINED["expected_claim_ids"]),
            stage_name="ArgumentMapper",
        )
    assert "source_attribution_placeholder" in str(exc.value)


def test_combined_synthetic_case() -> None:
    """Synthetisch: Quote + Enum-Bruch → beide Diagnosen, Schema-Teil zuerst."""
    bad = as_json([_mapping("c01", role="source_attribution")]).replace(
        '"reason": "r"', '"reason": "Laut „Reuters" belegt."')
    client = _run([bad, as_json([_mapping("c01")])], ["c01"])
    repair = client.prompts[1]
    assert repair.index("'source_attribution' nicht in") < repair.index(
        "JSON-Syntaxfehler")


# --- Regressionen -------------------------------------------------------------

@pytest.mark.parametrize("key", ["first_attempt", "repair_attempt"])
def test_quote_only_still_heals_without_retry(key) -> None:
    """Probe-4-Fixtures: Heilung genügt, genau 1 Call."""
    client = _run([QUOTE_ONLY[key]], QUOTE_ONLY["expected_claim_ids"])
    assert len(client.prompts) == 1


def test_pure_schema_error_message_unchanged() -> None:
    """Parsebares JSON mit kaputtem Enum: nur die spezifische Meldung."""
    client = _run(
        [as_json([_mapping("c01", role="source_attribution")]),
         as_json([_mapping("c01")])], ["c01"],
    )
    repair = client.prompts[1]
    assert "'source_attribution' nicht in" in repair
    assert HEALED_PREFIX not in repair
    assert "JSON-Syntaxfehler" not in repair


def test_pure_json_error_without_healing_success_unchanged() -> None:
    """Unheilbare Syntax: Meldung wie v0.15.2, ohne Vertragsbruch-Präfix."""
    broken = '[{"claim_id": "c01", "argument_role": "x" "ratings": }]'
    client = _run([broken, as_json([_mapping("c01")])], ["c01"])
    repair = client.prompts[1]
    assert "JSON-Syntaxfehler" in repair
    assert HEALED_PREFIX not in repair


# --- Teil B: S2-Rollen-Klarstellung -----------------------------------------

def test_mapper_prompt_separates_claim_type_from_role() -> None:
    """Der Mapper-Vertrag verbietet claim_type (auch abgewandelt) als Rolle."""
    prompt = build_mapper_prompt(load_case("katar747")["refiner_response"])
    assert "AUSSCHLIESSLICH einen dieser fünf Werte" in prompt
    assert "ist KEINE Rolle und erscheint NIE als `argument_role`" in prompt
    assert "auch nicht abgewandelt oder mit Zusätzen" in prompt
    assert "Attributions-Einheiten erhalten die Rolle ihrer argumentativen Funktion" in prompt
    assert len(ARGUMENT_ROLES) == 5  # „fünf" im Prompt bleibt wahr


def main() -> None:
    """Führt alle Tests ohne pytest aus."""
    test_fixture_has_both_defects()
    test_combined_fixture_repair_names_both_problems_schema_first()
    test_final_stage_error_still_names_the_role_problem()
    test_combined_synthetic_case()
    for key in ("first_attempt", "repair_attempt"):
        test_quote_only_still_heals_without_retry(key)
    test_pure_schema_error_message_unchanged()
    test_pure_json_error_without_healing_success_unchanged()
    test_mapper_prompt_separates_claim_type_from_role()
    print("ALLE TESTS OK")


if __name__ == "__main__":
    main()
