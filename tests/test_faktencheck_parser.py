"""Unit-Tests für den Faktencheck-Parser & Verifikations-Prompt (v0.10.0).

Lauf (ohne pytest):  python tests/test_faktencheck_parser.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.core.prompt_builder import (
    extract_claims_from_faktencheck,
    cap_claims,
    build_verification_prompt,
    clean_verification_output,
    VERDICT_VALUES,
)


# --- Beispiel-Analysen ----------------------------------------------------

ANALYSE_STANDARD = """### FRAMING
Sprecher X in einem Interview.

### KERNTHESE
Die zentrale Aussage.

### FAKTENCHECK
**Meinungen:**
1. Der Sprecher findet die Politik übertrieben.
2. Das sei eine Schande.

**Interpretationen:**
1. Daraus folgt vermutlich ein Strategiewechsel.

**Behauptungen (überprüfbar):**
1. Die Inflation lag 2023 bei 5,9 Prozent.
2. Das Gesetz wurde 2021 verabschiedet.
3. Die Stadt hat zwei Millionen Einwohner.

QUELLE:
YouTube-Video: "Titel" von Kanal
URL: https://youtu.be/x
"""

# Robust: fehlende Meinungen/Interpretationen, 1)-Nummerierung, GROSS-Marker,
# Folge-Überschrift beendet den Block.
ANALYSE_ROBUST = """### FAKTENCHECK
**BEHAUPTUNGEN (ÜBERPRÜFBAR):**
1) Erste belegbare Behauptung.
2) Zweite belegbare Behauptung.

### IMPLIKATION
Egal.
"""


def test_extract_standard():
    claims = extract_claims_from_faktencheck(ANALYSE_STANDARD)
    assert claims == [
        "Die Inflation lag 2023 bei 5,9 Prozent.",
        "Das Gesetz wurde 2021 verabschiedet.",
        "Die Stadt hat zwei Millionen Einwohner.",
    ], claims
    # Meinungen/Interpretationen tauchen NICHT auf
    joined = " ".join(claims)
    assert "übertrieben" not in joined and "Strategiewechsel" not in joined
    print("  extract_standard: 3 Behauptungen, Meinungen/Interpretationen ignoriert OK")


def test_extract_robust():
    claims = extract_claims_from_faktencheck(ANALYSE_ROBUST)
    assert claims == ["Erste belegbare Behauptung.", "Zweite belegbare Behauptung."], claims
    print("  extract_robust: fehlende Blöcke, 1)-Nummerierung, GROSS-Marker, Folge-### OK")


def test_extract_edge_cases():
    assert extract_claims_from_faktencheck("") == []
    assert extract_claims_from_faktencheck("### FRAMING\nKein Faktencheck hier.") == []
    # FAKTENCHECK-Block ohne Behauptungen-Marker -> []
    no_claims = "### FAKTENCHECK\n**Meinungen:**\n1. Nur eine Meinung.\n"
    assert extract_claims_from_faktencheck(no_claims) == []
    # VERIFIKATION-Header darf NICHT als Dekonstruktionsblock gegriffen werden
    only_verif = (
        "### FAKTENCHECK · VERIFIKATION\n"
        "**1. „X\"**\n- **Verdikt:** bestätigt\n"
    )
    assert extract_claims_from_faktencheck(only_verif) == []
    print("  extract_edge: leer/kein-Block/nur-Meinungen/VERIFIKATION-Header -> [] OK")


def test_cap_claims():
    many = [f"Behauptung {i}" for i in range(1, 15)]  # 14 Stück
    capped, total = cap_claims(many, 10)
    assert total == 14 and len(capped) == 10 and capped[0] == "Behauptung 1" and capped[-1] == "Behauptung 10"
    # N=0 -> unbegrenzt
    capped0, total0 = cap_claims(many, 0)
    assert capped0 == many and total0 == 14
    # len <= N -> unverändert
    few = ["A", "B"]
    capped_few, total_few = cap_claims(few, 10)
    assert capped_few == few and total_few == 2
    # Reihenfolge bleibt erhalten
    assert cap_claims(["c", "a", "b"], 2)[0] == ["c", "a"]
    print("  cap_claims: 14+N10->10/total14, N0->alle, len<=N->unverändert, Reihenfolge OK")


def test_build_verification_prompt():
    claims = ["Die Inflation lag 2023 bei 5,9 Prozent.", "Das Gesetz wurde 2021 verabschiedet."]
    prompt = build_verification_prompt(claims, language="Deutsch")
    # alle Behauptungen enthalten, nummeriert
    assert "1. Die Inflation lag 2023 bei 5,9 Prozent." in prompt
    assert "2. Das Gesetz wurde 2021 verabschiedet." in prompt
    # Verdikt-Skala vollständig & exakt
    for v in VERDICT_VALUES:
        assert v in prompt, f"Verdikt fehlt: {v}"
    # Format-/Vertragsbestandteile
    assert "**Verdikt:**" in prompt and "**Begründung:**" in prompt and "**Quelle:**" in prompt
    assert "Deutsch" in prompt
    # KEINE Meinungen (es wurden keine übergeben — Negativprobe)
    assert "übertrieben" not in prompt and "Schande" not in prompt
    # Sprache durchgereicht
    assert "Antworte in Englisch" in build_verification_prompt(claims, language="Englisch")
    # source_hint optional
    assert "KONTEXT" in build_verification_prompt(claims, source_hint="Titel · URL")
    assert "KONTEXT" not in build_verification_prompt(claims)
    print("  build_verification_prompt: Behauptungen+Skala+Format+Sprache+Hint OK")


def test_clean_verification_output():
    fenced = "```markdown\n**1. „X\"**\n- **Verdikt:** bestätigt\n```"
    assert clean_verification_output(fenced).startswith("**1.")
    assert clean_verification_output("# Vorspann\n\n**1. „X\"**").startswith("**1.")
    assert clean_verification_output("") == ""
    print("  clean_verification_output: Fences/Vorspann entfernt OK")


def main():
    print("Faktencheck-Parser-Tests:")
    test_extract_standard()
    test_extract_robust()
    test_extract_edge_cases()
    test_cap_claims()
    test_build_verification_prompt()
    test_clean_verification_output()
    print("ALLE TESTS OK")


if __name__ == "__main__":
    main()
