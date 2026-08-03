"""KI-Kennzeichnung in allen Output-Formen (v0.14.0, Art. 50 AI Act).

Prüft die zentrale Quelle (``ai_disclosure``) und die drei Einbaustellen:
LinkedIn (nur Text), Markdown-Export (Einzelanalyse UND Modellvergleich) und
WordPress (``assemble_content``). Plus Drift-Schutz (eine Quelle der Wahrheit)
und dass die Unicode-Sanitisierung den ``<img>``-Tag nicht zerlegt.

Alles offline — kein Netzwerk.

Lauf (ohne pytest):  python tests/test_ai_disclosure.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config.defaults import VideoInfo
from src.core.ai_disclosure import (
    AI_DISCLOSURE_HTML,
    AI_DISCLOSURE_ICON_ALT,
    AI_DISCLOSURE_ICON_URL,
    AI_DISCLOSURE_MARKDOWN,
    AI_DISCLOSURE_TEXT,
    _CORE,
)
from src.core.export import (
    get_markdown_content,
    sanitize_unicode_for_export,
    save_markdown,
)
from src.core.linkedin_formatter import format_for_linkedin
from src.core.wordpress_client import assemble_content

_ANALYSIS = "### FRAMING\nEin **Testtext** zur Analyse.\n\n### KERNTHESE\nThese."


# --- 1 · LinkedIn: nur Text, kein Icon/URL --------------------------------

def test_linkedin_ends_with_disclosure_text_only() -> None:
    """LinkedIn-Output endet mit der Kennzeichnungszeile; kein <img>/URL."""
    text, _ = format_for_linkedin(_ANALYSIS, "Videotitel", "Kanal")
    assert text.rstrip().endswith(AI_DISCLOSURE_TEXT), text[-200:]
    assert "<img" not in text
    assert AI_DISCLOSURE_ICON_URL not in text
    assert "http" not in AI_DISCLOSURE_TEXT  # die Zeile selbst ist link-frei
    print("  linkedin_ends_with_disclosure_text_only OK")


# --- 2 · Markdown: Einzelanalyse UND Modellvergleich ----------------------

def _assert_markdown_footer(doc: str, label: str) -> None:
    assert AI_DISCLOSURE_MARKDOWN in doc, f"{label}: Fußblock fehlt"
    assert 'width="90"' in doc, f"{label}: img width fehlt"
    assert f'alt="{AI_DISCLOSURE_ICON_ALT}"' in doc, f"{label}: alt-Text fehlt"
    assert _CORE in doc, f"{label}: Kerntext fehlt"


def test_markdown_single_analysis_has_footer() -> None:
    """Einzelanalyse (get_markdown_content) enthält den Fußblock."""
    info = VideoInfo(title="Titel", channel="Kanal", url="", duration=0)
    doc = get_markdown_content(_ANALYSIS, info)
    _assert_markdown_footer(doc, "Einzelanalyse")
    # Fuß: die Kennzeichnung steht am Ende.
    assert doc.rstrip().endswith(AI_DISCLOSURE_MARKDOWN.rstrip())
    print("  markdown_single_analysis_has_footer OK")


def test_markdown_single_without_videoinfo_has_footer() -> None:
    """Auch ohne Video-Metadaten (reiner Analyse-String) ist die Kennzeichnung da."""
    doc = get_markdown_content(_ANALYSIS, None)
    _assert_markdown_footer(doc, "Einzelanalyse ohne VideoInfo")
    print("  markdown_single_without_videoinfo_has_footer OK")


def test_markdown_comparison_has_footer(tmp_path) -> None:
    """Modellvergleich (save_markdown) enthält den Fußblock."""
    doc = "# Modellvergleich\n\nFertiges Jinja-Layout.\n"
    out = tmp_path / "vergleich.md"
    save_markdown(doc, "Titel", str(out))
    written = out.read_text(encoding="utf-8-sig")
    _assert_markdown_footer(written, "Modellvergleich")
    print("  markdown_comparison_has_footer OK")


# --- 3 · WordPress: HTML-Block am Ende ------------------------------------

def test_wordpress_assemble_appends_html() -> None:
    """assemble_content hängt den HTML-Block ans Ende an."""
    md = assemble_content("Intro", "Analyse", "Outro")
    assert md.rstrip().endswith(AI_DISCLOSURE_HTML)
    assert md.index("Outro") < md.index(AI_DISCLOSURE_HTML)
    print("  wordpress_assemble_appends_html OK")


def test_wordpress_empty_outro_still_works() -> None:
    """Leeres Outro: nur Intro/Analyse + Kennzeichnung, kein Crash/Leerblock."""
    md = assemble_content("", "Nur Analyse", "")
    assert md.rstrip().endswith(AI_DISCLOSURE_HTML)
    assert "Nur Analyse" in md
    # Keine führenden/leeren Doppelblöcke durch das weggefallene Outro.
    assert "\n\n\n" not in md
    print("  wordpress_empty_outro_still_works OK")


def test_wordpress_html_survives_markdown_conversion() -> None:
    """Der <p>-Block überlebt markdown_to_html (Roh-HTML wird durchgereicht)."""
    try:
        import markdown  # noqa: F401
    except ImportError:
        print("  wordpress_html_survives_markdown_conversion: markdown fehlt -> skip")
        return
    from src.core.wordpress_client import markdown_to_html

    html = markdown_to_html(assemble_content("", "Analyse", ""))
    assert AI_DISCLOSURE_ICON_URL in html
    assert "<strong>" in html and _CORE in html
    print("  wordpress_html_survives_markdown_conversion OK")


# --- 4 · Konsistenz (eine Quelle der Wahrheit) ----------------------------

def test_all_three_forms_share_core_text() -> None:
    """Alle drei Formen enthalten denselben Kerntext (Drift-Schutz)."""
    for name, form in (
        ("TEXT", AI_DISCLOSURE_TEXT),
        ("MARKDOWN", AI_DISCLOSURE_MARKDOWN),
        ("HTML", AI_DISCLOSURE_HTML),
    ):
        assert _CORE in form, f"{name}: Kerntext weicht ab"
        assert "KI-Kennzeichnung" in form, f"{name}: Label weicht ab"
    # Icon nur in Markdown/HTML, nicht im reinen Text.
    assert AI_DISCLOSURE_ICON_URL in AI_DISCLOSURE_MARKDOWN
    assert AI_DISCLOSURE_ICON_URL in AI_DISCLOSURE_HTML
    assert AI_DISCLOSURE_ICON_URL not in AI_DISCLOSURE_TEXT
    print("  all_three_forms_share_core_text OK")


# --- 5 · Sanitisierung zerlegt den <img>-Tag nicht ------------------------

def test_sanitize_keeps_img_tag_intact() -> None:
    """sanitize_unicode_for_export lässt den <img>-Tag (und Kerntext) intakt."""
    cleaned = sanitize_unicode_for_export(AI_DISCLOSURE_MARKDOWN)
    assert f'<img src="{AI_DISCLOSURE_ICON_URL}"' in cleaned
    assert f'alt="{AI_DISCLOSURE_ICON_ALT}"' in cleaned
    assert 'width="90"' in cleaned
    assert _CORE in cleaned
    print("  sanitize_keeps_img_tag_intact OK")


def main() -> None:
    print("KI-Kennzeichnung (v0.14.0):")
    test_linkedin_ends_with_disclosure_text_only()
    test_markdown_single_analysis_has_footer()
    test_markdown_single_without_videoinfo_has_footer()
    print("  (Modellvergleich-Test läuft nur unter pytest — braucht tmp_path)")
    test_wordpress_assemble_appends_html()
    test_wordpress_empty_outro_still_works()
    test_wordpress_html_survives_markdown_conversion()
    test_all_three_forms_share_core_text()
    test_sanitize_keeps_img_tag_intact()
    print("ALLE TESTS OK")


if __name__ == "__main__":
    main()
