"""OpenAI API Client (GPT + o-Series direkt).

Implementiert den LLM-Client für die OpenAI Chat Completions API.
Statische Modellliste, kein Web-Search.
"""

import logging
from typing import ClassVar

from .api_client import APIResponse, APIStatus, LLMClient

logger = logging.getLogger(__name__)


class OpenAIClient(LLMClient):
    """OpenAI API Client für GPT- und o-Series-Modelle."""

    PROVIDER_ID = "openai"
    PROVIDER_NAME = "OpenAI"

    MODELS: ClassVar[list[dict[str, str]]] = [
        {
            "id": "gpt-4o",
            "name": "GPT-4o",
            "description": "Flagship Multimodal",
        },
        {
            "id": "gpt-4o-mini",
            "name": "GPT-4o mini",
            "description": "Schnell & kostengünstig",
        },
        {
            "id": "o3",
            "name": "o3",
            "description": "Reasoning-Modell - langsam, sehr präzise",
        },
        {
            "id": "o4-mini",
            "name": "o4-mini",
            "description": "Schnelles Reasoning",
        },
    ]

    def __init__(self, api_key: str) -> None:
        """Initialisiert den OpenAI-Client.

        Args:
            api_key: OpenAI API-Key.
        """
        self.api_key = api_key

    def get_available_models(self) -> list[dict]:
        """Gibt Liste der verfügbaren Modelle zurück (statisch)."""
        return self.MODELS

    def send_prompt(self, prompt: str, model: str) -> APIResponse:
        """Sendet Prompt an die OpenAI Chat Completions API.

        Args:
            prompt: Der zu sendende Prompt-Text.
            model: Die Modell-ID (z.B. 'gpt-4o').

        Returns:
            APIResponse mit Status und Inhalt.
        """
        logger.info(f"OpenAI API-Call: model={model}, prompt_len={len(prompt)}")

        try:
            from openai import OpenAI

            client = OpenAI(api_key=self.api_key)

            # o-series Modelle verwenden max_completion_tokens statt max_tokens
            params = {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
            }
            if model.startswith("o"):
                params["max_completion_tokens"] = 4096
            else:
                params["max_tokens"] = 4096

            response = client.chat.completions.create(**params)

            content = response.choices[0].message.content or ""
            tokens_used = response.usage.total_tokens if response.usage else 0

            logger.info(
                f"OpenAI Antwort: {len(content)} Zeichen, "
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
            logger.error("openai SDK nicht installiert")
            return APIResponse(
                status=APIStatus.ERROR,
                error_message="openai SDK nicht installiert. Bitte: pip install openai",
            )
        except Exception as e:
            error_msg = str(e)
            logger.error(f"OpenAI Fehler: {error_msg}")

            if "authentication" in error_msg.lower() or "401" in error_msg:
                error_msg = "Ungültiger API-Key. Bitte in den Einstellungen prüfen."
            elif "rate_limit" in error_msg.lower() or "429" in error_msg:
                error_msg = "Rate Limit erreicht. Bitte kurz warten."

            return APIResponse(
                status=APIStatus.ERROR,
                error_message=f"OpenAI Fehler: {error_msg}",
            )

    def validate_key(self) -> bool:
        """Prüft ob der API-Key gültig ist (kostenlos via models.list)."""
        try:
            from openai import OpenAI

            client = OpenAI(api_key=self.api_key)
            client.models.list()
            return True
        except Exception:
            return False
