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


def test_extract_headings_without_space():
    # Header/Folge-Überschrift OHNE Leerzeichen nach ### -> normalize greift,
    # Block endet korrekt vor '###IMPLIKATION'.
    txt = (
        "###FAKTENCHECK\n"
        "**Behauptungen (überprüfbar):**\n"
        "1. Behauptung eins.\n"
        "2. Behauptung zwei.\n"
        "###IMPLIKATION\n"
        "3. Das ist KEINE Behauptung mehr.\n"
    )
    claims = extract_claims_from_faktencheck(txt)
    assert claims == ["Behauptung eins.", "Behauptung zwei."], claims
    print("  extract_headings_without_space: ###ohne-Space normalisiert, Block endet korrekt OK")


# Reale Fixture aus dem PO-Debug-Log (DeepSeek V4 Pro): FAKTENCHECK komplett inline.
ANALYSE_INLINE_DEEPSEEK = (
    "### FAKTENCHECK\n"
    "**Meinungen:** 1. Sanders pro-israelische Positionen sind nicht radikal. 2. Der Ausschluss aus dem Film ist eine himmelschreiende Ungerechtigkeit. 3. Die Branche war links, weil es in Mode war.\n"
    "**Interpretationen:** 1. Sanders Ausschluss zeigt ein strukturelles Problem der Filmbranche. 2. Anti-israelische Propaganda hat breite Gesellschaftsschichten erfasst.\n"
    "**Behauptungen (überprüfbar):** 1. Sander wurde wegen ihrer pro-israelischen Haltung aus dem Film „Die Todessehnsucht der Maria Om\" ausgeschlossen. 2. Sie verfasste das Drehbuch mit einem Co-Autor. 3. Sie führt seit Ende 2024 einen Rechtsstreit gegen die Produktionsfirma. 4. Das Kammergericht Berlin entschied in der Berufung zugunsten der Produktionsfirma. 5. Auf dem Campus der Burg Giebichenstein Kunsthochschule Halle wurden Flugblätter verteilt, die die jüdische Gemeinde als rassistisch und zionistisch bezeichnen und ihre Ausladung fordern. 6. Die Hochschulleitung entfernte diese Plakate. 7. Sander gibt an, täglich hunderte Hassnachrichten mit Holocaust-Bezug zu erhalten. 8. Sie steht eigenen Angaben zufolge in Kontakt mit dem LKA. 9. Auf Berliner Free-Palestine-Demos riefen Teilnehmer arabischsprachig „Tod den Juden\". 10. Auf der Sonnenallee in Berlin-Neukölln hängen Palästina-Flaggen. 11. Sander veröffentlichte im August 2025 ein kritisches Video über Teile der Schauspielbranche. 12. Die jüdische Gemeinde Halle organisierte Synagogenbesuche für Studierende.\n"
)


def test_extract_inline_deepseek():
    claims = extract_claims_from_faktencheck(ANALYSE_INLINE_DEEPSEEK)
    assert len(claims) == 12, f"erwartet 12, bekam {len(claims)}: {claims}"
    assert claims[0].startswith("Sander wurde wegen ihrer pro-israelischen Haltung")
    assert claims[11].startswith("Die jüdische Gemeinde Halle organisierte")
    # Meinungen/Interpretationen tauchen NICHT auf
    joined = " ".join(claims)
    assert "himmelschreiende" not in joined and "strukturelles Problem" not in joined
    print("  extract_inline_deepseek: 12 Behauptungen aus Inline-Block OK")


def test_extract_internal_numbers():
    # Interne Datums-/Jahreszahl darf einen Claim NICHT zerteilen.
    inline = (
        "### FAKTENCHECK\n"
        "**Behauptungen (überprüfbar):** 1. Sie reiste am 7. Oktober 2023 nach Israel. "
        "2. Das Gesetz gilt seit 2021.\n"
    )
    claims = extract_claims_from_faktencheck(inline)
    assert claims == [
        "Sie reiste am 7. Oktober 2023 nach Israel.",
        "Das Gesetz gilt seit 2021.",
    ], claims
    print("  extract_internal_numbers: '7. Oktober' zerreißt Claim nicht -> 2 Claims OK")


def test_extract_mixed_and_quelle_terminator():
    # Mehrzeilig + abschließender QUELLE-Abschnitt darf nicht in den letzten Claim lecken.
    txt = (
        "### FAKTENCHECK\n"
        "**Behauptungen (überprüfbar):**\n"
        "1. Erste Behauptung.\n"
        "2. Zweite Behauptung mit Datum am 3. März 2020.\n"
        "QUELLE:\n"
        'YouTube-Video: "Titel"\n'
    )
    claims = extract_claims_from_faktencheck(txt)
    assert claims == ["Erste Behauptung.", "Zweite Behauptung mit Datum am 3. März 2020."], claims
    print("  extract_mixed_and_quelle: mehrzeilig + QUELLE-Terminator OK")


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
    test_extract_headings_without_space()
    test_extract_inline_deepseek()
    test_extract_internal_numbers()
    test_extract_mixed_and_quelle_terminator()
    test_extract_edge_cases()
    test_cap_claims()
    test_build_verification_prompt()
    test_clean_verification_output()
    print("ALLE TESTS OK")


if __name__ == "__main__":
    main()
