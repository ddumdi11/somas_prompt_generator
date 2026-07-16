"""Anthropic API Client (Claude-Modelle direkt).

Implementiert den LLM-Client für die Anthropic Messages API.
Statische Modellliste, kein Web-Search.
"""

import logging
from typing import ClassVar

from .api_client import DEFAULT_MAX_TOKENS, APIResponse, APIStatus, LLMClient

logger = logging.getLogger(__name__)


class AnthropicClient(LLMClient):
    """Anthropic API Client für Claude-Modelle."""

    PROVIDER_ID = "anthropic"
    PROVIDER_NAME = "Anthropic"

    MODELS: ClassVar[list[dict[str, str]]] = [
        {
            "id": "claude-fable-5",
            "name": "Claude Fable 5",
            "description": "Flaggschiff – höchste Leistung, langsam & am teuersten",
        },
        {
            "id": "claude-opus-4-8",
            "name": "Claude Opus 4.8",
            "description": "Sehr leistungsstark – komplexe Analysen",
        },
        {
            "id": "claude-sonnet-5",
            "name": "Claude Sonnet 5",
            "description": "Neu – beste Balance aus Tempo und Intelligenz",
        },
        {
            "id": "claude-sonnet-4-6",
            "name": "Claude Sonnet 4.6",
            "description": "Balanciert – bewährt/empfohlen für SOMAS (Default)",
        },
        {
            "id": "claude-opus-4-6",
            "name": "Claude Opus 4.6",
            "description": "Stark – bisheriges Flaggschiff (Vorgänger)",
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

    def send_prompt(
        self, prompt: str, model: str, max_tokens: int | None = None
    ) -> APIResponse:
        """Sendet Prompt an die Anthropic Messages API.

        Args:
            prompt: Der zu sendende Prompt-Text.
            model: Die Modell-ID (z.B. 'claude-sonnet-4-6').
            max_tokens: Optionale Obergrenze für die Antwortlänge
                (``None`` → :data:`DEFAULT_MAX_TOKENS`).

        Returns:
            APIResponse mit Status und Inhalt.
        """
        logger.info(f"Anthropic API-Call: model={model}, prompt_len={len(prompt)}")
        tokens_cap = DEFAULT_MAX_TOKENS if max_tokens is None else max_tokens

        try:
            import anthropic

            client = anthropic.Anthropic(api_key=self.api_key)
            message = client.messages.create(
                model=model,
                max_tokens=tokens_cap,
                messages=[{"role": "user", "content": prompt}],
            )

            # Robust: nur TextBlocks extrahieren, leere Antworten abfangen
            content = ""
            if message.content:
                text_parts = [
                    block.text for block in message.content
                    if hasattr(block, "text") and block.text
                ]
                content = "\n".join(text_parts)

            stop_reason = getattr(message, "stop_reason", None)

            # Leerer Inhalt: sauber als Fehler melden (im Vergleich nicht
            # weiterverarbeiten, statt ein leeres "Erfolgs"-Ergebnis zu liefern).
            if not content.strip():
                logger.error(
                    f"Anthropic: leerer Inhalt (stop_reason={stop_reason})"
                )
                return self._build_empty_content_response(
                    "stop_reason", stop_reason, {"max_tokens": "length"}
                )

            tokens_used = 0
            if message.usage:
                tokens_used = (
                    getattr(message.usage, "input_tokens", 0)
                    + getattr(message.usage, "output_tokens", 0)
                )

            # v0.11.0: stop_reason durchreichen. Anthropic nennt Trunkierung
            # "max_tokens" — auf das providerübergreifende "length" normalisieren,
            # damit der finish_reason-Gate einheitlich greift.
            finish_reason = self._normalize_finish_reason(
                stop_reason, {"max_tokens": "length"}
            )

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
                finish_reason=finish_reason,
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
