"""QThread-Worker für Faktencheck Plus (v0.13.0, PR 4).

Orchestriert die fünf Stufen des ``factcheck_plus``-Packages:

    S1 ClaimRefiner → S2 ArgumentMapper → S3 PolicyScorer (LLM-frei)
    → S4 ResearchPlanner → S5 Recherche+Verdikt (ein Call PRO Claim)
    → Aggregation → Markdown-Abschnitt + Transparenz-Block

Der Worker ist die **Naht zwischen Qt und dem Package**: Das Package kennt kein
Qt (Spec §2.2), deshalb wandern Fortschritt und Abbruch als Callbacks hinein
(``on_progress``/``should_cancel``) und kommen als Signale wieder heraus. Auch
das Jinja2-Rendering liegt bewusst hier, nicht im Package — genau wie beim
Classic-Weg (:meth:`verification_worker.VerificationWorker._render`).

Fehler eines einzelnen Claim-Calls sind nicht fatal (der Claim wird sichtbar als
ungeprüft ausgewiesen); ein Fehler einer LLM-Stufe beendet den Lauf sauber mit
Fehlermeldung, ohne die Analyse zu verlieren.
"""

import logging
import time
from datetime import datetime

from jinja2 import Environment, FileSystemLoader
from PyQt6.QtCore import QThread, pyqtSignal

from src.config.api_config import get_api_key

from .api_client import APIResponse, APIStatus, LLMClient, create_client
from .comparison_item import ModelChoice
from .debug_logger import APP_VERSION, DebugLogger
from .factcheck_plus import (
    ArgumentMapper, ArgumentMapping, ClaimRefiner, ClaimVerdict, ClaimVerifier,
    PolicyScorer, RefinedClaim, ResearchCard, ResearchPlanner, SelectionResult,
    StageError, build_render_context, join_claims,
)
from .factcheck_plus_item import FactcheckPlusConfig, FactcheckPlusResult
from .prompt_builder import get_template_dir

logger = logging.getLogger(__name__)

NO_CLAIMS_SECTION = (
    "---\n\n### FAKTENCHECK · VERIFIKATION PLUS\n"
    "_Keine überprüfbaren Behauptungen gefunden._\n"
)

# Stufenanzahl für die Fortschrittsanzeige (S1, S2, S3, S4, S5).
TOTAL_STAGES = 5

# v0.13.3: Größeres Antwort-Budget für OpenRouter-Stage-Calls. DeepSeek-Upstream-
# Hosts respektieren den Reasoning-Cap (v0.13.2) nicht zuverlässig — das Reasoning
# frisst weiter das Budget (~11–15k), der sichtbare JSON-Content braucht schlicht
# mehr Luft (~5–6k bei 19–21 Claims). 32768 lässt ~11k Reserve über den Worst Case.
# Die Provider-Kenntnis sitzt bewusst HIER an der Qt↔Package-Naht, nicht im
# client-agnostischen ``llm_stage`` (das Package kennt keine Provider). Andere
# Provider bleiben bei ``llm_stage.STAGE_MAX_TOKENS`` (16384). 402-Vorauth gegen
# 32768 ist bei DeepSeek-Preisen vernachlässigbar (PO-Entscheidung); ein echtes 402
# bliebe ein offener Fehler (nicht still absenken, Linie aus v0.13.2).
#
# NICHT zu verwechseln mit `openrouter_client.OPENROUTER_DEFAULT_MAX_TOKENS`
# (v0.14.2, gleicher Wert 32768): das ist der Default-Budget für NORMALE
# OpenRouter-Calls (Analyse/Verifikation, `max_tokens is None`) im Client selbst.
# Diese Konstante hier ist das EXPLIZITE Stage-Budget, das die Naht als `max_tokens`
# durchreicht — andere Schicht, andere Bedeutung; getrennt, damit das Package
# provider-agnostisch bleibt.
STAGE_MAX_TOKENS_OPENROUTER = 32768


