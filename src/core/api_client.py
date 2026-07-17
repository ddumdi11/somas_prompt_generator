"""Abstrakte Basis-Klasse für LLM-API-Clients.

Definiert das Interface, das alle Provider-Implementierungen
(Perplexity, OpenRouter, etc.) einhalten müssen.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum

# Standard-Obergrenze für die Antwortlänge aller Provider. Explizit gesetzt, damit
# OpenRouter/Perplexity nicht das volle Context-Window als Worst-Case reservieren
# (führte zu HTTP 402). Großzügig genug, dass lange Verifikations-/Analyse-Antworten
# nicht abgeschnitten werden, aber weit unter dem vollen Window.
DEFAULT_MAX_TOKENS = 8192


class APIStatus(Enum):
    """Status eines API-Aufrufs."""
    IDLE = "idle"
    SENDING = "sending"
    PROCESSING = "processing"
    RECEIVED = "received"
    ERROR = "error"


# Einheitliche Leer-Inhalt-Fehlermeldung (alle 4 Clients). Der Präfix ist das
# Routing-Signal: HTTP 200 erreicht das Modell, aber der sichtbare Content war leer
# (typisch: Reasoning verbrennt das Token-Budget). Das ist derselbe Fehlermodus wie
# eine Trunkierung → in main_window durchläuft es den Retry-/Eskalationspfad, NICHT
# den harten Fehlerdialog. Muss daher wortgleich über alle Clients bleiben.
EMPTY_CONTENT_ERROR_PREFIX = "Modell lieferte leeren Inhalt"


def build_empty_content_error(reason_label: str, reason_value: object) -> str:
    """Baut die einheitliche Leer-Inhalt-Fehlermeldung.

    Args:
        reason_label: ``"finish_reason"`` oder ``"stop_reason"`` (provider-abhängig).
        reason_value: Der zugehörige Wert (kann ``None`` sein).

    Returns:
        Fehlermeldung mit stabilem Präfix, z.B.
        ``"Modell lieferte leeren Inhalt (finish_reason=length)"``.
    """
    return f"{EMPTY_CONTENT_ERROR_PREFIX} ({reason_label}={reason_value})"


def is_empty_content_error(message: str) -> bool:
    """Erkennt die einheitliche Leer-Inhalt-Fehlermeldung aller Clients.

    Routing-Signal für main_window: ``True`` → retrybarer Leer-Inhalt (wie
    Trunkierung), ``False`` → harter Transport-/Auth-/HTTP-Fehler.

    Args:
        message: Der ``error_message``-Text einer :class:`APIResponse`.

    Returns:
        True, wenn es sich um den Leer-Inhalt-Fehlermodus handelt.
    """
    return bool(message) and message.strip().startswith(EMPTY_CONTENT_ERROR_PREFIX)


# Finish-Reasons, die eine bei max_tokens abgeschnittene (trunkierte) Antwort
# signalisieren. Zentral hier definiert (v0.13.1), damit der GUI-Analysepfad
# (main_window) und die Faktencheck-Plus-Stufen (llm_stage) denselben
# Trunkierungs-Gate verwenden und nicht auseinanderdriften. Anthropic normalisiert
# "max_tokens" → "length" schon im Client; die übrigen Varianten bleiben defensiv
# erfasst.
TRUNCATION_FINISH_REASONS = frozenset({"length", "max_tokens", "truncated"})


def is_truncated_finish_reason(finish_reason: str) -> bool:
    """Erkennt einen finish_reason, der eine abgeschnittene Antwort anzeigt.

    Args:
        finish_reason: Der von der API gemeldete Stopp-Grund (kann leer sein).

    Returns:
        True, wenn die Antwort bei der Token-Grenze trunkiert wurde.
    """
    return (
        bool(finish_reason)
        and finish_reason.strip().lower() in TRUNCATION_FINISH_REASONS
    )


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
    duration_seconds: float = 0.0
    # v0.11.0: Warum das Modell gestoppt hat (z.B. "stop", "length", "max_tokens").
    # "length"/"max_tokens"/"truncated" signalisieren eine abgeschnittene Antwort
    # (Trunkierung) und werden im Antwort-Handling als harter Gate ausgewertet.
    finish_reason: str = ""
    # Tatsächlicher HTTP-Status des Roh-Requests (None = nicht bekannt/SDK-Pfad).
    # Ein Leer-Inhalt-Fehler trägt hier 200 (HTTP war OK, nur der Content leer) —
    # der Worker loggt diesen echten Status statt eines Default-500.
    http_status: int | None = None


class LLMClient(ABC):
    """Abstrakte Basis-Klasse für LLM-API-Clients.

    Jeder Provider (Perplexity, OpenRouter, ...) implementiert
    diese Klasse mit seiner spezifischen API-Logik.
    """

    PROVIDER_ID: str = ""
    PROVIDER_NAME: str = ""

    @staticmethod
    def _normalize_finish_reason(
        raw: str | None, extra_map: dict[str, str] | None = None
    ) -> str:
        """Normalisiert den provider-spezifischen Stopp-Grund einheitlich.

        Zentralisiert das ``raw or ""`` sowie provider-spezifische Aliasse, damit
        der Trunkierungs-Gate (:data:`TRUNCATION_FINISH_REASONS`) über alle
        Clients konsistente Werte bekommt.

        Args:
            raw: Roher finish_reason/stop_reason (kann None sein).
            extra_map: Optionale Aliasse, z.B. ``{"max_tokens": "length"}``
                für Anthropic.

        Returns:
            Bereinigter finish_reason ("" wenn nicht vorhanden).
        """
        value = (raw or "").strip()
        if extra_map and value in extra_map:
            return extra_map[value]
        return value

    def _build_empty_content_response(
        self, reason_label: str, reason_value: str | None,
        extra_map: dict[str, str] | None = None,
    ) -> "APIResponse":
        """Baut die einheitliche Leer-Inhalt-Fehlerantwort für alle Clients.

        Kapselt den identischen Block (Meldung, normalisierter finish_reason,
        ``http_status=200``), damit HTTP 200 + leerer Content über alle Provider
        konsistent als retrybarer Leer-Inhalt-Fehlermodus gemeldet wird (siehe
        :func:`is_empty_content_error`).

        Args:
            reason_label: ``"finish_reason"`` oder ``"stop_reason"`` (provider-abhängig).
            reason_value: Der rohe Stopp-Grund (kann ``None`` sein).
            extra_map: Optionale Aliasse für :meth:`_normalize_finish_reason`
                (z.B. ``{"max_tokens": "length"}`` bei Anthropic).

        Returns:
            Die fertige :class:`APIResponse` mit Status ERROR.
        """
        return APIResponse(
            status=APIStatus.ERROR,
            error_message=build_empty_content_error(reason_label, reason_value),
            finish_reason=self._normalize_finish_reason(reason_value, extra_map),
            http_status=200,
        )

    @abstractmethod
    def get_available_models(self) -> list[dict]:
        """Gibt Liste der verfügbaren Modelle zurück.

        Returns:
            Liste von Dicts mit mindestens 'id', 'name', 'description'.
        """

    @abstractmethod
    def send_prompt(
        self, prompt: str, model: str, max_tokens: int | None = None,
        cap_reasoning: bool = False,
    ) -> APIResponse:
        """Sendet einen Prompt an die API und gibt die Antwort zurück.

        Args:
            prompt: Der zu sendende Prompt-Text.
            model: Die Modell-ID (z.B. 'sonar-pro').
            max_tokens: Optionale Obergrenze für die Antwortlänge. ``None`` →
                :data:`DEFAULT_MAX_TOKENS`. Höhere Werte kommen nur aus den
                Faktencheck-Plus-Stufen (``llm_stage.STAGE_MAX_TOKENS``), NICHT
                global — OpenRouter/Perplexity pre-authen gegen ``max_tokens``
                (HTTP 402, v0.10.1).
            cap_reasoning: Bittet um ein gedeckeltes Reasoning-Budget für
                strukturierte Stage-Calls (v0.13.2). **Nur OpenRouter** wertet das
                Flag aus (Effort-Cap); die anderen Clients ignorieren es
                dokumentiert — sie kennen kein providerübergreifendes
                Reasoning-Steuer-Feld. Default ``False`` = heutiges Verhalten.

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


def create_client(provider_id: str, api_key: str) -> LLMClient:
    """Erstellt den passenden API-Client für einen Provider.

    Zentrale Factory, die von BatchWorker und ComparisonWorker gemeinsam
    genutzt wird. Die konkreten Client-Klassen werden lazy importiert, um
    Import-Zyklen und unnötige Abhängigkeiten zu vermeiden.

    Args:
        provider_id: Provider-ID (perplexity, openrouter, anthropic, openai).
        api_key: API-Key.

    Returns:
        LLMClient-Instanz.

    Raises:
        ValueError: Bei unbekanntem Provider.
    """
    if provider_id == "perplexity":
        from .perplexity_client import PerplexityClient
        return PerplexityClient(api_key)
    elif provider_id == "openrouter":
        from .openrouter_client import OpenRouterClient
        return OpenRouterClient(api_key)
    elif provider_id == "anthropic":
        from .anthropic_client import AnthropicClient
        return AnthropicClient(api_key)
    elif provider_id == "openai":
        from .openai_client import OpenAIClient
        return OpenAIClient(api_key)
    else:
        raise ValueError(f"Unbekannter Provider: {provider_id}")
