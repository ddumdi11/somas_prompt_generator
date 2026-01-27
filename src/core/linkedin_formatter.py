"""LinkedIn-Formatter für Unicode-basierte Textformatierung.

LinkedIn unterstützt kein Markdown, aber Unicode-Zeichen für Fett/Kursiv.
"""

import re

# Unicode Bold (Sans-Serif Bold)
UNICODE_BOLD = {
    'A': '𝗔', 'B': '𝗕', 'C': '𝗖', 'D': '𝗗', 'E': '𝗘', 'F': '𝗙', 'G': '𝗚',
    'H': '𝗛', 'I': '𝗜', 'J': '𝗝', 'K': '𝗞', 'L': '𝗟', 'M': '𝗠', 'N': '𝗡',
    'O': '𝗢', 'P': '𝗣', 'Q': '𝗤', 'R': '𝗥', 'S': '𝗦', 'T': '𝗧', 'U': '𝗨',
    'V': '𝗩', 'W': '𝗪', 'X': '𝗫', 'Y': '𝗬', 'Z': '𝗭',
    'a': '𝗮', 'b': '𝗯', 'c': '𝗰', 'd': '𝗱', 'e': '𝗲', 'f': '𝗳', 'g': '𝗴',
    'h': '𝗵', 'i': '𝗶', 'j': '𝗷', 'k': '𝗸', 'l': '𝗹', 'm': '𝗺', 'n': '𝗻',
    'o': '𝗼', 'p': '𝗽', 'q': '𝗾', 'r': '𝗿', 's': '𝘀', 't': '𝘁', 'u': '𝘂',
    'v': '𝘃', 'w': '𝘄', 'x': '𝘅', 'y': '𝘆', 'z': '𝘇',
    '0': '𝟬', '1': '𝟭', '2': '𝟮', '3': '𝟯', '4': '𝟰',
    '5': '𝟱', '6': '𝟲', '7': '𝟳', '8': '𝟴', '9': '𝟵',
    # Umlaute haben keine Unicode-Bold-Varianten, bleiben normal
}

# Unicode Italic (Sans-Serif Italic)
UNICODE_ITALIC = {
    'A': '𝘈', 'B': '𝘉', 'C': '𝘊', 'D': '𝘋', 'E': '𝘌', 'F': '𝘍', 'G': '𝘎',
    'H': '𝘏', 'I': '𝘐', 'J': '𝘑', 'K': '𝘒', 'L': '𝘓', 'M': '𝘔', 'N': '𝘕',
    'O': '𝘖', 'P': '𝘗', 'Q': '𝘘', 'R': '𝘙', 'S': '𝘚', 'T': '𝘛', 'U': '𝘜',
    'V': '𝘝', 'W': '𝘞', 'X': '𝘟', 'Y': '𝘠', 'Z': '𝘡',
    'a': '𝘢', 'b': '𝘣', 'c': '𝘤', 'd': '𝘥', 'e': '𝘦', 'f': '𝘧', 'g': '𝘨',
    'h': '𝘩', 'i': '𝘪', 'j': '𝘫', 'k': '𝘬', 'l': '𝘭', 'm': '𝘮', 'n': '𝘯',
    'o': '𝘰', 'p': '𝘱', 'q': '𝘲', 'r': '𝘳', 's': '𝘴', 't': '𝘵', 'u': '𝘶',
    'v': '𝘷', 'w': '𝘸', 'x': '𝘹', 'y': '𝘺', 'z': '𝘻',
    # Umlaute haben keine Unicode-Italic-Varianten, bleiben normal
}


def to_bold(text: str) -> str:
    """Konvertiert Text zu Unicode Bold.

    Args:
        text: Eingabetext

    Returns:
        Text mit Unicode Bold-Zeichen
    """
    return ''.join(UNICODE_BOLD.get(c, c) for c in text)