class _TokenCountingClient:
    """Zählt Tokens und loggt Requests, ohne die Stufen davon wissen zu lassen.

    Die Stufen des Packages bekommen nur ``send_prompt(prompt, model)`` zu sehen
    (``factcheck_plus.llm_stage.PromptClient``). Debug-Logging und
    Token-Summierung sind SOMAS-Belange und gehören daher in diese Hülle statt
    ins Package.

    Attributes:
        tokens_used: Summe der Tokens über alle Calls dieser Hülle.
        citations: Eingesammelte Quellen-URLs (sofern der Provider welche liefert).
    """

    def __init__(
        self, client: LLMClient, stage: str,
        debug_logger: DebugLogger | None = None, meta: dict | None = None,
    ) -> None:
        """Initialisiert die Hülle.

        Args:
            client: Der echte LLM-Client.
            stage: Stufenname fürs Debug-Log (z.B. "factcheck_plus.s1_refiner").
            debug_logger: Optionaler DebugLogger.
            meta: Zusätzliche Log-Metadaten.
        """
        self._client = client
        self._stage = stage
        self._debug_logger = debug_logger
        self._meta = meta or {}
        self.tokens_used = 0
        self.citations: list[str] = []

    def send_prompt(
        self, prompt: str, model: str, max_tokens: int | None = None,
        cap_reasoning: bool = False,
    ) -> APIResponse:
        """Reicht den Call durch, misst Dauer, loggt und summiert Tokens.

        Args:
            prompt: Der Stufen-Prompt.
            model: Die Modell-ID.
            max_tokens: Antwort-Budget der Stufe (``llm_stage.STAGE_MAX_TOKENS``);
                wird unverändert an den echten Client durchgereicht.
            cap_reasoning: Reasoning-Cap-Wunsch der Stufe (v0.13.2); wird
                unverändert durchgereicht (nur OpenRouter wertet ihn aus).
        """
        log_dir = None
        if self._debug_logger:
            endpoint = (
                getattr(self._client, "BASE_URL", "")
                + getattr(self._client, "CHAT_ENDPOINT", "")
            )
            log_dir = self._debug_logger.log_request(
                provider=getattr(self._client, "PROVIDER_ID", ""),
                model=model,
                endpoint=endpoint,
                prompt=prompt,
                meta={
                    "app_version": APP_VERSION,
                    "feature": "factcheck_plus",
                    "stage": self._stage,
                    **self._meta,
                },
            )

        # v0.13.3: OpenRouter-Stufen bekommen das größere Budget (s.
        # STAGE_MAX_TOKENS_OPENROUTER). Die Anhebung greift nur, wenn die Stufe
        # überhaupt ein Budget anfordert (max_tokens gesetzt) und der echte Client
        # OpenRouter ist — die Provider-Wahl bleibt an dieser Naht, nicht im Package.
        effective_max_tokens = max_tokens
        if (
            max_tokens is not None
            and getattr(self._client, "PROVIDER_ID", "") == "openrouter"
        ):
            effective_max_tokens = STAGE_MAX_TOKENS_OPENROUTER

        start = time.time()
        response = self._client.send_prompt(
            prompt, model, max_tokens=effective_max_tokens,
            cap_reasoning=cap_reasoning,
        )
        duration = time.time() - start
        response.duration_seconds = duration

        self.tokens_used += response.tokens_used or 0
        for citation in response.citations or []:
            if citation and citation not in self.citations:
                self.citations.append(citation)

        if self._debug_logger:
            ok = response.status == APIStatus.RECEIVED
            self._debug_logger.log_response(
                log_dir=log_dir,
                status_code=(
                    response.http_status if response.http_status is not None
                    else (200 if ok else 500)
                ),
                content=response.content,
                tokens=response.token_log_dict(),
                duration=duration,
                model_used=response.model_used,
                citations=response.citations,
                error=None if ok else (response.error_message or "Fehler"),
                # v0.13.1: finish_reason durchreichen — sonst stand im Stage-Log
                # immer "" und verschleppte die Trunkierungs-Diagnose (Teil B).
                finish_reason=response.finish_reason,
                # v0.13.3: Token-Split + Reasoning-Anteil (Datensammlung).
                reasoning_tokens=response.reasoning_tokens,
            )
        return response


