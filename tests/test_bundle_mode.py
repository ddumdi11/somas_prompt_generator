"""Quellenbündel-Modus, Stufe 1 (v0.16.0) — Spec ``SOMAS_v0.16.0_SPEC_buendel.md`` §5.

Deckt die Spec-Tests 1–9 ab, dazu die PO-Entscheidungen vom 2026-10-27:
- Bündel-Template gewinnt auch gegen Presets mit eigenem Transkript-Template
  (Musik, Songstruktur).
- B4-Reset beim Video-Laden nur bei echtem Quellenwechsel (nicht beim ersten
  Video der Sitzung).
- „Ersetzen" = eine Bearbeitung entfernt den gesamten bisherigen Inhalt.
Außerdem der erwartete Nebeneffekt (Spec §4): Der Modellvergleich mit
Transkript-Eingabe erbt den Bündel-Modus über denselben Builder.

Fixture ``tests/fixtures/bundle_musk_starlink_v1.txt``: das reale Musk/Starlink-
Bündel (Proben 4/7) in der Textfassung OHNE L/R — Lesehilfe und Rahmung
entfernt, Quellenliste als Legende mit „Bündelhinweise:"-Zeile, D1 ergänzt.

Läuft headless (Qt-Offscreen); kein Netzwerk.

Lauf (ohne pytest):  QT_QPA_PLATFORM=offscreen python -m pytest tests/test_bundle_mode.py
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PyQt6.QtGui import QTextCursor
from PyQt6.QtWidgets import QApplication, QMessageBox

import src.core.comparison_worker as cw
import src.gui.main_window as mw
from src.config.defaults import VideoInfo
from src.core.comparison_item import ComparisonConfig, ModelChoice
from src.core.prompt_builder import FAKTENCHECK_FORMAT
from src.gui.transcript_widget import TranscriptInputWidget
from tests.transcript_golden_helpers import (
    case_keys, key_str, load_golden, render_case,
)

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"
BUNDLE = (FIXTURE_DIR / "bundle_musk_starlink_v1.txt").read_text(encoding="utf-8")
FRAMING = (FIXTURE_DIR / "bundle_musk_starlink_v1_framing.txt").read_text(
    encoding="utf-8")

LESEHILFE = "LESEHILFE (gilt für den gesamten Text unter QUELLENBÜNDEL):"
B5_HEADER = "QUELLENKÜRZEL UND ZUSCHREIBUNG:"
RAHMUNG_HEADER = "RAHMUNG DURCH DEN KURATOR (Deutung — nicht prüfbar, keine Quelle):"
FK_PARAGRAPH_EXCEPTION = (
    "Diese Absatz- und Satzvorgaben gelten NICHT für einen FAKTENCHECK-Abschnitt"
)


def _bundle_prompt(preset: str = "Academia", module: str | None = None,
                   framing: str = "", transcript: str | None = None,
                   auto: bool = False) -> str:
    """Rendert einen Bündel-Prompt mit festem Datum (Zeitanker deterministisch)."""
    from tests import transcript_golden_helpers as g
    from unittest.mock import patch
    from src.core import prompt_builder
    with patch.object(prompt_builder, "datetime", g._FixedDatetime):
        return prompt_builder.build_prompt_from_transcript(
            title="Musk/Starlink", author="Kurator", transcript=transcript or BUNDLE,
            config=g.SomasConfig(), preset_name=preset, is_auto_transcript=auto,
            custom_module=module, is_bundle=True, framing=framing,
        )


# --- 1. Regression: Checkbox aus → byte-identisch zu v0.15.3 ------------------

@pytest.mark.parametrize("case", case_keys(), ids=lambda c: key_str(*c))
def test_without_bundle_prompt_is_byte_identical_to_v0153(case) -> None:
    """Alle Presets × Modul × STT: unverändert gegenüber dem v0.15.3-Snapshot."""
    assert render_case(*case) == load_golden()[key_str(*case)]


def test_framing_is_ignored_without_bundle_flag() -> None:
    """Eine (stale) Rahmung darf ohne Bündel-Flagge nichts am Prompt ändern."""
    case = ("Standard", None, False)
    assert render_case(*case, is_bundle=False, framing="Klammer: X") == \
        load_golden()[key_str(*case)]


# --- 2. Bündel-Template ---------------------------------------------------------

@pytest.mark.parametrize("auto", [False, True])
def test_bundle_template_core_instructions(auto) -> None:
    """Lesehilfe + B5 + FAKTENCHECK-Ausnahme präsent; kein STT, keine Sprecher."""
    prompt = _bundle_prompt(auto=auto)
    assert "Analysiere das folgende Quellenbündel" in prompt
    assert LESEHILFE in prompt
    assert "kein Transkript eines einzelnen Beitrags, sondern ein Quellenbündel" in prompt
    assert "Gegenstand der Analyse ist das Ereignis" in prompt
    assert "nicht die Frage, ob eine Quelle ihn genannt hat" in prompt
    assert "ist das Wiedergabe, keine unabhängige Bestätigung" in prompt
    assert B5_HEADER in prompt
    assert FK_PARAGRAPH_EXCEPTION in prompt
    for gone in ("HINWEIS ZUM TRANSKRIPT", "Speech-to-Text",
                 "BEZEICHNUNG DER SPRECHENDEN", "Wer spricht",
                 "O-Töne des Sprechers", "TRANSKRIPT:"):
        assert gone not in prompt, gone


# --- 3. Rahmung-Block -----------------------------------------------------------

def test_framing_filled_renders_marked_block_before_bundle() -> None:
    """Gefüllte Rahmung → gekennzeichneter Block VOR dem Bündeltext."""
    prompt = _bundle_prompt(framing=FRAMING)
    assert RAHMUNG_HEADER in prompt
    assert "Extrahiere sie NICHT als Behauptung, Meinung oder Interpretation" in prompt
    assert FRAMING.strip() in prompt
    assert prompt.index(RAHMUNG_HEADER) < prompt.index("QUELLENBÜNDEL:\n")


@pytest.mark.parametrize("empty", ["", "   \n  "])
def test_empty_framing_renders_no_block(empty) -> None:
    """Leere Rahmung → kein Block, kein „None"."""
    prompt = _bundle_prompt(framing=empty)
    assert "RAHMUNG" not in prompt
    assert "None" not in prompt


