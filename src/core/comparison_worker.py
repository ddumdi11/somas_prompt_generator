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

from .api_client import (
    APIResponse,
    APIStatus,
    LLMClient,
    create_client,
    is_truncated_finish_reason,
)
from .comparison_item import ComparisonConfig, ComparisonResult, ModelChoice
from .debug_logger import APP_VERSION, DebugLogger
from .prompt_builder import (
    build_prompt,
    build_prompt_from_transcript,
    build_synthesis_prompt,
    clean_synthesis_output,
    get_template_dir,
    normalize_markdown_headings,
    strip_reasoning_preamble,
    validate_analysis_structure,
)
from .youtube_client import build_thumbnail_urls, extract_video_id, resolve_video_info

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
                    video_info = resolve_video_info(cfg.url)
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
                # Wie BatchWorker: vorhandenes YouTube-Transkript einbetten, damit
                # auch Modelle ohne Web-Suche den Inhalt analysieren können.
                if video_info.transcript:
                    analysis_prompt = build_prompt_from_transcript(
                        title=video_info.title,
                        author=video_info.channel,
                        transcript=video_info.transcript,
                        config=somas,
                        url=video_info.url,
                        questions=cfg.questions,
                        preset_name=cfg.preset_name,
                        is_auto_transcript=True,
                        perspective=cfg.perspective,
                    )
                else:
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

            # 2) Analyse A (mit v0.11-Prüfkette + 1× Auto-Retry, s. _run_analysis_step)
            self._emit_step("a")
            result_a = self._run_analysis_step(
                client_a, analysis_prompt, cfg.model_a, video_info, "a"
            )
            if result_a is None:
                return  # abgebrochen oder offener Fehlschlag (bereits gemeldet)
            resp_a, display_a = result_a  # display_a = preamble-bereinigt (kein Leak)
            self._result.analysis_a_text = normalize_markdown_headings(display_a)
            self._result.tokens_a = resp_a.tokens_used
            self.analysis_completed.emit("a", display_a, resp_a)

            # 3) Analyse B (gleiche Prüfkette)
            self._emit_step("b")
            result_b = self._run_analysis_step(
                client_b, analysis_prompt, cfg.model_b, video_info, "b"
            )
            if result_b is None:
                return
            resp_b, display_b = result_b
            self._result.analysis_b_text = normalize_markdown_headings(display_b)
            self._result.tokens_b = resp_b.tokens_used
            self.analysis_completed.emit("b", display_b, resp_b)

            # 4) Synthese (Fehler ist NICHT fatal → Platzhalter + Warnung).
            #    Auch die Synthese bekommt den bereinigten Text, damit ein
            #    Reasoning-Vorspann die Kurzbeschreibung nicht verunreinigt.
            self._emit_step("synth")
            synth_prompt = build_synthesis_prompt(
                display_a,
                display_b,
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

    def _validate_analysis(self, response: APIResponse) -> tuple[bool, str, str]:
        """Prüft eine erhaltene Analyse mit der v0.11-Kette.

        Kombiniert das finish_reason-Gate (Trunkierung) mit dem Struktur-/
        Schriftmix-Validator auf dem preamble-bereinigten Text. Im Vergleich wird
        KEIN Modul erzwungen → ``require_faktencheck=False`` (der Validator
        toleriert die freie Modulwahl per v0.11-Design).

        Args:
            response: Die (bereits als RECEIVED bestätigte) API-Antwort.

        Returns:
            ``(ok, grund, display_content)`` — ``display_content`` ist der
            preamble-bereinigte Text (wie in der Einzelanalyse angezeigt) und wird
            vom Aufrufer weiterverwendet, damit ein entfernbarer Reasoning-Vorspann
            NICHT ins Vergleichsdokument leakt. ``grund`` ist bei ``ok=True`` leer.
        """
        display_content, _ = strip_reasoning_preamble(response.content)
        if is_truncated_finish_reason(response.finish_reason or ""):
            return False, "Antwort abgeschnitten (Token-Limit)", display_content
        result = validate_analysis_structure(display_content)
        if not result.ok:
            return False, result.reason, display_content
        return True, "", display_content

    def _run_analysis_step(
        self,
        client: LLMClient,
        prompt: str,
        model_choice: ModelChoice,
        video_info: VideoInfo,
        step: str,
    ) -> tuple[APIResponse, str] | None:
        """Führt eine Analyse-Stufe (A oder B) mit Prüfkette + 1× Auto-Retry aus.

        Sendet den Prompt und prüft ihn mit :meth:`_validate_analysis`. Bei
        Ungültigkeit wird GENAU EINMAL sichtbar neu angefordert (Fortschritts-
        Signal ``"{step}_retry"``). Bleibt die Analyse ungültig, schlägt der
        GESAMTE Vergleich offen fehl (kein Teil-Dokument, keine kosmetische
        Reparatur — eine kaputte Analyse macht den Vergleich wertlos, Startprompt
        v0.14.3 §Teil A.4). Ein Transport-Fehler bricht sofort ab (kein Retry).

        Args:
            client: Der LLM-Client für dieses Modell.
            prompt: Der (für A und B identische) Analyse-Prompt.
            model_choice: Modellwahl des Schritts (Name für die Fehlermeldung).
            video_info: Metadaten (für das Debug-Log).
            step: ``"a"`` oder ``"b"``.

        Returns:
            ``(response, display_content)`` bei gültiger Analyse —
            ``display_content`` ist der preamble-bereinigte Text (der Aufrufer
            speichert/emittiert/synthetisiert diesen, NICHT den Rohtext). ``None``
            bei Abbruch, Transport-Fehler oder endgültiger Ungültigkeit (``_fail``
            wurde in den beiden Fehlerfällen bereits emittiert).
        """
        step_label = f"analysis_{step}"
        model_name = model_choice.model_name or model_choice.model_id
        max_attempts = 2  # 1 regulärer Versuch + 1 sichtbarer Auto-Retry (v0.11-Linie)
        last_reason = ""
        for attempt in range(max_attempts):
            if attempt > 0:
                # Sichtbarer Auto-Retry. Eigener Status-Wert, damit _result.status
                # (der reale Schritt "a"/"b") nicht überschrieben wird.
                self.step_status_changed.emit(f"{step}_retry")
                logger.warning(
                    f"Vergleich: Analyse {step.upper()} ungültig ({last_reason}) — "
                    f"Wiederholung {attempt}/{max_attempts - 1}"
                )
            response = self._send(client, prompt, model_choice.model_id, video_info, step_label)
            if self._cancelled:
                return None
            if response.status != APIStatus.RECEIVED:
                # Transport-/API-Fehler: sofort offener Fehlschlag, kein Retry.
                self._fail(step, response.error_message or f"Analyse {step.upper()} fehlgeschlagen.")
                return None
            ok, reason, display_content = self._validate_analysis(response)
            if ok:
                return response, display_content
            last_reason = reason

        # Beide Versuche ungültig → offener Fehlschlag des GESAMTEN Vergleichs.
        self._fail(
            step,
            f"Analyse {step.upper()} ({model_name}) blieb nach Wiederholung "
            f"ungültig: {last_reason}. Der Vergleich wurde abgebrochen "
            f"(kein Teil-Dokument).",
        )
        return None

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
                tokens=response.token_log_dict(),
                duration=duration,
                model_used=response.model_used,
                citations=response.citations,
                error=None if ok else (response.error_message or "Fehler"),
                finish_reason=response.finish_reason,
                reasoning_tokens=response.reasoning_tokens,
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
