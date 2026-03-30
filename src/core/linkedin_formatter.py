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


def create_post_header(
    title: str, channel: str,
    model_name: str = "", provider_name: str = "",
) -> str:
    """Erstellt den LinkedIn-Post-Header aus Video-Metadaten.

    Format:
        𝗩𝗶𝗱𝗲𝗼-𝗧𝗶𝘁𝗲𝗹 (fett)
        Kanal, YT

        𝗦𝗢𝗠𝗔𝗦-𝗔𝗻𝗮𝗹𝘆𝘀𝗲 (fett)
        via Modell, Provider (optional)

    Args:
        title: Video-Titel
        channel: Kanal-Name
        model_name: Optional - Name des verwendeten Modells
        provider_name: Optional - Name des API-Providers

    Returns:
        Formatierter Header für LinkedIn-Post
    """
    bold_title = to_bold(title)
    bold_somas = to_bold("Analyse · SOMAS")
    header = f"{bold_title}\n{channel}, YT\n\n{bold_somas}\n"
    if model_name and provider_name:
        header += f"via {model_name}, {provider_name}\n"
    header += "\n"
    return header


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


def strip_url_protocol(url: str) -> str:
    """Entfernt Protokoll und www. von einer URL.

    Args:
        url: Vollständige URL

    Returns:
        URL ohne https://, http:// und www.
    """
    url = re.sub(r'^https?://', '', url)
    url = re.sub(r'^www\.', '', url)
    return url


def extract_domain_name(url: str) -> str:
    """Extrahiert den Domain-Namen ohne Protokoll, www und TLD.

    Args:
        url: Vollständige URL oder Domain

    Returns:
        Reiner Domain-Name (z.B. 'timesofisrael', 'cnn')
    """
    domain = strip_url_protocol(url).split('/')[0]
    # Compound-TLDs entfernen (.co.uk, .com.au, .org.uk, etc.)
    stripped = re.sub(
        r'\.(co|com|org|net|gov)\.[a-z]{2}$', '', domain, flags=re.IGNORECASE
    )
    if stripped != domain:
        domain = stripped
    else:
        # Einfache TLD entfernen (.com, .org, .net, .de, etc.)
        domain = re.sub(r'\.[a-z]{2,}$', '', domain, flags=re.IGNORECASE)
    return domain


