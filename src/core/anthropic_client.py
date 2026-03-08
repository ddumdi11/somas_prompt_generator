"""Anthropic API Client (Claude-Modelle direkt).

Implementiert den LLM-Client für die Anthropic Messages API.
Statische Modellliste, kein Web-Search.
"""

import logging
from typing import ClassVar

from .api_client import APIResponse, APIStatus, LLMClient

logger = logging.getLogger(__name__)


class AnthropicClient(LLMClient):
    """Anthropic API Client für Claude-Modelle."""

    PROVIDER_ID = "anthropic"
    PROVIDER_NAME = "Anthropic"

    MODELS: ClassVar[list[dict[str, str]]] = [
        {
            "id": "claude-opus-4-6",
            "name": "Claude Opus 4.6",
            "description": "Leistungsstärkstes Modell – komplex, langsam",
        },
        {
            "id": "claude-sonnet-4-6",
            "name": "Claude Sonnet 4.6",
            "description": "Balanciert – empfohlen für SOMAS",
        },
        {
            "id": "claude-haiku-4-5-20251001",
            "name": "Claude Haiku 4.5",
            "description": "Schnell & günstig – für kurze Inhalte",
        },
    ]

    def __init__(self, api_key: str) -> None:
        """Initialisiert den Anthropic-Client.

        Args:
            api_key: Anthropic API-Key.
        """
        self.api_key = api_key

    def get_available_models(self) -> list[dict]:
        """Gibt Liste der verfügbaren Modelle zurück (statisch)."""
        return self.MODELS

    def send_prompt(self, prompt: str, model: str) -> APIResponse:
        """Sendet Prompt an die Anthropic Messages API.

        Args:
            prompt: Der zu sendende Prompt-Text.
            model: Die Modell-ID (z.B. 'claude-sonnet-4-6').

        Returns:
            APIResponse mit Status und Inhalt.
        """
        logger.info(f"Anthropic API-Call: model={model}, prompt_len={len(prompt)}")

        try:
            import anthropic

            client = anthropic.Anthropic(api_key=self.api_key)
            message = client.messages.create(
                model=model,
                max_tokens=4096,
                messages=[{"role": "user", "content": prompt}],
            )

            content = message.content[0].text
            tokens_used = message.usage.input_tokens + message.usage.output_tokens

            logger.info(
                f"Anthropic Antwort: {len(content)} Zeichen, "
                f"{tokens_used} Tokens"
            )

            return APIResponse(
                status=APIStatus.RECEIVED,
                content=content,
                model_used=model,
                provider_used=self.PROVIDER_NAME,
                tokens_used=tokens_used,
            )

        except ImportError:
            logger.error("anthropic SDK nicht installiert")
            return APIResponse(
                status=APIStatus.ERROR,
                error_message="anthropic SDK nicht installiert. Bitte: pip install anthropic",
            )
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Anthropic Fehler: {error_msg}")

            if "authentication" in error_msg.lower() or "401" in error_msg:
                error_msg = "Ungültiger API-Key. Bitte in den Einstellungen prüfen."
            elif "rate_limit" in error_msg.lower() or "429" in error_msg:
                error_msg = "Rate Limit erreicht. Bitte kurz warten."

            return APIResponse(
                status=APIStatus.ERROR,
                error_message=f"Anthropic Fehler: {error_msg}",
            )

    def validate_key(self) -> bool:
        """Prüft ob der API-Key gültig ist."""
        try:
            import anthropic

            client = anthropic.Anthropic(api_key=self.api_key)
            client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=10,
                messages=[{"role": "user", "content": "Hi"}],
            )
            return True
        except Exception:
            return False
