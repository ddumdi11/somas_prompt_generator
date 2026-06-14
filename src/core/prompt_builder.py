"""Prompt-Builder für SOMAS-Analyse-Prompts.

Changelog v0.3.1:
- Neues Research-Preset mit recommended_models und model_hint
- Unterstützung für Presets ohne Zeichenbegrenzung (max_chars=0)

Changelog v0.5.1:
- Neues Feld requires_web_search im PromptPreset für Web-Search-abhängige Presets
"""

import json
import re
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from jinja2 import Environment, FileSystemLoader

from src.config.defaults import VideoInfo, SomasConfig


@dataclass
class PromptPreset:
    """Repräsentiert ein Prompt-Preset."""
    id: str
    name: str
    description: str
    max_chars: int
    sentences_per_section: int
    reading_time_seconds: int
    system_prompt: str
    template_file: str
    # Neu in v0.3.1:
    recommended_models: Optional[List[str]] = None
    show_model_hint: bool = False
    model_hint_message: Optional[str] = None
    # Neu in v0.4.2: Preset-Template enthält eigene {{ transcript }}-Einbettung
    transcript_aware: bool = False
    # Neu in v0.5.1: Preset erfordert Web-Search-fähiges Modell
    requires_web_search: bool = False
    # Neu in v0.6.0: Default-Perspektive für Analysehaltung
    perspective: str = "neutral"

    @property
    def reading_time_display(self) -> str:
        """Formatiert die Lesezeit für die Anzeige."""
        if self.reading_time_seconds == 0:
            return "variabel"
        if self.reading_time_seconds < 60:
            return f"~{self.reading_time_seconds} Sek."
        minutes = self.reading_time_seconds // 60
        return f"~{minutes} Min."
    
    @property
    def max_chars_display(self) -> str:
        """Formatiert die Zeichenbegrenzung für die Anzeige."""
        if self.max_chars == 0:
            return "unbegrenzt"
        return f"max. {self.max_chars:,}".replace(',', '.')
    
    @property
    def is_unlimited(self) -> bool:
        """Prüft ob das Preset keine Zeichenbegrenzung hat."""
        return self.max_chars == 0
    
    @property
    def has_model_recommendation(self) -> bool:
        """Prüft ob das Preset Modellempfehlungen hat."""
        return self.recommended_models is not None and len(self.recommended_models) > 0


def get_config_dir() -> Path:
    """Gibt den Pfad zum Config-Verzeichnis zurück."""
    return Path(__file__).parent.parent / "config"


