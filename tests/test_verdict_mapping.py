"""Tests für Faktencheck Plus PR 3: Verdikt-Taxonomie und 8→4-Mapping.

Deckt Theorie §6.3 ab:
- Das Mapping ist VOLLSTÄNDIG (alle 8 internen Werte haben ein Ziel) und trifft
  nur echte UI-Verdikte des Classic-Wegs.
- Die Begründungszeile ist Pflicht und trägt den internen Grund — sie ist der
  einzige Ort, an dem die Feinheit das verlustbehaftete Mapping überlebt.
- Harte Leitplanken: kein positives Teilverdikt ohne benannten belegten
  Teilclaim samt Quelle; kein Rechercheerfolg ohne Quelle.
- Drift-Schutz: `UI_VERDICTS` muss zu `prompt_builder.VERDICT_VALUES` passen
  (das Package spiegelt die Werte bewusst, statt sie zu importieren).

Lauf (ohne pytest):  python tests/test_verdict_mapping.py
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.core.factcheck_plus import (
    INTERNAL_VERDICTS, UI_VERDICTS, VERDICT_MAP, VERDICTS_REQUIRING_SOURCE,
    VERDICTS_REQUIRING_SUBCLAIM, VerdictError, check_verdict_guardrails,
    format_reason_line, map_verdict,
)
from src.core.factcheck_plus.verdict import check_forbidden_sources, is_forbidden_source
from src.core.prompt_builder import VERDICT_VALUES

# Realistischer Hint: der Worker fügt Titel und URL zusammen (s.
# `verification_worker`) — beide Teile müssen einzeln greifen.
HINT = "Taylor Lorenz Interview https://www.youtube.com/watch?v=2yVJffNplJc"


# --- Vollständigkeit und Drift-Schutz -------------------------------------

def test_ui_verdicts_match_classic_path() -> None:
    """Drift-Schutz: die gespiegelten UI-Verdikte müssen dem Classic-Weg gleichen.

    Das Package importiert `prompt_builder` bewusst NICHT (Ein-Naht-Invariante,
    Spec §2.2) — dieser Test ersetzt den Import, wie
    `test_model_lists_consistency.py` es für die Modelllisten tut.
    """
    assert UI_VERDICTS == VERDICT_VALUES


def test_mapping_is_complete_over_all_eight_internal_verdicts() -> None:
    assert set(VERDICT_MAP) == set(INTERNAL_VERDICTS)
    assert len(INTERNAL_VERDICTS) == 8


def test_mapping_only_targets_real_ui_verdicts() -> None:
    for internal, (ui, ground) in VERDICT_MAP.items():
        assert ui in UI_VERDICTS, f"{internal} zielt auf unbekanntes UI-Verdikt {ui}"
        assert ground.strip(), f"{internal} hat keinen Grundtext"


@pytest.mark.parametrize("internal, expected_ui", [
    ("supported", "bestätigt"),
    ("partially_supported", "teilweise bestätigt"),
    ("attribution_only", "teilweise bestätigt"),
    ("contradicted", "widerlegt"),
    ("unsupported", "nicht überprüfbar"),
    ("under_specified", "nicht überprüfbar"),
    ("methodologically_unfounded", "nicht überprüfbar"),
    ("mixed_evidence", "nicht überprüfbar"),
])
def test_each_internal_verdict_maps_as_specified(internal, expected_ui) -> None:
    ui, _ground = map_verdict(internal)
    assert ui == expected_ui


def test_unknown_verdict_raises() -> None:
    with pytest.raises(VerdictError) as exc:
        map_verdict("ziemlich_wahr")
    assert "Unbekanntes internes Verdikt" in str(exc.value)


def test_lossy_mapping_is_compensated_by_distinct_reasons() -> None:
    """Vier interne Werte teilen sich „nicht überprüfbar" — die Gründe nicht.

    Das ist der Grund, warum die Begründungszeile Pflicht ist: „unbelegt" und
    „methodisch nicht herleitbar" sind fachlich verschieden (Theorie §5.1:
    Retrieval-Grenze ≠ Prüfbarkeits-Grenze), das UI-Label unterscheidet sie nicht.
    """
    collapsed = [i for i, (ui, _) in VERDICT_MAP.items() if ui == "nicht überprüfbar"]
    assert len(collapsed) == 4
    grounds = [VERDICT_MAP[i][1] for i in collapsed]
    assert len(set(grounds)) == 4, "jeder kollabierte Wert braucht einen eigenen Grund"
    assert "unbelegt" in VERDICT_MAP["unsupported"][1]


# --- Begründungszeile -----------------------------------------------------

def test_reason_line_names_the_supported_subclaim() -> None:
    line = format_reason_line(
        "partially_supported", "Die Zahl deckt sich mit dem Bericht.",
        supported_subclaim="die Spanne 54–120 Mrd. €",
    )
    assert line.startswith("belegter Teilclaim: die Spanne 54–120 Mrd. €")
    assert "Die Zahl deckt sich mit dem Bericht." in line


def test_reason_line_carries_internal_ground_for_collapsed_verdicts() -> None:
    line = format_reason_line("methodologically_unfounded", "Keine tragfähige Methode.")
    assert line.startswith("methodisch nicht herleitbar")
    line2 = format_reason_line("unsupported", "Nichts gefunden.")
    assert "unbelegt" in line2


def test_reason_line_survives_empty_reason() -> None:
    assert format_reason_line("supported", "") == "alle wesentlichen Teilbedingungen gestützt."


def test_attribution_only_reason_names_subclaim() -> None:
    line = format_reason_line(
        "attribution_only", "Das Statement ist dokumentiert.",
        supported_subclaim="Boeing hat sich so geäußert",
    )
    assert "Aussage belegt, Sachverhalt offen: Boeing hat sich so geäußert" in line


# --- Leitplanken ----------------------------------------------------------

@pytest.mark.parametrize("internal", VERDICTS_REQUIRING_SUBCLAIM)
def test_positive_partial_verdict_without_subclaim_is_rejected(internal) -> None:
    """Kein positives Teilverdikt ohne benannten belegten Teilclaim (§6.3)."""
    with pytest.raises(VerdictError) as exc:
        check_verdict_guardrails(internal, None, ["https://example.org/quelle"])
    assert "ohne benannten belegten Teilclaim" in str(exc.value)

    with pytest.raises(VerdictError):
        check_verdict_guardrails(internal, "   ", ["https://example.org/quelle"])


@pytest.mark.parametrize("internal", VERDICTS_REQUIRING_SOURCE)
def test_research_success_without_source_is_rejected(internal) -> None:
    subclaim = "ein belegter Teil" if internal in VERDICTS_REQUIRING_SUBCLAIM else None
    with pytest.raises(VerdictError) as exc:
        check_verdict_guardrails(internal, subclaim, [])
    assert "ohne Quelle" in str(exc.value)


def test_em_dash_placeholder_does_not_count_as_source() -> None:
    """„—" ist die Kein-Beleg-Markierung des Classic-Wegs, keine Quelle."""
    with pytest.raises(VerdictError):
        check_verdict_guardrails("supported", None, ["—", "  "])


