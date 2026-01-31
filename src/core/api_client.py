"""Abstrakte Basis-Klasse für LLM-API-Clients.

Definiert das Interface, das alle Provider-Implementierungen
(Perplexity, OpenRouter, etc.) einhalten müssen.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum


class APIStatus(Enum):
    """Status eines API-Aufrufs."""
    IDLE = "idle"
    SENDING = "sending"
    PROCESSING = "processing"
    RECEIVED = "received"
    ERROR = "error"


@dataclass
class APIResponse:
    """Antwort eines LLM-API-Aufrufs."""
    status: APIStatus
    content: str = ""
    error_message: str = ""
    model_used: str = ""
    provider_used: str = ""
    tokens_used: int = 0
    citations: list[str] = field(default_factory=list)


class LLMClient(ABC):
    """Abstrakte Basis-Klasse für LLM-API-Clients.

    Jeder Provider (Perplexity, OpenRouter, ...) implementiert
    diese Klasse mit seiner spezifischen API-Logik.
    """

    PROVIDER_ID: str = ""
    PROVIDER_NAME: str = ""

    @abstractmethod
    def get_available_models(self) -> list[dict]:
        """Gibt Liste der verfügbaren Modelle zurück.

        Returns:
            Liste von Dicts mit mindestens 'id', 'name', 'description'.
        """

    @abstractmethod
    def send_prompt(self, prompt: str, model: str) -> APIResponse:
        """Sendet einen Prompt an die API und gibt die Antwort zurück.

        Args:
            prompt: Der zu sendende Prompt-Text.
            model: Die Modell-ID (z.B. 'sonar-pro').

        Returns:
            APIResponse mit Status und Inhalt.
        """

    def validate_key(self) -> bool:
        """Prüft ob der API-Key gültig ist.

        Default-Implementierung: Versucht Modell-Liste abzurufen.
        Provider können dies überschreiben.

        Returns:
            True wenn der Key gültig ist.
        """
        try:
            models = self.get_available_models()
            return len(models) > 0
        except Exception:
            return False