def load_presets() -> Dict[str, PromptPreset]:
    """Lädt alle Prompt-Presets aus der JSON-Konfiguration.

    Returns:
        Dictionary mit Preset-Key und PromptPreset-Objekten
    """
    config_path = get_config_dir() / "prompt_presets.json"
    with open(config_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    presets = {}
    for key, preset_data in data["presets"].items():
        presets[key] = PromptPreset(
            id=preset_data["id"],
            name=preset_data["name"],
            description=preset_data["description"],
            max_chars=preset_data["max_chars"],
            sentences_per_section=preset_data["sentences_per_section"],
            reading_time_seconds=preset_data["reading_time_seconds"],
            system_prompt=preset_data["system_prompt"],
            template_file=preset_data["template_file"],
            # Neue Felder mit Defaults für Rückwärtskompatibilität
            recommended_models=preset_data.get("recommended_models"),
            show_model_hint=preset_data.get("show_model_hint", False),
            model_hint_message=preset_data.get("model_hint_message"),
            transcript_aware=preset_data.get("transcript_aware", False),
            requires_web_search=preset_data.get("requires_web_search", False),
            perspective=preset_data.get("perspective", "neutral"),
        )
    return presets


def get_preset_names() -> List[str]:
    """Gibt eine Liste aller verfügbaren Preset-Namen zurück."""
    presets = load_presets()
    return [p.name for p in presets.values()]


def get_preset_by_name(name: str) -> Optional[PromptPreset]:
    """Findet ein Preset anhand seines Anzeigenamens."""
    presets = load_presets()
    for preset in presets.values():
        if preset.name == name:
            return preset
    return None


def get_preset_by_id(preset_id: str) -> Optional[PromptPreset]:
    """Findet ein Preset anhand seiner ID."""
    presets = load_presets()
    for preset in presets.values():
        if preset.id == preset_id:
            return preset
    return None


# Perspektive-Texte (v0.6.0)
PERSPECTIVE_TEXTS = {
    "neutral": (
        "PERSPEKTIVE: Neutral-Deskriptiv.\n"
        "Beschreibe in nüchterner Sprache, was gesagt wird, ohne eigene Wertung. "
        "Ordne Positionen und Argumente ein, ohne sie zu bewerten. Gib die Logik "
        "des Sprechers wieder, auch wenn sie fehlerhaft ist – die Einordnung "
        "übernimmt der Leser. Bei mehreren Sprechern: Stelle die verschiedenen "
        "Standpunkte gleichwertig dar."
    ),
    "critical": (
        "PERSPEKTIVE: Kritisch-Analytisch.\n"
        "Hinterfrage in analytischer Sprache rhetorische Techniken, identifiziere "
        "Auslassungen und bewerte die Schlüssigkeit der Argumentation. Benenne, "
        "was gesagt wird, aber auch, was bewusst nicht gesagt wird. Bei mehreren "
        "Sprechern: Analysiere, wer den Diskurs dominiert und mit welchen Mitteln."
    ),
    "empathic": (
        "PERSPEKTIVE: Empathisch-Rekonstruktiv.\n"
        "Versetze dich in die Position der Zielgruppe und erkläre in einfühlsamer "
        "Sprache, warum der Inhalt sie überzeugt. Rekonstruiere die innere Logik "
        "und emotionale Wirkung, ohne sie dir zu eigen zu machen oder zu bewerten. "
        "Ziel ist Verständnis, nicht Zustimmung. Bei mehreren Sprechern: Beschreibe "
        "die emotionalen Dynamiken zwischen den Teilnehmern."
    ),
}


def get_perspective_text(perspective: str) -> str:
    """Gibt den Perspektive-Textblock für ein Prompt-Template zurück.

    Args:
        perspective: Perspektiv-Schlüssel ("neutral", "critical", "empathic").

    Returns:
        Perspektiv-Text; bei unbekanntem Schlüssel der neutrale Standardtext.
    """
    return PERSPECTIVE_TEXTS.get(perspective, PERSPECTIVE_TEXTS["neutral"])


# Alle Standard-Schema-Module (für Anti-Monotonie)
ALL_MODULES = [
    "KRITIK", "ZITATE", "OFFENE_FRAGEN", "VERBINDUNGEN",
    "SUBTEXT", "FAKTENCHECK",
]


def get_anti_monotony_hint(
    recent_modules: List[str], threshold: int = 3
) -> str:
    """Generiert einen Anti-Monotonie-Hinweis wenn nötig.

    Prüft ob die letzten `threshold` Module identisch sind.
    Wenn ja, wird ein Hinweis generiert, der andere Module bevorzugt.

    Args:
        recent_modules: Liste der letzten N Module (neueste zuerst).
        threshold: Ab wie vielen Wiederholungen der Hinweis greift.

    Returns:
        Hinweis-Text oder leere Zeichenkette.
    """
    if len(recent_modules) < threshold:
        return ""

    # Prüfe ob die letzten threshold Module alle identisch sind
    last_n = recent_modules[:threshold]
    if len(set(last_n)) != 1:
        return ""

    repeated_module = last_n[0]
    alternatives = [m for m in ALL_MODULES if m != repeated_module]
    alternatives_str = ", ".join(alternatives)

    return (
        f"Wähle für diese Analyse bevorzugt eines der folgenden Module: "
        f"{alternatives_str}."
    )


def get_template_dir() -> Path:
    """Gibt den Pfad zum Templates-Verzeichnis zurück."""
    # Vom src/core/ aus zwei Ebenen hoch, dann in templates/
    base_dir = Path(__file__).parent.parent.parent
    return base_dir / "templates"


def load_template(template_name: str = "somas_prompt.txt") -> str:
    """Lädt ein Template aus dem Templates-Verzeichnis.

    Args:
        template_name: Name der Template-Datei

    Returns:
        Template-Inhalt als String
    """
    template_path = get_template_dir() / template_name
    with open(template_path, "r", encoding="utf-8") as f:
        return f.read()


# --- Faktencheck-Verifikation (v0.10.0) ---

# Single Source of Truth für das parsbare Stufe-1-Format. Enthält die exakten
# Vertrags-Marker (**Meinungen:** / **Interpretationen:** / **Behauptungen
# (überprüfbar):**), auf die der Claim-Parser (extract_claims_from_faktencheck)
# angewiesen ist. Wird bei erzwungenem FAKTENCHECK injiziert (s. _apply_custom_overrides),
# damit das Format in JEDEM Preset garantiert ist – auch in den namens-only-Templates.
FAKTENCHECK_FORMAT = (
    "FAKTENCHECK-FORMAT — gib den Abschnitt GENAU so aus (Header exakt '### FAKTENCHECK'):\n"
    "**Meinungen:** subjektive Wertungen (nicht prüfbar), nummeriert.\n"
    "**Interpretationen:** Deutungen/Schlussfolgerungen (nicht direkt prüfbar), nummeriert.\n"
    "**Behauptungen (überprüfbar):** je eine einzelne, in sich abgeschlossene, falsifizierbare\n"
    "Tatsachenaussage pro Punkt, nummeriert; neutral und kontextfrei formuliert (ohne\n"
    "Meinungswörter); KEIN Urteil über Wahr/Falsch.\n"
    "Ordne JEDEN Block nach Relevanz absteigend (wichtigste zuerst): zentral für Kernthese/\n"
    "Hauptthema und/oder strittig bzw. folgenreich im Diskurs. Triviale Selbstverständlichkeiten\n"
    "NICHT auflisten bzw. ans Ende stellen.\n"
    "Schreibe JEDEN nummerierten Punkt auf eine EIGENE Zeile (Zeilenumbruch nach jedem Punkt); "
    "KEINE Inline-Aufzählung mehrerer Punkte in einer Zeile."
)

# Hebt das Antwort-Zeichenlimit NUR für den erzwungenen FAKTENCHECK-Lauf (Verifikation) auf,
# damit die vollständige, relevanz-sortierte Behauptungsliste für das Top-N-Capping entsteht.
# Steht vor dem (im Template späteren) GESAMTZEICHENLIMIT-Text und überschreibt es so.
FAKTENCHECK_NO_LIMIT_HINT = (
    "HINWEIS: Für diesen Lauf ist ein etwaiges Gesamtzeichenlimit AUFGEHOBEN. Die "
    "Vollständigkeit der relevanz-sortierten Behauptungsliste hat Vorrang vor Kürze."
)


def _apply_custom_overrides(
    rendered: str,
    custom_system_prompt: Optional[str] = None,
    custom_module: Optional[str] = None,
) -> str:
    """Wendet Custom-Overrides auf einen gerenderten Prompt an.

    Args:
        rendered: Der bereits gerenderte Template-Prompt.
        custom_system_prompt: Optionaler System-Prompt-Override (wird vorangestellt).
        custom_module: Optionales erzwungenes Modul (z.B. "KRITIK").

    Returns:
        Prompt mit angewendeten Overrides.
    """
    parts = []

    if custom_system_prompt:
        parts.append(custom_system_prompt.strip())

    if custom_module:
        parts.append(
            f"PFLICHT-MODUL: Verwende ausschließlich das Modul '{custom_module}'. "
            f"Keine andere Wahl ist erlaubt."
        )
        # v0.10.0: Bei erzwungenem FAKTENCHECK zusätzlich das parsbare 3-Block-Format
        # und die Limit-Aufhebung injizieren (deckt alle Presets ab, auch namens-only).
        if custom_module.strip().upper() == "FAKTENCHECK":
            parts.append(FAKTENCHECK_NO_LIMIT_HINT)
            parts.append(FAKTENCHECK_FORMAT)

    if parts:
        parts.append(rendered)
        return "\n\n".join(parts)

    return rendered


def build_prompt(
    video_info: VideoInfo,
    config: SomasConfig,
    questions: str = "",
    preset_name: Optional[str] = None,
    perspective: Optional[str] = None,
    anti_monotony_hint: str = "",
    custom_system_prompt: Optional[str] = None,
    custom_module: Optional[str] = None,
) -> str:
    """Generiert einen SOMAS-Prompt aus Template und Konfiguration.

    Args:
        video_info: Metadaten des Videos
        config: SOMAS-Konfiguration (Tiefe, Sprache, etc.)
        questions: Optionale Anschlussfragen
        preset_name: Name des zu verwendenden Presets (None für Legacy-Template)
        perspective: Perspektive-Override (None = Preset-Default verwenden)
        anti_monotony_hint: Optionaler Hinweis zur Modul-Variation.
        custom_system_prompt: Optionaler System-Prompt-Override aus PromptEditDialog.
        custom_module: Optionales erzwungenes Modul aus PromptEditDialog.

    Returns:
        Fertig gerenderte Prompt-Zeichenkette
    """
    template_dir = get_template_dir()
    env = Environment(
        loader=FileSystemLoader(template_dir),
        trim_blocks=True,
        lstrip_blocks=True,
    )

    # Wähle Template basierend auf Preset
    preset = None
    if preset_name:
        preset = get_preset_by_name(preset_name)
        if preset:
            template_file = preset.template_file
        else:
            template_file = "somas_prompt.txt"
    else:
        template_file = "somas_prompt.txt"

    # Verwende sentences_per_section vom Preset wenn vorhanden
    # Bei Research-Preset (sentences_per_section=0) wird dieser Wert nicht verwendet
    sentences_per_section = (
        preset.sentences_per_section if preset and preset.sentences_per_section > 0
        else config.sentences_per_section
    )

    template = env.get_template(template_file)

    # Perspektive: expliziter Override > Preset-Default > "neutral"
    effective_perspective = perspective or (preset.perspective if preset else "neutral")
    perspective_text = get_perspective_text(effective_perspective)

    # Anti-Monotonie wird durch custom_module überschrieben
    effective_hint = "" if custom_module else anti_monotony_hint

    rendered = template.render(
        video_title=video_info.title,
        channel_name=video_info.channel,
        video_url=video_info.url,
        depth=config.depth,
        depth_description=config.depth_description,
        sentences_per_section=sentences_per_section,
        language=config.language,
        time_range=config.time_range,
        max_chars=preset.max_chars if preset else 0,
        questions=questions.strip() if questions else "",
        perspective_text=perspective_text,
        anti_monotony_hint=effective_hint,
    )

    return _apply_custom_overrides(rendered, custom_system_prompt, custom_module)


def build_prompt_from_transcript(
    title: str,
    author: str,
    transcript: str,
    config: SomasConfig,
    url: Optional[str] = None,
    questions: str = "",
    preset_name: Optional[str] = None,
    is_auto_transcript: bool = False,
    perspective: Optional[str] = None,
    anti_monotony_hint: str = "",
    custom_system_prompt: Optional[str] = None,
    custom_module: Optional[str] = None,
) -> str:
    """Generiert einen SOMAS-Prompt aus manuellem Transkript.

    Verwendet ein eigenes Template (somas_prompt_transcript.txt), das
    den Transkript-Text direkt in den Prompt einbettet.

    Args:
        title: Titel der Quelle.
        author: Autor/Kanal/Sprecher.
        transcript: Der Transkript-Text.
        config: SOMAS-Konfiguration (Tiefe, Sprache).
        url: Optionale Quellen-URL.
        questions: Optionale Anschlussfragen.
        preset_name: Name des Presets (für sentences_per_section).
        is_auto_transcript: True wenn automatisch transkribiert (YouTube STT).
            Fügt einen Disclaimer über typische Erkennungsfehler ein.
        perspective: Perspektive-Override (None = Preset-Default verwenden).
        anti_monotony_hint: Optionaler Hinweis zur Modul-Variation.
        custom_system_prompt: Optionaler System-Prompt-Override aus PromptEditDialog.
        custom_module: Optionales erzwungenes Modul aus PromptEditDialog.

    Returns:
        Fertig gerenderte Prompt-Zeichenkette.
    """
    template_dir = get_template_dir()
    env = Environment(
        loader=FileSystemLoader(template_dir),
        trim_blocks=True,
        lstrip_blocks=True,
    )

    # Sentences_per_section vom Preset wenn vorhanden
    preset = None
    sentences_per_section = config.sentences_per_section
    if preset_name:
        preset = get_preset_by_name(preset_name)
        if preset and preset.sentences_per_section > 0:
            sentences_per_section = preset.sentences_per_section

    # Preset mit eigenem Transkript-Template (z.B. Musik) nutzt sein Template,
    # andere Presets nutzen das generische Transkript-Template
    if preset and preset.transcript_aware:
        template = env.get_template(preset.template_file)
    else:
        template = env.get_template("somas_prompt_transcript.txt")

    # Perspektive: expliziter Override > Preset-Default > "neutral"
    effective_perspective = perspective or (preset.perspective if preset else "neutral")
    perspective_text = get_perspective_text(effective_perspective)

    # Anti-Monotonie wird durch custom_module überschrieben
    effective_hint = "" if custom_module else anti_monotony_hint

    rendered = template.render(
        title=title,
        author=author,
        url=url,
        transcript=transcript,
        is_auto_transcript=is_auto_transcript,
        # Aliase für Kompatibilität mit Video-Templates
        video_title=title,
        channel_name=author,
        video_url=url or "",
        depth=config.depth,
        depth_description=config.depth_description,
        sentences_per_section=sentences_per_section,
        language=config.language,
        time_range=config.time_range,
        max_chars=preset.max_chars if preset else 0,
        questions=questions.strip() if questions else "",
        perspective_text=perspective_text,
        anti_monotony_hint=effective_hint,
    )

    return _apply_custom_overrides(rendered, custom_system_prompt, custom_module)


def build_prompt_with_preset(
    video_info: VideoInfo,
    preset: PromptPreset,
    questions: str = "",
    time_range: Optional[str] = None
) -> str:
    """Generiert einen SOMAS-Prompt direkt aus einem Preset.

    Args:
        video_info: Metadaten des Videos
        preset: Das zu verwendende PromptPreset
        questions: Optionale Anschlussfragen
        time_range: Optionaler Zeitbereich

    Returns:
        Fertig gerenderte Prompt-Zeichenkette
    """
    template_dir = get_template_dir()
    env = Environment(
        loader=FileSystemLoader(template_dir),
        trim_blocks=True,
        lstrip_blocks=True,
    )

    template = env.get_template(preset.template_file)

    return template.render(
        video_title=video_info.title,
        channel_name=video_info.channel,
        video_url=video_info.url,
        time_range=time_range,
        questions=questions.strip() if questions else "",
    )


# --- Modellvergleich (v0.9.0): Synthese-Prompt + Output-Säuberung ---

def build_synthesis_prompt(
    analysis_a: str,
    analysis_b: str,
    title: str,
    channel: str,
    duration_formatted: str,
    model_a_name: str,
    model_b_name: str,
    language: str = "Deutsch",
) -> str:
    """Baut den Synthese-Prompt für die Vergleichs-Kurzbeschreibung.

    Eingabe sind die VOLLSTÄNDIGEN Analysetexte A und B (alle Module),
    bewusst OHNE Transkript (PO-Entscheidung): Die Analysen sind bereits
    das verdichtete Produkt; das Transkript würde Tokens aufblähen und das
    Modell zum Neu-Analysieren statt Zusammenfassen verleiten.

    Das Modell soll AUSSCHLIESSLICH einen Fließtext (ein Absatz, ~4-6 Sätze)
    zurückgeben — keine Überschriften, Listen oder Modell-Meta. Die Ausgabe
    wird zusätzlich durch clean_synthesis_output() nachbereinigt.

    Args:
        analysis_a: Vollständiger SOMAS-Analysetext von Modell A.
        analysis_b: Vollständiger SOMAS-Analysetext von Modell B.
        title: Videotitel.
        channel: Kanal/Autor.
        duration_formatted: Formatierte Dauer (z.B. "12:34").
        model_a_name: Anzeigename von Modell A.
        model_b_name: Anzeigename von Modell B.
        language: Sprache der Kurzbeschreibung (Default: Deutsch).

    Returns:
        Der fertige Synthese-Prompt als String.
    """
    return (
        f"Du erhältst zwei unabhängige SOMAS-Analysen DESSELBEN Videos, erstellt von zwei\n"
        f"verschiedenen KI-Modellen. Schreibe eine neutrale, zusammenfassende Kurzbeschreibung\n"
        f"des Videos in {language} (ein zusammenhängender Absatz, 4-6 Sätze).\n\n"
        f"Regeln:\n"
        f"- Gib AUSSCHLIESSLICH den Absatz aus - keine Überschrift, keine Liste, keine Meta-Hinweise.\n"
        f"- Stütze dich nur auf die Inhalte beider Analysen; erfinde nichts hinzu.\n"
        f"- Wo sich die Analysen einig sind, formuliere bestätigend; wo sie abweichen, formuliere\n"
        f"  vorsichtig (\"das Video legt nahe\", \"dargestellt wird\").\n"
        f"- Neutraler, sachlicher Ton. Keine Wertung der Modelle.\n\n"
        f"VIDEO: {title} - {channel} ({duration_formatted})\n\n"
        f"ANALYSE A ({model_a_name}):\n{analysis_a}\n\n"
        f"ANALYSE B ({model_b_name}):\n{analysis_b}\n"
    )


def normalize_markdown_headings(text: str) -> str:
    """Korrigiert Markdown-Überschriften ohne Leerzeichen nach den Rauten.

    Manche Modelle geben `###FRAMING` statt `### FRAMING` aus — das rendert in
    strikten Markdown-Parsern nicht als Überschrift. Diese Funktion fügt rein
    strukturell ein Leerzeichen ein (`###Foo` → `### Foo`), ohne den Inhalt zu
    verändern. Bereits korrekt gesetzte Überschriften bleiben unberührt.

    Args:
        text: Beliebiger Markdown-Text (z.B. eine SOMAS-Analyse).

    Returns:
        Text mit normalisierten Überschriften-Markern.
    """
    if not text:
        return text
    # Zeilenanfang, optionale Einrückung, 1-6 Rauten, direkt gefolgt von einem
    # Zeichen, das weder Raute noch Whitespace ist (Lookahead verhindert, dass
    # bei "### FRAMING" das dritte # fälschlich als Nicht-Space gegriffen wird).
    return re.sub(r'(?m)^(\s*#{1,6})(?=[^#\s])', r'\1 ', text)


def clean_synthesis_output(text: str) -> str:
    """Bereinigt die Synthese-Ausgabe für die saubere Einbettung ins Layout.

    Entfernt umschließende Code-Fences (```...```), führende
    Überschriften-Zeilen (z.B. "# Kurzbeschreibung") und führende Leerzeilen.
    Der Rest bleibt unverändert, damit das deterministische Jinja2-Layout
    nicht durch Modell-Formatierung gestört wird.

    Args:
        text: Roh-Ausgabe des Synthese-Modells.

    Returns:
        Bereinigter Fließtext (kann leer sein, falls Eingabe leer war).
    """
    if not text:
        return ""

    s = text.strip()

    # Umschließende Code-Fences entfernen (```markdown ... ```)
    if s.startswith("```"):
        lines = s.splitlines()
        lines = lines[1:]  # öffnende Fence-Zeile weg
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]  # schließende Fence-Zeile weg
        s = "\n".join(lines).strip()

    # Führende Überschriften- und Leerzeilen entfernen
    lines = s.splitlines()
    while lines and (not lines[0].strip() or lines[0].lstrip().startswith("#")):
        lines.pop(0)

    return "\n".join(lines).strip()


