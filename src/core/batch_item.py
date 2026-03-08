"""Datenmodelle für die Batch-Verarbeitung.

Enthält BatchItem (Zustand pro URL) und BatchConfig (gemeinsame
Einstellungen eines Batch-Durchlaufs).
"""

from dataclasses import dataclass, field
from typing import Optional

from src.config.defaults import VideoInfo


@dataclass
class BatchItem:
    """Ein Eintrag in der Batch-Warteschlange.

    Attributes:
        url: YouTube-URL.
        position: Laufende Nummer (1-5).
        status: Aktueller Verarbeitungsstatus.
        video_info: Metadaten nach URL-Auflösung.
        prompt: Generierter SOMAS-Prompt (für Debugging).
        result_text: API-Ergebnis.
        error_message: Fehlermeldung bei status='error'.
        analysis_id: DB-ID aus RatingStore (für Bewertung).
        tokens_used: Token-Verbrauch der API-Antwort.
        response_time: Antwortzeit in Sekunden.
    """

    url: str
    position: int  # 1-5

    # Status: pending | loading | prompting | calling | done | error
    status: str = "pending"

    # Video-Infos (nach URL-Auflösung)
    video_info: Optional[VideoInfo] = None

    # Prompt und Ergebnis
    prompt: str = ""
    result_text: str = ""
    error_message: str = ""

    # Verknüpfung mit DB
    analysis_id: Optional[int] = None

    # Metriken
    tokens_used: int = 0
    response_time: float = 0.0

    def to_dict(self) -> dict:
        """Serialisiert das BatchItem für JSON-Persistenz.

        VideoInfo wird in ein flaches Dict konvertiert;
        api_key und andere sensible Daten sind nicht enthalten.
        """
        video_dict = None
        if self.video_info:
            video_dict = {
                "title": self.video_info.title,
                "channel": self.video_info.channel,
                "duration": self.video_info.duration,
                "url": self.video_info.url,
                "transcript": self.video_info.transcript,
            }
        return {
            "url": self.url,
            "position": self.position,
            "status": self.status,
            "video_info": video_dict,
            "prompt": self.prompt,
            "result_text": self.result_text,
            "error_message": self.error_message,
            "analysis_id": self.analysis_id,
            "tokens_used": self.tokens_used,
            "response_time": self.response_time,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "BatchItem":
        """Deserialisiert ein BatchItem aus einem JSON-Dict."""
        video_info = None
        vi = data.get("video_info")
        if vi and isinstance(vi, dict):
            video_info = VideoInfo(
                title=vi.get("title", ""),
                channel=vi.get("channel", ""),
                duration=vi.get("duration", 0),
                url=vi.get("url", ""),
                transcript=vi.get("transcript", ""),
            )
        return cls(
            url=data["url"],
            position=data.get("position", 1),
            status=data.get("status", "pending"),
            video_info=video_info,
            prompt=data.get("prompt", ""),
            result_text=data.get("result_text", ""),
            error_message=data.get("error_message", ""),
            analysis_id=data.get("analysis_id"),
            tokens_used=data.get("tokens_used", 0),
            response_time=data.get("response_time", 0.0),
        )


@dataclass
class BatchConfig:
    """Gemeinsame Einstellungen für einen Batch-Durchlauf.

    Werden beim Start des Batch-Modus aus dem Hauptfenster übernommen
    und bleiben für alle URLs identisch.

    Attributes:
        provider_id: API-Provider ("perplexity", "openrouter").
        model_id: Modell-ID (z.B. "anthropic/claude-sonnet-4-5").
        model_name: Anzeigename des Modells.
        preset_name: SOMAS-Preset (z.B. "Standard").
        perspective: Analyse-Perspektive ("neutral", "critical", "empathic").
        depth: Tiefenstufe (1-3).
        language: Analysesprache.
        api_key: API-Key (wird NICHT in Temp-Dateien persistiert).
    """

    provider_id: str
    model_id: str
    model_name: str
    preset_name: str
    perspective: str
    depth: int = 2
    language: str = "Deutsch"
    api_key: str = ""

    def to_dict(self) -> dict:
        """Serialisiert die Config für JSON-Persistenz.

        api_key wird bewusst ausgelassen (Sicherheit).
        """
        return {
            "provider_id": self.provider_id,
            "model_id": self.model_id,
            "model_name": self.model_name,
            "preset_name": self.preset_name,
            "perspective": self.perspective,
            "depth": self.depth,
            "language": self.language,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "BatchConfig":
        """Deserialisiert eine BatchConfig aus einem JSON-Dict."""
        return cls(
            provider_id=data["provider_id"],
            model_id=data["model_id"],
            model_name=data.get("model_name", ""),
            preset_name=data["preset_name"],
            perspective=data.get("perspective", "neutral"),
            depth=data.get("depth", 2),
            language=data.get("language", "Deutsch"),
        )
