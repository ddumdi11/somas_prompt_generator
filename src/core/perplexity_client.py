"""Perplexity AI API Client.

Implementiert den LLM-Client für die Perplexity Sonar API.
Perplexity hat keinen /models Endpoint, daher sind die Modelle hardcoded.
"""

import logging

import requests

from .api_client import APIResponse, APIStatus, LLMClient

logger = logging.getLogger(__name__)


class PerplexityClient(LLMClient):
    """Perplexity AI API Client."""

    BASE_URL = "https://api.perplexity.ai"
    PROVIDER_ID = "perplexity"
    PROVIDER_NAME = "Perplexity AI"

    # Aktuelle Modellnamen (Stand Januar 2026)
    MODELS = [
        {
            "id": "sonar",
            "name": "Sonar",
            "description": "Balanced - Geschwindigkeit & Kosten",
        },
        {
            "id": "sonar-pro",
            "name": "Sonar Pro",
            "description": "Best für komplexe Queries (empfohlen für SOMAS)",
        },
        {
            "id": "sonar-reasoning",
            "name": "Sonar Reasoning",
            "description": "Spezialisiert für Reasoning-Tasks",
        },
    ]

    def __init__(self, api_key: str) -> None:
        """Initialisiert den Perplexity-Client.

        Args:
            api_key: Perplexity API-Key.
        """
        self.api_key = api_key
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    def get_available_models(self) -> list[dict]:
        """Gibt Liste der verfügbaren Modelle zurück.

        Perplexity hat keinen /models Endpoint, daher hardcoded.
        """
        return self.MODELS

    def send_prompt(self, prompt: str, model: str) -> APIResponse:
        """Sendet Prompt an Perplexity API.

        Args:
            prompt: Der zu sendende Prompt-Text.
            model: Die Modell-ID (z.B. 'sonar-pro').

        Returns:
            APIResponse mit Status und Inhalt.
        """
        logger.info(f"Perplexity API-Call: model={model}, prompt_len={len(prompt)}")

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
                content = data["choices"][0]["message"]["content"]
                tokens = data.get("usage", {}).get("total_tokens", 0)
                citations = data.get("citations", [])

                logger.info(
                    f"Perplexity Antwort: {len(content)} Zeichen, "
                    f"{tokens} Tokens, {len(citations)} Quellen"
                )

                return APIResponse(
                    status=APIStatus.RECEIVED,
                    content=content,
                    model_used=model,
                    provider_used=self.PROVIDER_NAME,
                    tokens_used=tokens,
                    citations=citations,
                )

            logger.error(f"Perplexity HTTP {response.status_code}: {response.text}")
            return APIResponse(
                status=APIStatus.ERROR,
                error_message=f"HTTP {response.status_code}: {response.text[:200]}",
            )

        except requests.Timeout:
            logger.error("Perplexity Timeout nach 120 Sekunden")
            return APIResponse(
                status=APIStatus.ERROR,
                error_message="Timeout: API antwortet nicht innerhalb von 2 Minuten",
            )
        except requests.ConnectionError:
            logger.error("Perplexity Verbindungsfehler")
            return APIResponse(
                status=APIStatus.ERROR,
                error_message="Verbindungsfehler: Keine Internetverbindung oder API nicht erreichbar",
            )
        except Exception as e:
            logger.error(f"Perplexity unerwarteter Fehler: {e}")
            return APIResponse(
                status=APIStatus.ERROR,
                error_message=f"Unerwarteter Fehler: {e}",
            )

    def validate_key(self) -> bool:
        """Prüft ob der API-Key gültig ist.

        Sendet einen minimalen Request an die API.
        """
        try:
            response = requests.post(
                f"{self.BASE_URL}/chat/completions",
                headers=self.headers,
                json={
                    "model": "sonar",
                    "messages": [{"role": "user", "content": "Hi"}],
                },
                timeout=15,
            )
            return response.status_code == 200
        except Exception:
            return False
