"""GUI-Flow-Tests: Leer-Inhalt-Retry-Pfad + Abbruch während Retry.

Deckt den Robustheits-Fix ab: Leer-Inhalt (HTTP 200, aber Content leer — Reasoning
verbrennt das Budget) durchläuft denselben Eskalationspfad wie eine Trunkierung
(1× sichtbarer Auto-Retry, dann offener „Modelllauf fehlgeschlagen"); der
Abbrechen-Button greift auch WÄHREND des Auto-Retrys.

Läuft headless über die Qt-Offscreen-Plattform. `_start_api_call` wird gestubbt,
damit kein echter Worker/Netzwerk-Call startet — geprüft wird die Entscheidungs-
und Zustandslogik in main_window.

Lauf (ohne pytest):  QT_QPA_PLATFORM=offscreen python tests/test_analysis_retry_cancel.py
"""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PyQt6.QtWidgets import QApplication, QMessageBox

from src.core.api_client import APIResponse, APIStatus, build_empty_content_error
import src.gui.main_window as mw


EMPTY_MSG = build_empty_content_error("finish_reason", "length")


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def win(app, monkeypatch):
    """Frisches MainWindow mit gestubbtem _start_api_call und stummen Dialogen."""
    # Modale QMessageBox-Aufrufe im Test unterdrücken (würden sonst blockieren).
    monkeypatch.setattr(
        QMessageBox, "warning",
        lambda *a, **k: QMessageBox.StandardButton.Ok, raising=True,
    )
    monkeypatch.setattr(
        QMessageBox, "information",
        lambda *a, **k: QMessageBox.StandardButton.Ok, raising=True,
    )
    w = mw.MainWindow()

    calls: list[dict] = []

    def fake_start(prompt, require_faktencheck=False, is_retry=False):
        calls.append(
            {"prompt": prompt, "require_faktencheck": require_faktencheck,
             "is_retry": is_retry}
        )
        # Neuen aktiven Lauf simulieren (wie der echte _start_api_call).
        w._api_request_seq += 1
        w._api_active_request_id = w._api_request_seq
        w.btn_api_cancel.setEnabled(True)

    monkeypatch.setattr(w, "_start_api_call", fake_start)
    w._start_calls = calls
    yield w
    w.close()


def test_empty_content_triggers_retry(win):
    """Erster Leer-Inhalt → sichtbarer Auto-Retry statt hartem Fehlerdialog."""
    win._is_rework = False
    win._analysis_prompt = "PROMPT"
    win._analysis_requires_faktencheck = False
    win._analysis_retry_count = 0
    win._api_active_request_id = 5

    win._on_api_error(EMPTY_MSG, request_id=5)

    assert win._analysis_retry_count == 1
    assert len(win._start_calls) == 1
    assert win._start_calls[0]["is_retry"] is True
    assert win._start_calls[0]["prompt"] == "PROMPT"
    assert "erneuter versuch" in win.result_text.toPlainText().lower()


def test_second_empty_open_failure(win):
    """Zweiter Leer-Inhalt (Retry verbraucht) → offener Fehlschlag, KEIN Retry,
    Fehlertext inkl. finish_reason bleibt erhalten."""
    win._is_rework = False
    win._analysis_prompt = "PROMPT"
    win._analysis_retry_count = 1  # Auto-Retry bereits verbraucht
    win._api_active_request_id = 6
    win.btn_api_cancel.setEnabled(True)

    win._on_api_error(EMPTY_MSG, request_id=6)

    assert len(win._start_calls) == 0
    txt = win.result_text.toPlainText()
    assert "fehlgeschlagen" in txt.lower()
    assert "finish_reason=length" in txt
    # Terminaler Zustand: Abbrechen deaktiviert
    assert win.btn_api_cancel.isEnabled() is False


def test_cancel_during_retry(win):
    """Abbrechen während des Auto-Retrys: Worker wird gecancelt, Lauf invalidiert,
    Retry-Kontext neutralisiert; verspätete Antwort/Fehler lösen keinen Retry aus."""
    class FakeWorker:
        def __init__(self):
            self.cancelled = False

        def isRunning(self):
            return True

        def cancel(self):
            self.cancelled = True

    fw = FakeWorker()
    win._api_worker = fw
    win._analysis_prompt = "PROMPT"
    win._analysis_retry_count = 1
    win._api_active_request_id = 7
    win.btn_api_cancel.setEnabled(True)

    win._on_api_cancel()

    assert fw.cancelled is True
    assert win._api_active_request_id == 0
    assert win._analysis_prompt == ""
    assert win.btn_api_cancel.isEnabled() is False

    # Verspätete (ungültige) Antwort des abgebrochenen Retry-Laufs → verworfen.
    late = APIResponse(status=APIStatus.RECEIVED, content="", finish_reason="length")
    win._on_api_response(late, request_id=7)
    assert len(win._start_calls) == 0
    # Verspäteter Leer-Inhalt-Fehler des abgebrochenen Laufs → ebenfalls verworfen.
    win._on_api_error(EMPTY_MSG, request_id=7)
    assert len(win._start_calls) == 0


def test_truncation_still_retries(win):
    """Regression: trunkierte (RECEIVED, finish_reason=length) Analyse eskaliert
    weiterhin in genau einen Auto-Retry."""
    win._is_rework = False
    win._analysis_prompt = "PROMPT"
    win._analysis_requires_faktencheck = False
    win._analysis_retry_count = 0
    win._api_active_request_id = 8

    resp = APIResponse(
        status=APIStatus.RECEIVED, content="### FRAMING\nnur ein Anfang",
        finish_reason="length",
    )
    win._on_api_response(resp, request_id=8)

    assert win._analysis_retry_count == 1
    assert len(win._start_calls) == 1
    assert win._start_calls[0]["is_retry"] is True


def test_hard_error_no_retry(win):
    """Regression: harter Transport-/HTTP-Fehler → hartem Dialog, KEIN Auto-Retry."""
    win._is_rework = False
    win._analysis_prompt = "PROMPT"
    win._analysis_retry_count = 0
    win._api_active_request_id = 9

    win._on_api_error("HTTP 402: Insufficient credits", request_id=9)

    assert len(win._start_calls) == 0
    assert win._analysis_retry_count == 0


def main():
    app = QApplication.instance() or QApplication([])  # noqa: F841
    # Minimaler Selbstlauf ohne pytest-Fixtures ist nicht vorgesehen (Fixtures
    # kapseln Stubbing/Dialog-Unterdrückung). Bitte über pytest ausführen.
    print("Bitte über pytest ausführen: pytest tests/test_analysis_retry_cancel.py")


if __name__ == "__main__":
    main()
