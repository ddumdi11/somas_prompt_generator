"""QThread-Worker für non-blocking API-Aufrufe.

Führt LLM-API-Calls in einem separaten Thread aus,
damit die GUI während des Wartens responsiv bleibt.
"""

import logging

from PyQt6.QtCore import QThread, pyqtSignal

from .api_client import APIResponse, APIStatus, LLMClient

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

    def __init__(self, client: LLMClient, prompt: str, model: str):
        super().__init__()
        self.client = client
        self.prompt = prompt
        self.model = model
        self._cancelled = False

    def run(self) -> None:
        """Führt den API-Call im Worker-Thread aus."""
        if self._cancelled:
            return

        self.status_changed.emit(APIStatus.SENDING.value)
        logger.info(f"API-Worker gestartet: model={self.model}")

        try:
            self.status_changed.emit(APIStatus.PROCESSING.value)

            response = self.client.send_prompt(self.prompt, self.model)

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
            else:
                self.status_changed.emit(APIStatus.ERROR.value)
                self.error_occurred.emit(response.error_message)
                logger.error(f"API-Worker Fehler: {response.error_message}")

        except Exception as e:
            if not self._cancelled:
                self.status_changed.emit(APIStatus.ERROR.value)
                self.error_occurred.emit(str(e))
                logger.error(f"API-Worker Exception: {e}")

    def cancel(self) -> None:
        """Markiert den Worker als abgebrochen.

        Hinweis: Der laufende HTTP-Request wird nicht sofort abgebrochen,
        aber das Ergebnis wird nach Empfang ignoriert.
        """
        self._cancelled = True
        logger.info("API-Worker Abbruch angefordert")
