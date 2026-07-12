"""Schützt vor Auseinanderlaufen der zwei Anthropic-Direkt-Modelllisten.

Die App exponiert die Anthropic-Modelle an zwei Stellen, die synchron bleiben
müssen (IDs, Namen, Beschreibungen, Reihenfolge, Default):
  1. ``AnthropicClient.MODELS`` (src/core/anthropic_client.py)
  2. Provider-Objekt ``"id": "anthropic"`` in src/config/api_providers.json

Lauf (ohne pytest):  python tests/test_model_lists_consistency.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.core.anthropic_client import AnthropicClient


def _load_anthropic_block() -> dict:
    path = (
        Path(__file__).resolve().parent.parent
        / "src" / "config" / "api_providers.json"
    )
    data = json.loads(path.read_text(encoding="utf-8"))
    for prov in data["providers"]:
        if prov.get("id") == "anthropic":
            return prov
    raise AssertionError("anthropic-Provider fehlt in api_providers.json")


def test_anthropic_model_lists_in_sync():
    block = _load_anthropic_block()

    json_ids = [m["id"] for m in block["models"]]
    code_ids = [m["id"] for m in AnthropicClient.MODELS]
    # Gleiche IDs UND gleiche Reihenfolge
    assert code_ids == json_ids, f"IDs/Reihenfolge divergieren:\n{code_ids}\n{json_ids}"

    # Default in beiden Listen vorhanden und wie vom PO festgelegt
    assert block["default_model"] == "claude-sonnet-4-6", block["default_model"]
    assert "claude-sonnet-4-6" in code_ids

    # Namen + Beschreibungen vollständig synchron (kein stiller Drift)
    json_map = {m["id"]: (m["name"], m.get("description")) for m in block["models"]}
    code_map = {m["id"]: (m["name"], m.get("description")) for m in AnthropicClient.MODELS}
    assert json_map == code_map, "Namen/Beschreibungen divergieren zwischen den Listen"
    print(f"  anthropic_model_lists_in_sync: {len(code_ids)} Modelle synchron OK")


def main():
    print("Anthropic-Modelllisten-Konsistenz:")
    test_anthropic_model_lists_in_sync()
    print("ALLE TESTS OK")


if __name__ == "__main__":
    main()
