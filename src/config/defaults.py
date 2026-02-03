"""SOMAS-Konfiguration und Standardwerte."""

from dataclasses import dataclass
from typing import Optional


# Tiefenstufen mit Beschreibungen
DEPTH_DESCRIPTIONS = {
    1: "Kurzquellen-Modus (< 5 Min)",
    2: "Standard-Analyse",
    3: "Tiefenanalyse mit Details",
}

# Anzahl Sätze pro Abschnitt je Tiefenstufe
DEPTH_SENTENCES = {
    1: 2,
    2: 3,
    3: 5,
}


@dataclass
class TimeRange:
    """Optionaler Zeitbereich für die Analyse."""
    start: str  # Format: "HH:MM:SS" (normalisiert)
    end: str
    include_context: bool = False
    video_duration_formatted: str = ""  # z.B. "45:32" für Kontext-Text


@dataclass
class SomasConfig:
    """Konfiguration für die SOMAS-Analyse."""
    depth: int = 2
    language: str = "Deutsch"
    time_range: Optional[TimeRange] = None

    @property
    def depth_description(self) -> str:
        """Gibt die Beschreibung der aktuellen Tiefenstufe zurück."""
        return DEPTH_DESCRIPTIONS.get(self.depth, "Standard-Analyse")

    @property
    def sentences_per_section(self) -> int:
        """Gibt die Anzahl Sätze pro Abschnitt zurück."""
        return DEPTH_SENTENCES.get(self.depth, 3)


@dataclass
class VideoInfo:
    """Metadaten eines YouTube-Videos."""
    title: str
    channel: str
    duration: int  # Sekunden
    url: str

    @property
    def duration_formatted(self) -> str:
        """Formatiert die Dauer als MM:SS oder HH:MM:SS."""
        hours, remainder = divmod(self.duration, 3600)
        minutes, seconds = divmod(remainder, 60)
        if hours > 0:
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        return f"{minutes}:{seconds:02d}"


# Test-URLs für Entwicklung
TEST_URLS = [
    "https://www.youtube.com/watch?v=2yVJffNplJc",  # Taylor Lorenz
    "https://www.youtube.com/watch?v=MZWansUMeS8",  # Based Camp Collins
    "https://www.youtube.com/shorts/8tYx3kJNnhI",  # Candace Owens Short
]
