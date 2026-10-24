"""Präzise JSON-Fehlerdiagnose + Quote-Heilung in den Plus-Stufen (v0.15.2).

Realtest 2026-10-24 (Quellenbündel-Probe, GLM 5.3 Flash): S2-Chunk 2 scheiterte
zweimal mit „kein parsebares JSON-Array" — Ursache war ein unescaptes ASCII-``"``
in einem ``reason``-String (``„Message received."``). Der generische Fehler ohne
Position wurde im Reparatur-Retry wortgleich wiederholt; zudem lag die Stelle
(Zeichen 4995) hinter dem 4000-Zeichen-Auszug des Reparatur-Prompts.

- **Teil A** — Syntaxfehler gehen mit Fehlerart, Zeile/Spalte/Position und
  Kontext-Zitat (±100 Zeichen) in die Vertragsbruch-Meldung; liegt der Fehler in
  einem String, folgt die gezielte Anführungszeichen-Anweisung.
- **Teil B** — Vor dem Reparatur-Retry eine deterministische, rein additive
  Quote-Heilung; Akzeptanz nur bei parse- UND schema-validem Ergebnis.

Fixture ``tests/fixtures/s2_glm_unescaped_quote.json``: beide realen
Fehl-Antworten (Erstversuch + Reparatur-Retry), unverändert aus den Debug-Logs.

Alles offline, gemockt — kein Netzwerk.

Lauf (ohne pytest):  python tests/test_json_diagnosis_quote_healing.py
"""
import difflib
import json
import logging
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.core.factcheck_plus.llm_stage import (
    DIAGNOSIS_CONTEXT_CHARS, JSONSyntaxError, StageError, extract_json_array,
    extract_json_object, heal_unescaped_quotes, run_json_stage,
)
from src.core.factcheck_plus.mapper import validate_mappings
from tests.factcheck_plus_helpers import FIXTURE_DIR, FakeClient, as_json, load_case

LOGGER_NAME = "src.core.factcheck_plus.llm_stage"


def _fixture() -> dict:
    """Lädt die beiden realen GLM-Fehl-Antworten samt erwarteter Chunk-IDs."""
    path = FIXTURE_DIR / "s2_glm_unescaped_quote.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _mapping(claim_id: str, role: str = "supporting_premise") -> dict:
    """Ein schema-valides S2-Mapping (für synthetische Fälle)."""
    keys = [
        "thesis_proximity", "conclusion_dependency", "harm_potential",
        "reach_mobilization", "concreteness", "non_triviality", "recency",
        "contestedness", "source_access", "evidence_gap", "discrepancy_potential",
    ]
    return {
        "claim_id": claim_id, "argument_role": role,
        "counterfactual_impact": "medium",
        "ratings": {k: 3 for k in keys}, "reason": "Begründung.",
    }


def _mapper_parse(ids: list[str]):
    """Die echte S2-Validierung als ``parse``-Callback."""
    return lambda raw: validate_mappings(raw, ids)


# --- 1. Reale Fixture: Heilung greift, kein Reparatur-Retry ------------------

@pytest.mark.parametrize("key", ["first_attempt", "repair_attempt"])
def test_real_fixture_is_unparsable_as_is(key) -> None:
    """Belegt den Ausgangsbefund: beide Antworten sind roh nicht parsebar."""
    with pytest.raises(JSONSyntaxError):
        extract_json_array(_fixture()[key])


@pytest.mark.parametrize("key", ["first_attempt", "repair_attempt"])
def test_real_fixture_heals_without_repair_call(key, caplog) -> None:
    """Quote-Heilung macht die reale Antwort parse- + schema-valide: genau 1 Call."""
    fx = _fixture()
    client = FakeClient([fx[key]])
    with caplog.at_level(logging.INFO, logger=LOGGER_NAME):
        result = run_json_stage(
            client, "m", "prompt", parse=_mapper_parse(fx["expected_claim_ids"]),
            stage_name="ArgumentMapper",
        )
    assert len(client.prompts) == 1
    assert [m.claim_id for m in result] == fx["expected_claim_ids"]
    assert "Quote-Heilung angewendet: 3 Stellen" in caplog.text


def test_healed_fixture_keeps_the_quoted_text() -> None:
    """Der reparierte reason-String trägt das Zitat inkl. ASCII-Schlussquote."""
    healed, count = heal_unescaped_quotes(_fixture()["first_attempt"])
    assert count == 3
    reasons = {o["claim_id"]: o["reason"] for o in json.loads(healed)}
    assert reasons["c17a"].startswith('Das kurze Zitat „Message received." dient')
    assert '„a fraud"' in reasons["c21b"]
    assert '„Q2"' in reasons["c23a"]