def to_italic(text: str) -> str:
    """Konvertiert Text zu Unicode Italic.

    Args:
        text: Eingabetext

    Returns:
        Text mit Unicode Italic-Zeichen
    """
    return ''.join(UNICODE_ITALIC.get(c, c) for c in text)


def create_post_header(title: str, channel: str) -> str:
    """Erstellt den LinkedIn-Post-Header aus Video-Metadaten.

    Format:
        Video-Titel
        Kanal, YT

        SOMAS-Analyse

    Args:
        title: Video-Titel
        channel: Kanal-Name

    Returns:
        Formatierter Header für LinkedIn-Post
    """
    return f"{title}\n{channel}, YT\n\nSOMAS-Analyse\n\n"


def extract_analysis_body(text: str) -> str:
    """Extrahiert den Analyse-Text ab FRAMING (ohne Einleitung).

    Args:
        text: Vollständiger Analyse-Text

    Returns:
        Text ab FRAMING (ohne Einleitungssätze)
    """
    # Suche nach FRAMING (mit oder ohne ### Markdown-Header)
    framing_patterns = [
        r'(?m)^###?\s*FRAMING',  # ### FRAMING oder # FRAMING
        r'(?m)^FRAMING',          # FRAMING ohne Markdown
        r'(?m)^𝗙𝗥𝗔𝗠𝗜𝗡𝗚',        # Bereits konvertiertes Unicode-Bold
    ]

    for pattern in framing_patterns:
        match = re.search(pattern, text)
        if match:
            return text[match.start():]

    # Falls kein FRAMING gefunden, gib den ganzen Text zurück
    return text


def format_for_linkedin(text: str, video_title: str = "", video_channel: str = "") -> str:
    """Konvertiert Markdown-formatierten Text zu LinkedIn-kompatiblem Format.

    Transformationen:
    - Extrahiert nur den Analyse-Teil (ab FRAMING)
    - ### HEADING → 𝗛𝗘𝗔𝗗𝗜𝗡𝗚
    - **bold** → 𝗯𝗼𝗹𝗱
    - *italic* oder _italic_ → 𝘪𝘵𝘢𝘭𝘪𝘤
    - - item → • item
    - [text](url) → text (url)

    Args:
        text: Markdown-formatierter Text
        video_title: Optional - Video-Titel für Post-Header
        video_channel: Optional - Kanal-Name für Post-Header

    Returns:
        LinkedIn-kompatibler Text mit Unicode-Formatierung
    """
    # Nur den Analyse-Teil ab FRAMING extrahieren (ohne Einleitung)
    analysis_text = extract_analysis_body(text)

    lines = analysis_text.split('\n')
    result_lines = []

    for line in lines:
        # Headers: ### HEADING → 𝗛𝗘𝗔𝗗𝗜𝗡𝗚
        header_match = re.match(r'^(#{1,6})\s+(.+)$', line)
        if header_match:
            header_text = header_match.group(2)
            result_lines.append(to_bold(header_text))
            continue

        # Markdown Links: [text](url) → text (url)
        line = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'\1 (\2)', line)

        # Code blocks: `code` → code (einfach Backticks entfernen)
        line = re.sub(r'`([^`]+)`', r'\1', line)

        # Bold: **text** → Unicode Bold
        def bold_replace(match):
            return to_bold(match.group(1))
        line = re.sub(r'\*\*([^*]+)\*\*', bold_replace, line)

        # Italic: *text* oder _text_ → Unicode Italic
        def italic_replace(match):
            return to_italic(match.group(1))
        line = re.sub(r'(?<!\*)\*([^*]+)\*(?!\*)', italic_replace, line)
        line = re.sub(r'_([^_]+)_', italic_replace, line)

        # Bullet points: - item → • item
        line = re.sub(r'^(\s*)-\s+', r'\1• ', line)

        result_lines.append(line)

    formatted_text = '\n'.join(result_lines)

    # Post-Header hinzufügen, wenn Video-Infos vorhanden
    if video_title and video_channel:
        header = create_post_header(video_title, video_channel)
        return header + formatted_text

    return formatted_text
