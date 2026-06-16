"""Tests für den einheitlichen Export-Kopf (PR 7, v0.10.1).

Lauf (ohne pytest):  python tests/test_export_header.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.core.export import get_markdown_content
from src.config.defaults import VideoInfo


def test_youtube_export_header() -> None:
    """YouTube-Export: Titel-Block + 'Kanal, YT' + Thumbnail, dann '# Analyse · SOMAS'
    (ohne Titel-Dopplung)."""
    vi = VideoInfo(
        title="Mein Titel – Test", channel="Kanal X", duration=754,
        url="https://youtu.be/niBe6WqG0A4",
    )
    md = get_markdown_content("### FRAMING\nText", vi,
                             model_name="Sonar Pro", provider_name="Perplexity AI")
    assert md.startswith("# Mein Titel"), md[:60]
    assert "**Kanal X, YT**" in md
    assert "![Thumbnail zum Video](https://i.ytimg.com/vi/niBe6WqG0A4/maxresdefault.jpg)" in md
    assert "# Analyse · SOMAS\n" in md
    assert "Analyse · SOMAS: " not in md  # keine Titel-Dopplung mehr
    assert "**Modell:** Sonar Pro (Perplexity AI)" in md
    print("  youtube_export_header: Titelblock + Thumbnail + # Analyse · SOMAS OK")


def test_transcript_export_header() -> None:
    """Transkript-Export (keine YouTube-URL): Titel-Block OHNE Thumbnail und ohne ', YT'."""
    vi = VideoInfo(title="Podcast-Folge", channel="Sprecher Y", duration=0, url="")
    md = get_markdown_content("### FRAMING\nText", vi,
                             model_name="GPT-4o", provider_name="OpenAI")
    assert md.startswith("# Podcast-Folge")
    assert "**Sprecher Y**" in md and ", YT" not in md
    assert "ytimg" not in md and "Thumbnail" not in md
    assert "# Analyse · SOMAS\n" in md
    print("  transcript_export_header: Titelblock ohne Thumbnail/', YT' OK")


def main() -> None:
    """Führt alle Export-Kopf-Tests aus."""
    print("Export-Kopf-Tests:")
    test_youtube_export_header()
    test_transcript_export_header()
    print("ALLE TESTS OK")


if __name__ == "__main__":
    main()
