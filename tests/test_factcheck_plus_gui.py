"""GUI-Flow-Tests für Faktencheck Plus (v0.13.0, PR 4).

Deckt Spec §4 ab:
- Die SpinBox trägt zwei Bedeutungen (Cap vs. Deep-Research-Budget) — Label,
  Wertebereich und Wert wechseln mit dem Modus, und beide Werte überleben den
  Wechsel in getrennten Preference-Keys.
- Der Ausschluss mit dem Modellvergleich gilt auch für Plus (Plus hängt an der
  Verifikations-Checkbox, die den Ausschluss bereits trägt).
- Der Start-Pfad verzweigt korrekt: Plus → FactcheckPlusWorker (ungekappt,
  Analyse-Modell + Recherchemodell), Classic → VerificationWorker (gekappt).
- Der Race-Schutz kennt BEIDE Worker.

Läuft headless über die Qt-Offscreen-Plattform; Worker-Start und Dialoge sind
gestubbt — geprüft wird die Entscheidungs- und Zustandslogik in main_window.

Lauf (ohne pytest):  QT_QPA_PLATFORM=offscreen python tests/test_factcheck_plus_gui.py
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PyQt6.QtWidgets import QApplication, QMessageBox

import src.gui.main_window as mw
from src.gui.main_window import (
    CLASSIC_SPIN_LABEL, DEFAULT_PLUS_BUDGET, PLUS_BUDGET_RANGE, PLUS_SPIN_LABEL,
)

ANALYSIS_WITH_FAKTENCHECK = """### FRAMING
Rahmen.

### KERNTHESE
Die Aktivitaeten der IRGC verursachen in Europa massive Kosten.

### ELABORATION
Text.

### IMPLIKATION
Text.