def format_for_linkedin(
    text: str, video_title: str = "", video_channel: str = "",
    model_name: str = "", provider_name: str = "",
    citations: list[str] | None = None,
) -> tuple[str, str]:
    """Konvertiert Markdown-formatierten Text zu LinkedIn-kompatiblem Format.

    Transformationen:
    - Extrahiert nur den Analyse-Teil (ab FRAMING)
    - ### HEADING → entfernt (Zwischenüberschriften werden zu Leerzeilen)
    - **bold** → 𝗯𝗼𝗹𝗱
    - *italic* oder _italic_ → 𝘪𝘵𝘢𝘭𝘪𝘤
    - - item → • item
    - URLs aus Fließtext entfernen, am Ende als Quellenblock sammeln

    Args:
        text: Markdown-formatierter Text
        video_title: Optional - Video-Titel für Post-Header
        video_channel: Optional - Kanal-Name für Post-Header
        model_name: Optional - Name des verwendeten Modells
        provider_name: Optional - Name des API-Providers
        citations: Optional - Liste von Quell-URLs (z.B. von Perplexity API).
            Wenn vorhanden, werden diese als Quellen übernommen. Die [N]-Marker
            im Text (von der API gesetzt) bleiben erhalten.

    Returns:
        Tuple aus (LinkedIn-Text, Detail-Quellen).
        LinkedIn-Text: Formatierter Text mit Unicode und Kurzquellen.
        Detail-Quellen: Nummerierte Quellenliste mit vollen URLs.
    """
    # Nur den Analyse-Teil ab FRAMING extrahieren (ohne Einleitung)
    analysis_text = extract_analysis_body(text)

    lines = analysis_text.split('\n')
    result_lines: list[str] = []
    collected_sources: list[tuple[int, str, str, str]] = []  # (nr, name, url, domain)
    footnote_counter = 0

    # API-Citations vorbelegen (z.B. Perplexity gibt URLs separat zurück,
    # der Text enthält bereits [1][2]-Marker ohne die eigentlichen URLs)
    if citations:
        for i, url in enumerate(citations, start=1):
            domain = extract_domain_name(url)
            collected_sources.append((i, domain, url, domain))
            footnote_counter = i

    # SOMAS-Abschnittsüberschriften (mit und ohne Markdown-Hashes)
    somas_headers = [
        'FRAMING', 'KERNTHESE', 'ELABORATION', 'IMPLIKATION',
        'KRITIK', 'OFFENE_FRAGEN', 'ZITATE', 'VERBINDUNGEN',
        'ANSCHLUSSFRAGE', 'QUICK INFO'
    ]
    somas_pattern = r'^(?:#{1,6}\s+)?(' + '|'.join(somas_headers) + r')(?:\s*:?)?\s*$'

    for line in lines:
        # SOMAS-Überschriften → Leerzeile (Abschnitt visuell trennen)
        if re.match(somas_pattern, line.strip(), re.IGNORECASE):
            # Füge Leerzeile als Trenner hinzu (falls nicht am Anfang)
            if result_lines and result_lines[-1].strip():
                result_lines.append('')
            continue

        # Andere Markdown-Headers: ### HEADING → auch entfernen
        header_match = re.match(r'^(#{1,6})\s+(.+)$', line)
        if header_match:
            if result_lines and result_lines[-1].strip():
                result_lines.append('')
            continue

        # SOMAS-Header am Zeilenanfang entfernen (auch mit nachfolgendem Text)
        for header in somas_headers:
            line = re.sub(rf'^{header}\s*:\s*', '', line, flags=re.IGNORECASE)

        # Markdown Links: [text](url) → Text [N]
        def collect_markdown_link(match: re.Match[str]) -> str:
            nonlocal footnote_counter
            name = match.group(1)
            url = match.group(2)
            footnote_counter += 1
            domain = extract_domain_name(url)
            collected_sources.append((footnote_counter, name, url, domain))
            return f"{name} [{footnote_counter}]"
        line = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', collect_markdown_link, line)

        # Bare URLs im Text: durch [N] ersetzen
        def collect_bare_url(match: re.Match[str]) -> str:
            nonlocal footnote_counter
            url = match.group(0).rstrip('.,!?;:')
            domain = extract_domain_name(url)
            footnote_counter += 1
            collected_sources.append((footnote_counter, domain, url, domain))
            return f"[{footnote_counter}]"
        line = re.sub(r'https?://[^\s,)]+', collect_bare_url, line)

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

    # Mehrfache Leerzeilen auf eine reduzieren
    formatted_text = re.sub(r'\n{3,}', '\n\n', formatted_text)

    # Führende/trailing Leerzeilen entfernen
    formatted_text = formatted_text.strip()

    # Post-Header hinzufügen, wenn Video-Infos vorhanden
    if video_title and video_channel:
        header = create_post_header(
            video_title, video_channel, model_name, provider_name
        )
        formatted_text = header + formatted_text

    # Domain-Namen vor [N]-Markern entfernen (AI gibt oft "domainname URL" aus)
    if collected_sources:
        for _, _, _url, domain in collected_sources:
            # "domainname [N]" → "[N]" und "domainname. [N]" → "[N]"
            formatted_text = re.sub(
                rf'\b{re.escape(domain)}\.?\s*(\[\d+\])',
                r'\1',
                formatted_text,
                flags=re.IGNORECASE
            )

    # Quellenblock am Ende: gleiche Domains zusammenfassen
    if collected_sources:
        # Gruppiere Fußnoten-Nummern nach Domain
        domain_numbers: dict[str, list[int]] = {}
        for number, _name, _url, domain in collected_sources:
            if domain not in domain_numbers:
                domain_numbers[domain] = []
            domain_numbers[domain].append(number)

        # Formatiere: "1,6: timesofisrael" oder "2: cnn"
        source_parts: list[str] = []
        for domain, numbers in domain_numbers.items():
            nums = ",".join(str(n) for n in numbers)
            source_parts.append(f"{nums}: {domain}")

        formatted_text += "\n\nQuellen: " + " | ".join(source_parts)

    # Detail-Quellen: nummerierte Liste mit vollen URLs
    detailed_sources = ""
    if collected_sources:
        detail_lines: list[str] = ["Quellenangaben im Detail:"]
        for number, name, url, _domain in collected_sources:
            detail_lines.append(f"[{number}] {name} - {url}")
        detailed_sources = "\n".join(detail_lines)

    return formatted_text, detailed_sources