# --- 2. Unheilbar → Reparatur-Retry mit präziser Diagnose ---------------------

def test_unhealable_structure_goes_to_repair_with_diagnosis(caplog) -> None:
    """Abgerissene Struktur: Heilung lehnt ab, Reparatur-Prompt trägt die Diagnose."""
    broken = '[{"claim_id": "c01", "argument_role": "x" "ratings": }]'
    client = FakeClient([broken, as_json([_mapping("c01")])])
    with caplog.at_level(logging.INFO, logger=LOGGER_NAME):
        result = run_json_stage(
            client, "m", "prompt", parse=_mapper_parse(["c01"]), stage_name="S2",
        )
    assert [m.claim_id for m in result] == ["c01"]
    assert len(client.prompts) == 2
    repair = client.prompts[1]
    try:
        json.loads(broken)
    except json.JSONDecodeError as exc:
        err = exc
    assert err.msg in repair
    assert f"Zeile {err.lineno}, Spalte {err.colno}, Zeichen {err.pos}" in repair
    assert "--- ZITAT ANFANG ---" in repair and "⟦HIER⟧" in repair
    assert "Quote-Heilung verworfen" in caplog.text


def test_structural_error_without_quotes_skips_healing() -> None:
    """Kein Quote-Problem (doppeltes Komma): keine Heilung, kein String-Hinweis."""
    broken = '[{"claim_id": "c01",, "x": 1}]'
    with pytest.raises(JSONSyntaxError) as exc:
        extract_json_array(broken)
    msg = str(exc.value)
    assert "kein parsebares JSON-Array" in msg
    assert "Expecting property name" in msg
    assert "unescapte Anführungszeichen" not in msg
    assert heal_unescaped_quotes(broken) == (broken, 0)


def test_missing_separator_between_strings_gets_no_quote_hint() -> None:
    """``"a" "b"`` ist ein fehlendes Trennzeichen, kein inneres Zitat → kein Hinweis."""
    with pytest.raises(JSONSyntaxError) as exc:
        extract_json_array('[{"claim_id": "c01" "x": 1}]')
    assert "Expecting ',' delimiter" in str(exc.value)
    assert "unescapte Anführungszeichen" not in str(exc.value)


def test_string_error_carries_targeted_quote_hint() -> None:
    """Fehler in einem String → gezielte Anweisung zu unescapten Anführungszeichen."""
    with pytest.raises(JSONSyntaxError) as exc:
        extract_json_array('[{"reason": "Er sagte "Ja" und ging", "x": ]')
    assert "Prüfe unescapte Anführungszeichen in String-Werten" in str(exc.value)


def test_error_beyond_repair_excerpt_is_quoted() -> None:
    """Fehler hinter den ersten 4000 Zeichen landet trotzdem als Zitat im Retry."""
    padding = ", ".join(as_json(_mapping(f"c{i:02d}")) for i in range(1, 20))
    broken = f"[{padding}, {{\"claim_id\": \"c20\" \"KAPUTT_MARKE\": 1}}]"
    assert broken.index("KAPUTT_MARKE") > 4000
    client = FakeClient([broken, broken])
    with pytest.raises(StageError):
        run_json_stage(client, "m", "p", parse=lambda raw: raw, stage_name="S")
    assert "KAPUTT_MARKE" in client.prompts[1]


def test_context_window_is_bounded() -> None:
    """Das Zitat ist auf ±DIAGNOSIS_CONTEXT_CHARS um die Fehlerstelle begrenzt."""
    text = "[" + "1, " * 500 + "x]"
    with pytest.raises(JSONSyntaxError) as exc:
        extract_json_array(text)
    quote = str(exc.value).split("--- ZITAT ANFANG ---\n")[1].split("\n--- ZITAT ENDE")[0]
    assert len(quote) <= 2 * DIAGNOSIS_CONTEXT_CHARS + len("⟦HIER⟧") + 2


def test_heal_accepted_only_if_schema_passes(caplog) -> None:
    """Parsebar nach Heilung, aber Schema bricht → Reparatur mit JSON-Diagnose."""
    fx = _fixture()
    client = FakeClient([fx["first_attempt"], fx["first_attempt"]])
    with caplog.at_level(logging.INFO, logger=LOGGER_NAME):
        with pytest.raises(StageError):
            run_json_stage(
                client, "m", "p", parse=_mapper_parse(["c99"]), stage_name="S2",
            )
    assert len(client.prompts) == 2
    assert "JSON-Syntaxfehler: Expecting ',' delimiter" in client.prompts[1]
    assert "Quote-Heilung verworfen" in caplog.text
    assert "Quote-Heilung angewendet" not in caplog.text