@pytest.mark.parametrize("internal", ["unsupported", "under_specified",
                                      "methodologically_unfounded"])
def test_negative_verdicts_need_no_source(internal) -> None:
    """Quelle ist nur bei echter Verifikation Pflicht (Regel des Classic-Wegs)."""
    check_verdict_guardrails(internal, None, [])


def test_valid_partial_verdict_passes() -> None:
    check_verdict_guardrails(
        "partially_supported", "die Spanne", ["https://example.org/bericht"],
    )


# --- Unabhängigkeits-Riegel, server-seitig --------------------------------

@pytest.mark.parametrize("source", [
    "https://www.youtube.com/watch?v=2yVJffNplJc",
    "https://youtu.be/2yVJffNplJc",                       # andere Domain, gleiche ID
    "https://www.youtube.com/watch?v=2yVJffNplJc&t=42s",  # Tracking-Suffix
    "  HTTPS://WWW.YOUTUBE.COM/WATCH?V=2YVJFFNPLJC  ",    # Groß/Klein + Whitespace
    "Taylor Lorenz Interview",                            # der Titel allein
    "2yVJffNplJc",                                        # nackte Video-ID
])
def test_self_citation_is_detected(source) -> None:
    """Das geprüfte Video zählt nie als Beleg — auch verkleidet nicht."""
    assert is_forbidden_source(source, HINT) is True


