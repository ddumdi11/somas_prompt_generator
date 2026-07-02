"""Tests für den Reasoning-Leak-/Struktur-Validator (PR 5 / B1, v0.11.0).

Crash-Test-Dummy: der reale Iran-DeepSeek-Leak (2026-07-01) als Fixture. Prüft,
dass Leak + Trunkierung erkannt werden, eine saubere Analyse gültig bleibt und
legitime Analysen mit Reasoning-Trigger-Wörtern im Fließtext NICHT fälschlich
verworfen werden (False-Positive-Guards).

Lauf (ohne pytest):  python tests/test_reasoning_leak_validator.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.core.prompt_builder import (
    strip_reasoning_preamble,
    validate_analysis_structure,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def _load(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_iran_leak_invalid() -> None:
    """Iran-Leak: sowohl roh als auch preamble-bereinigt ungültig (Leak + Trunkierung)."""
    iran = _load("reasoning_leak_iran.txt")

    # Roh: beginnt mit „Wir müssen …" statt ### FRAMING → Leak.
    raw = validate_analysis_structure(iran, require_faktencheck=True)
    assert not raw.ok, "Iran-Rohtext dürfte nicht gültig sein"

    # Nach strip_reasoning_preamble: startet mit dem zitierten Template-Skelett
    # (### [GEWÄHLTES MODUL]) und endet trunkiert → weiterhin ungültig.
    cleaned, was_stripped = strip_reasoning_preamble(iran)
    assert was_stripped, "Iran-Preamble hätte entfernt werden müssen"
    res = validate_analysis_structure(cleaned, require_faktencheck=True)
    assert not res.ok, "Iran-Content (bereinigt) dürfte nicht gültig sein"
    print(f"  iran_leak_invalid: roh + bereinigt ungültig (Grund: {res.reason}) OK")


def test_iran_truncation_detected() -> None:
    """Die Trunkierungs-Heuristik erkennt das abgeschnittene Ende ('… dann')."""
    iran = _load("reasoning_leak_iran.txt")
    # Iran endet auf „Sortieren: 1 zentral, dann" — offenes Funktionswort.
    from src.core.prompt_builder import _looks_truncated
    assert _looks_truncated(iran), "Iran-Ende müsste als trunkiert erkannt werden"
    print("  iran_truncation_detected: Ende '… dann' als Trunkierung erkannt OK")


def test_clean_litcafe_valid() -> None:
    """Literaturcafé-Clean: volle Struktur, FAKTENCHECK nach IMPLIKATION, 3 Sub-Header."""
    clean = _load("reasoning_clean_litcafe.txt")
    cleaned, _ = strip_reasoning_preamble(clean)
    res = validate_analysis_structure(cleaned, require_faktencheck=True)
    assert res.ok, f"CLEAN-Content sollte gültig sein, war: {res.reason}"
    print("  clean_litcafe_valid: vollständige FAKTENCHECK-Analyse gültig OK")


def test_false_positive_guard_trigger_words() -> None:
    """Legitime Analyse mit 'Prompt'/'ich werde'/'fordert … auf' im Fließtext → gültig.

    Kein globaler Substring-Scan: die Trigger-Wörter stehen im Body, der Text
    startet sauber mit ### FRAMING.
    """
    legit = (
        "### FRAMING\n"
        "In diesem Video geht es um Prompt-Engineering; ich werde zeigen, wie der "
        "Kanal seine Zuschauer auffordert, kritisch zu denken.\n"
        "### KERNTHESE\n"
        "Die zentrale These lautet, dass gute Prompts Zeit sparen.\n"
        "### ELABORATION\n"
        "Der Autor erklärt die Mechanismen und nennt konkrete Belege dafür.\n"
        "### IMPLIKATION\n"
        "Für die Praxis bedeutet das einen klaren Vorteil im Alltag.\n"
        "### KRITIK\n"
        "Es fehlt eine Einordnung der Grenzen dieser Methode.\n"
    )
    res = validate_analysis_structure(legit, require_faktencheck=False)
    assert res.ok, f"Legitime Analyse fälschlich verworfen: {res.reason}"
    print("  false_positive_guard: Trigger-Wörter im Fließtext bleiben gültig OK")


def test_truncated_numbering_invalid() -> None:
    """Analyse, die mitten in einer Nummerierung endet → ungültig (Trunkierung)."""
    truncated = (
        "### FRAMING\nEinleitender Satz.\n"
        "### KERNTHESE\nDie zentrale These.\n"
        "### ELABORATION\nVertiefung mit Belegen.\n"
        "### IMPLIKATION\nDas Fazit dazu.\n"
        "### FAKTENCHECK\n"
        "**Meinungen:**\n1. Eine Meinung.\n"
        "**Interpretationen:**\n1. Eine Deutung.\n"
        "**Behauptungen (überprüfbar):**\n1. Erste Behauptung.\n2"
    )
    res = validate_analysis_structure(truncated, require_faktencheck=True)
    assert not res.ok, "Abgeschnittene Nummerierung müsste ungültig sein"
    print(f"  truncated_numbering_invalid: offene Nummerierung ungültig ({res.reason}) OK")


def test_missing_faktencheck_when_required() -> None:
    """Erzwungener FAKTENCHECK fehlt → ungültig; ohne Zwang dieselbe Analyse gültig."""
    no_faktencheck = (
        "### FRAMING\nEinleitender Satz.\n"
        "### KERNTHESE\nDie zentrale These.\n"
        "### ELABORATION\nVertiefung mit Belegen.\n"
        "### IMPLIKATION\nDas Fazit dazu.\n"
        "### KRITIK\nEine kritische Einordnung.\n"
    )
    assert not validate_analysis_structure(no_faktencheck, require_faktencheck=True).ok
    assert validate_analysis_structure(no_faktencheck, require_faktencheck=False).ok
    print("  missing_faktencheck_when_required: Zwang greift, ohne Zwang gültig OK")


def main() -> None:
    """Führt alle Validator-Tests aus."""
    print("Reasoning-Leak-Validator-Tests:")
    test_iran_leak_invalid()
    test_iran_truncation_detected()
    test_clean_litcafe_valid()
    test_false_positive_guard_trigger_words()
    test_truncated_numbering_invalid()
    test_missing_faktencheck_when_required()
    print("ALLE TESTS OK")


if __name__ == "__main__":
    main()