# --- Faktencheck-Verifikation: Parser / Prompt / Cleaner (v0.10.0) ---

# Verdikt-Skala (exakt) für die Stufe-2-Ausgabe.
VERDICT_VALUES = (
    "bestätigt", "teilweise bestätigt", "widerlegt", "nicht überprüfbar",
)


def _split_consecutive_claims(region: str) -> list[str]:
    """Zerlegt eine Behauptungs-Region an FORTLAUFENDEN Nummern-Grenzen.

    Funktioniert für zeilen- UND inline-nummerierte Listen. Getrennt wird nur an
    der jeweils nächsten erwarteten Nummer (n → n+1), damit interne Zahlen wie
    'am 7. Oktober 2023' einen Claim nicht zerreißen.

    Args:
        region: Der zusammengefügte Behauptungs-Text (eine oder mehrere Zeilen).

    Returns:
        Liste der Behauptungs-Strings in Reihenfolge.
    """
    # Eine Nummer ist nur dann eine echte Claim-Grenze, wenn sie (a) fortlaufend
    # ist (n -> n+1) UND (b) am Zeilenanfang oder nach satzbeendender Interpunktion
    # steht. So zerreißt eine interne Zahl wie 'am 3. März 2020' den Claim nicht,
    # selbst wenn sie zufällig der nächsten erwarteten Nummer entspricht.
    chosen: list[tuple[int, int]] = []
    expected = None
    for m in re.finditer(r"(\d+)[\.\)]\s+", region):
        pos, num = m.start(), int(m.group(1))
        before = region[:pos].rstrip()
        boundary_ctx = (
            pos == 0
            or region[pos - 1] == "\n"
            or (before != "" and before[-1] in ".!?:)")
        )
        if not boundary_ctx:
            continue
        if expected is None:
            expected = num
        if num == expected:
            chosen.append((pos, m.end()))
            expected += 1

    claims: list[str] = []
    for i, (_pos, end) in enumerate(chosen):
        stop = chosen[i + 1][0] if i + 1 < len(chosen) else len(region)
        text = region[end:stop].strip().strip('*"„“”').strip()
        text = re.sub(r"\s+", " ", text).strip()
        if text:
            claims.append(text)
    return claims


