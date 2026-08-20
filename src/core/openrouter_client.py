"""OpenRouter API Client.

Implementiert den LLM-Client für die OpenRouter API.
OpenRouter bietet Zugang zu 200+ Modellen über eine einheitliche API.
Unterstützt dynamisches Laden der Modell-Liste via /models Endpoint.
"""

import logging
from typing import ClassVar, Optional

import requests

from .api_client import APIResponse, APIStatus, LLMClient

logger = logging.getLogger(__name__)

# v0.14.2: Eigener Default-Budget für normale (nicht-Stage) OpenRouter-Calls —
# also Analyse UND (klassische) Verifikation, alles was mit `max_tokens=None`
# reinkommt. DeepSeek V4 raisont invers zur Prompt-Größe: bei kleinem Prompt
# 6–8k+ Reasoning → das alte 8192er-Budget (`DEFAULT_MAX_TOKENS`) platzte mitten
# im sichtbaren Content (`finish_reason=length`, Realtests 2026-08-20). 32768 gibt
# der finalen Analyse Luft, auch wenn der Host `exclude`/Cap ignoriert; die
# Sicherheitsnetze (v0.11-Gate + Retry, Struktur-Validator, Phase-17-Eskalation)
# bleiben. Reasoning des Analyse-Calls wird bewusst NICHT gecappt (erwünscht).
#
# NICHT zu verwechseln mit `factcheck_plus_worker.STAGE_MAX_TOKENS_OPENROUTER`
# (v0.13.3, gleicher Wert 32768): das ist das explizite Stufen-Budget an der
# Qt↔Package-Naht — andere Schicht, andere Bedeutung. Stage-Calls übergeben
# `max_tokens` explizit; dieser Default hier greift nur bei `max_tokens is None`.
OPENROUTER_DEFAULT_MAX_TOKENS = 32768


