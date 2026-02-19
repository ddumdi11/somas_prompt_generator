"""Prompt-Builder für SOMAS-Analyse-Prompts.

Changelog v0.3.1:
- Neues Research-Preset mit recommended_models und model_hint
- Unterstützung für Presets ohne Zeichenbegrenzung (max_chars=0)
"""

import json
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


def build_prompt(
    video_info: VideoInfo,
    config: SomasConfig,
    questions: str = "",
    preset_name: Optional[str] = None
) -> str:
    """Generiert einen SOMAS-Prompt aus Template und Konfiguration.

    Args:
        video_info: Metadaten des Videos
        config: SOMAS-Konfiguration (Tiefe, Sprache, etc.)
        questions: Optionale Anschlussfragen
        preset_name: Name des zu verwendenden Presets (None für Legacy-Template)

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

    return template.render(
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
    )


def build_prompt_from_transcript(
    title: str,
    author: str,
    transcript: str,
    config: SomasConfig,
    url: Optional[str] = None,
    questions: str = "",
    preset_name: Optional[str] = None,
    is_auto_transcript: bool = False,
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

    return template.render(
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
    )


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
