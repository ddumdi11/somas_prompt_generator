"""QThread-Worker für den Modellvergleich (v0.9.0).

Führt zu EINEM Video/Transkript sequenziell aus:
Metadaten → Analyse A → Analyse B → Synthese → Layout-Render.

Sequenziell (nicht parallel), um Worker-Logik, Rate-Limits und Debug-Logging
einfach zu halten. SOMAS-Parameter (Preset, Perspektive, Tiefe, Sprache)
gelten für BEIDE Analysen identisch — variiert wird nur das Modell.
"""

import logging
import time

from jinja2 import Environment, FileSystemLoader
from PyQt6.QtCore import QThread, pyqtSignal

from src.config.api_config import get_api_key
from src.config.defaults import SomasConfig, VideoInfo

from .api_client import APIResponse, APIStatus, LLMClient, create_client
from .comparison_item import ComparisonConfig, ComparisonResult
from .debug_logger import APP_VERSION, DebugLogger
from .prompt_builder import (
    build_prompt,
    build_prompt_from_transcript,
    build_synthesis_prompt,
    clean_synthesis_output,
    get_template_dir,
)
from .youtube_client import build_thumbnail_urls, extract_video_id, get_video_info

logger = logging.getLogger(__name__)

SYNTHESIS_PLACEHOLDER = (
    "_Automatische Kurzbeschreibung fehlgeschlagen — bitte manuell ergänzen._"
)


