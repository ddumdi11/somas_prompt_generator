"""Export-Funktionen für SOMAS-Analysen.

Unterstützt:
- Markdown (.md)
- PDF (später)
"""

from datetime import datetime
from typing import Optional

from src.config.defaults import VideoInfo


def sanitize_filename(title: str, max_length: int = 50) -> str:
    """Erstellt einen sicheren Dateinamen aus einem Titel.

    Args:
        title: Original-Titel
        max_length: Maximale Länge des Dateinamens

    Returns:
        Sicherer Dateiname ohne Sonderzeichen
    """
    safe_chars = []
    for c in title:
        if c.isalnum() or c in ' -_':
            safe_chars.append(c)
        elif c in '/\\:*?"<>|':
            safe_chars.append('_')

    filename = ''.join(safe_chars).strip()
    while '  ' in filename:
        filename = filename.replace('  ', ' ')
    while '__' in filename:
        filename = filename.replace('__', '_')

    return filename[:max_length].strip('_- ')


def export_to_markdown(
    analysis_result: str,
    video_info: Optional[VideoInfo] = None,
    output_path: Optional[str] = None
) -> str:
    """Exportiert die Analyse als Markdown-Datei.

    Args:
        analysis_result: Der Analyse-Text
        video_info: Optional - Video-Metadaten für Header
        output_path: Optional - Zielpfad

    Returns:
        Pfad zur erstellten Datei
    """
    content = get_markdown_content(analysis_result, video_info)

    if not output_path:
        if video_info:
            base_name = sanitize_filename(video_info.title)
        else:
            base_name = "somas_analyse"
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_path = f"{base_name}_{timestamp}.md"

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(content)

    return output_path


def get_markdown_content(
    analysis_result: str,
    video_info: Optional[VideoInfo] = None
) -> str:
    """Gibt den Markdown-Inhalt als String zurück.

    Args:
        analysis_result: Der Analyse-Text
        video_info: Optional - Video-Metadaten für Header

    Returns:
        Formatierter Markdown-String
    """
    parts = []

    if video_info:
        parts.append(f"# SOMAS-Analyse: {video_info.title}\n")
        parts.append(f"**Kanal:** {video_info.channel}  ")
        parts.append(f"**Dauer:** {video_info.duration_formatted}  ")
        parts.append(f"**URL:** {video_info.url}\n")
        parts.append("---\n")

    parts.append(analysis_result)

    return '\n'.join(parts)