### FAKTENCHECK
**Meinungen:** 1. Das ist unverantwortlich.
**Interpretationen:** 1. Ein politischer Erfolg.
**Behauptungen (überprüfbar):** 1. Die Kosten liegen bei 100 Mrd. Euro pro Jahr.
2. Die IRGC ist seit 2023 gelistet. [Basisfakt]
3. Die Analyse stammt von einem Institut.
"""


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def win(app, monkeypatch, tmp_path):
    """Frisches MainWindow mit isolierten Preferences und stummen Dialogen."""
    prefs: dict = {}
    monkeypatch.setattr(mw, "load_preferences", lambda: dict(prefs))
    monkeypatch.setattr(mw, "save_preferences", lambda p: prefs.update(p))
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: None)
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: None)
    monkeypatch.setattr(QMessageBox, "critical", lambda *a, **k: None)
    window = mw.MainWindow()
    window._prefs_spy = prefs
    return window


class _FakeWorker:
    """Worker-Doppelgänger: fängt start() ab, damit kein Thread/Netzwerk läuft."""

    instances: list = []

    def __init__(self, config, debug_logger=None):
        self.config = config
        self.started = False
        type(self).instances.append(self)

    def __getattr__(self, name):
        # status_changed/finished_ok/... — Signale schlucken.
        class _Sig:
            def connect(self, *_a, **_k):
                return None
        return _Sig()

    def start(self):
        self.started = True

    def isRunning(self):
        return self.started

    def cancel(self):
        self.started = False

    def wait(self, _ms=0):
        return True


@pytest.fixture
def workers(monkeypatch):
    """Ersetzt beide Worker durch Doppelgänger und liefert die Instanzlisten."""
    class PlusWorker(_FakeWorker):
        instances: list = []

    class ClassicWorker(_FakeWorker):
        instances: list = []

    monkeypatch.setattr(mw, "FactcheckPlusWorker", PlusWorker)
    monkeypatch.setattr(mw, "VerificationWorker", ClassicWorker)
    return {"plus": PlusWorker, "classic": ClassicWorker}


def _choice(provider: str = "perplexity", model: str = "sonar-pro") -> mw.ModelChoice:
    """Baut eine ModelChoice für Tests.

    Args:
        provider: Provider-ID (Default: web-fähiges Perplexity).
        model: Modell-ID.

    Returns:
        Die ModelChoice mit Name = ID.
    """
    return mw.ModelChoice(
        provider_id=provider, model_id=model,
        model_name=model, provider_name=provider,
    )


# --- SpinBox: zwei Bedeutungen, eine Box ----------------------------------

def test_spin_starts_in_classic_mode(win) -> None:
    assert win.verify_plus_checkbox.isChecked() is False
    assert win.verify_max_label.text() == CLASSIC_SPIN_LABEL
    assert (win.verify_max_spin.minimum(), win.verify_max_spin.maximum()) == (0, 100)


def test_plus_toggle_switches_the_spin_meaning(win) -> None:
    win.verify_max_spin.setValue(25)
    win.verify_plus_checkbox.setChecked(True)

    assert win.verify_max_label.text() == PLUS_SPIN_LABEL
    assert (win.verify_max_spin.minimum(), win.verify_max_spin.maximum()) == PLUS_BUDGET_RANGE
    assert win.verify_max_spin.value() == DEFAULT_PLUS_BUDGET


def test_both_values_survive_a_mode_round_trip(win) -> None:
    """Der Cap darf nicht vom Budget überschrieben werden — und umgekehrt."""
    win.verify_max_spin.setValue(25)       # Classic-Cap
    win.verify_plus_checkbox.setChecked(True)
    win.verify_max_spin.setValue(12)       # Plus-Budget
    win.verify_plus_checkbox.setChecked(False)

    assert win.verify_max_spin.value() == 25, "Classic-Cap überlebt"
    win.verify_plus_checkbox.setChecked(True)
    assert win.verify_max_spin.value() == 12, "Plus-Budget überlebt"


def test_values_go_into_separate_preference_keys(win) -> None:
    win.verify_max_spin.setValue(25)
    win.verify_plus_checkbox.setChecked(True)
    win.verify_max_spin.setValue(12)

    prefs = win._prefs_spy
    assert prefs["verification_max_claims"] == 25
    assert prefs["factcheck_plus_budget"] == 12
    assert prefs["factcheck_plus_enabled"] is True


def test_mode_switch_does_not_write_the_wrong_key(win) -> None:
    """Regression: Range/Wert-Umsetzen darf keinen valueChanged-Schreiber auslösen."""
    win.verify_max_spin.setValue(25)
    win._prefs_spy.clear()
    win.verify_plus_checkbox.setChecked(True)

    assert "verification_max_claims" not in win._prefs_spy, (
        "Der Moduswechsel hat den Classic-Cap überschrieben"
    )
    assert win._verification_max_claims == 25


def test_plus_preference_is_restored_on_startup(app, monkeypatch) -> None:
    prefs = {"factcheck_plus_enabled": True, "factcheck_plus_budget": 15,
             "verification_max_claims": 42}
    monkeypatch.setattr(mw, "load_preferences", lambda: dict(prefs))
    monkeypatch.setattr(mw, "save_preferences", lambda p: None)
    window = mw.MainWindow()

    assert window.verify_plus_checkbox.isChecked() is True
    assert window.verify_max_label.text() == PLUS_SPIN_LABEL
    assert window.verify_max_spin.value() == 15


# --- Ausschluss mit dem Modellvergleich -----------------------------------

def test_plus_is_excluded_with_comparison_via_the_verify_checkbox(win) -> None:
    """Plus hängt an der Verify-Checkbox, die den Ausschluss bereits trägt."""
    win.verify_checkbox.setChecked(True)
    win.verify_plus_checkbox.setChecked(True)
    assert win.compare_checkbox.isEnabled() is False

    win.compare_checkbox.setEnabled(True)
    win.compare_checkbox.setChecked(True)
    assert win.verify_checkbox.isChecked() is False, "Vergleich schaltet Verifikation ab"
    # …und damit auch den Plus-Pfad: ohne Verify-Checkbox startet keine Stufe 2.


def test_plus_checkbox_lives_inside_the_verify_section(win) -> None:
    """Sichtbar nur bei aktiver Verifikation (Spec §4).

    Geprüft wird `isHidden()`, nicht `isVisible()`: Ohne gezeigtes Fenster ist
    headless jedes Widget „unsichtbar", `isHidden()` spiegelt dagegen die
    explizit gesetzte Sichtbarkeit.
    """
    win.verify_checkbox.setChecked(False)
    assert win.verify_section.isHidden() is True
    win.verify_checkbox.setChecked(True)
    assert win.verify_section.isHidden() is False
    # Der Plus-Schalter sitzt IN der Sektion — er teilt ihr Schicksal.
    assert win.verify_plus_checkbox.parent() is not None


# --- Start-Pfad -----------------------------------------------------------

def _prepare(win, plus: bool) -> None:
    """Versetzt das Fenster in einen startbereiten Verifikations-Zustand.

    Args:
        win: Das MainWindow.
        plus: True = Plus-Modus, False = Classic.
    """
    win._verification_base_text = ANALYSIS_WITH_FAKTENCHECK
    win.verify_checkbox.setChecked(True)
    win.verify_plus_checkbox.setChecked(plus)


def test_plus_mode_starts_the_plus_worker(win, workers, monkeypatch) -> None:
    _prepare(win, plus=True)
    monkeypatch.setattr(
        win, "_current_analysis_choice", lambda: _choice("anthropic", "claude-sonnet-4-6")
    )

    win._start_verification(_choice())

    assert len(workers["plus"].instances) == 1
    assert workers["classic"].instances == []
    cfg = workers["plus"].instances[0].config
    assert cfg.research_model.model_id == "sonar-pro"
    assert cfg.analysis_model.model_id == "claude-sonnet-4-6"


def test_classic_mode_starts_the_classic_worker(win, workers) -> None:
    _prepare(win, plus=False)

    win._start_verification(_choice())

    assert len(workers["classic"].instances) == 1
    assert workers["plus"].instances == []


def test_plus_passes_claims_uncapped_but_without_basisfakten(win, workers, monkeypatch) -> None:
    """Im Plus-Modus wählt der Scorer aus — die GUI kappt nicht (Spec §4)."""
    _prepare(win, plus=True)
    win.verify_max_spin.setValue(1)  # Budget 1 — darf die Liste NICHT kappen
    monkeypatch.setattr(win, "_current_analysis_choice", lambda: _choice("anthropic", "m"))

    win._start_verification(_choice())

    cfg = workers["plus"].instances[0].config
    assert len(cfg.claims) == 2, "beide Nicht-Basisfakt-Claims, ungekappt"
    assert cfg.budget == 1
    assert not any("Basisfakt" in c for c in cfg.claims)
    assert not any("2023 gelistet" in c for c in cfg.claims), "Basisfakt fliegt raus"


def test_plus_extracts_the_core_thesis_as_context(win, workers, monkeypatch) -> None:
    """Ohne Kernthese fehlt S2 der Maßstab für thesis_proximity."""
    _prepare(win, plus=True)
    monkeypatch.setattr(win, "_current_analysis_choice", lambda: _choice("anthropic", "m"))

    win._start_verification(_choice())

    cfg = workers["plus"].instances[0].config
    assert "IRGC" in cfg.core_thesis
    assert "massive Kosten" in cfg.core_thesis


def test_plus_without_analysis_model_fails_gracefully(win, workers, monkeypatch) -> None:
    """Kein Analyse-Modell → Hinweis im Abschnitt, kein Absturz, kein Worker."""
    _prepare(win, plus=True)
    monkeypatch.setattr(win, "_current_analysis_choice", lambda: None)

    win._start_verification(_choice())

    assert workers["plus"].instances == []
    assert "Kein Analyse-Modell" in win.result_text.toPlainText()


def test_plus_marks_web_unverified_for_non_web_models(win, workers, monkeypatch) -> None:
    _prepare(win, plus=True)
    monkeypatch.setattr(win, "_current_analysis_choice", lambda: _choice("anthropic", "m"))

    win._start_verification(_choice("anthropic", "claude-sonnet-4-6"))

    assert workers["plus"].instances[0].config.web_unverified is True


# --- Analyse-Modell-Auflösung ---------------------------------------------
#
# Diese Tests rufen `_current_analysis_choice` ECHT auf. Die Start-Pfad-Tests
# oben stubben es weg — dadurch blieb die Methode ungetestet, und genau darin
# steckten zwei Fehler (CodeRabbit, PR #60): ein Aufruf einer nicht existenten
# ModelSelector-Methode und der Griff auf den falschen Selector.

def _select_provider(win: "mw.MainWindow", provider_id: str) -> None:
    """Wählt einen Provider in der Combo — er MUSS vorhanden sein.

    Bewusst ohne `skip`-Ausweg: Die Provider stammen aus dem versionierten
    `src/config/api_providers.json`, sind also in jeder Arbeitskopie identisch.
    Fehlt einer, ist das eine Regression und kein Grund, den Test zu überspringen.

    Args:
        win: Das MainWindow.
        provider_id: Die zu wählende Provider-ID.

    Raises:
        AssertionError: Wenn der Provider nicht angeboten wird.
    """
    for i in range(win.provider_combo.count()):
        if win.provider_combo.itemData(i) == provider_id:
            win.provider_combo.setCurrentIndex(i)
            return
    raise AssertionError(
        f"Provider '{provider_id}' fehlt in der Combo — erwartet aus "
        f"api_providers.json. Angeboten: "
        f"{[win.provider_combo.itemData(i) for i in range(win.provider_combo.count())]}"
    )


def test_analysis_choice_uses_the_combo_for_non_openrouter(win) -> None:
    """Nur OpenRouter nutzt den filterbaren Selector — alle anderen die Combo.

    Der Regressionstest zum PR-#60-Blocker: `_current_analysis_choice` griff auf
    `model_selector` zu, der für Nicht-OpenRouter-Provider `None` liefert — Plus
    wäre für den Default-Provider Anthropic nie gestartet.
    """
    _select_provider(win, "anthropic")
    assert win.model_combo.count() > 0, (
        "Anthropic-Modelle fehlen — api_providers.json ist versioniert, das wäre "
        "eine Regression (siehe tests/test_model_lists_consistency.py)"
    )
    win.model_combo.setCurrentIndex(0)
    expected_id = win.model_combo.currentData()

    choice = win._current_analysis_choice()

    assert choice is not None, "Nicht-OpenRouter-Provider muss ein Modell liefern"
    assert choice.provider_id == "anthropic"
    assert choice.model_id == expected_id
    assert choice.model_name, "Anzeigename darf nicht leer sein"
    assert choice.model_name != choice.model_id, "Anzeigename statt roher ID erwartet"


def test_analysis_choice_returns_none_without_a_model(win, monkeypatch) -> None:
    """Ohne gewähltes Modell liefert die Auflösung None (statt zu werfen)."""
    monkeypatch.setattr(win, "_get_active_model_id", lambda: None)
    assert win._current_analysis_choice() is None


def test_analysis_choice_matches_the_analysis_run(win) -> None:
    """Plus MUSS dasselbe Modell nehmen, mit dem auch analysiert wird (Spec §8.3)."""
    _select_provider(win, "anthropic")
    win.model_combo.setCurrentIndex(0)

    choice = win._current_analysis_choice()

    assert choice is not None
    assert choice.model_id == win._get_active_model_id()


# --- Race-Schutz ----------------------------------------------------------

def test_running_check_knows_both_workers(win, workers, monkeypatch) -> None:
    """Regression: Der Race-Schutz darf keinen der beiden Worker vergessen."""
    assert win._verification_is_running() is False

    _prepare(win, plus=True)
    monkeypatch.setattr(win, "_current_analysis_choice", lambda: _choice("anthropic", "m"))
    win._start_verification(_choice())

    assert win._verification_is_running() is True, "Plus-Lauf wird erkannt"


def test_running_plus_locks_the_source_and_the_mode(win, workers, monkeypatch) -> None:
    _prepare(win, plus=True)
    monkeypatch.setattr(win, "_current_analysis_choice", lambda: _choice("anthropic", "m"))
    win._start_verification(_choice())

    assert win.url_input.isEnabled() is False, "Quelle gesperrt (Stale-State-Riegel)"
    assert win.btn_get_meta.isEnabled() is False
    assert win.verify_plus_checkbox.isEnabled() is False, "Modus während des Laufs fix"
    assert win.verify_online_checkbox.isEnabled() is False
    assert win.btn_verify_cancel.isEnabled() is True


def test_cancel_stops_the_plus_worker(win, workers, monkeypatch) -> None:
    _prepare(win, plus=True)
    monkeypatch.setattr(win, "_current_analysis_choice", lambda: _choice("anthropic", "m"))
    win._start_verification(_choice())

    win._on_verify_cancel()

    assert workers["plus"].instances[0].started is False
    assert win.btn_verify_cancel.isEnabled() is False


def test_retry_is_blocked_while_plus_runs(win, workers, monkeypatch) -> None:
    _prepare(win, plus=True)
    monkeypatch.setattr(win, "_current_analysis_choice", lambda: _choice("anthropic", "m"))
    win._start_verification(_choice())
    workers["plus"].instances.clear()

    win._on_verify_retry()

    assert workers["plus"].instances == [], "kein zweiter Lauf während eines Laufs"


def test_mode_switch_disables_stale_retry(win) -> None:
    """Ein Abschnitt aus dem anderen Modus darf nicht per Retry ersetzt werden."""
    win.btn_verify_retry.setEnabled(True)
    win.verify_plus_checkbox.setChecked(True)
    assert win.btn_verify_retry.isEnabled() is False


# --- Verspätete Callbacks (Lauf-ID-Riegel) --------------------------------

def _plus_result(status: str = "done") -> mw.FactcheckPlusResult:
    """Baut ein fertiges Plus-Ergebnis für die Callback-Tests.

    Args:
        status: Der Lauf-Status ("done" | "cancelled" | "skipped").

    Returns:
        Ein FactcheckPlusResult mit plausiblen Zählwerten.
    """
    cfg = mw.FactcheckPlusConfig(
        claims=["x"], analysis_model=_choice("anthropic", "m"),
        research_model=_choice(),
    )
    result = mw.FactcheckPlusResult(config=cfg, status=status)
    result.refined_count = 4
    result.selected_count = 2
    result.verified_count = 2
    return result


def test_late_plus_result_is_discarded(win) -> None:
    """Ein Ergebnis aus einem toten Lauf darf nicht in die neue Analyse schreiben.

    Anders als der Classic-Worker meldet der Plus-Worker auch nach `cancel()`
    sein (gültiges) Teilergebnis. Steckt er noch in einem Claim-Call, läuft
    `wait(2000)` ins Timeout und das Signal kommt NACH dem Quellenwechsel.
    """
    win.result_text.setPlainText("Neue Analyse")
    win._plus_active_run_id = 5

    win._on_plus_finished("### ALTER ABSCHNITT", _plus_result(), run_id=4)

    assert win.result_text.toPlainText() == "Neue Analyse", (
        "Verspätetes Plus-Ergebnis hat die neue Analyse überschrieben"
    )


def test_late_plus_error_is_discarded(win) -> None:
    """Auch ein Fehler aus einem toten Lauf darf die neue Analyse nicht anfassen."""
    win.result_text.setPlainText("Neue Analyse")
    win._plus_active_run_id = 5

    win._on_plus_error("Alter Fehler", run_id=4)

    assert win.result_text.toPlainText() == "Neue Analyse"


def test_current_plus_result_is_applied(win) -> None:
    """Gegenprobe: Der Riegel darf das AKTUELLE Ergebnis nicht mitverwerfen."""
    win._verification_base_text = "Analyse"
    win._plus_active_run_id = 5

    win._on_plus_finished("### PLUS", _plus_result(), run_id=5)

    assert "### PLUS" in win.result_text.toPlainText()


def test_new_source_invalidates_a_running_plus_run(win, workers, monkeypatch) -> None:
    """Der Quellenwechsel muss den laufenden Plus-Lauf für tot erklären.

    Abbruch und Lauf-ID-Erhöhung stehen ganz oben in `_on_get_meta`, vor dem
    URL-Check — mit leerer URL steigt die Methode direkt danach aus. So wird
    genau dieser Riegel geprüft, ohne einen Metadaten-Abruf auszulösen.
    """
    _prepare(win, plus=True)
    monkeypatch.setattr(win, "_current_analysis_choice", lambda: _choice("anthropic", "m"))
    win._start_verification(_choice())
    run_id_before = win._plus_active_run_id
    assert workers["plus"].instances[0].started is True

    win.url_input.setText("")
    win._on_get_meta()

    assert win._plus_active_run_id > run_id_before, (
        "Lauf-ID nicht hochgezählt — verspätete Callbacks könnten durchschlagen"
    )
    assert workers["plus"].instances[0].started is False, "alter Lauf abgebrochen"

    # Gegenprobe: Das jetzt eintreffende Ergebnis des toten Laufs prallt ab.
    win.result_text.setPlainText("Neue Analyse")
    win._on_plus_finished("### ALTER PLUS", _plus_result(), run_id=run_id_before)
    assert win.result_text.toPlainText() == "Neue Analyse"


def test_user_cancel_keeps_the_run_valid(win, workers, monkeypatch) -> None:
    """Der Nutzer-Abbruch verwirft NICHT: das Teilergebnis ist gewollt."""
    _prepare(win, plus=True)
    monkeypatch.setattr(win, "_current_analysis_choice", lambda: _choice("anthropic", "m"))
    win._start_verification(_choice())
    run_id = win._plus_active_run_id

    win._on_verify_cancel()

    assert win._plus_active_run_id == run_id, (
        "Nutzer-Abbruch darf das Teilergebnis nicht wegwerfen"
    )


# --- Fehleranzeige --------------------------------------------------------

def test_plus_error_shows_a_dialog(win, monkeypatch) -> None:
    """Wie beim Classic-Weg: Der Fehler muss sichtbar sein, nicht nur im Text."""
    shown: list = []
    monkeypatch.setattr(
        QMessageBox, "warning", lambda _p, title, msg, *a, **k: shown.append((title, msg))
    )

    win._on_plus_error("Kein Analyse-Modell gewählt")

    assert len(shown) == 1
    assert "Kein Analyse-Modell gewählt" in shown[0][1]
    assert "Faktencheck Plus fehlgeschlagen" in win.result_text.toPlainText()


def main() -> None:
    """Hinweis: Diese Suite braucht pytest (Fixtures/monkeypatch)."""
    print("Bitte mit pytest ausführen:  python -m pytest tests/test_factcheck_plus_gui.py")


if __name__ == "__main__":
    main()
