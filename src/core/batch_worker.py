"""QThread-Worker für die sequenzielle Batch-Verarbeitung.

Verarbeitet 2-5 YouTube-URLs nacheinander:
URL → Metadaten → Transkript → Prompt → API-Call → Speicherung.
"""

import logging
import time

from PyQt6.QtCore import QThread, pyqtSignal

from .api_client import APIResponse, APIStatus, LLMClient
from .batch_item import BatchConfig, BatchItem
from .batch_persistence import save_item_state
from .prompt_builder import (
    build_prompt,
    build_prompt_from_transcript,
    get_anti_monotony_hint,
    get_preset_by_name,
)
from .rating_store import (
    AnalysisRecord,
    RatingStore,
    extract_module_from_result,
)
from .youtube_client import get_video_info

logger = logging.getLogger(__name__)


def _create_client(provider_id: str, api_key: str) -> LLMClient:
    """Erstellt den passenden API-Client für einen Provider.

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


class BatchWorker(QThread):
    """Worker-Thread für sequenzielle Batch-Verarbeitung.

    Verarbeitet eine Liste von YouTube-URLs nacheinander,
    emittiert Fortschritts-Signals für jeden Schritt.

    Signals:
        item_status_changed(int, str): Index + neuer Status.
        item_metadata_loaded(int, object): Index + VideoInfo.
        item_completed(int, str, object): Index + Ergebnis-Text + APIResponse.
        item_error(int, str): Index + Fehlermeldung.
        batch_finished(): Alle Items verarbeitet.
    """

    item_status_changed = pyqtSignal(int, str)
    item_metadata_loaded = pyqtSignal(int, object)
    item_completed = pyqtSignal(int, str, object)
    item_error = pyqtSignal(int, str)
    batch_finished = pyqtSignal()

    def __init__(
        self,
        config: BatchConfig,
        items: list[BatchItem],
        rating_store: RatingStore,
        session_dir=None,
        debug_logger=None,
    ) -> None:
        """Initialisiert den BatchWorker.

        Args:
            config: Gemeinsame Batch-Einstellungen.
            items: Liste der zu verarbeitenden BatchItems.
            rating_store: DB-Zugriff für Analyse-Speicherung.
            session_dir: Pfad zur Temp-Session (für Crash-Resistenz).
            debug_logger: Optionaler DebugLogger.
        """
        super().__init__()
        self._config = config
        self._items = items
        self._rating_store = rating_store
        self._session_dir = session_dir
        self._debug_logger = debug_logger
        self._cancelled = False

    def run(self) -> None:
        """Verarbeitet alle Items sequenziell."""
        client = None
        try:
            client = _create_client(
                self._config.provider_id, self._config.api_key
            )
        except Exception as e:
            logger.exception("Client-Erstellung fehlgeschlagen")
            for i in range(len(self._items)):
                self.item_error.emit(i, f"Provider-Fehler: {e}")
            self.batch_finished.emit()
            return

        for i, item in enumerate(self._items):
            if self._cancelled:
                logger.info("Batch abgebrochen")
                break

            try:
                self._process_single_item(i, item, client)
            except Exception as e:
                logger.exception(f"Batch-Item {i+1} fehlgeschlagen")
                item.status = "error"
                item.error_message = str(e)
                self.item_error.emit(i, str(e))

            # Temp-Datei aktualisieren nach jedem Item
            if self._session_dir:
                save_item_state(self._session_dir, i, item)

        self.batch_finished.emit()

    def _process_single_item(
        self, index: int, item: BatchItem, client: LLMClient
    ) -> None:
        """Verarbeitet ein einzelnes BatchItem.

        Pipeline: Metadaten → Prompt → API-Call → Speicherung.
        """
        from src.config.defaults import SomasConfig

        # 1. Metadaten laden
        self.item_status_changed.emit(index, "loading")
        item.status = "loading"

        video_info = get_video_info(item.url)
        item.video_info = video_info
        self.item_metadata_loaded.emit(index, video_info)

        if self._cancelled:
            return

        # 2. Prompt generieren
        self.item_status_changed.emit(index, "prompting")
        item.status = "prompting"

        config = SomasConfig(
            depth=self._config.depth,
            language=self._config.language,
        )

        # Anti-Monotonie
        recent_modules = self._rating_store.get_recent_modules(3)
        anti_monotony_hint = get_anti_monotony_hint(recent_modules)

        if video_info.transcript:
            prompt = build_prompt_from_transcript(
                title=video_info.title,
                author=video_info.channel,
                transcript=video_info.transcript,
                config=config,
                url=video_info.url,
                preset_name=self._config.preset_name,
                is_auto_transcript=True,
                perspective=self._config.perspective,
                anti_monotony_hint=anti_monotony_hint,
            )
        else:
            prompt = build_prompt(
                video_info=video_info,
                config=config,
                preset_name=self._config.preset_name,
                perspective=self._config.perspective,
                anti_monotony_hint=anti_monotony_hint,
            )

        item.prompt = prompt

        if self._cancelled:
            return

        # 3. API-Call
        self.item_status_changed.emit(index, "calling")
        item.status = "calling"

        start_time = time.time()
        response = client.send_prompt(prompt, self._config.model_id)
        duration = time.time() - start_time
        response.duration_seconds = duration

        if response.status != APIStatus.RECEIVED:
            raise RuntimeError(
                response.error_message or "API-Call fehlgeschlagen"
            )

        item.result_text = response.content
        item.tokens_used = response.tokens_used
        item.response_time = duration

        # 4. Analyse in DB speichern
        preset = get_preset_by_name(self._config.preset_name)
        record = AnalysisRecord(
            provider_id=response.provider_used or self._config.provider_id,
            model_id=response.model_used or self._config.model_id,
            model_name=self._config.model_name,
            video_url=video_info.url,
            video_title=video_info.title,
            channel_name=video_info.channel,
            video_duration=video_info.duration,
            preset_name=self._config.preset_name,
            preset_max_chars=preset.max_chars if preset else 0,
            result_chars=len(response.content),
            response_time=duration,
            tokens_used=response.tokens_used,
            input_mode="youtube",
            had_transcript=bool(video_info.transcript),
            had_time_range=False,
            had_questions=False,
        )
        analysis_id = self._rating_store.save_analysis(record)
        item.analysis_id = analysis_id

        # 5. Modul extrahieren
        extract_module_from_result(
            self._rating_store, analysis_id, response.content
        )

        # 6. Erfolg melden
        item.status = "done"
        self.item_completed.emit(index, response.content, response)
        logger.info(
            f"Batch-Item {index+1}: {video_info.title[:40]} "
            f"({len(response.content)} Zeichen, {response.tokens_used} Tokens)"
        )

    def cancel(self) -> None:
        """Markiert den Worker als abgebrochen."""
        self._cancelled = True
        logger.info("Batch-Worker Abbruch angefordert")