@pytest.mark.parametrize("source", [
    "https://www.tagesschau.de/artikel-123",
    "https://www.youtube.com/watch?v=ANDEREVIDEO",
    "Reuters: Bericht vom 12.07.2026",
    "",
])
def test_independent_sources_pass(source) -> None:
    assert is_forbidden_source(source, HINT) is False


def test_short_hint_does_not_blacklist_everything() -> None:
    """Ein kurzer Titel darf nicht jede Quelle sperren, die das Wort enthält."""
    assert is_forbidden_source("https://www.zdf.de/nachrichten/xyz", "ZDF") is False


def test_check_forbidden_sources_rejects_and_explains() -> None:
    with pytest.raises(VerdictError) as exc:
        check_forbidden_sources(
            ["https://example.org/gut", "https://youtu.be/2yVJffNplJc"], HINT,
        )
    assert "Eigenbeleg unzulässig" in str(exc.value)
    assert "youtu.be/2yVJffNplJc" in str(exc.value)
    assert "'unsupported'" in str(exc.value)


def test_check_forbidden_sources_passes_clean_list() -> None:
    check_forbidden_sources(["https://www.tagesschau.de/a"], HINT)


def test_without_hint_the_riegel_cannot_fire() -> None:
    """Ohne Referenz gibt es nichts zu vergleichen (z.B. Transkript-Modus)."""
    check_forbidden_sources(["https://youtu.be/2yVJffNplJc"], "")


def main() -> None:
    """Führt alle Tests ohne pytest aus (Parametrize-Fälle explizit)."""
    test_ui_verdicts_match_classic_path()
    test_mapping_is_complete_over_all_eight_internal_verdicts()
    test_mapping_only_targets_real_ui_verdicts()
    for internal, ui in [
        ("supported", "bestätigt"), ("partially_supported", "teilweise bestätigt"),
        ("attribution_only", "teilweise bestätigt"), ("contradicted", "widerlegt"),
        ("unsupported", "nicht überprüfbar"), ("under_specified", "nicht überprüfbar"),
        ("methodologically_unfounded", "nicht überprüfbar"),
        ("mixed_evidence", "nicht überprüfbar"),
    ]:
        test_each_internal_verdict_maps_as_specified(internal, ui)
    test_unknown_verdict_raises()
    test_lossy_mapping_is_compensated_by_distinct_reasons()
    test_reason_line_names_the_supported_subclaim()
    test_reason_line_carries_internal_ground_for_collapsed_verdicts()
    test_reason_line_survives_empty_reason()
    test_attribution_only_reason_names_subclaim()
    for internal in VERDICTS_REQUIRING_SUBCLAIM:
        test_positive_partial_verdict_without_subclaim_is_rejected(internal)
    for internal in VERDICTS_REQUIRING_SOURCE:
        test_research_success_without_source_is_rejected(internal)
    test_em_dash_placeholder_does_not_count_as_source()
    for internal in ["unsupported", "under_specified", "methodologically_unfounded"]:
        test_negative_verdicts_need_no_source(internal)
    test_valid_partial_verdict_passes()
    for source in ["https://www.youtube.com/watch?v=2yVJffNplJc",
                   "https://youtu.be/2yVJffNplJc",
                   "https://www.youtube.com/watch?v=2yVJffNplJc&t=42s",
                   "  HTTPS://WWW.YOUTUBE.COM/WATCH?V=2YVJFFNPLJC  ",
                   "Taylor Lorenz Interview", "2yVJffNplJc"]:
        test_self_citation_is_detected(source)
    for source in ["https://www.tagesschau.de/artikel-123",
                   "https://www.youtube.com/watch?v=ANDEREVIDEO",
                   "Reuters: Bericht vom 12.07.2026", ""]:
        test_independent_sources_pass(source)
    test_short_hint_does_not_blacklist_everything()
    test_check_forbidden_sources_rejects_and_explains()
    test_check_forbidden_sources_passes_clean_list()
    test_without_hint_the_riegel_cannot_fire()
    print("ALLE TESTS OK")


if __name__ == "__main__":
    main()
