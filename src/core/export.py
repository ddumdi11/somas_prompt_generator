"""Export-Funktionen für SOMAS-Analysen.

Unterstützt:
- Markdown (.md)
- PDF (später)

Changelog v0.3.1:
- UTF-8-BOM für bessere Pandoc-Kompatibilität
- Unicode-Sanitization für problematische Zeichen (U+02BC, Emojis, etc.)
- Verbesserte Dateinamen-Bereinigung
"""

import re
import unicodedata
from datetime import datetime
from typing import Optional

from src.config.defaults import VideoInfo


# Mapping von problematischen Unicode-Zeichen zu sicheren Alternativen
UNICODE_REPLACEMENTS = {
    '\u02BC': "'",      # Modifier Letter Apostrophe → normales Apostroph
    '\u2019': "'",      # Right Single Quotation Mark → normales Apostroph
    '\u2018': "'",      # Left Single Quotation Mark → normales Apostroph
    '\u201C': '"',      # Left Double Quotation Mark → normales Anführungszeichen
    '\u201D': '"',      # Right Double Quotation Mark → normales Anführungszeichen
    '\u2026': '...',    # Horizontal Ellipsis → drei Punkte
    '\u2013': '-',      # En Dash → Bindestrich
    '\u2014': '--',     # Em Dash → zwei Bindestriche
    '\u00A0': ' ',      # Non-Breaking Space → normales Leerzeichen
    '\u200B': '',       # Zero Width Space → entfernen
    '\u200C': '',       # Zero Width Non-Joiner → entfernen
    '\u200D': '',       # Zero Width Joiner → entfernen
    '\uFEFF': '',       # BOM → entfernen (wird beim Schreiben neu gesetzt)
}


def sanitize_unicode_for_export(text: str) -> str:
    """Ersetzt problematische Unicode-Zeichen durch sichere Alternativen.
    
    Diese Funktion behandelt Zeichen, die in Pandoc/LaTeX Probleme verursachen,
    wie z.B. das Modifier Letter Apostrophe (U+02BC) aus YouTube-Titeln.
    
    Args:
        text: Der zu bereinigende Text
        
    Returns:
        Text mit ersetzten problematischen Zeichen
    """
    # Normalisiere Unicode (NFC = kanonische Komposition)
    text = unicodedata.normalize('NFC', text)
    
    # Ersetze bekannte problematische Zeichen
    for old, new in UNICODE_REPLACEMENTS.items():
        text = text.replace(old, new)
    
    return text


def sanitize_filename(title: str, max_length: int = 80) -> str:
    """Erstellt einen sicheren Dateinamen aus einem Titel.
    
    Behandelt:
    - Ungültige Dateisystem-Zeichen (: / \\ * ? " < > |)
    - Problematische Unicode-Zeichen (Modifier Apostrophe, etc.)
    - Emojis und andere Nicht-BMP-Zeichen
    - Mehrfache Leerzeichen/Unterstriche
    
    Args:
        title: Original-Titel (z.B. YouTube-Video-Titel)
        max_length: Maximale Länge des Dateinamens (ohne Erweiterung)
        
    Returns:
        Sicherer Dateiname, der auf allen Betriebssystemen funktioniert
    """
    if not title:
        return "SOMAS_Analyse"
    
    # 1. Normalisiere Unicode (NFC)
    filename = unicodedata.normalize('NFC', title)
    
    # 2. Ersetze problematische Unicode-Zeichen
    filename = sanitize_unicode_for_export(filename)
    
    # 3. Entferne Emojis und andere Nicht-BMP-Zeichen (> U+FFFF)
    # sowie Control-Zeichen (U+0000-U+001F)
    filename = ''.join(
        c for c in filename 
        if ord(c) < 0x10000 and ord(c) > 0x1F
    )
    
    # 4. Entferne/Ersetze Zeichen, die auf Windows/Mac/Linux ungültig sind
    # Windows: < > : " / \ | ? *
    # Mac: : /
    # Linux: / NUL
    invalid_chars_pattern = r'[<>:"/\\|?*\x00-\x1f]'
    filename = re.sub(invalid_chars_pattern, '', filename)
    
    # 5. Ersetze mehrfache Leerzeichen durch einzelnes
    filename = re.sub(r'\s+', ' ', filename)
    
    # 6. Ersetze mehrfache Unterstriche durch einzelnen
    filename = re.sub(r'_+', '_', filename)
    
    # 7. Entferne führende/abschließende Leerzeichen, Punkte und Unterstriche
    filename = filename.strip(' ._-')
    
    # 8. Kürze auf max_length (am Wortende wenn möglich)
    if len(filename) > max_length:
        filename = filename[:max_length]
        # Versuche am letzten Leerzeichen abzuschneiden
        last_space = filename.rfind(' ')
        if last_space > max_length * 0.5:  # Nur wenn nicht zu viel verloren geht
            filename = filename[:last_space]
        filename = filename.strip(' ._-')
    
    # 9. Fallback falls leer
    if not filename:
        filename = "SOMAS_Analyse"
    
    return filename