class FactcheckPlusWorker(QThread):
    """Worker-Thread für einen Faktencheck-Plus-Lauf (S1–S5).

    Signals:
        status_changed(str): "running" | "done" | "error" | "skipped" | "cancelled".
        stage_changed(str, int, int): Klartext, aktuelle Stufe, Gesamtstufen.
        claim_progress(int, int): geprüfter Claim (1-basiert), Gesamtzahl.
        finished_ok(str, object): rendered_section, FactcheckPlusResult.
        error_occurred(str): Fehlermeldung (nicht fatal für die Analyse).
    """

    status_changed = pyqtSignal(str)
    stage_changed = pyqtSignal(str, int, int)
    claim_progress = pyqtSignal(int, int)
    finished_ok = pyqtSignal(str, object)
    error_occurred = pyqtSignal(str)

    def __init__(
        self,
        config: FactcheckPlusConfig,
        debug_logger: DebugLogger | None = None,
    ) -> None:
        """Initialisiert den Worker.

        Args:
            config: Die Plus-Konfiguration (ungekappte Claims + beide Modelle).
            debug_logger: Optionaler DebugLogger für Request/Response-Logging.
        """
        super().__init__()
        self._config = config
        self._debug_logger = debug_logger
        self._cancelled = False
        self._result = FactcheckPlusResult(config=config)
        self._wrappers: list[_TokenCountingClient] = []

    @property
    def result(self) -> FactcheckPlusResult:
        """Gibt den aktuellen Lauf-Zustand zurück (GUI/Headless-Zugriff)."""
        return self._result

    def cancel(self) -> None:
        """Markiert den Worker als abgebrochen.

        S5 prüft das zwischen den Claim-Calls und gibt die bisherigen Verdikte
        zurück; die früheren Stufen brechen an ihren Prüfpunkten ab.
        """
        self._cancelled = True
        logger.info("FactcheckPlusWorker Abbruch angefordert")

    # --- Lauf -------------------------------------------------------------

    def run(self) -> None:
        """Führt S1–S5 aus und rendert den Abschnitt."""
        cfg = self._config

        if not cfg.claims:
            self._result.status = "skipped"
            self._result.rendered_section = NO_CLAIMS_SECTION
            self.status_changed.emit("skipped")
            self.finished_ok.emit(NO_CLAIMS_SECTION, self._result)
            return

        analysis_client = self._make_client(cfg.analysis_model)
        if analysis_client is None:
            return
        research_client = self._make_client(cfg.research_model)
        if research_client is None:
            return

        self._result.status = "running"
        self.status_changed.emit("running")

        try:
            refined = self._run_refiner(analysis_client)
            if refined is None:
                return

            mappings = self._run_mapper(analysis_client, refined)
            if mappings is None:
                return

            selection, selected = self._run_scorer(refined, mappings)
            if selection is None:
                return

            cards = self._run_planner(analysis_client, selected)
            if cards is None:
                return

            verdicts = self._run_verifier(research_client, selected, cards)
            if verdicts is None:
                return

            self._finish(refined, selection, verdicts)

        except StageError as exc:
            logger.warning("FactcheckPlusWorker: Stufe fehlgeschlagen — %s", exc)
            if not self._cancelled:
                self._fail(str(exc))
        except Exception as exc:  # noqa: BLE001 — Plus-Fehler darf Analyse nicht verlieren
            logger.exception("FactcheckPlusWorker: unerwarteter Fehler")
            if not self._cancelled:
                self._fail(str(exc))

    # --- Stufen -----------------------------------------------------------

    def _run_refiner(self, client: LLMClient) -> list[RefinedClaim] | None:
        """S1: Roh-Behauptungen → atomare Prüfeinheiten."""
        self._emit_stage("Verfeinere Behauptungen …", 1)
        if self._cancelled:
            return None
        wrapper = self._wrap(client, "s1_refiner")
        refined = ClaimRefiner(wrapper, self._config.analysis_model.model_id).refine(
            self._config.claims,
            core_thesis=self._config.core_thesis,
            source_hint=self._config.source_hint,
        )
        self._result.refined_count = len(refined)
        logger.info("S1: %d Roh-Claims → %d Prüfeinheiten",
                    len(self._config.claims), len(refined))
        return None if self._cancelled else refined

    def _run_mapper(
        self, client: LLMClient, refined: list[RefinedClaim],
    ) -> list[ArgumentMapping] | None:
        """S2: Prüfeinheiten → Argumentrolle + Impact + Ratings."""
        self._emit_stage("Gewichte Argumente …", 2)
        if self._cancelled:
            return None
        wrapper = self._wrap(client, "s2_mapper")
        mappings = ArgumentMapper(wrapper, self._config.analysis_model.model_id).map_claims(
            refined, core_thesis=self._config.core_thesis,
        )
        return None if self._cancelled else mappings

    def _run_scorer(
        self, refined: list[RefinedClaim], mappings: list[ArgumentMapping],
    ) -> tuple[SelectionResult | None, list[RefinedClaim] | None]:
        """S3: deterministische Auswahl (kein LLM, kein Netzwerk).

        Die selektierten Claims werden in **Auswahlrang-Reihenfolge** (Klasse A
        vor B vor C, innerhalb der Klasse nach priority) zurückgegeben, nicht in
        Refiner-Reihenfolge. Das ist kein Kosmetikdetail:

          - Der Bericht liest sich top-down nach argumentativem Gewicht — sonst
            stünde der schwächste Claim oben und das Modul widerspräche seinem
            eigenen Zweck.
          - Bricht der Nutzer nach 2 von 8 Claims ab, sind die beiden
            WICHTIGSTEN geprüft, nicht zwei beliebige.
        """
        self._emit_stage("Wähle Behauptungen aus (Policy) …", 3)
        if self._cancelled:
            return None, None
        selection = PolicyScorer.from_file().select(
            join_claims(refined, mappings), budget=self._config.budget,
        )
        self._result.selected_count = len(selection.selected_ids)
        by_id = {rc.claim_id: rc for rc in refined}
        selected = [by_id[cid] for cid in selection.selected_ids]
        logger.info(
            "S3: %d von %d Prüfeinheiten selektiert (Policy %s, Budget %d)",
            len(selected), len(refined), selection.policy_version, self._config.budget,
        )
        if self._cancelled:
            return None, None
        return selection, selected

    def _run_planner(
        self, client: LLMClient, selected: list[RefinedClaim],
    ) -> list[ResearchCard] | None:
        """S4: Recherchekarte je selektiertem Claim."""
        if not selected:
            # Alles weggefiltert (z.B. nur Basisfakten/Meinungen) — kein Planner-Call.
            return []
        self._emit_stage("Plane Recherche …", 4)
        if self._cancelled:
            return None
        wrapper = self._wrap(client, "s4_planner")
        cards = ResearchPlanner(wrapper, self._config.analysis_model.model_id).plan(
            selected, core_thesis=self._config.core_thesis,
        )
        return None if self._cancelled else cards

    def _run_verifier(
        self, client: LLMClient, selected: list[RefinedClaim],
        cards: list[ResearchCard],
    ) -> list[ClaimVerdict] | None:
        """S5: ein Recherche-/Verdikt-Call PRO Claim."""
        if not selected:
            return []
        self._emit_stage("Recherchiere …", 5)
        if self._cancelled:
            return None

        wrapper = self._wrap(client, "s5_verifier")
        verifier = ClaimVerifier(
            wrapper,
            self._config.research_model.model_id,
            source_hint=self._config.source_hint,
            language=self._config.language,
        )
        verdicts = verifier.verify_all(
            selected, cards,
            on_progress=self._on_claim_progress,
            should_cancel=lambda: self._cancelled,
        )
        self._result.verified_count = len(verdicts)
        self._result.failed_count = sum(1 for v in verdicts if v.failed)
        return verdicts

    # --- Abschluss --------------------------------------------------------

    def _finish(
        self, refined: list[RefinedClaim], selection: SelectionResult,
        verdicts: list[ClaimVerdict],
    ) -> None:
        """Aggregiert, rendert und meldet das Ergebnis."""
        self._result.tokens_used = sum(w.tokens_used for w in self._wrappers)
        self._result.citations = self._collect_citations()

        context = build_render_context(
            claims=refined,
            selection=selection,
            verdicts=verdicts,
            raw_claim_count=len(self._config.claims),
            model_name=(
                self._config.research_model.model_name
                or self._config.research_model.model_id
            ),
            provider_name=(
                self._config.research_model.provider_name
                or self._config.research_model.provider_id
            ),
            date=datetime.now().strftime("%d.%m.%Y"),
            web_unverified=self._config.web_unverified,
        )
        rendered = self._render(context)
        self._result.rendered_section = rendered

        # Ein Abbruch ist kein Fehler: Das Teilergebnis ist gültig und wird
        # angehängt — das Template weist den Abbruch sichtbar aus.
        status = "cancelled" if self._cancelled else "done"
        self._result.status = status
        self.status_changed.emit(status)
        self.finished_ok.emit(rendered, self._result)

    def _render(self, context: dict) -> str:
        """Rendert den Plus-Abschnitt via Jinja2 (wie der Classic-Weg)."""
        env = Environment(
            loader=FileSystemLoader(get_template_dir()),
            trim_blocks=True,
            lstrip_blocks=True,
        )
        return env.get_template("somas_verification_plus.txt").render(**context)

    # --- Helfer -----------------------------------------------------------

    def _make_client(self, model: ModelChoice) -> LLMClient | None:
        """Baut einen Client oder meldet den fehlenden Key (nicht fatal)."""
        key = get_api_key(model.provider_id)
        if not key:
            name = model.provider_name or model.provider_id
            self._fail(f"Kein API-Key für Provider '{name}' konfiguriert.")
            return None
        return create_client(model.provider_id, key)

    def _wrap(self, client: LLMClient, stage: str) -> _TokenCountingClient:
        """Hüllt einen Client für Debug-Logging und Token-Zählung einer Stufe."""
        wrapper = _TokenCountingClient(
            client, f"factcheck_plus.{stage}", self._debug_logger,
            meta={
                "language": self._config.language,
                "budget": self._config.budget,
                "raw_claims": len(self._config.claims),
            },
        )
        self._wrappers.append(wrapper)
        return wrapper

    def _collect_citations(self) -> list[str]:
        """Sammelt Provider-Quellen über alle Stufen, dedupliziert, in Reihenfolge."""
        seen: set[str] = set()
        result: list[str] = []
        for wrapper in self._wrappers:
            for citation in wrapper.citations:
                if citation not in seen:
                    seen.add(citation)
                    result.append(citation)
        return result

    def _emit_stage(self, text: str, index: int) -> None:
        """Meldet den Stufenwechsel an die GUI."""
        logger.info("FactcheckPlus Stufe %d/%d: %s", index, TOTAL_STAGES, text)
        self.stage_changed.emit(text, index, TOTAL_STAGES)

    def _on_claim_progress(self, index: int, total: int, claim_id: str) -> None:
        """Callback aus S5 — reicht den Claim-Fortschritt als Signal weiter."""
        self.stage_changed.emit(f"Recherchiere Claim {index}/{total} …", 5, TOTAL_STAGES)
        self.claim_progress.emit(index, total)

    def _fail(self, message: str) -> None:
        """Markiert den Lauf als fehlgeschlagen (nicht fatal) und meldet ihn."""
        self._result.status = "error"
        self._result.error_message = message
        self.status_changed.emit("error")
        self.error_occurred.emit(message)
