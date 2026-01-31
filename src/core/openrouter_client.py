"""OpenRouter API Client.

Implementiert den LLM-Client für die OpenRouter API.
OpenRouter bietet Zugang zu 200+ Modellen über eine einheitliche API.
Unterstützt dynamisches Laden der Modell-Liste via /models Endpoint.
"""

import logging
from typing import Optional

import requests

from .api_client import APIResponse, APIStatus, LLMClient

logger = logging.getLogger(__name__)


class OpenRouterClient(LLMClient):
    """OpenRouter API Client."""

    BASE_URL = "https://openrouter.ai/api/v1"
    PROVIDER_ID = "openrouter"
    PROVIDER_NAME = "OpenRouter"

    # Fallback-Modelle falls /models nicht erreichbar (Stand Januar 2026)
    FALLBACK_MODELS = [
        {
            "id": "anthropic/claude-sonnet-4.5",
            "name": "Claude Sonnet 4.5",
            "description": "Anthropic's beliebtestes Modell",
        },
        {
            "id": "anthropic/claude-opus-4.5",
            "name": "Claude Opus 4.5",
            "description": "Frontier Reasoning & Coding",
        },
        {
            "id": "anthropic/claude-3.5-haiku",
            "name": "Claude 3.5 Haiku",
            "description": "Schnell und günstig",
        },
        {
            "id": "google/gemini-2.5-flash-preview",
            "name": "Gemini 2.5 Flash",
            "description": "Google's schnellstes Modell",
        },
        {
            "id": "google/gemini-2.0-flash",
            "name": "Gemini 2.0 Flash",
            "description": "Google Budget-Option",
        },
    ]

    def __init__(self, api_key: str) -> None:
        """Initialisiert den OpenRouter-Client.

        Args:
            api_key: OpenRouter API-Key.
        """
        self.api_key = api_key
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "X-Title": "SOMAS Prompt Generator",
        }
        self._cached_models: Optional[list[dict]] = None

    def get_available_models(self) -> list[dict]:
        """Gibt Liste der verfügbaren Modelle zurück.

        Versucht dynamisch von /models zu laden, fällt auf
        FALLBACK_MODELS zurück bei Fehler.
        """
        if self._cached_models is not None:
            return self._cached_models

        try:
            response = requests.get(
                f"{self.BASE_URL}/models",
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=15,
            )

            if response.status_code == 200:
                data = response.json()
                models = []
                for m in data.get("data", []):
                    model_id = m.get("id", "")
                    model_name = m.get("name", model_id)
                    models.append({
                        "id": model_id,
                        "name": model_name,
                        "description": self._format_model_description(m),
                    })

                if models:
                    self._cached_models = models
                    logger.info(f"OpenRouter: {len(models)} Modelle geladen")
                    return models

        except Exception as e:
            logger.warning(f"OpenRouter /models Fehler: {e}, nutze Fallback")

        logger.info("OpenRouter: Verwende Fallback-Modelle")
        return self.FALLBACK_MODELS

    def send_prompt(self, prompt: str, model: str) -> APIResponse:
        """Sendet Prompt an OpenRouter API.

        Args:
            prompt: Der zu sendende Prompt-Text.
            model: Die Modell-ID (z.B. 'anthropic/claude-3-haiku').

        Returns:
            APIResponse mit Status und Inhalt.
        """
        logger.info(f"OpenRouter API-Call: model={model}, prompt_len={len(prompt)}")

        try:
            response = requests.post(
                f"{self.BASE_URL}/chat/completions",
                headers=self.headers,
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                },
                timeout=120,
            )

            if response.status_code == 200:
                data = response.json()
                try:
                    content = data["choices"][0]["message"]["content"]
                except (KeyError, IndexError, TypeError) as e:
                    logger.error(f"Unerwartete API-Antwort-Struktur: {e}")
                    return APIResponse(
                        status=APIStatus.ERROR,
                        error_message=f"Unerwartete API-Antwort: {e}",
                    )
                tokens = data.get("usage", {}).get("total_tokens", 0)

                logger.info(
                    f"OpenRouter Antwort: {len(content)} Zeichen, "
                    f"{tokens} Tokens"
                )

                return APIResponse(
                    status=APIStatus.RECEIVED,
                    content=content,
                    model_used=model,
                    provider_used=self.PROVIDER_NAME,
                    tokens_used=tokens,
                )

            logger.error(f"OpenRouter HTTP {response.status_code}: {response.text}")
            return APIResponse(
                status=APIStatus.ERROR,
                error_message=f"HTTP {response.status_code}: {response.text[:200]}",
            )

        except requests.Timeout:
            logger.error("OpenRouter Timeout nach 120 Sekunden")
            return APIResponse(
                status=APIStatus.ERROR,
                error_message="Timeout: API antwortet nicht innerhalb von 2 Minuten",
            )
        except requests.ConnectionError:
            logger.error("OpenRouter Verbindungsfehler")
            return APIResponse(
                status=APIStatus.ERROR,
                error_message="Verbindungsfehler: Keine Internetverbindung oder API nicht erreichbar",
            )
        except Exception as e:
            logger.error(f"OpenRouter unerwarteter Fehler: {e}")
            return APIResponse(
                status=APIStatus.ERROR,
                error_message=f"Unerwarteter Fehler: {e}",
            )

    def validate_key(self) -> bool:
        """Prüft ob der API-Key gültig ist.

        Ruft /models Endpoint auf, da dies keinen Credit verbraucht.
        """
        try:
            response = requests.get(
                f"{self.BASE_URL}/models",
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=15,
            )
            return response.status_code == 200
        except Exception:
            return False

    @staticmethod
    def _format_model_description(model_data: dict) -> str:
        """Formatiert eine Modell-Beschreibung aus API-Daten."""
        parts = []

        context = model_data.get("context_length")
        if context:
            if context >= 1_000_000:
                parts.append(f"{context // 1_000_000}M ctx")
            elif context >= 1000:
                parts.append(f"{context // 1000}k ctx")

        pricing = model_data.get("pricing", {})
        prompt_price = pricing.get("prompt")
        if prompt_price:
            try:
                price_float = float(prompt_price)
                if price_float == 0:
                    parts.append("kostenlos")
                elif price_float < 0.001:
                    parts.append(f"${price_float:.6f}/tok")
                else:
                    parts.append(f"${price_float:.4f}/tok")
            except (ValueError, TypeError):
                pass

        return ", ".join(parts) if parts else ""