class ComparisonWorker(QThread):
    """Worker-Thread für einen Modellvergleichs-Lauf.

    Signals:
        step_status_changed(str): "meta"|"a"|"b"|"synth"|"render"|"done".
        metadata_loaded(object): VideoInfo nach Auflösung/Konstruktion.
        analysis_completed(str, str, object): step("a"|"b"), Text, APIResponse.
        synthesis_completed(str): Kurzbeschreibung (oder Platzhalter).
        comparison_finished(str): Fertiges Markdown-Dokument.
        error_occurred(str, str): step, Fehlermeldung.
    """

    step_status_changed = pyqtSignal(str)
    metadata_loaded = pyqtSignal(object)
    analysis_completed = pyqtSignal(str, str, object)
    synthesis_completed = pyqtSignal(str)
    comparison_finished = pyqtSignal(str)
    error_occurred = pyqtSignal(str, str)

    def __init__(
        self,
        config: ComparisonConfig,
        rating_store=None,
        debug_logger: DebugLogger | None = None,
    ) -> None:
        """Initialisiert den ComparisonWorker.

        Args:
            config: Die Vergleichs-Konfiguration (Eingabe, SOMAS-Parameter, Modelle).
            rating_store: Optionaler RatingStore (für spätere DB-Anbindung; MVP nutzt ihn nicht).
            debug_logger: Optionaler DebugLogger für Request/Response-Logging.
        """
        super().__init__()
        self._config = config
        self._rating_store = rating_store
        self._debug_logger = debug_logger
        self._cancelled = False
        self._result = ComparisonResult(config=config)

    @property
    def result(self) -> ComparisonResult:
        """Gibt den aktuellen Lauf-Zustand zurück (für GUI/Headless-Zugriff)."""
        return self._result

    # --- Hauptablauf ---

    def run(self) -> None:
        """Führt den Vergleichslauf sequenziell aus."""
        cfg = self._config
        try:
            # 0) Modelle + API-Keys prüfen (kein Start bei fehlendem Key)
            for choice, step in (
                (cfg.model_a, "a"), (cfg.model_b, "b"), (cfg.model_synth, "synth")
            ):
                if choice is None:
                    self._fail(step, f"Kein Modell für Schritt '{step}' gewählt.")
                    return
                if not get_api_key(choice.provider_id):
                    name = choice.provider_name or choice.provider_id
                    self._fail(step, f"Kein API-Key für Provider '{name}' konfiguriert.")
                    return

            # Clients bauen
            client_a = create_client(cfg.model_a.provider_id, get_api_key(cfg.model_a.provider_id))
            client_b = create_client(cfg.model_b.provider_id, get_api_key(cfg.model_b.provider_id))
            client_synth = create_client(
                cfg.model_synth.provider_id, get_api_key(cfg.model_synth.provider_id)
            )
            if self._cancelled:
                return

            # 1) Metadaten
            self._emit_step("meta")
            if cfg.input_mode == "youtube":
                try:
                    video_info = get_video_info(cfg.url)
                except ValueError as e:
                    self._fail("meta", str(e))
                    return
            else:
                video_info = VideoInfo(
                    title=cfg.transcript_title or "Transkript",
                    channel=cfg.transcript_author or "",
                    duration=0,
                    url="",
                    transcript=cfg.transcript_text,
                )
            self._result.video_info = video_info
            self.metadata_loaded.emit(video_info)
            if self._cancelled:
                return

            # Analyse-Prompt einmal bauen (identisch für A und B → fairer Vergleich)
            somas = SomasConfig(depth=cfg.depth, language=cfg.language)
            if cfg.input_mode == "youtube":
                analysis_prompt = build_prompt(
                    video_info=video_info,
                    config=somas,
                    questions=cfg.questions,
                    preset_name=cfg.preset_name,
                    perspective=cfg.perspective,
                )
            else:
                analysis_prompt = build_prompt_from_transcript(
                    title=video_info.title,
                    author=video_info.channel,
                    transcript=cfg.transcript_text,
                    config=somas,
                    url=None,
                    questions=cfg.questions,
                    preset_name=cfg.preset_name,
                    is_auto_transcript=cfg.is_auto_transcript,
                    perspective=cfg.perspective,
                )

            # 2) Analyse A
            self._emit_step("a")
            resp_a = self._send(client_a, analysis_prompt, cfg.model_a.model_id, video_info, "analysis_a")
            if self._cancelled:
                return
            if resp_a.status != APIStatus.RECEIVED:
                self._fail("a", resp_a.error_message or "Analyse A fehlgeschlagen.")
                return
            self._result.analysis_a_text = resp_a.content
            self._result.tokens_a = resp_a.tokens_used
            self.analysis_completed.emit("a", resp_a.content, resp_a)

            # 3) Analyse B
            self._emit_step("b")
            resp_b = self._send(client_b, analysis_prompt, cfg.model_b.model_id, video_info, "analysis_b")
            if self._cancelled:
                return
            if resp_b.status != APIStatus.RECEIVED:
                self._fail("b", resp_b.error_message or "Analyse B fehlgeschlagen.")
                return
            self._result.analysis_b_text = resp_b.content
            self._result.tokens_b = resp_b.tokens_used
            self.analysis_completed.emit("b", resp_b.content, resp_b)

            # 4) Synthese (Fehler ist NICHT fatal → Platzhalter + Warnung)
            self._emit_step("synth")
            synth_prompt = build_synthesis_prompt(
                resp_a.content,
                resp_b.content,
                title=video_info.title,
                channel=video_info.channel,
                duration_formatted=video_info.duration_formatted,
                model_a_name=cfg.model_a.model_name or cfg.model_a.model_id,
                model_b_name=cfg.model_b.model_name or cfg.model_b.model_id,
                language=cfg.language,
            )
            summary = SYNTHESIS_PLACEHOLDER
            try:
                resp_s = self._send(
                    client_synth, synth_prompt, cfg.model_synth.model_id, video_info, "synthesis"
                )
                if resp_s.status == APIStatus.RECEIVED and resp_s.content.strip():
                    summary = clean_synthesis_output(resp_s.content) or SYNTHESIS_PLACEHOLDER
                    self._result.tokens_synth = resp_s.tokens_used
                else:
                    self._note_error("synth", resp_s.error_message or "Synthese fehlgeschlagen.")
            except Exception as e:  # noqa: BLE001 — Synthese-Fehler darf den Lauf nicht abbrechen
                logger.exception("Synthese fehlgeschlagen")
                self._note_error("synth", str(e))
            self._result.synthesis_summary = summary
            self.synthesis_completed.emit(summary)
            if self._cancelled:
                return

            # 5) Render
            self._emit_step("render")
            final_md = self._render(video_info, summary)
            self._result.final_markdown = final_md
            self._result.status = "done"
            self.comparison_finished.emit(final_md)
            self._emit_step("done")

        except Exception as e:  # noqa: BLE001 — unerwartete Fehler sauber melden
            logger.exception("ComparisonWorker: unerwarteter Fehler")
            if not self._cancelled:
                self._fail(self._result.error_step or "meta", str(e))

    # --- Helfer ---

    def _emit_step(self, step: str) -> None:
        """Setzt den Status und emittiert step_status_changed."""
        self._result.status = step
        self.step_status_changed.emit(step)

    def _fail(self, step: str, message: str) -> None:
        """Markiert den Lauf als fehlgeschlagen und emittiert error_occurred."""
        self._note_error(step, message)
        self._result.status = "error"
        self.error_occurred.emit(step, message)

    def _note_error(self, step: str, message: str) -> None:
        """Schreibt Fehlerinfo in das Result (ohne Status auf 'error' zu zwingen).

        Für nicht-fatale Fehler (Synthese): GUI wird via error_occurred gewarnt,
        der Lauf läuft aber weiter.
        """
        self._result.error_step = step
        self._result.error_message = message
        if step == "synth":
            # Synthese-Fehler ist nicht fatal → trotzdem GUI warnen
            self.error_occurred.emit(step, message)

    def _send(
        self,
        client: LLMClient,
        prompt: str,
        model_id: str,
        video_info: VideoInfo,
        step_label: str,
    ) -> APIResponse:
        """Sendet einen Prompt, misst die Dauer und loggt optional (Debug)."""
        log_dir = None
        if self._debug_logger:
            endpoint = getattr(client, "BASE_URL", "") + getattr(client, "CHAT_ENDPOINT", "")
            log_dir = self._debug_logger.log_request(
                provider=getattr(client, "PROVIDER_ID", ""),
                model=model_id,
                endpoint=endpoint,
                prompt=prompt,
                meta=self._debug_meta(video_info, step_label),
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

    def _debug_meta(self, video_info: VideoInfo | None, step: str) -> dict:
        """Baut die Debug-Meta für einen Schritt."""
        cfg = self._config
        return {
            "app_version": APP_VERSION,
            "feature": "comparison",
            "step": step,
            "preset_name": cfg.preset_name,
            "perspective": cfg.perspective,
            "depth": cfg.depth,
            "language": cfg.language,
            "input_mode": cfg.input_mode,
            "video_title": video_info.title if video_info else "",
            "video_url": (video_info.url if video_info else "") or cfg.url,
        }

    def _render(self, video_info: VideoInfo, summary: str) -> str:
        """Rendert das Vergleichsdokument via Jinja2."""
        cfg = self._config
        is_youtube = cfg.input_mode == "youtube"

        thumb = {"maxres": "", "sd": "", "hq": ""}
        if is_youtube:
            video_id = extract_video_id(cfg.url)
            if video_id:
                thumb = build_thumbnail_urls(video_id)

        env = Environment(
            loader=FileSystemLoader(get_template_dir()),
            trim_blocks=True,
            lstrip_blocks=True,
        )
        template = env.get_template("somas_comparison.txt")
        return template.render(
            video_title=video_info.title,
            channel=video_info.channel,
            duration_formatted=(
                video_info.duration_formatted if (is_youtube and video_info.duration) else ""
            ),
            url=video_info.url if is_youtube else "",
            thumbnail_url=thumb["maxres"],
            thumbnail_url_sd=thumb["sd"],
            thumbnail_url_hq=thumb["hq"],
            model_a_name=cfg.model_a.model_name or cfg.model_a.model_id,
            model_a_provider=cfg.model_a.provider_name or cfg.model_a.provider_id,
            model_b_name=cfg.model_b.model_name or cfg.model_b.model_id,
            model_b_provider=cfg.model_b.provider_name or cfg.model_b.provider_id,
            analysis_a=self._result.analysis_a_text,
            analysis_b=self._result.analysis_b_text,
            synthesis_summary=summary,
            synthesis_model_name=cfg.model_synth.model_name or cfg.model_synth.model_id,
            synthesis_provider=cfg.model_synth.provider_name or cfg.model_synth.provider_id,
            is_youtube=is_youtube,
        )

    def cancel(self) -> None:
        """Markiert den Worker als abgebrochen.

        Ein laufender HTTP-Request wird nicht hart abgebrochen, das Ergebnis
        aber nach Empfang ignoriert (kein weiterer Schritt, kein finished-Signal).
        """
        self._cancelled = True
        logger.info("ComparisonWorker Abbruch angefordert")
