"""Tests für den Zeitanker im Prompt (v0.12.x).

Der Zeitanker (ZEITLICHER RAHMEN) verhindert, dass Modelle mit älterem
Wissensstand reale aktuelle Ereignisse als fiktiv einstufen. Geprüft wird, dass
er in beiden Build-Pfaden (YouTube + Transkript) über alle Presets erscheint, das
Datum locale-sicher ist und der Transkript-Pfad kein Veröffentlichungsdatum trägt.

Lauf (ohne pytest):  python tests/test_temporal_anchor.py
"""
import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.core.prompt_builder import (
    build_prompt, build_prompt_from_transcript, load_presets,
    _build_temporal_anchor, _format_german_date,
)
from src.config.defaults import VideoInfo, SomasConfig

_ANTI_FICTION = "es sei denn, der Beitrag kennzeichnet sich SELBST"


def test_format_german_date_locale_safe() -> None:
    """_format_german_date: deutsches Datum unabhängig von der System-Locale."""
    assert _format_german_date(datetime(2026, 7, 4)) == "4. Juli 2026"
    assert _format_german_date(datetime(2026, 3, 1)) == "1. März 2026"
    assert _format_german_date(datetime(2025, 12, 31)) == "31. Dezember 2025"
    print("  format_german_date_locale_safe: deutsche Monatsnamen, keine Locale OK")


def test_build_temporal_anchor_content() -> None:
    """_build_temporal_anchor: Datum + Anti-Fiktions-Satz; video_published optional."""
    a = _build_temporal_anchor("4. Juli 2026")
    assert "ZEITLICHER RAHMEN:" in a
    assert "Heute ist der 4. Juli 2026." in a
    assert _ANTI_FICTION in a
    assert "veröffentlicht" not in a
    b = _build_temporal_anchor("4. Juli 2026", video_published="1. Juli 2026")
    assert "Der Beitrag wurde am 1. Juli 2026 veröffentlicht." in b
    print("  build_temporal_anchor_content: Datum/Anti-Fiktion/optional-Datum OK")


def test_youtube_prompt_has_anchor_all_presets() -> None:
    """build_prompt: Zeitanker mit heutigem Datum in ALLEN Presets, vor 'Analysiere'."""
    today = _format_german_date(datetime.now())
    cfg = SomasConfig()
    vi = VideoInfo(title="Khamenei Funeral", channel="Firstpost", duration=300,
                   url="https://youtu.be/abcdef12345")
    presets = list(load_presets().values())
    for preset in presets:
        p = build_prompt(vi, cfg, preset_name=preset.name)
        assert "ZEITLICHER RAHMEN:" in p, preset.name
        assert f"Heute ist der {today}." in p, preset.name
        assert _ANTI_FICTION in p, preset.name
    print(f"  youtube_prompt_has_anchor_all_presets: {len(presets)} Presets OK")


def test_transcript_prompt_has_anchor_no_published() -> None:
    """build_prompt_from_transcript: aktuelles Datum, aber KEIN Veröffentlichungsdatum."""
    today = _format_german_date(datetime.now())
    cfg = SomasConfig()
    p = build_prompt_from_transcript(
        "Vortrag", "Sprecher", "Ein längerer Transkripttext zur Analyse.",
        cfg, preset_name="Standard",
    )
    assert "ZEITLICHER RAHMEN:" in p
    assert f"Heute ist der {today}." in p
    assert "veröffentlicht" not in p  # kein Video -> kein video_published
    print("  transcript_prompt_has_anchor_no_published: Datum ja, Publish-Datum nein OK")


def test_format_german_date_accepts_date() -> None:
    """_format_german_date nimmt auch ein date (nicht nur datetime) — v0.15.0."""
    assert _format_german_date(date(2026, 8, 24)) == "24. August 2026"
    print("  format_german_date_accepts_date: date-Objekt OK")


def test_youtube_prompt_with_published_date_all_presets() -> None:
    """build_prompt mit VideoInfo.published → Veröffentlichungszeile in ALLEN Presets."""
    cfg = SomasConfig()
    vi = VideoInfo(title="T", channel="C", duration=300,
                   url="https://youtu.be/abcdef12345", published=date(2026, 8, 24))
    presets = list(load_presets().values())
    for preset in presets:
        p = build_prompt(vi, cfg, preset_name=preset.name)
        assert "Der Beitrag wurde am 24. August 2026 veröffentlicht." in p, preset.name
    print(f"  youtube_prompt_with_published_date_all_presets: {len(presets)} Presets OK")


def test_youtube_prompt_without_published_unchanged() -> None:
    """OHNE Datum: keine Veröffentlichungszeile (Regression, bisheriger Text)."""
    cfg = SomasConfig()
    vi = VideoInfo(title="T", channel="C", duration=300,
                   url="https://youtu.be/abcdef12345")  # published=None (Default)
    p = build_prompt(vi, cfg, preset_name="Standard")
    assert "ZEITLICHER RAHMEN:" in p
    assert "veröffentlicht" not in p
    print("  youtube_prompt_without_published_unchanged: kein Publish-Datum OK")


def test_transcript_prompt_with_published_date() -> None:
    """build_prompt_from_transcript mit video_published → Veröffentlichungszeile."""
    cfg = SomasConfig()
    p = build_prompt_from_transcript(
        "Vortrag", "Sprecher", "Ein längerer Transkripttext zur Analyse.",
        cfg, preset_name="Standard", video_published=date(2026, 8, 24),
    )
    assert "Der Beitrag wurde am 24. August 2026 veröffentlicht." in p
    print("  transcript_prompt_with_published_date: Publish-Datum durchgereicht OK")


def test_anchor_with_forced_faktencheck() -> None:
    """Zeitanker bleibt auch bei erzwungenem FAKTENCHECK erhalten (kein Verdrängen)."""
    cfg = SomasConfig()
    vi = VideoInfo(title="T", channel="C", duration=60, url="https://youtu.be/abcdef12345")
    p = build_prompt(vi, cfg, preset_name="Standard", custom_module="FAKTENCHECK")
    assert "ZEITLICHER RAHMEN:" in p
    assert "FAKTENCHECK-FORMAT" in p  # Erzwingung unberührt
    print("  anchor_with_forced_faktencheck: Anker + FAKTENCHECK koexistieren OK")


def main() -> None:
    """Führt alle Zeitanker-Tests aus."""
    print("Zeitanker-Tests:")
    test_format_german_date_locale_safe()
    test_build_temporal_anchor_content()
    test_youtube_prompt_has_anchor_all_presets()
    test_transcript_prompt_has_anchor_no_published()
    test_format_german_date_accepts_date()
    test_youtube_prompt_with_published_date_all_presets()
    test_youtube_prompt_without_published_unchanged()
    test_transcript_prompt_with_published_date()
    test_anchor_with_forced_faktencheck()
    print("ALLE TESTS OK")


if __name__ == "__main__":
    main()