def export_to_markdown(
    analysis_result: str,
    video_info: Optional[VideoInfo] = None,
    output_path: Optional[str] = None,
    model_name: str = "",
    provider_name: str = "",
    sources: Optional[list[str]] = None,
) -> str:
    """Exportiert die Analyse als Markdown-Datei.
    
    Die Datei wird mit UTF-8-BOM gespeichert für bessere Kompatibilität
    mit Pandoc und anderen Windows-Tools.

    Args:
        analysis_result: Der Analyse-Text
        video_info: Optional - Video-Metadaten für Header
        output_path: Optional - Zielpfad
        model_name: Optional - Name des verwendeten Modells
        provider_name: Optional - Name des API-Providers
        sources: Optional - Liste von Quellen-URLs (z.B. von Perplexity)

    Returns:
        Pfad zur erstellten Datei
    """
    content = get_markdown_content(
        analysis_result, video_info, model_name, provider_name, sources
    )

    if not output_path:
        if video_info:
            base_name = sanitize_filename(video_info.title)
        else:
            base_name = "somas_analyse"
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_path = f"{base_name}_{timestamp}.md"

    # Schreibe mit UTF-8-BOM und Unix-Zeilenenden für maximale Kompatibilität
    # encoding='utf-8-sig' fügt automatisch das BOM hinzu
    # newline='\n' erzwingt Unix-Zeilenenden (auch auf Windows)
    with open(output_path, 'w', encoding='utf-8-sig', newline='\n') as f:
        f.write(content)

    return output_path


def get_markdown_content(
    analysis_result: str,
    video_info: Optional[VideoInfo] = None,
    model_name: str = "",
    provider_name: str = "",
    sources: Optional[list[str]] = None,
) -> str:
    """Gibt den Markdown-Inhalt als String zurück.
    
    Der Inhalt wird Unicode-sanitized für Pandoc-Kompatibilität.

    Args:
        analysis_result: Der Analyse-Text
        video_info: Optional - Video-Metadaten für Header
        model_name: Optional - Name des verwendeten Modells
        provider_name: Optional - Name des API-Providers
        sources: Optional - Liste von Quellen-URLs (z.B. von Perplexity)

    Returns:
        Formatierter Markdown-String
    """
    parts = []

    if video_info:
        # Sanitize den Titel für den Header
        safe_title = sanitize_unicode_for_export(video_info.title)
        parts.append(f"# SOMAS-Analyse: {safe_title}\n")
        parts.append(f"**Kanal:** {video_info.channel}  ")
        parts.append(f"**Dauer:** {video_info.duration_formatted}  ")
        parts.append(f"**URL:** {video_info.url}  ")
        if model_name and provider_name:
            parts.append(f"**Modell:** {model_name} ({provider_name})")
        parts.append("")
        parts.append("---\n")

    # Sanitize den Analyse-Text
    safe_analysis = sanitize_unicode_for_export(analysis_result)
    parts.append(safe_analysis)

    if sources:
        parts.append("\n\n---\n")
        parts.append("## Quellen\n")
        for i, url in enumerate(sources, 1):
            parts.append(f"[{i}] {url}  ")

    return '\n'.join(parts)


def get_suggested_filename(video_info: Optional[VideoInfo], preset_name: str = "") -> str:
    """Generiert einen Vorschlag für den Dateinamen.
    
    Args:
        video_info: Video-Metadaten
        preset_name: Name des verwendeten Presets
        
    Returns:
        Vorgeschlagener Dateiname (ohne Erweiterung)
    """
    if video_info:
        base_name = sanitize_filename(video_info.title, max_length=60)
    else:
        base_name = "SOMAS_Analyse"
    
    if preset_name:
        # Kürze Preset-Name für Dateinamen
        short_preset = preset_name[:10].replace(' ', '_')
        return f"{base_name}_{short_preset}"
    
    return base_name
