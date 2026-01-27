"""Prompt-Builder für SOMAS-Analyse-Prompts."""

import json
from pathlib import Path
from dataclasses import dataclass
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

    @property
    def reading_time_display(self) -> str:
        """Formatiert die Lesezeit für die Anzeige."""
        if self.reading_time_seconds < 60:
            return f"~{self.reading_time_seconds} Sek."
        minutes = self.reading_time_seconds // 60
        return f"~{minutes} Min."


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
    if preset_name:
        preset = get_preset_by_name(preset_name)
        if preset:
            template_file = preset.template_file
        else:
            template_file = "somas_prompt.txt"
    else:
        template_file = "somas_prompt.txt"

    template = env.get_template(template_file)

    return template.render(
        video_title=video_info.title,
        channel_name=video_info.channel,
        video_url=video_info.url,
        depth=config.depth,
        depth_description=config.depth_description,
        sentences_per_section=config.sentences_per_section,
        language=config.language,
        time_range=config.time_range,
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