# --- 4. Preset-Kombination ------------------------------------------------------

def test_academia_overlay_on_bundle_template() -> None:
    """Academia liefert Limit + kritische Perspektive über dem Bündel-Template."""
    prompt = _bundle_prompt("Academia")
    assert "unter 3000 Zeichen" in prompt
    assert "PERSPEKTIVE: Kritisch-Analytisch." in prompt
    assert "ZEITLICHER RAHMEN:\n- Heute ist der 26. Oktober 2026." in prompt
    assert LESEHILFE in prompt


def test_forced_faktencheck_coexists_with_bundle() -> None:
    """Erzwungener FAKTENCHECK: Format injiziert, Limit-Zeilen raus, Bündel bleibt."""
    prompt = _bundle_prompt("Academia", module="FAKTENCHECK")
    assert "PFLICHT-MODUL: Erzwinge 'FAKTENCHECK'" in prompt
    assert FAKTENCHECK_FORMAT in prompt
    assert "ZEICHENLIMIT" not in prompt
    assert "ZEITLICHER RAHMEN:" in prompt
    assert LESEHILFE in prompt and B5_HEADER in prompt


@pytest.mark.parametrize("preset", ["Musik", "Songstruktur"])
def test_bundle_wins_over_transcript_aware_presets(preset) -> None:
    """PO 2026-10-27: Bündel ist Eingabe-Eigenschaft — auch gegen Musik-Templates."""
    prompt = _bundle_prompt(preset)
    assert LESEHILFE in prompt
    assert "Songtext" not in prompt


# --- 5. B2: keine Normalisierung ------------------------------------------------

def test_bundle_text_survives_build_unchanged() -> None:
    """Zeilenumbrüche und führende Nummern bleiben 1:1 (Verweise wie „Abschnitt 4")."""
    prompt = _bundle_prompt(module="FAKTENCHECK", framing=FRAMING)
    assert f'QUELLENBÜNDEL:\n"""\n{BUNDLE}\n"""' in prompt
    assert "\n3.4 Musk erklärte" in prompt and "\n4.1 Wer entschied" in prompt


def test_transcript_widget_passes_bundle_text_through(app) -> None:
    """Auch der GUI-Weg (get_data) lässt den Bündeltext innen unverändert."""
    widget = TranscriptInputWidget()
    widget.title_edit.setText("Musk/Starlink")
    widget.transcript_edit.setPlainText(BUNDLE)
    assert widget.get_data()["transcript"] == BUNDLE.strip()


# --- 6. B4: Reset bei Quellenwechsel -------------------------------------------

def _fill_inputs(win) -> None:
    """Füllt Fragen- und Rahmung-Feld (Bündel-Modus an)."""
    win.transcript_widget.bundle_checkbox.setChecked(True)
    win.questions_text.setPlainText("Eine Frage?")
    win.transcript_widget.framing_edit.setPlainText(FRAMING)


def _inputs_cleared(win) -> bool:
    return (win.questions_text.toPlainText() == ""
            and win.transcript_widget.framing_edit.toPlainText() == "")


