"""Tests für den Schriftmix-Detektor im Struktur-Validator (Teil B, v0.14.3).

Anlass: DeepSeek V4 Flash lieferte im Modellvergleich (Realtest 2026-08-24) einen
lexikalisch zerfallenen Output bei ``finish_reason=stop`` — alle Kanonik-Header in
Reihenfolge, alle FAKTENCHECK-Sub-Header da, Ende „…einmalig se". Der v0.11-
Struktur-Validator ließ ihn DURCH (empirisch geprüft). Das präzise Signal ist die
Vermischung zweier verwechselbarer Alphabete INNERHALB eines Tokens
(„Selbstseгрегация" = Latin+Kyrillisch).

Test 1 ist der empirische DoD-Beweis: der reale Flash-Output als eingecheckte
Fixture → Validator ungültig, Grund nennt das Token.

Lauf (ohne pytest):  python tests/test_script_mix_validator.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.core.prompt_builder import (
    find_mixed_script_token,
    strip_reasoning_preamble,
    validate_analysis_structure,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def _load(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


# --- Test 1: empirischer DoD-Beweis (reale Flash-Fixture) -----------------

def test_real_flash_fixture_invalid_script_mix() -> None:
    """Der reale degenerierte Flash-Output ist ungültig; Grund nennt das Token.

    Genau dieser Output rutschte vor v0.14.3 durch (finish_reason=stop, Struktur
    intakt). Jetzt fängt ihn der Schriftmix-Detektor.
    """
    content = _load("comparison_degenerate_flash.txt")
    display, _ = strip_reasoning_preamble(content)

    res = validate_analysis_structure(display, require_faktencheck=False)
    assert not res.ok, "Reale Flash-Fixture müsste ungültig sein"
    assert "Schriftsystem-Mix" in res.reason, res.reason
    # Das benannte Token ist real Latin+Kyrillisch gemischt.
    assert find_mixed_script_token(display) is not None
    print(f"  real_flash_fixture_invalid_script_mix OK (Grund: {res.reason})")


# --- Test 2: False-Positive-Guards ----------------------------------------

def _valid_analysis(body: str) -> str:
    """Baut eine strukturell gültige Analyse mit variablem FRAMING-Body."""
    return (
        f"### FRAMING\n{body}\n"
        "### KERNTHESE\nDie zentrale These ist klar.\n"
        "### ELABORATION\nVertiefung mit konkreten Belegen.\n"
        "### IMPLIKATION\nDas Fazit für die Praxis.\n"
        "### KRITIK\nEine kritische Einordnung der Grenzen.\n"
    )


def test_standalone_cyrillic_token_valid() -> None:
    """Eigenständiges kyrillisches Zitat-Token (Songtitel/Name) bleibt gültig."""
    text = _valid_analysis('Der Kanal heißt „Россия Сегодня" und sendet täglich.')
    res = validate_analysis_structure(text, require_faktencheck=False)
    assert res.ok, f"Standalone-Kyrillisch fälschlich verworfen: {res.reason}"
    print("  standalone_cyrillic_token_valid OK")


def test_standalone_foreign_script_token_valid() -> None:
    """Ein persischer/arabischer Name als eigenes Token bleibt gültig.

    Arabisch wird gar nicht überwacht (nur Latin/Kyrillisch/Griechisch) — hier
    zusätzlich als eigenständiges Token abgesichert.
    """
    text = _valid_analysis('Der Sprecher nennt sich „ناس" im Beitrag.')
    res = validate_analysis_structure(text, require_faktencheck=False)
    assert res.ok, f"Standalone-Fremdschrift fälschlich verworfen: {res.reason}"
    print("  standalone_foreign_script_token_valid OK")


def test_alphanumeric_tokens_valid() -> None:
    """„N8N" und „GPT-5.6" (Buchstaben+Ziffern/Interpunktion) bleiben gültig."""
    text = _valid_analysis("Er nutzt N8N und GPT-5.6 zur Automatisierung.")
    res = validate_analysis_structure(text, require_faktencheck=False)
    assert res.ok, f"Alphanumerische Tokens fälschlich verworfen: {res.reason}"
    print("  alphanumeric_tokens_valid OK")


def test_pure_latin_analysis_valid() -> None:
    """Reine Latin-Analyse (mit Umlauten) bleibt gültig — Regression."""
    text = _valid_analysis("Ein ganz normaler deutscher Fließtext über Größe.")
    res = validate_analysis_structure(text, require_faktencheck=False)
    assert res.ok, f"Reine Latin-Analyse fälschlich verworfen: {res.reason}"
    print("  pure_latin_analysis_valid OK")


# --- Direkte Unit-Tests des Detektors -------------------------------------

def test_find_mixed_script_token_unit() -> None:
    """Der Detektor findet nur echte Intra-Token-Mischungen."""
    assert find_mixed_script_token("Selbstseгрегация") == "Selbstseгрегация"
    # Latin+Griechisch (generisch über die verwechselbaren Alphabete).
    assert find_mixed_script_token("Aνθρωπος-Test Bαsis") is not None
    # Reines Kyrillisch / Latin / Alphanumerik → kein Mix.
    assert find_mixed_script_token("Россия Сегодня") is None
    assert find_mixed_script_token("GPT-5.6 und N8N laufen") is None
    assert find_mixed_script_token("Ein normaler deutscher Satz über Größe.") is None
    print("  find_mixed_script_token_unit OK")


def main() -> None:
    """Führt alle Schriftmix-Validator-Tests aus."""
    print("Schriftmix-Validator-Tests (Teil B, v0.14.3):")
    test_real_flash_fixture_invalid_script_mix()
    test_standalone_cyrillic_token_valid()
    test_standalone_foreign_script_token_valid()
    test_alphanumeric_tokens_valid()
    test_pure_latin_analysis_valid()
    test_find_mixed_script_token_unit()
    print("ALLE TESTS OK")


if __name__ == "__main__":
    main()