def extract_claims_from_faktencheck(analysis_text: str) -> list[str]:
    """Extrahiert NUR die nummerierten Behauptungen aus dem FAKTENCHECK-Block.

    Sucht den Stufe-1-Block ``### FAKTENCHECK`` (Dekonstruktion, NICHT
    ``### FAKTENCHECK · VERIFIKATION``) bis zur nächsten ``### ``-Überschrift
    bzw. EOF. Ab dem Sub-Header ``Behauptungen`` wird die Claim-Region (Resttext
    der Header-Zeile + Folgezeilen bis zum nächsten Sub-Header/Terminator)
    eingesammelt und an fortlaufenden Nummern getrennt — robust gegen
    zeilen- UND inline-nummerierte Listen.

    Die Reihenfolge bleibt erhalten (Stufe 1 ordnet bereits nach Relevanz
    absteigend). Es findet KEINE Kappung statt — die Liste ist vollständig.

    Args:
        analysis_text: Der vollständige SOMAS-Analysetext.

    Returns:
        Liste aller Behauptungs-Strings in Relevanz-Reihenfolge (kann leer sein).
    """
    if not analysis_text:
        return []

    # Überschriften normalisieren ('###FAKTENCHECK' -> '### FAKTENCHECK'), damit die
    # Block-Ende-Erkennung (^\s*###\s) auch bei fehlendem Leerzeichen greift.
    analysis_text = normalize_markdown_headings(analysis_text)

    lines = analysis_text.splitlines()

    # 1) FAKTENCHECK-Header der Dekonstruktion finden (nicht den VERIFIKATION-Header)
    header_re = re.compile(r"^\s*###\s*FAKTENCHECK\b", re.IGNORECASE)
    start = None
    for i, line in enumerate(lines):
        if header_re.match(line) and "VERIFIKATION" not in line.upper():
            start = i
            break
    if start is None:
        return []

    # 2) Blockende = nächste '### '-Überschrift oder EOF
    end = len(lines)
    for j in range(start + 1, len(lines)):
        if re.match(r"^\s*###\s", lines[j]):
            end = j
            break
    block = lines[start + 1:end]

    # 3) Sub-Header 'Behauptungen' finden; er kann die Behauptungen bereits
    #    inline enthalten (z.B. DeepSeek: '**Behauptungen (überprüfbar):** 1. … 2. …').
    behaupt_re = re.compile(
        r"^\s*\*{0,2}\s*Behauptungen[^:]*:\s*\*{0,2}\s*(.*)$", re.IGNORECASE
    )
    next_subheader_re = re.compile(r"^\s*\*\*[^*]+:\*\*")
    stop_re = re.compile(
        r'^\s*(QUELLE|ANSCHLUSSFRAGE|WICHTIG|HINWEIS|TRANSKRIPT|---|""")',
        re.IGNORECASE,
    )
    header_idx = None
    inline_rest = ""
    for k, line in enumerate(block):
        m = behaupt_re.match(line)
        if m:
            header_idx = k
            inline_rest = m.group(1)
            break
    if header_idx is None:
        return []

    # 4) Claim-Region = Resttext der Header-Zeile + Folgezeilen bis zum nächsten
    #    Sub-Header / Abschnitts-Terminator / Blockende; dann an Nummern splitten.
    region_parts = [inline_rest]
    for line in block[header_idx + 1:]:
        if next_subheader_re.match(line) or stop_re.match(line):
            break
        region_parts.append(line)
    region = "\n".join(region_parts)

    return _split_consecutive_claims(region)


