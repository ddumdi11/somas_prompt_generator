"""Tests für S1/S2-Chunking gegen Claim-Fluten (v0.15.1).

Anlass (Realtest 2026-08-30/31, „Axis of Truth", DeepSeek V4 Pro): Die Analyse
extrahierte 69 Roh-Claims; der Ein-Call-Refiner (jede Prüfeinheit echot
`original_text` + `normalized_claim`) lief in beiden Versuchen bis exakt 32.768
Tokens und wurde abgeschnitten. Fix: Batching à `S1_CHUNK_SIZE` (S1) bzw.
`S2_CHUNK_SIZE` (S2), globale IDs bleiben stabil (`start_index`), Merge + globale
Prüfung, Reparatur-Retry/Trunkierungs-Gate pro Chunk.

Fixture `refiner_axis_of_truth_claims.json` ist die ECHTE 69-Claim-Liste aus dem
S1-Request des Realtests (14.343 Zeichen) — authentischer als synthetisch.

Alles offline, gemockt — kein Netzwerk.

Lauf (ohne pytest):
    QT_QPA_PLATFORM=offscreen python tests/test_s1_s2_chunking.py
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.core.api_client import APIResponse, APIStatus
from src.core.factcheck_plus.aggregate import build_transparency
from src.core.factcheck_plus.llm_stage import StageError
from src.core.factcheck_plus.mapper import ArgumentMapper, S2_CHUNK_SIZE
from src.core.factcheck_plus.models import RefinedClaim, join_claims
from src.core.factcheck_plus.policy_scorer import PolicyScorer
from src.core.factcheck_plus.prompts import build_refiner_prompt
from src.core.factcheck_plus.refiner import ClaimRefiner, S1_CHUNK_SIZE
from tests.factcheck_plus_helpers import FakeClient, as_json

FIXTURES = Path(__file__).resolve().parent / "fixtures"
CLAIMS_69 = json.loads(
    (FIXTURES / "refiner_axis_of_truth_claims.json").read_text(encoding="utf-8")
)

_RATING_DIMS = [
    "thesis_proximity", "conclusion_dependency", "harm_potential",
    "reach_mobilization", "concreteness", "non_triviality", "recency",
    "contestedness", "source_access", "evidence_gap", "discrepancy_potential",
]


# --- Fixture-Bausteine (identische Atomisierung: 1 Roh-Claim → 1 Prüfeinheit) ---

def _refined_dict(cid: str) -> dict:
    return {
        "claim_id": cid, "parent_id": None,
        "original_text": f"Rohtext {cid}", "normalized_claim": f"Prüfbarer Satz {cid}.",
        "claim_type": "hard_fact", "entities": [], "timeframe": None, "metric": None,
    }


def _mapping_dict(cid: str) -> dict:
    return {
        "claim_id": cid, "argument_role": "supporting_premise",
        "counterfactual_impact": "high",
        "ratings": {d: 3 for d in _RATING_DIMS}, "reason": "Kurzer Grund.",
    }


def _ids(offset: int, length: int) -> list[str]:
    """Globale Claim-IDs c{offset+1}..c{offset+length}."""
    return [f"c{i:02d}" for i in range(offset + 1, offset + length + 1)]


def _s1_response(offset: int, length: int) -> str:
    return as_json([_refined_dict(cid) for cid in _ids(offset, length)])


def _truncated() -> APIResponse:
    """Valid-aussehende, aber bei der Token-Grenze abgeschnittene Antwort."""
    return APIResponse(
        status=APIStatus.RECEIVED, content='[{"claim_id": "c31", "normalized',
        finish_reason="length",
    )


# === S1: Refiner-Chunking ==================================================

def test_s1_69_claims_five_chunks_complete() -> None:
    """69 Roh-Claims → 5 Chunks (15/15/15/15/9), Merge vollständig, Kontext je Call."""
    sizes = [15, 15, 15, 15, 9]
    offsets = [0, 15, 30, 45, 60]
    client = FakeClient([_s1_response(o, s) for o, s in zip(offsets, sizes)])

    merged = ClaimRefiner(client, "m").refine(
        CLAIMS_69, core_thesis="Kernthese XYZ", anchor_date="24. August 2026",
    )

    assert client.call_count == 5, client.call_count
    assert len(merged) == 69
    assert {c.claim_id for c in merged} == {f"c{i:02d}" for i in range(1, 70)}
    # Kontext (Kernthese + Zeitanker) steht in JEDEM Chunk-Call.
    for p in client.prompts:
        assert "Kernthese XYZ" in p
        assert "24. August 2026" in p
    # Chunk-Isolation: globale IDs, kein Reset auf c01.
    assert "c01:" in client.prompts[0] and "c16:" not in client.prompts[0]
    assert "c16:" in client.prompts[1] and "c31:" not in client.prompts[1]
    assert "c61:" in client.prompts[4] and "c69:" in client.prompts[4]
    print("  s1_69_claims_five_chunks_complete OK")


def test_s1_small_input_single_call_byte_identical() -> None:
    """≤ S1_CHUNK_SIZE → genau 1 Call, Prompt byte-identisch zum Direkt-Bau (Regression)."""
    claims = [f"Behauptung Nummer {i}" for i in range(1, 11)]  # 10 ≤ 15
    client = FakeClient([_s1_response(0, 10)])

    merged = ClaimRefiner(client, "m").refine(claims, core_thesis="T", source_hint="Q")

    assert client.call_count == 1
    assert len(merged) == 10
    # Der gesendete Prompt ist identisch zum ungechunkten build_refiner_prompt.
    expected = build_refiner_prompt(claims, "T", "Q", "", start_index=1)
    assert client.prompts[0] == expected
    print("  s1_small_input_single_call_byte_identical OK")


def test_s1_repair_retry_only_in_affected_chunk() -> None:
    """Kaputtes JSON in Chunk 2 → 1 Reparatur-Retry NUR dort (Chunk 1 unberührt)."""
    claims = [f"Claim {i}" for i in range(1, 31)]  # 30 → 2 Chunks (15/15)
    client = FakeClient([
        _s1_response(0, 15),          # Chunk 1: gültig, 1 Call
        "kein JSON",                  # Chunk 2: kaputt → Reparatur
        _s1_response(15, 15),         # Chunk 2: Reparatur gültig
    ])

    merged = ClaimRefiner(client, "m").refine(claims)

    assert client.call_count == 3, client.call_count
    assert len(merged) == 30
    # Der Retry betraf Chunk 2 (c16-Prompt zweimal), Chunk 1 (c01) genau einmal.
    assert sum("c16:" in p for p in client.prompts) == 2
    assert sum("c01:" in p for p in client.prompts) == 1
    print("  s1_repair_retry_only_in_affected_chunk OK")


def test_s1_truncation_in_chunk_raises_no_further_calls() -> None:
    """Trunkierung in Chunk 3 → StageError, kein Call für Chunk 4."""
    claims = [f"Claim {i}" for i in range(1, 51)]  # 50 → 4 Chunks (15/15/15/5)
    client = FakeClient([
        _s1_response(0, 15),   # Chunk 1
        _s1_response(15, 15),  # Chunk 2
        _truncated(),          # Chunk 3: abgeschnitten → StageError
        # Chunk 4 darf NICHT mehr aufgerufen werden.
    ])

    with pytest.raises(StageError) as exc:
        ClaimRefiner(client, "m").refine(claims)

    assert "abgeschnitten" in str(exc.value)
    assert client.call_count == 3, "Chunk 4 hätte nicht mehr laufen dürfen"
    print("  s1_truncation_in_chunk_raises_no_further_calls OK")


def test_s1_cancel_between_chunks_stops() -> None:
    """Abbruch nach Chunk 2 → keine weiteren Calls, Teilergebnis ohne globale Prüfung."""
    claims = [f"Claim {i}" for i in range(1, 51)]  # 50 → 4 Chunks
    client = FakeClient([_s1_response(0, 15), _s1_response(15, 15)])

    # Abbruch, sobald 2 Calls erfolgt sind (greift dann vor Chunk 3).
    merged = ClaimRefiner(client, "m").refine(
        claims, should_cancel=lambda: client.call_count >= 2,
    )

    assert client.call_count == 2
    assert len(merged) == 30  # nur die ersten beiden Chunks, kein StageError
    print("  s1_cancel_between_chunks_stops OK")


# === S2: Mapper-Chunking ===================================================

def _refined_objs(n: int) -> list[RefinedClaim]:
    return [RefinedClaim.from_dict(_refined_dict(f"c{i:02d}")) for i in range(1, n + 1)]


def test_s2_ninety_units_chunks_complete() -> None:
    """90 Prüfeinheiten → Chunks (20×4 + 10), Bijektion je Chunk, Merge vollständig."""
    refined = _refined_objs(90)
    offsets = list(range(0, 90, S2_CHUNK_SIZE))  # 0,20,40,60,80
    client = FakeClient([
        as_json([_mapping_dict(rc.claim_id) for rc in refined[o:o + S2_CHUNK_SIZE]])
        for o in offsets
    ])

    mappings = ArgumentMapper(client, "m").map_claims(refined, core_thesis="T")

    assert client.call_count == 5, client.call_count  # 20/20/20/20/10
    assert len(mappings) == 90
    assert {m.claim_id for m in mappings} == {rc.claim_id for rc in refined}
    print("  s2_ninety_units_chunks_complete OK")


def test_s2_small_input_single_call() -> None:
    """≤ S2_CHUNK_SIZE → genau 1 Call (Regression)."""
    refined = _refined_objs(12)  # ≤ 20
    client = FakeClient([as_json([_mapping_dict(rc.claim_id) for rc in refined])])

    mappings = ArgumentMapper(client, "m").map_claims(refined)

    assert client.call_count == 1
    assert len(mappings) == 12
    print("  s2_small_input_single_call OK")


# === Transparenz-Block trägt die Gesamtzahlen NACH dem Merge ================

def test_transparency_reflects_merged_totals() -> None:
    """S1+S2 gechunkt → Transparenz zeigt 69 extrahiert → 69 atomisiert, Budget 8.

    Fährt den echten Flow: Refiner (5 Chunks) → Mapper (4 Chunks) →
    PolicyScorer (real) → build_transparency. Der wichtige Beweis: die
    Gesamtzahlen kommen aus dem GEMERGTEN Ergebnis, nicht aus einem Chunk.
    """
    s1_client = FakeClient([_s1_response(o, s) for o, s in
                            zip([0, 15, 30, 45, 60], [15, 15, 15, 15, 9])])
    merged = ClaimRefiner(s1_client, "m").refine(CLAIMS_69)
    assert len(merged) == 69

    ids = [c.claim_id for c in merged]
    s2_client = FakeClient([
        as_json([_mapping_dict(cid) for cid in ids[o:o + S2_CHUNK_SIZE]])
        for o in range(0, 69, S2_CHUNK_SIZE)
    ])
    mappings = ArgumentMapper(s2_client, "m").map_claims(merged)
    assert len(mappings) == 69

    selection = PolicyScorer.from_file().select(join_claims(merged, mappings), budget=8)
    transparency = build_transparency(selection, raw_claim_count=len(CLAIMS_69))

    assert transparency["extracted"] == 69   # Roh-Claims (len config.claims)
    assert transparency["atomised"] == 69    # alle gemergten Prüfeinheiten
    assert transparency["budget"] == 8
    assert transparency["researched"] <= 8
    print("  transparency_reflects_merged_totals OK")


def main() -> None:
    """Führt alle Chunking-Tests aus."""
    print("S1/S2-Chunking (v0.15.1):")
    test_s1_69_claims_five_chunks_complete()
    test_s1_small_input_single_call_byte_identical()
    test_s1_repair_retry_only_in_affected_chunk()
    test_s1_truncation_in_chunk_raises_no_further_calls()
    test_s1_cancel_between_chunks_stops()
    test_s2_ninety_units_chunks_complete()
    test_s2_small_input_single_call()
    test_transparency_reflects_merged_totals()
    print("ALLE TESTS OK")


if __name__ == "__main__":
    main()