class OpenRouterClient(LLMClient):
    """OpenRouter API Client."""

    BASE_URL = "https://openrouter.ai/api/v1"
    PROVIDER_ID = "openrouter"
    PROVIDER_NAME = "OpenRouter"

    # v0.13.2: Reasoning-Cap für strukturierte Stage-Calls (Faktencheck Plus).
    # DeepSeek V4 Pro reasonte bei der JSON-Extraktion ~14,7k Tokens (durch
    # `exclude: true` unsichtbar, zählt aber voll gegen `max_tokens`) → trotz
    # 16384-Budget `finish_reason=length`, kein verwertbarer Output. Ein Effort-Cap
    # deckelt das Reasoning für Stage-Calls.
    #
    # BEWUSST `effort` statt `max_tokens`: Das reale Zielmodell DeepSeek V4 ist auf
    # OpenRouter effort-gesteuert (Issue earendil-works/pi#4055). Die
    # effort→Budget-Normalisierung ist die dokumentierte Richtung; die
    # `max_tokens`→effort-Rückabbildung nur vage. `"max"` gemieden (bekannter
    # Mapping-Bug); `"low"` ist ein valider normalisierter Enum-Wert und liegt für
    # token-basierte Familien (0.2 × max_tokens ≈ 3,3k) über Anthropics 1024-Minimum.
    # Kombinierbar mit `exclude` (laut Doku orthogonal).
    REASONING_CAP_EFFORT = "low"

    # Fallback-Modelle falls /models nicht erreichbar (Stand Januar 2026)
    FALLBACK_MODELS: ClassVar[list[dict]] = [
        {
            "id": "anthropic/claude-sonnet-4.5",
            "name": "Claude Sonnet 4.5",
            "description": "Anthropic's beliebtestes Modell",
            "context_length": 200000,
            "pricing_prompt": "0.000003",
            "pricing_completion": "0.000015",
        },
        {
            "id": "anthropic/claude-opus-4.5",
            "name": "Claude Opus 4.5",
            "description": "Frontier Reasoning & Coding",
            "context_length": 200000,
            "pricing_prompt": "0.000015",
            "pricing_completion": "0.000075",
        },
        {
            "id": "anthropic/claude-3.5-haiku",
            "name": "Claude 3.5 Haiku",
            "description": "Schnell und günstig",
            "context_length": 200000,
            "pricing_prompt": "0.0000008",
            "pricing_completion": "0.000004",
        },
        {
            "id": "google/gemini-2.5-pro",
            "name": "Gemini 2.5 Pro",
            "description": "Google's stärkstes Modell",
            "context_length": 1000000,
            "pricing_prompt": "0.00000125",
            "pricing_completion": "0.00001",
        },
        {
            "id": "google/gemini-2.5-flash-lite",
            "name": "Gemini 2.5 Flash Lite",
            "description": "Google Budget-Option",
            "context_length": 1000000,
            "pricing_prompt": "0",
            "pricing_completion": "0",
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
                    pricing = m.get("pricing", {})
                    models.append({
                        "id": model_id,
                        "name": model_name,
                        "description": self._format_model_description(m),
                        "context_length": m.get("context_length", 0),
                        "pricing_prompt": str(pricing.get("prompt") or "0"),
                        "pricing_completion": str(pricing.get("completion") or "0"),
                    })

                if models:
                    self._cached_models = models
                    logger.info(f"OpenRouter: {len(models)} Modelle geladen")
                    return models

        except Exception as e:
            logger.warning(f"OpenRouter /models Fehler: {e}, nutze Fallback")

        logger.info("OpenRouter: Verwende Fallback-Modelle")
        return self.FALLBACK_MODELS

    def send_prompt(
        self, prompt: str, model: str, max_tokens: int | None = None,
        cap_reasoning: bool = False,
    ) -> APIResponse:
        """Sendet Prompt an OpenRouter API.

        Args:
            prompt: Der zu sendende Prompt-Text.
            model: Die Modell-ID (z.B. 'anthropic/claude-3-haiku').
            max_tokens: Optionale Obergrenze für die Antwortlänge. ``None``
                (normaler Analyse-/Verifikations-Call) → :data:`OPENROUTER_DEFAULT_MAX_TOKENS`
                (32768, v0.14.2); explizite Werte (Stage-Calls) bleiben unangetastet.
            cap_reasoning: Wenn ``True``, wird das Reasoning zusätzlich per
                Effort-Cap gedeckelt (:data:`REASONING_CAP_EFFORT`) — nur für
                strukturierte Stage-Calls, nicht für die normale Analyse (dort ist
                Reasoning erwünscht). Einziger Consumer dieses Flags: OpenRouter.

        Returns:
            APIResponse mit Status und Inhalt.
        """
        logger.info(f"OpenRouter API-Call: model={model}, prompt_len={len(prompt)}")
        # v0.14.2: normaler Call (max_tokens is None) → OpenRouter-eigener 32768-
        # Default statt 8192; explizite Stage-Werte 1:1 respektieren.
        tokens_cap = (
            OPENROUTER_DEFAULT_MAX_TOKENS if max_tokens is None else max_tokens
        )

        # v0.11.0 (Reasoning-Leak-Härtung, stärkster Hebel): Das Modell reasont
        # weiterhin INTERN (Qualität bleibt), gibt die Reasoning-Tokens aber NICHT
        # zurück. Verhindert, dass manche Upstream-Backends das Reasoning inline in
        # `content` serialisieren, das Token-Budget auffressen und die finale
        # Analyse abschneiden (realer Iran-DeepSeek-Fall 2026-07-01). Nur OpenRouter
        # — andere Provider haben eigene Reasoning-Semantik und bleiben unangetastet.
        reasoning: dict = {"exclude": True}
        # v0.13.2: Für Stage-Calls zusätzlich das Reasoning-Budget kappen (s.
        # REASONING_CAP_EFFORT). `exclude` bleibt orthogonal aktiv.
        if cap_reasoning:
            reasoning["effort"] = self.REASONING_CAP_EFFORT

        try:
            response = requests.post(
                f"{self.BASE_URL}/chat/completions",
                headers=self.headers,
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    # max_tokens setzen, sonst rechnet OpenRouter mit dem vollen
                    # Context-Window als Worst-Case und blockt bei moderatem
                    # Guthaben mit HTTP 402.
                    "max_tokens": tokens_cap,
                    "reasoning": reasoning,
                },
                timeout=120,
            )

            if response.status_code == 200:
                data = response.json()
                try:
                    choice = data["choices"][0]
                    message = choice.get("message", {}) or {}
                    finish_reason = choice.get("finish_reason")
                except (KeyError, IndexError, TypeError) as e:
                    logger.error(f"Unerwartete API-Antwort-Struktur: {e}")
                    return APIResponse(
                        status=APIStatus.ERROR,
                        error_message=f"Unerwartete API-Antwort: {e}",
                    )

                # content kann fehlen oder None sein; manche (Reasoning-)Modelle
                # liefern den Text stattdessen im Feld 'reasoning'.
                # v0.11.0: Mit reasoning.exclude=true (s. Request-Body) sollte
                # 'reasoning' im Normalfall leer sein; bleibt dann auch 'content'
                # leer, greift unten der Leer-Guard → sauberer Fehler statt
                # Reasoning-Müll. Der 'reasoning'-Fallback bleibt nur als Notnagel
                # für Backends, die exclude ignorieren; solche Fälle fängt zusätzlich
                # der finish_reason-Gate (PR 3) bzw. der Struktur-Validator (PR 5) ab.
                content = message.get("content") or message.get("reasoning")

                # v0.13.3: Token-Split fürs Debug-Log. OpenRouter (OpenAI-kompatibel)
                # liefert usage immer mit: prompt_tokens/completion_tokens/total_tokens
                # + optional completion_tokens_details.reasoning_tokens (gegen die
                # Live-Doku „Usage Accounting" geprüft). v0.14.2: VOR der Leer-Prüfung
                # extrahiert, damit auch der Leer-Inhalt-Fehlerpfad belegt, WOHIN das
                # Budget ging (typisch: Reasoning) — genau dort standen die Felder
                # bisher auf 0.
                usage = data.get("usage") or {}
                tokens = usage.get("total_tokens", 0)
                reasoning_tokens = (
                    usage.get("completion_tokens_details") or {}
                ).get("reasoning_tokens")

                # Leerer/fehlender Inhalt: sauber als Fehler melden statt bei
                # len(content) zu crashen (NoneType has no len()).
                if not content or not content.strip():
                    logger.error(
                        f"OpenRouter: leerer Inhalt (finish_reason={finish_reason})"
                    )
                    return self._build_empty_content_response(
                        "finish_reason", finish_reason,
                        tokens_input=usage.get("prompt_tokens", 0),
                        tokens_output=usage.get("completion_tokens", 0),
                        tokens_used=tokens,
                        reasoning_tokens=reasoning_tokens,
                    )

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
                    tokens_input=usage.get("prompt_tokens", 0),
                    tokens_output=usage.get("completion_tokens", 0),
                    reasoning_tokens=reasoning_tokens,
                    finish_reason=self._normalize_finish_reason(finish_reason),
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
