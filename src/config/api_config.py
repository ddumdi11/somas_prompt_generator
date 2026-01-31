"""API-Konfiguration: Provider-Definitionen, Key-Verwaltung, User-Preferences.

Trennt sensible Daten (API-Keys via keyring) von öffentlicher Config (JSON).
"""

import json
import logging
from dataclasses import dataclass
from pathlib import Path

import keyring

logger = logging.getLogger(__name__)

SERVICE_NAME = "somas_prompt_generator"

# Pfade
_CONFIG_DIR = Path(__file__).parent
_PROVIDERS_FILE = _CONFIG_DIR / "api_providers.json"
_PREFERENCES_FILE = _CONFIG_DIR / "user_preferences.json"


# --- Datenmodelle ---

@dataclass
class ProviderModel:
    """Ein verfügbares LLM-Modell."""
    id: str
    name: str
    description: str = ""


@dataclass
class ProviderDefinition:
    """Definition eines API-Providers aus api_providers.json."""
    id: str
    name: str
    base_url: str
    chat_endpoint: str
    models_endpoint: str | None
    supports_dynamic_models: bool
    default_model: str
    models: list[ProviderModel]


# --- API-Key-Verwaltung (keyring) ---

def save_api_key(provider_id: str, api_key: str) -> None:
    """Speichert API-Key sicher im OS Credential Manager.

    Args:
        provider_id: Provider-ID (z.B. 'perplexity').
        api_key: Der API-Key.
    """
    keyring.set_password(SERVICE_NAME, f"{provider_id}_api_key", api_key)
    logger.info(f"API-Key für '{provider_id}' gespeichert")


def get_api_key(provider_id: str) -> str | None:
    """Holt API-Key aus dem OS Credential Manager.

    Args:
        provider_id: Provider-ID (z.B. 'perplexity').

    Returns:
        API-Key oder None wenn nicht konfiguriert.
    """
    return keyring.get_password(SERVICE_NAME, f"{provider_id}_api_key")


def delete_api_key(provider_id: str) -> None:
    """Löscht API-Key aus dem OS Credential Manager.

    Args:
        provider_id: Provider-ID (z.B. 'perplexity').
    """
    try:
        keyring.delete_password(SERVICE_NAME, f"{provider_id}_api_key")
        logger.info(f"API-Key für '{provider_id}' gelöscht")
    except keyring.errors.PasswordDeleteError:
        pass  # Key existierte nicht


def has_api_key(provider_id: str) -> bool:
    """Prüft ob ein API-Key für den Provider konfiguriert ist.

    Args:
        provider_id: Provider-ID (z.B. 'perplexity').

    Returns:
        True wenn ein Key vorhanden ist.
    """
    return get_api_key(provider_id) is not None


# --- Provider-Definitionen (JSON) ---

def load_providers() -> dict[str, ProviderDefinition]:
    """Lädt Provider-Definitionen aus api_providers.json.

    Returns:
        Dict von provider_id → ProviderDefinition.
    """
    if not _PROVIDERS_FILE.exists():
        logger.warning(f"Provider-Datei nicht gefunden: {_PROVIDERS_FILE}")
        return {}

    try:
        with open(_PROVIDERS_FILE, encoding="utf-8") as f:
            data = json.load(f)

        providers: dict[str, ProviderDefinition] = {}
        for p in data.get("providers", []):
            models = [
                ProviderModel(
                    id=m["id"],
                    name=m["name"],
                    description=m.get("description", ""),
                )
                for m in p.get("models", [])
            ]
            providers[p["id"]] = ProviderDefinition(
                id=p["id"],
                name=p["name"],
                base_url=p["base_url"],
                chat_endpoint=p["chat_endpoint"],
                models_endpoint=p.get("models_endpoint"),
                supports_dynamic_models=p.get("supports_dynamic_models", False),
                default_model=p.get("default_model", ""),
                models=models,
            )

        logger.info(f"{len(providers)} Provider geladen: {list(providers.keys())}")
        return providers

    except Exception as e:
        logger.error(f"Fehler beim Laden der Provider: {e}")
        return {}


def get_default_provider_id() -> str:
    """Gibt die ID des Default-Providers zurück.

    Returns:
        Provider-ID aus der JSON-Config oder 'perplexity' als Fallback.
    """
    try:
        with open(_PROVIDERS_FILE, encoding="utf-8") as f:
            data = json.load(f)
        return data.get("default_provider", "perplexity")
    except Exception:
        return "perplexity"


# --- User Preferences (nicht-sensitive Config) ---

def load_preferences() -> dict:
    """Lädt User-Preferences aus user_preferences.json.

    Returns:
        Dict mit Preferences oder leeres Dict.
    """
    if not _PREFERENCES_FILE.exists():
        return {}

    try:
        with open(_PREFERENCES_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Fehler beim Laden der Preferences: {e}")
        return {}


def save_preferences(prefs: dict) -> None:
    """Speichert User-Preferences in user_preferences.json.

    Args:
        prefs: Dict mit Preferences.
    """
    try:
        with open(_PREFERENCES_FILE, "w", encoding="utf-8") as f:
            json.dump(prefs, f, indent=2, ensure_ascii=False)
        logger.info("User-Preferences gespeichert")
    except Exception as e:
        logger.error(f"Fehler beim Speichern der Preferences: {e}")


def get_last_provider() -> str:
    """Gibt den zuletzt gewählten Provider zurück.

    Returns:
        Provider-ID oder Default-Provider.
    """
    prefs = load_preferences()
    return prefs.get("last_provider", get_default_provider_id())


def get_last_model(provider_id: str) -> str | None:
    """Gibt das zuletzt gewählte Modell für einen Provider zurück.

    Args:
        provider_id: Provider-ID.

    Returns:
        Modell-ID oder None.
    """
    prefs = load_preferences()
    return prefs.get("last_models", {}).get(provider_id)


def save_last_selection(provider_id: str, model_id: str) -> None:
    """Speichert die letzte Provider/Modell-Auswahl.

    Args:
        provider_id: Provider-ID.
        model_id: Modell-ID.
    """
    prefs = load_preferences()
    prefs["last_provider"] = provider_id
    if "last_models" not in prefs:
        prefs["last_models"] = {}
    prefs["last_models"][provider_id] = model_id
    save_preferences(prefs)