def test_object_stage_gets_diagnosis_and_healing() -> None:
    """S5-Pfad (JSON-Objekt) profitiert identisch."""
    broken = '{"verdict": "bestätigt", "reason": "Laut „Reuters" belegt."}'
    with pytest.raises(JSONSyntaxError) as exc:
        extract_json_object(broken)
    assert "kein parsebares JSON-Objekt" in str(exc.value)
    client = FakeClient([broken])
    result = run_json_stage(
        client, "m", "p", parse=lambda raw: raw, stage_name="S5",
        extract=extract_json_object,
    )
    assert result["reason"] == 'Laut „Reuters" belegt.'
    assert len(client.prompts) == 1


# --- 3. Heilung ändert nie Inhalte -------------------------------------------

@pytest.mark.parametrize("key", ["first_attempt", "repair_attempt"])
def test_healing_only_inserts_backslashes(key) -> None:
    """Diff Original → geheilt besteht ausschließlich aus eingefügten Backslashes."""
    original = _fixture()[key]
    healed, count = heal_unescaped_quotes(original)
    ops = difflib.SequenceMatcher(None, original, healed, autojunk=False).get_opcodes()
    inserted = [healed[j1:j2] for tag, _, _, j1, j2 in ops if tag != "equal"]
    assert all(tag in ("equal", "insert") for tag, *_ in ops)
    assert "".join(inserted) == "\\" * count
    assert len(healed) == len(original) + count


@pytest.mark.parametrize("key", ["first_attempt", "repair_attempt"])
def test_healed_strings_equal_original_text(key) -> None:
    """Jeder geparste String steht nach Unescape wörtlich im Original-Output."""
    original = _fixture()[key]
    healed, _ = heal_unescaped_quotes(original)
    for obj in json.loads(healed):
        assert obj["reason"] in original
        assert obj["claim_id"] in original


def test_existing_escapes_are_preserved() -> None:
    """Bereits escapte Quotes bleiben unangetastet; nur die nackten werden ergänzt."""
    text = '{"r": "a \\"b\\" und "c" d"}'
    healed, count = heal_unescaped_quotes(text)
    assert count == 2
    assert json.loads(healed)["r"] == 'a "b" und "c" d'


def test_valid_json_is_never_healed() -> None:
    """Valides JSON ist ein Fixpunkt der Heilung (0 Stellen, identischer Text)."""
    for name in ("irgc", "katar747"):
        case = load_case(name)
        for key in ("refiner_response", "mapper_response"):
            text = json.dumps(case[key], ensure_ascii=False, indent=2)
            assert heal_unescaped_quotes(text) == (text, 0)


# --- 4. Regression ------------------------------------------------------------

def test_valid_json_no_healing_no_log(caplog) -> None:
    """Valides JSON: ein Call, keine Heilung im Log, unverändertes Ergebnis."""
    client = FakeClient([as_json([_mapping("c01")])])
    with caplog.at_level(logging.INFO, logger=LOGGER_NAME):
        result = run_json_stage(
            client, "m", "p", parse=_mapper_parse(["c01"]), stage_name="S2",
        )
    assert [m.claim_id for m in result] == ["c01"]
    assert len(client.prompts) == 1
    assert "Quote-Heilung" not in caplog.text


def test_schema_violation_message_unchanged() -> None:
    """Enum-Vertragsbruch: spezifische Schema-Meldung, keine JSON-Diagnose."""
    bad = _mapping("c01", role="source_attribution")
    client = FakeClient([as_json([bad]), as_json([_mapping("c01")])])
    run_json_stage(client, "m", "p", parse=_mapper_parse(["c01"]), stage_name="S2")
    repair = client.prompts[1]
    assert "source_attribution" in repair
    assert "JSON-Syntaxfehler" not in repair
    assert "ZITAT ANFANG" not in repair


def main() -> None:
    """Führt die Tests ohne pytest aus (ohne caplog-abhängige Fälle)."""
    for key in ("first_attempt", "repair_attempt"):
        test_real_fixture_is_unparsable_as_is(key)
        test_healing_only_inserts_backslashes(key)
        test_healed_strings_equal_original_text(key)
    test_healed_fixture_keeps_the_quoted_text()
    test_structural_error_without_quotes_skips_healing()
    test_missing_separator_between_strings_gets_no_quote_hint()
    test_string_error_carries_targeted_quote_hint()
    test_error_beyond_repair_excerpt_is_quoted()
    test_context_window_is_bounded()
    test_object_stage_gets_diagnosis_and_healing()
    test_existing_escapes_are_preserved()
    test_valid_json_is_never_healed()
    test_schema_violation_message_unchanged()
    print("ALLE TESTS OK")


if __name__ == "__main__":
    main()