def test_first_paste_into_empty_transcript_keeps_inputs(win) -> None:
    """Rahmung-zuerst-Workflow: Erst-Einfügen in leeres Feld resettet NICHT."""
    _fill_inputs(win)
    win.transcript_widget.transcript_edit.setPlainText(BUNDLE)
    assert win.questions_text.toPlainText() == "Eine Frage?"
    assert win.transcript_widget.framing_edit.toPlainText() == FRAMING


@pytest.mark.parametrize("how", ["set", "select_all_paste", "select_all_delete"])
def test_replacing_nonempty_transcript_clears_inputs(win, how) -> None:
    """Ersetzen/Leeren eines nicht-leeren Transkripts leert Fragen + Rahmung."""
    edit = win.transcript_widget.transcript_edit
    edit.setPlainText(BUNDLE)
    _fill_inputs(win)
    if how == "set":
        edit.setPlainText("Ein ganz anderes Bündel.")
    elif how == "select_all_paste":
        edit.selectAll()
        edit.insertPlainText("Ein ganz anderes Bündel.")
    else:
        edit.selectAll()
        edit.textCursor().removeSelectedText()
    assert _inputs_cleared(win)


def test_typing_and_trimming_do_not_clear_inputs(win) -> None:
    """Tippen und Kürzen eines Blocks (z. B. alte L-/R-Abschnitte) resetten nicht."""
    edit = win.transcript_widget.transcript_edit
    edit.setPlainText(BUNDLE)
    _fill_inputs(win)
    cursor = edit.textCursor()
    cursor.movePosition(QTextCursor.MoveOperation.End)
    edit.setTextCursor(cursor)
    edit.insertPlainText("\nNachtrag.")
    cursor.setPosition(0)
    cursor.setPosition(len(BUNDLE) // 2, QTextCursor.MoveMode.KeepAnchor)
    cursor.removeSelectedText()
    assert win.questions_text.toPlainText() == "Eine Frage?"
    assert win.transcript_widget.framing_edit.toPlainText() == FRAMING


def _stub_video(monkeypatch, title: str) -> None:
    monkeypatch.setattr(mw, "resolve_video_info", lambda url: VideoInfo(
        title=title, channel="Kanal", duration=60, url=url))


def test_new_video_after_previous_source_clears_inputs(win, monkeypatch) -> None:
    """Zweites Video = Quellenwechsel → Fragen + Rahmung leer."""
    _stub_video(monkeypatch, "A")
    win.url_input.setText("https://www.youtube.com/watch?v=AAAAAAAAAAA")
    win._on_get_meta()
    _fill_inputs(win)
    _stub_video(monkeypatch, "B")
    win.url_input.setText("https://www.youtube.com/watch?v=BBBBBBBBBBB")
    win._on_get_meta()
    assert _inputs_cleared(win)


def test_first_video_of_session_keeps_inputs(win, monkeypatch) -> None:
    """PO 2026-10-27: vor dem ersten Video getippte Frage bleibt erhalten."""
    _fill_inputs(win)
    _stub_video(monkeypatch, "A")
    win.url_input.setText("https://www.youtube.com/watch?v=AAAAAAAAAAA")
    win._on_get_meta()
    assert win.questions_text.toPlainText() == "Eine Frage?"
    assert win.transcript_widget.framing_edit.toPlainText() == FRAMING


def test_preset_change_keeps_inputs(win) -> None:
    """Regression: bloßer Preset-Wechsel lässt Fragen + Rahmung stehen."""
    win.transcript_widget.transcript_edit.setPlainText(BUNDLE)
    _fill_inputs(win)
    win.preset_combo.setCurrentIndex(win.preset_combo.findText("Academia"))
    win.preset_combo.setCurrentIndex(win.preset_combo.findText("Standard"))
    assert win.questions_text.toPlainText() == "Eine Frage?"
    assert win.transcript_widget.framing_edit.toPlainText() == FRAMING


# --- 7. GUI: Rahmung-Feld nur mit Checkbox -------------------------------------

def test_framing_field_visible_only_with_checkbox(app) -> None:
    """Default aus, Feld verborgen; Checkbox an → sichtbar; aus → wieder weg."""
    widget = TranscriptInputWidget()
    assert not widget.bundle_checkbox.isChecked()
    assert widget.framing_edit.isHidden() and widget.framing_label.isHidden()
    widget.bundle_checkbox.setChecked(True)
    assert not widget.framing_edit.isHidden()
    widget.framing_edit.setPlainText(FRAMING)
    assert widget.get_framing() == FRAMING.strip()
    widget.bundle_checkbox.setChecked(False)
    assert widget.framing_edit.isHidden()
    assert widget.get_framing() == ""  # unsichtbare Rahmung geht nie in den Prompt


def test_generate_from_transcript_uses_bundle_mode(win) -> None:
    """Der Transkript-Lauf reicht Flagge + Rahmung an den Builder durch."""
    tw = win.transcript_widget
    tw.title_edit.setText("Musk/Starlink")
    tw.transcript_edit.setPlainText(BUNDLE)
    tw.bundle_checkbox.setChecked(True)
    tw.framing_edit.setPlainText(FRAMING)
    win.api_checkbox.setChecked(False)
    win._generate_from_transcript()
    prompt = win.prompt_text.toPlainText()
    assert LESEHILFE in prompt and RAHMUNG_HEADER in prompt
    assert BUNDLE.strip() in prompt


# --- 8. B5-Vorrang mit Scope ----------------------------------------------------

def test_b5_precedence_scoped_to_bundle_sources() -> None:
    """Keine Q-/Kanal-Attribution; Ereignis-Akteure + Ursprungsdokumente bleiben."""
    prompt = _bundle_prompt(module="FAKTENCHECK")
    assert "[Q1]" in prompt  # die Fixture trägt die Kürzel wirklich
    b5 = prompt.split(B5_HEADER)[1].split("KONFIGURATION:")[0]
    assert "Quellenkürzel ([Q1], [Q1, Q2] …)" in b5
    assert "NICHT in Sachbehauptungen" in b5
    assert "VORRANG vor dem allgemeinen Hinweis, Attributionsaussagen" in b5
    assert "NUR für die bündel-eigenen Quellen (Q1 … Qn" in b5
    assert "Aussagen von Akteuren IM Ereignis" in b5
    assert "Zuschreibungen an Ursprungsdokumente" in b5
    # Der allgemeine Attributions-Hinweis (Phase 16) bleibt unangetastet im Prompt.
    assert "Attributionsaussagen („X behauptet/erklärt, dass …“) als solche" in prompt


# --- 9. Bündelhinweise-Zeile ----------------------------------------------------

def test_lesehilfe_points_to_buendelhinweise_line() -> None:
    """Lesehilfe verweist auf „Bündelhinweise:" — als Lesehilfe, nicht als Inhalt."""
    prompt = _bundle_prompt()
    lesehilfe = prompt.split(LESEHILFE)[1].split("BEZEICHNUNGEN:")[0]
    assert "Beginnt die Quellenlegende mit einer Zeile „Bündelhinweise:“" in lesehilfe
    assert "Lesehilfe des Kurators" in lesehilfe
    assert "weder als Behauptung noch als Interpretation" in lesehilfe
    assert "Bündelhinweise: Beide Quellen" in prompt  # Fixture-Zeile kommt an


# --- Spec §4: Modellvergleich erbt den Modus -----------------------------------

def test_comparison_with_transcript_inherits_bundle_mode(monkeypatch) -> None:
    """Erwünschter Nebeneffekt: Vergleich über denselben Builder → Bündel-Prompt."""
    captured: dict = {}

    class _Stop(Exception):
        pass

    def spy(**kwargs):
        captured.update(kwargs)
        raise _Stop

    monkeypatch.setattr(cw, "get_api_key", lambda pid: "key")
    monkeypatch.setattr(cw, "create_client", lambda pid, key: object())
    monkeypatch.setattr(cw, "build_prompt_from_transcript", spy)
    choice = ModelChoice(provider_id="openrouter", model_id="m")
    cfg = ComparisonConfig(
        input_mode="transcript", transcript_title="Musk/Starlink",
        transcript_text=BUNDLE, is_bundle=True, framing=FRAMING,
        model_a=choice, model_b=choice, model_synth=choice,
    )
    cw.ComparisonWorker(cfg).run()
    assert captured["is_bundle"] is True
    assert captured["framing"] == FRAMING
    assert captured["transcript"] == BUNDLE


def test_comparison_config_from_gui_carries_bundle_fields(win) -> None:
    """main_window baut die Vergleichs-Config mit Flagge + Rahmung."""
    tw = win.transcript_widget
    tw.title_edit.setText("Musk/Starlink")
    tw.transcript_edit.setPlainText(BUNDLE)
    tw.bundle_checkbox.setChecked(True)
    tw.framing_edit.setPlainText(FRAMING)
    win.input_tabs.setCurrentIndex(1)
    choice = ModelChoice(provider_id="openrouter", model_id="m")
    cfg = win._build_comparison_config(choice, choice, choice)
    assert cfg.is_bundle is True and cfg.framing == FRAMING.strip()


# --- Fixtures -------------------------------------------------------------------

@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def win(app, monkeypatch):
    """Frisches MainWindow mit isolierten Preferences und stummen Dialogen."""
    prefs: dict = {}
    monkeypatch.setattr(mw, "load_preferences", lambda: dict(prefs))
    monkeypatch.setattr(mw, "save_preferences", lambda p: prefs.update(p))
    for name in ("warning", "information", "critical"):
        monkeypatch.setattr(QMessageBox, name, lambda *a, **k: None)
    return mw.MainWindow()
