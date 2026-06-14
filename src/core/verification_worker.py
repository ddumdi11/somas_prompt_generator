"""QThread-Worker für die Faktencheck-Verifikation (Stufe 2, v0.10.0).

Bewusst schlank: ein einzelner API-Call an das gewählte Verifikationsmodell,
das ausschließlich die (bereits gekappten) Behauptungen prüft. Muster wie
ComparisonWorker/APIWorker. Stufe 2 ist ein optionaler Anhang — Fehler sind
NICHT fatal für die Analyse (die GUI hängt bei error_occurred einen
Platzhalter an, statt die Analyse zu verlieren).
"""

import logging
import time
from datetime import datetime

from jinja2 import Environment, FileSystemLoader
from PyQt6.QtCore import QThread, pyqtSignal

from src.config.api_config import get_api_key

from .api_client import APIResponse, APIStatus, LLMClient, create_client
from .debug_logger import APP_VERSION, DebugLogger
from .prompt_builder import (
    build_verification_prompt,
    clean_verification_output,
    get_template_dir,
)
from .verification_item import VerificationConfig, VerificationResult

logger = logging.getLogger(__name__)

NO_CLAIMS_SECTION = (
    "---\n\n### FAKTENCHECK · VERIFIKATION\n"
    "_Keine überprüfbaren Behauptungen gefunden._\n"
)


class VerificationWorker(QThread):
    """Worker-Thread für einen Verifikationslauf (Stufe 2).

    Signals:
        status_changed(str): "running" | "done" | "error" | "skipped".
        finished_ok(str, object): rendered_section, VerificationResult.
        error_occurred(str): Fehlermeldung (nicht fatal für die Analyse).
    """

    status_changed = pyqtSignal(str)
    finished_ok = pyqtSignal(str, object)
    error_occurred = pyqtSignal(str)

    def __init__(
        self,
        config: VerificationConfig,
        debug_logger: DebugLogger | None = None,
    ) -> None:
        """Initialisiert den VerificationWorker.

        Args:
            config: Die Verifikations-Konfiguration (gekappte claims + Modell).
            debug_logger: Optionaler DebugLogger für Request/Response-Logging.
        """
        super().__init__()
        self._config = config
        self._debug_logger = debug_logger
        self._cancelled = False
        self._result = VerificationResult(config=config)

    @property
    def result(self) -> VerificationResult:
        """Gibt den aktuellen Lauf-Zustand zurück (GUI/Headless-Zugriff)."""
        return self._result

    def run(self) -> None:
        """Führt den Verifikationslauf aus."""
        cfg = self._config

        # 0) Keine Behauptungen → übersprungen, aber sauberer Hinweis-Abschnitt.
        if not cfg.claims:
            self._result.status = "skipped"
            self._result.rendered_section = NO_CLAIMS_SECTION
            self.status_changed.emit("skipped")
            self.finished_ok.emit(NO_CLAIMS_SECTION, self._result)
            return

        # 1) API-Key prüfen
        key = get_api_key(cfg.model.provider_id)
        if not key:
            name = cfg.model.provider_name or cfg.model.provider_id
            self._fail(f"Kein API-Key für Provider '{name}' konfiguriert.")
            return

        self._result.status = "running"
        self.status_changed.emit("running")

        try:
            client = create_client(cfg.model.provider_id, key)

            source_hint = ""
            if cfg.source_title or cfg.source_url:
                source_hint = " ".join(p for p in (cfg.source_title, cfg.source_url) if p)

            prompt = build_verification_prompt(
                cfg.claims, language=cfg.language, source_hint=source_hint
            )

            if self._cancelled:
                return

            resp = self._send(client, prompt, cfg.model.model_id)

            if self._cancelled:
                return

            if resp.status != APIStatus.RECEIVED or not (resp.content or "").strip():
                self._fail(resp.error_message or "Modell lieferte leeren Inhalt.")
                return

            body = clean_verification_output(resp.content)
            citations = self._dedup(resp.citations)
            self._result.raw_output = body
            self._result.citations = citations
            self._result.tokens_used = resp.tokens_used

            rendered = self._render(body, citations)
            self._result.rendered_section = rendered
            self._result.status = "done"
            self.status_changed.emit("done")
            self.finished_ok.emit(rendered, self._result)

        except Exception as e:  # noqa: BLE001 — Stufe-2-Fehler darf Analyse nicht verlieren
            logger.exception("VerificationWorker: unerwarteter Fehler")
            if not self._cancelled:
                self._fail(str(e))

    # --- Helfer ---

    def _fail(self, message: str) -> None:
        """Markiert den Lauf als fehlgeschlagen (nicht fatal) und meldet ihn."""
        self._result.status = "error"
        self._result.error_message = message
        self.status_changed.emit("error")
        self.error_occurred.emit(message)

    def _send(self, client: LLMClient, prompt: str, model_id: str) -> APIResponse:
        """Sendet den Prompt, misst die Dauer und loggt optional (Debug)."""
        log_dir = None
        if self._debug_logger:
            endpoint = getattr(client, "BASE_URL", "") + getattr(client, "CHAT_ENDPOINT", "")
            log_dir = self._debug_logger.log_request(
                provider=getattr(client, "PROVIDER_ID", ""),
                model=model_id,
                endpoint=endpoint,
                prompt=prompt,
                meta={
                    "app_version": APP_VERSION,
                    "feature": "verification",
                    "language": self._config.language,
                    "claims_count": len(self._config.claims),
                    "total_claims": self._config.total_claims,
                },
            )

        start = time.time()
        response = client.send_prompt(prompt, model_id)
        duration = time.time() - start
        response.duration_seconds = duration

        if self._debug_logger:
            ok = response.status == APIStatus.RECEIVED
            self._debug_logger.log_response(
                log_dir=log_dir,
                status_code=200 if ok else 500,
                content=response.content,
                tokens={"total": response.tokens_used},
                duration=duration,
                model_used=response.model_used,
                citations=response.citations,
                error=None if ok else (response.error_message or "Fehler"),
            )
        return response

    @staticmethod
    def _dedup(citations: list[str] | None) -> list[str]:
        """Dedupliziert Quellen unter Erhalt der Reihenfolge."""
        seen: set[str] = set()
        result: list[str] = []
        for c in citations or []:
            if c and c not in seen:
                seen.add(c)
                result.append(c)
        return result

    def _render(self, body: str, citations: list[str]) -> str:
        """Rendert den Verifikationsabschnitt via Jinja2."""
        cfg = self._config
        env = Environment(
            loader=FileSystemLoader(get_template_dir()),
            trim_blocks=True,
            lstrip_blocks=True,
        )
        template = env.get_template("somas_verification.txt")
        claims_capped = len(cfg.claims) < cfg.total_claims
        return template.render(
            model_name=cfg.model.model_name or cfg.model.model_id,
            provider_name=cfg.model.provider_name or cfg.model.provider_id,
            date=datetime.now().strftime("%d.%m.%Y"),
            claims_capped=claims_capped,
            checked_count=len(cfg.claims),
            total_count=cfg.total_claims,
            web_unverified=cfg.web_unverified,
            verification_body=body,
            citations=citations,
        )

    def cancel(self) -> None:
        """Markiert den Worker als abgebrochen (Ergebnis wird ignoriert)."""
        self._cancelled = True
        logger.info("VerificationWorker Abbruch angefordert")