def cap_claims(claims: list[str], max_claims: int) -> tuple[list[str], int]:
    """Wendet die konfigurierbare Obergrenze deterministisch an.

    Args:
        claims: Vollständige, relevanz-sortierte Behauptungsliste.
        max_claims: Obergrenze (0 = unbegrenzt).

    Returns:
        Tupel ``(gekappte_liste, total_count)``. Bei ``max_claims == 0`` oder
        ``len(claims) <= max_claims`` bleibt die Liste unverändert (Kopie). Die
        App entscheidet anhand ``len(capped) < total``, ob gekappt wurde.
    """
    total = len(claims)
    if max_claims and max_claims > 0 and total > max_claims:
        return list(claims[:max_claims]), total
    return list(claims), total


def build_verification_prompt(
    claims: list[str],
    language: str = "Deutsch",
    source_hint: str = "",
) -> str:
    """Baut den Stufe-2-Verifikations-Prompt.

    Enthält AUSSCHLIESSLICH die Behauptungen (keine Meinungen, kein Transkript)
    → sauberer Handoff an das web-fähige Modell.

    Args:
        claims: Die (bereits gekappte) Liste der zu prüfenden Behauptungen.
        language: Sprache der Ausgabe (Default Deutsch).
        source_hint: Optionaler Kontext (z.B. Titel/URL) — nur als Orientierung.

    Returns:
        Der fertige Prompt-String.
    """
    numbered = "\n".join(f"{i}. {c}" for i, c in enumerate(claims, 1))
    verdicts = " | ".join(VERDICT_VALUES)
    hint = f"\nKONTEXT (nur zur Orientierung): {source_hint}\n" if source_hint else ""

    return (
        f"Du bist ein sorgfältiger Faktenprüfer. Prüfe die folgenden Behauptungen "
        f"einzeln per Websuche bzw. aktuellem Wissen. Antworte in {language}.\n"
        f"{hint}\n"
        f"REGELN:\n"
        f"- Prüfe AUSSCHLIESSLICH die vorgelegten Behauptungen, in gegebener "
        f"Reihenfolge. Erfinde keine neuen Behauptungen.\n"
        f"- Gib pro Behauptung EXAKT dieses Markdown-Format aus (kein Vorspann, "
        f"keine Meta, keine Einleitung):\n"
        f"\n"
        f"**<Nr>. „<Behauptung>\"**\n"
        f"- **Verdikt:** <eines von: {verdicts}>\n"
        f"- **Begründung:** <1–2 Sätze>\n"
        f"- **Quelle:** <URL oder Titel; bei 'nicht überprüfbar' ein Gedankenstrich: —>\n"
        f"\n"
        f"- Gib NUR Quellen an, die du tatsächlich abgerufen/verifiziert hast. "
        f"Erfinde KEINE URLs. Kannst du eine Behauptung nicht mit einer belastbaren "
        f"Quelle belegen, nutze Verdikt 'nicht überprüfbar' und Quelle '—'.\n"
        f"- Eine Quelle ist nur dann verpflichtend, wenn die Behauptung tatsächlich "
        f"verifiziert wurde (bestätigt / teilweise bestätigt / widerlegt).\n"
        f"- Verwende ausschließlich die vier genannten Verdikt-Werte, exakt geschrieben.\n"
        f"\n"
        f"ZU PRÜFENDE BEHAUPTUNGEN:\n"
        f"{numbered}\n"
    )


