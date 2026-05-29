"""Datenmodelle für den Modellvergleich (v0.9.0).

Analog zu batch_item.py, aber für genau ein Video, das von zwei Modellen
(A und B) nach dem SOMAS-Schema analysiert wird; ein drittes Modell (Synthese)
erzeugt daraus eine zusammenfassende Kurzbeschreibung.

- ModelChoice:      Provider/Modell-Auswahl eines einzelnen Pickers.
- ComparisonConfig: Gemeinsame Eingabe- und SOMAS-Parameter + drei Modellauswahlen.
- ComparisonResult: Laufzeit-Zustand eines Vergleichslaufs (Texte, Tokens, Fehler).
"""

from dataclasses import dataclass, field
from typing import Optional

from src.config.defaults import VideoInfo


@dataclass
class ModelChoice:
    """Provider- und Modellauswahl eines einzelnen Pickers.

    Attributes:
        provider_id: Provider-ID ("perplexity" | "openrouter" | "anthropic" | "openai").
        model_id: Modell-ID (z.B. "deepseek/deepseek-chat-v3.2").
        model_name: Anzeigename des Modells (z.B. "DeepSeek V3.2").
        provider_name: Anzeigename des Providers (z.B. "OpenRouter").
    """

    provider_id: str
    model_id: str
    model_name: str = ""
    provider_name: str = ""

    def to_dict(self) -> dict:
        """Serialisiert die Auswahl für JSON-Persistenz."""
        return {
            "provider_id": self.provider_id,
            "model_id": self.model_id,
            "model_name": self.model_name,
            "provider_name": self.provider_name,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ModelChoice":
        """Deserialisiert eine ModelChoice aus einem JSON-Dict."""
        return cls(
            provider_id=data["provider_id"],
            model_id=data["model_id"],
            model_name=data.get("model_name", ""),
            provider_name=data.get("provider_name", ""),
        )


@dataclass
class ComparisonConfig:
    """Gemeinsame Einstellungen eines Vergleichslaufs.

    Die SOMAS-Parameter (Preset, Perspektive, Tiefe, Sprache, Fragen) gelten
    bewusst für BEIDE Analysen identisch — variiert wird nur das Modell. Das
    hält den Vergleich fair (gleiche Aufgabe, anderes Modell).

    Attributes:
        input_mode: "youtube" | "transcript".
        url: YouTube-URL (bei input_mode == "youtube").
        transcript_title: Titel der Quelle (bei Transkript).
        transcript_author: Autor/Kanal/Sprecher (bei Transkript).
        transcript_text: Der Transkript-Text (bei Transkript).
        is_auto_transcript: True, wenn automatisch transkribiert (STT-Disclaimer).
        preset_name: SOMAS-Preset (Anzeigename, z.B. "Standard").
        perspective: Analyse-Perspektive ("neutral" | "critical" | "empathic").
        depth: Tiefenstufe (1-3).
        language: Analysesprache.
        questions: Optionale Anschlussfragen.
        model_a: Modellauswahl für Analyse A.
        model_b: Modellauswahl für Analyse B.
        model_synth: Modellauswahl für die Synthese (Kurzbeschreibung).
    """

    input_mode: str  # "youtube" | "transcript"
    url: str = ""

    # Transkript-Felder (bei input_mode == "transcript")
    transcript_title: str = ""
    transcript_author: str = ""
    transcript_text: str = ""
    is_auto_transcript: bool = False

    # Gemeinsame SOMAS-Parameter (gelten für BEIDE Analysen identisch)
    preset_name: str = "standard"
    perspective: str = "neutral"
    depth: int = 2
    language: str = "Deutsch"
    questions: str = ""

    # Modellauswahl (vor dem Start vom GUI/Worker gesetzt und validiert)
    model_a: Optional[ModelChoice] = None
    model_b: Optional[ModelChoice] = None
    model_synth: Optional[ModelChoice] = None

    def to_dict(self) -> dict:
        """Serialisiert die Config für JSON-Persistenz.

        API-Keys werden bewusst NICHT serialisiert (Sicherheit) — sie sind hier
        ohnehin nicht enthalten, sondern werden zur Laufzeit aus dem Keyring geholt.
        """
        return {
            "input_mode": self.input_mode,
            "url": self.url,
            "transcript_title": self.transcript_title,
            "transcript_author": self.transcript_author,
            "transcript_text": self.transcript_text,
            "is_auto_transcript": self.is_auto_transcript,
            "preset_name": self.preset_name,
            "perspective": self.perspective,
            "depth": self.depth,
            "language": self.language,
            "questions": self.questions,
            "model_a": self.model_a.to_dict() if self.model_a else None,
            "model_b": self.model_b.to_dict() if self.model_b else None,
            "model_synth": self.model_synth.to_dict() if self.model_synth else None,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ComparisonConfig":
        """Deserialisiert eine ComparisonConfig aus einem JSON-Dict."""

        def _choice(key: str) -> Optional[ModelChoice]:
            raw = data.get(key)
            return ModelChoice.from_dict(raw) if raw else None

        return cls(
            input_mode=data["input_mode"],
            url=data.get("url", ""),
            transcript_title=data.get("transcript_title", ""),
            transcript_author=data.get("transcript_author", ""),
            transcript_text=data.get("transcript_text", ""),
            is_auto_transcript=data.get("is_auto_transcript", False),
            preset_name=data.get("preset_name", "standard"),
            perspective=data.get("perspective", "neutral"),
            depth=data.get("depth", 2),
            language=data.get("language", "Deutsch"),
            questions=data.get("questions", ""),
            model_a=_choice("model_a"),
            model_b=_choice("model_b"),
            model_synth=_choice("model_synth"),
        )


@dataclass
class ComparisonResult:
    """Laufzeit-Zustand eines Vergleichslaufs.

    Attributes:
        config: Die zugrunde liegende ComparisonConfig.
        status: pending|meta|analysis_a|analysis_b|synth|render|done|error.
        video_info: Metadaten nach Auflösung (YouTube) bzw. aus Transkript.
        analysis_a_text: SOMAS-Analysetext von Modell A.
        analysis_b_text: SOMAS-Analysetext von Modell B.
        synthesis_summary: Vom Synthese-Modell erzeugte Kurzbeschreibung.
        final_markdown: Fertig gerendertes Vergleichsdokument.
        tokens_a/tokens_b/tokens_synth: Token-Verbrauch pro Schritt.
        error_message: Fehlermeldung bei status == "error".
        error_step: Schritt, in dem der Fehler auftrat ("meta"|"a"|"b"|"synth").
    """

    config: ComparisonConfig
    status: str = "pending"
    video_info: Optional[VideoInfo] = None
    analysis_a_text: str = ""
    analysis_b_text: str = ""
    synthesis_summary: str = ""
    final_markdown: str = ""

    # Meta pro Schritt (Tokens aus APIResponse)
    tokens_a: int = 0
    tokens_b: int = 0
    tokens_synth: int = 0

    error_message: str = ""
    error_step: str = ""  # "meta" | "a" | "b" | "synth"
