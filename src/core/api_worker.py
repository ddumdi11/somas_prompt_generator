"""QThread-Worker für non-blocking API-Aufrufe.

Führt LLM-API-Calls in einem separaten Thread aus,
damit die GUI während des Wartens responsiv bleibt.
"""

import logging
import time

from PyQt6.QtCore import QThread, pyqtSignal

from .api_client import APIResponse, APIStatus, LLMClient
from .debug_logger import DebugLogger

logger = logging.getLogger(__name__)


class APIWorker(QThread):
    """Worker-Thread für API-Aufrufe ohne UI-Blockierung.

    Signals:
        status_changed: Emittiert bei Statuswechsel (APIStatus-Wert als String).
        response_received: Emittiert bei erfolgreicher Antwort (APIResponse).
        error_occurred: Emittiert bei Fehler (Fehlermeldung als String).
    """

    status_changed = pyqtSignal(str)
    response_received = pyqtSignal(object)
    error_occurred = pyqtSignal(str)

    def __init__(
        self, client: LLMClient, prompt: str, model: str,
        debug_logger: DebugLogger | None = None,
        debug_meta: dict | None = None,
    ) -> None:
        """Initialisiert den API-Worker.

        Args:
            client: LLM-Client-Instanz für den API-Aufruf.
            prompt: Der zu sendende Prompt-Text.
            model: Die Modell-ID (z.B. 'sonar-pro').
            debug_logger: Optionaler DebugLogger für Request/Response-Logging.
            debug_meta: Optionale Meta-Informationen für Debug-Logs.
        """
        super().__init__()
        self.client = client
        self.prompt = prompt
        self.model = model
        self._cancelled = False
        self._debug_logger = debug_logger
        self._debug_meta = debug_meta or {}

    def run(self) -> None:
        """Führt den API-Call im Worker-Thread aus."""
        if self._cancelled:
            return

        self.status_changed.emit(APIStatus.SENDING.value)
        logger.info(f"API-Worker gestartet: model={self.model}")

        # Debug: Request loggen
        log_dir = None
        if self._debug_logger:
            endpoint = getattr(self.client, 'BASE_URL', '') + getattr(
                self.client, 'CHAT_ENDPOINT', ''
            )
            log_dir = self._debug_logger.log_request(
                provider=self.client.PROVIDER_ID,
                model=self.model,
                endpoint=endpoint,
                prompt=self.prompt,
                meta=self._debug_meta,
            )

        start_time = time.time()

        try:
            self.status_changed.emit(APIStatus.PROCESSING.value)

            response = self.client.send_prompt(self.prompt, self.model)
            duration = time.time() - start_time

            if self._cancelled:
                logger.info("API-Worker abgebrochen")
                return

            if response.status == APIStatus.RECEIVED:
                self.status_changed.emit(APIStatus.RECEIVED.value)
                self.response_received.emit(response)
                logger.info(
                    f"API-Worker fertig: {len(response.content)} Zeichen, "
                    f"{response.tokens_used} Tokens"
                )
                # Debug: Erfolgreiche Response loggen
                if self._debug_logger:
                    self._debug_logger.log_response(
                        log_dir=log_dir,
                        status_code=200,
                        content=response.content,
                        tokens={"total": response.tokens_used},
                        duration=duration,
                        model_used=response.model_used,
                        citations=response.citations,
                    )
            else:
                self.status_changed.emit(APIStatus.ERROR.value)
                self.error_occurred.emit(response.error_message)
                logger.error(f"API-Worker Fehler: {response.error_message}")
                # Debug: Fehler-Response loggen
                if self._debug_logger:
                    self._debug_logger.log_response(
                        log_dir=log_dir,
                        status_code=500,
                        content=response.content,
                        tokens={"total": response.tokens_used},
                        duration=duration,
                        model_used=response.model_used,
                        error=response.error_message,
                    )

        except Exception as e:
            duration = time.time() - start_time
            if not self._cancelled:
                self.status_changed.emit(APIStatus.ERROR.value)
                self.error_occurred.emit(str(e))
                logger.exception("API-Worker Exception")
                # Debug: Exception loggen
                if self._debug_logger:
                    self._debug_logger.log_response(
                        log_dir=log_dir,
                        status_code=0,
                        content="",
                        tokens={},
                        duration=duration,
                        error=str(e),
                    )

    def cancel(self) -> None:
        """Markiert den Worker als abgebrochen.

        Hinweis: Der laufende HTTP-Request wird nicht sofort abgebrochen,
        aber das Ergebnis wird nach Empfang ignoriert.
        """
        self._cancelled = True
        logger.info("API-Worker Abbruch angefordert")