def clean_verification_output(text: str) -> str:
    """Bereinigt die Stufe-2-Ausgabe für das saubere Anhängen.

    Analog zu :func:`clean_synthesis_output`: entfernt umschließende Code-Fences
    sowie führende Leer-/Überschriftenzeilen, damit der Verifikationsabschnitt
    sauber unter den deterministischen Header gerendert werden kann.

    Args:
        text: Roh-Ausgabe des Verifikationsmodells.

    Returns:
        Bereinigter Markdown-Text (kann leer sein).
    """
    return clean_synthesis_output(text)


def get_preset_info_for_display(preset: PromptPreset) -> str:
    """Erstellt einen Info-String für die GUI-Anzeige.
    
    Args:
        preset: Das Preset
        
    Returns:
        Formatierter Info-String für Tooltip oder Beschreibung
    """
    info_parts = [preset.description]
    
    if preset.is_unlimited:
        info_parts.append("📝 Keine Zeichenbegrenzung")
    else:
        info_parts.append(f"📝 {preset.max_chars_display} Zeichen")
    
    info_parts.append(f"⏱️ Lesezeit: {preset.reading_time_display}")
    
    if preset.has_model_recommendation:
        models = ", ".join(m.split("/")[-1] for m in preset.recommended_models[:3])
        info_parts.append(f"🤖 Empfohlen: {models}")
    
    return "\n".join(info_parts)
