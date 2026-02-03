"""Hauptfenster der SOMAS Prompt Generator App."""

import logging
import re
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QTextEdit, QMessageBox,
    QFrame, QApplication, QComboBox, QCheckBox, QTabWidget,
)
from PyQt6.QtCore import Qt, pyqtSlot
from PyQt6.QtGui import QFont

from src.config.defaults import VideoInfo, SomasConfig, TimeRange
from src.core.youtube_client import get_video_info
from src.core.prompt_builder import (
    build_prompt, build_prompt_from_transcript,
    load_presets, get_preset_by_name, PromptPreset,
)
from src.core.linkedin_formatter import format_for_linkedin
from src.core.export import export_to_markdown, get_suggested_filename
from src.core.api_client import APIResponse, APIStatus
from src.core.api_worker import APIWorker
from src.core.debug_logger import DebugLogger, APP_VERSION
from src.core.perplexity_client import PerplexityClient
from src.core.openrouter_client import OpenRouterClient
from src.gui.model_selector import FilterableModelSelector, ModelData, extract_provider
from src.gui.transcript_widget import TranscriptInputWidget
from src.config.api_config import (
    load_providers, get_api_key, has_api_key,
    get_last_provider, get_last_model, save_last_selection,
    load_preferences,
)


logger = logging.getLogger(__name__)

# Status-Farben und Labels für API-Anzeige
STATUS_DISPLAY = {
    "idle": ("", "#808080", "Bereit"),
    "sending": ("", "#2196F3", "Sende..."),
    "processing": ("", "#FFC107", "Verarbeite..."),
    "received": ("", "#4CAF50", "Empfangen"),
    "error": ("", "#F44336", "Fehler"),
}


def parse_time_input(time_str: str) -> str | None:
    """Konvertiert MM:SS oder HH:MM:SS zu normalisiertem HH:MM:SS.

    Args:
        time_str: Zeiteingabe im Format MM:SS oder HH:MM:SS.

    Returns:
        Normalisiertes HH:MM:SS oder None bei ungültigem Format.
    """
    time_str = time_str.strip()

    # HH:MM:SS
    if re.match(r'^\d{1,2}:\d{2}:\d{2}$', time_str):
        parts = time_str.split(':')
        h, m, s = int(parts[0]), int(parts[1]), int(parts[2])
        if m > 59 or s > 59:
            return None
        return f"{h:02d}:{m:02d}:{s:02d}"

    # MM:SS → 00:MM:SS
    if re.match(r'^\d{1,2}:\d{2}$', time_str):
        parts = time_str.split(':')
        m, s = int(parts[0]), int(parts[1])
        if m > 59 or s > 59:
            return None
        return f"00:{m:02d}:{s:02d}"

    return None


def time_to_seconds(time_str: str) -> int:
    """Konvertiert HH:MM:SS zu Gesamtsekunden.

    Args:
        time_str: Zeitangabe im Format HH:MM:SS.

    Returns:
        Gesamtsekunden.
    """
    parts = time_str.split(':')
    return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])


class MainWindow(QMainWindow):
    """Hauptfenster der SOMAS Prompt Generator Anwendung."""

    def __init__(self):
        super().__init__()
        self.video_info: VideoInfo | None = None
        self.config = SomasConfig()
        self.current_preset: PromptPreset | None = None

        # API-State
        self._api_worker: APIWorker | None = None
        self._api_providers = load_providers()
        self._last_api_response: APIResponse | None = None
        self._openrouter_raw_models: list[dict] = []

        # Debug-Logger (Preference-gesteuert)
        prefs = load_preferences()
        self._debug_logger = DebugLogger(enabled=prefs.get("debug_logging", False))

        # Lade Presets mit Fehlerbehandlung
        try:
            self.presets = load_presets()
        except Exception as e:
            logger.error(f"Fehler beim Laden der Presets: {e}")
            self.presets = {}
            QMessageBox.critical(
                None,
                "Preset-Fehler",
                f"Presets konnten nicht geladen werden:\n{e}\n\n"
                "Die App startet mit deaktivierten Presets."
            )

        self._setup_ui()
        self._connect_signals()
        self._on_preset_changed()  # Initialisiere mit erstem Preset
        self._restore_api_selection()  # Letzte Provider/Modell-Auswahl wiederherstellen

    def _setup_ui(self):
        """Initialisiert das UI-Layout."""
        self.setWindowTitle("SOMAS Prompt Generator")
        self.setMinimumSize(800, 700)

        # Zentrales Widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(20, 20, 20, 20)

        # Eingabe-Tabs: YouTube URL / Manuelles Transkript
        self.input_tabs = QTabWidget()

        # Tab 1: YouTube URL + Meta
        youtube_tab = QWidget()
        youtube_layout = QVBoxLayout(youtube_tab)
        youtube_layout.setContentsMargins(5, 10, 5, 5)
        youtube_layout.addLayout(self._create_url_section())
        youtube_layout.addWidget(self._create_meta_section())
        self.input_tabs.addTab(youtube_tab, "YouTube URL")

        # Tab 2: Manuelles Transkript
        self.transcript_widget = TranscriptInputWidget()
        self.input_tabs.addTab(self.transcript_widget, "Manuelles Transkript")

        main_layout.addWidget(self.input_tabs)

        # Zeitbereich (optional, nur für YouTube-Tab sichtbar)
        self.time_range_frame = self._create_time_range_section()
        main_layout.addWidget(self.time_range_frame)

        # Fragen-Sektion
        main_layout.addWidget(self._create_questions_section())

        # Preset-Auswahl
        main_layout.addLayout(self._create_preset_section())

        # API-Modus
        main_layout.addWidget(self._create_api_section())

        # Generate Button
        self.btn_generate = QPushButton("Generate Prompt")
        self.btn_generate.setMinimumHeight(40)
        self.btn_generate.setEnabled(False)
        main_layout.addWidget(self.btn_generate)

        # Generierter Prompt
        main_layout.addWidget(self._create_prompt_section())

        # Analyse-Ergebnis
        main_layout.addWidget(self._create_result_section())

        # Export-Buttons
        main_layout.addLayout(self._create_export_section())

    def _create_url_section(self) -> QHBoxLayout:
        """Erstellt die URL-Eingabezeile."""
        layout = QHBoxLayout()

        label = QLabel("YouTube URL:")
        label.setMinimumWidth(100)
        layout.addWidget(label)

        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("https://www.youtube.com/watch?v=...")
        layout.addWidget(self.url_input)

        self.btn_get_meta = QPushButton("Get Meta")
        self.btn_get_meta.setMinimumWidth(100)
        layout.addWidget(self.btn_get_meta)

        return layout

    def _create_meta_section(self) -> QFrame:
        """Erstellt den Metadaten-Bereich."""
        frame = QFrame()
        frame.setFrameStyle(QFrame.Shape.StyledPanel)
        layout = QVBoxLayout(frame)

        # Header
        header_layout = QHBoxLayout()
        header_label = QLabel("META-INFORMATIONEN")
        header_label.setFont(QFont("", -1, QFont.Weight.Bold))
        header_layout.addWidget(header_label)
        header_layout.addStretch()
        layout.addLayout(header_layout)

        # Metadaten-Textfeld (editierbar)
        self.meta_text = QTextEdit()
        self.meta_text.setMaximumHeight(100)
        self.meta_text.setPlaceholderText("Metadaten werden hier angezeigt...")
        layout.addWidget(self.meta_text)

        return frame

    def _create_time_range_section(self) -> QFrame:
        """Erstellt den Zeitbereich-Bereich (optional)."""
        frame = QFrame()
        frame.setFrameStyle(QFrame.Shape.StyledPanel)
        layout = QVBoxLayout(frame)

        # Haupt-Checkbox
        self.time_range_checkbox = QCheckBox("Nur Ausschnitt analysieren")
        layout.addWidget(self.time_range_checkbox)

        # Start/Ende-Eingabefelder
        time_layout = QHBoxLayout()
        time_layout.addWidget(QLabel("Start:"))
        self.time_start_edit = QLineEdit()
        self.time_start_edit.setPlaceholderText("00:00:00")
        self.time_start_edit.setMaximumWidth(100)
        time_layout.addWidget(self.time_start_edit)

        time_layout.addWidget(QLabel("Ende:"))
        self.time_end_edit = QLineEdit()
        self.time_end_edit.setPlaceholderText("00:00:00")
        self.time_end_edit.setMaximumWidth(100)
        time_layout.addWidget(self.time_end_edit)
        time_layout.addStretch()
        layout.addLayout(time_layout)

        # Kontext-Checkbox
        self.time_context_checkbox = QCheckBox(
            "Kontext des Gesamtvideos einbeziehen"
        )
        layout.addWidget(self.time_context_checkbox)

        # Initial deaktiviert
        self.time_start_edit.setEnabled(False)
        self.time_end_edit.setEnabled(False)
        self.time_context_checkbox.setEnabled(False)

        return frame

    def _create_questions_section(self) -> QFrame:
        """Erstellt den Fragen-Bereich."""
        frame = QFrame()
        frame.setFrameStyle(QFrame.Shape.StyledPanel)
        layout = QVBoxLayout(frame)

        label = QLabel("FRAGEN (optional):")
        label.setFont(QFont("", -1, QFont.Weight.Bold))
        layout.addWidget(label)

        self.questions_text = QTextEdit()
        self.questions_text.setMaximumHeight(80)
        self.questions_text.setPlaceholderText("Anschlussfragen an die Analyse...")
        layout.addWidget(self.questions_text)

        return frame

    def _create_preset_section(self) -> QHBoxLayout:
        """Erstellt die Preset-Auswahl mit Lesezeit-Anzeige."""
        layout = QHBoxLayout()

        # Preset-Label
        label = QLabel("Variante:")
        label.setMinimumWidth(60)
        layout.addWidget(label)

        # Preset-Dropdown
        self.preset_combo = QComboBox()
        self.preset_combo.setMinimumWidth(150)
        for preset in self.presets.values():
            self.preset_combo.addItem(preset.name)
        layout.addWidget(self.preset_combo)

        # Preset-Beschreibung
        self.preset_description = QLabel("")
        self.preset_description.setStyleSheet("color: gray; font-style: italic;")
        layout.addWidget(self.preset_description)

        layout.addStretch()

        # Lesezeit-Anzeige
        self.reading_time_label = QLabel("")
        self.reading_time_label.setStyleSheet(
            "background-color: #e8f4e8; padding: 4px 8px; border-radius: 4px;"
        )
        layout.addWidget(self.reading_time_label)

        # Max-Zeichen-Anzeige
        self.max_chars_label = QLabel("")
        self.max_chars_label.setStyleSheet(
            "background-color: #e8e8f4; padding: 4px 8px; border-radius: 4px;"
        )
        layout.addWidget(self.max_chars_label)

        return layout

    def _create_api_section(self) -> QFrame:
        """Erstellt den API-Modus-Bereich."""
        frame = QFrame()
        frame.setFrameStyle(QFrame.Shape.StyledPanel)
        layout = QVBoxLayout(frame)

        # Zeile 1: Checkbox
        self.api_checkbox = QCheckBox("API-Automatik aktivieren")
        layout.addWidget(self.api_checkbox)

        # Zeile 2: Provider + Modell + Settings
        controls_layout = QHBoxLayout()

        controls_layout.addWidget(QLabel("Provider:"))
        self.provider_combo = QComboBox()
        self.provider_combo.setMinimumWidth(150)
        for provider in self._api_providers.values():
            self.provider_combo.addItem(provider.name, provider.id)
        controls_layout.addWidget(self.provider_combo)

        self.model_label = QLabel("Modell:")
        controls_layout.addWidget(self.model_label)
        self.model_combo = QComboBox()
        self.model_combo.setMinimumWidth(200)
        controls_layout.addWidget(self.model_combo)

        # OpenRouter: FilterableModelSelector (Popup-Dropdown, initial versteckt)
        self.model_selector = FilterableModelSelector()
        self.model_selector.setVisible(False)
        controls_layout.addWidget(self.model_selector)

        self.btn_settings = QPushButton("Settings")
        self.btn_settings.setMaximumWidth(80)
        controls_layout.addWidget(self.btn_settings)

        controls_layout.addStretch()

        # Debug-Icon (nur sichtbar wenn Debug-Logging aktiv)
        self.debug_icon_label = QLabel("Debug")
        self.debug_icon_label.setStyleSheet("color: #FFC107; font-weight: bold;")
        self.debug_icon_label.setToolTip("Debug-Logging aktiv — Logs in %TEMP%/somas_debug/")
        self.debug_icon_label.setVisible(self._debug_logger.enabled)
        controls_layout.addWidget(self.debug_icon_label)

        # Status-Anzeige
        self.api_status_label = QLabel("Bereit")
        self.api_status_label.setStyleSheet(
            "padding: 4px 8px; border-radius: 4px; "
            "background-color: #f0f0f0; color: #808080;"
        )
        controls_layout.addWidget(self.api_status_label)

        layout.addLayout(controls_layout)

        # Initial: Controls deaktiviert bis Checkbox aktiv
        self._set_api_controls_enabled(False)

        return frame

    def _create_prompt_section(self) -> QFrame:
        """Erstellt den Prompt-Ausgabebereich."""
        frame = QFrame()
        frame.setFrameStyle(QFrame.Shape.StyledPanel)
        layout = QVBoxLayout(frame)

        # Header mit Copy-Button
        header_layout = QHBoxLayout()
        header_label = QLabel("GENERIERTER PROMPT")
        header_label.setFont(QFont("", -1, QFont.Weight.Bold))
        header_layout.addWidget(header_label)
        header_layout.addStretch()

        self.btn_copy_prompt = QPushButton("Copy")
        self.btn_copy_prompt.setMaximumWidth(80)
        header_layout.addWidget(self.btn_copy_prompt)
        layout.addLayout(header_layout)

        # Prompt-Textfeld (read-only)
        self.prompt_text = QTextEdit()
        self.prompt_text.setReadOnly(True)
        self.prompt_text.setMinimumHeight(150)
        self.prompt_text.setPlaceholderText("Der generierte Prompt erscheint hier...")
        layout.addWidget(self.prompt_text)

        return frame

    def _create_result_section(self) -> QFrame:
        """Erstellt den Analyse-Ergebnis-Bereich."""
        frame = QFrame()
        frame.setFrameStyle(QFrame.Shape.StyledPanel)
        layout = QVBoxLayout(frame)

        # Header mit Paste-Button
        header_layout = QHBoxLayout()
        header_label = QLabel("ANALYSE-ERGEBNIS")
        header_label.setFont(QFont("", -1, QFont.Weight.Bold))
        header_layout.addWidget(header_label)
        header_layout.addStretch()

        self.btn_paste_result = QPushButton("Paste")
        self.btn_paste_result.setMaximumWidth(80)
        header_layout.addWidget(self.btn_paste_result)
        layout.addLayout(header_layout)

        # Ergebnis-Textfeld
        self.result_text = QTextEdit()
        self.result_text.setMinimumHeight(150)
        self.result_text.setPlaceholderText("Analyse-Ergebnis hier einfügen...")
        layout.addWidget(self.result_text)

        return frame

    def _create_export_section(self) -> QHBoxLayout:
        """Erstellt die Export-Buttons."""
        layout = QHBoxLayout()

        self.btn_export_linkedin = QPushButton("Export: LinkedIn")
        self.btn_export_markdown = QPushButton("Export: Markdown")
        self.btn_export_pdf = QPushButton("Export: PDF")

        # Quellen-Detail-Button (erscheint nach LinkedIn-Export)
        self.btn_sources_detail = QPushButton("Quellen (Details)")
        self.btn_sources_detail.setVisible(False)
        self._detailed_sources: str = ""

        # PDF vorerst deaktiviert (Phase 3)
        self.btn_export_pdf.setEnabled(False)

        layout.addWidget(self.btn_export_linkedin)
        layout.addWidget(self.btn_export_markdown)
        layout.addWidget(self.btn_export_pdf)
        layout.addWidget(self.btn_sources_detail)
        layout.addStretch()

        return layout

    def _connect_signals(self):
        """Verbindet Signals mit Slots."""
        self.btn_get_meta.clicked.connect(self._on_get_meta)
        self.btn_generate.clicked.connect(self._on_generate_prompt)
        self.btn_copy_prompt.clicked.connect(self._on_copy_prompt)
        self.btn_paste_result.clicked.connect(self._on_paste_result)
        self.url_input.returnPressed.connect(self._on_get_meta)
        # Preset-Dropdown
        self.preset_combo.currentTextChanged.connect(self._on_preset_changed)
        # Export-Buttons
        self.btn_export_linkedin.clicked.connect(self._on_export_linkedin)
        self.btn_export_markdown.clicked.connect(self._on_export_markdown)
        self.btn_sources_detail.clicked.connect(self._on_copy_sources_detail)
        # Input-Tabs (YouTube / Transkript)
        self.input_tabs.currentChanged.connect(self._on_input_tab_changed)
        # Zeitbereich
        self.time_range_checkbox.toggled.connect(self._toggle_time_range_fields)
        # API-Controls
        self.api_checkbox.toggled.connect(self._on_api_toggle)
        self.provider_combo.currentIndexChanged.connect(self._on_provider_changed)
        self.model_combo.currentIndexChanged.connect(self._on_model_changed)
        self.model_selector.model_selected.connect(self._on_openrouter_model_selected)
        self.btn_settings.clicked.connect(self._on_settings)

    @pyqtSlot()
    def _on_preset_changed(self) -> None:
        """Handler für Preset-Auswahl."""
        preset_name = self.preset_combo.currentText()
        self.current_preset = get_preset_by_name(preset_name)

        if self.current_preset:
            # Beschreibung aktualisieren
            self.preset_description.setText(self.current_preset.description)
            # Lesezeit aktualisieren
            self.reading_time_label.setText(
                f"Lesezeit: {self.current_preset.reading_time_display}"
            )
            # Max-Zeichen aktualisieren (nutzt max_chars_display Property)
            self.max_chars_label.setText(
                f"Max: {self.current_preset.max_chars_display} Zeichen"
            )
            # Model-Hint anzeigen (z.B. bei Research-Preset)
            if self.current_preset.show_model_hint and self.current_preset.model_hint_message:
                QMessageBox.information(
                    self, "Preset-Hinweis", self.current_preset.model_hint_message
                )
        else:
            # Keine Presets verfügbar
            self.preset_description.setText("Keine Presets verfügbar")
            self.reading_time_label.setText("")
            self.max_chars_label.setText("")

    @pyqtSlot(int)
    def _on_input_tab_changed(self, index: int) -> None:
        """Handler für Tab-Wechsel zwischen YouTube und Transkript."""
        is_youtube = index == 0
        # Zeitbereich nur für YouTube-Tab sinnvoll
        self.time_range_frame.setVisible(is_youtube)
        # Generate-Button aktivieren je nach Tab
        if is_youtube:
            self.btn_generate.setEnabled(self.video_info is not None)
        else:
            self.btn_generate.setEnabled(True)

    @pyqtSlot(bool)
    def _toggle_time_range_fields(self, enabled: bool) -> None:
        """Aktiviert/deaktiviert die Zeitbereich-Eingabefelder."""
        self.time_start_edit.setEnabled(enabled)
        self.time_end_edit.setEnabled(enabled)
        self.time_context_checkbox.setEnabled(enabled)
        if not enabled:
            self.time_start_edit.clear()
            self.time_end_edit.clear()
            self.time_context_checkbox.setChecked(False)

    @pyqtSlot()
    def _on_get_meta(self):
        """Handler für 'Get Meta' Button."""
        url = self.url_input.text().strip()
        if not url:
            QMessageBox.warning(self, "Fehler", "Bitte eine YouTube-URL eingeben.")
            return

        try:
            self.video_info = get_video_info(url)
            self._display_meta()
            self._clear_stale_sources()
            self.btn_generate.setEnabled(True)
        except ValueError as e:
            QMessageBox.critical(self, "Fehler", str(e))
            logger.error(f"Fehler beim Abrufen der Metadaten: {e}")

    def _display_meta(self):
        """Zeigt die Video-Metadaten im Textfeld an."""
        if not self.video_info:
            return

        meta_text = (
            f"Titel: {self.video_info.title}\n"
            f"Kanal: {self.video_info.channel}\n"
            f"Dauer: {self.video_info.duration_formatted}\n"
            f"URL: {self.video_info.url}"
        )
        self.meta_text.setText(meta_text)

    @pyqtSlot()
    def _on_generate_prompt(self):
        """Handler für 'Generate Prompt' Button."""
        # Transcript-Tab aktiv → eigene Generierungslogik
        if self.input_tabs.currentIndex() == 1:
            self._generate_from_transcript()
            return

        if not self.video_info:
            QMessageBox.warning(self, "Fehler", "Bitte zuerst Metadaten abrufen.")
            return

        # Zeitbereich validieren und setzen
        if self.time_range_checkbox.isChecked():
            start = parse_time_input(self.time_start_edit.text())
            end = parse_time_input(self.time_end_edit.text())

            if not start or not end:
                QMessageBox.warning(
                    self, "Zeitbereich ungültig",
                    "Bitte Start und Ende im Format MM:SS oder HH:MM:SS eingeben."
                )
                return

            if time_to_seconds(start) >= time_to_seconds(end):
                QMessageBox.warning(
                    self, "Zeitbereich ungültig",
                    "Start muss vor Ende liegen."
                )
                return

            # Ende auf Videodauer begrenzen
            if self.video_info and self.video_info.duration > 0:
                if time_to_seconds(end) > self.video_info.duration:
                    dur = self.video_info.duration
                    end = f"{dur // 3600:02d}:{(dur % 3600) // 60:02d}:{dur % 60:02d}"
                    self.time_end_edit.setText(end)
                    QMessageBox.information(
                        self, "Zeitbereich angepasst",
                        f"Ende wurde auf die Videodauer "
                        f"({self.video_info.duration_formatted}) begrenzt."
                    )

            self.config.time_range = TimeRange(
                start=start,
                end=end,
                include_context=self.time_context_checkbox.isChecked(),
                video_duration_formatted=(
                    self.video_info.duration_formatted
                    if self.video_info and self.video_info.duration > 0
                    else ""
                ),
            )
        else:
            self.config.time_range = None

        questions = self.questions_text.toPlainText()

        # Verwende das ausgewählte Preset
        preset_name = self.current_preset.name if self.current_preset else None
        prompt = build_prompt(self.video_info, self.config, questions, preset_name)
        self.prompt_text.setText(prompt)

        # Zeige Zeichenzahl im Prompt-Header
        char_count = len(prompt)
        max_chars = self.current_preset.max_chars if self.current_preset else 2800
        logger.info(f"Prompt generiert: {char_count} Zeichen (Max: {max_chars})")

        # API-Automatik: Falls aktiv, automatisch API-Call starten
        if self.api_checkbox.isChecked():
            self._start_api_call(prompt)

    def _generate_from_transcript(self) -> None:
        """Generiert einen SOMAS-Prompt aus manuellem Transkript."""
        data = self.transcript_widget.get_data()
        if not data:
            QMessageBox.warning(
                self, "Fehlende Eingaben",
                "Bitte Titel und Transkript eingeben."
            )
            return

        # VideoInfo für Export-Kompatibilität erstellen
        self.video_info = VideoInfo(
            title=data["title"],
            channel=data["author"],
            duration=0,
            url=data["url"] or "",
        )

        # Kein Zeitbereich bei Transkript-Modus
        self.config.time_range = None

        questions = self.questions_text.toPlainText()
        preset_name = self.current_preset.name if self.current_preset else None

        prompt = build_prompt_from_transcript(
            title=data["title"],
            author=data["author"],
            transcript=data["transcript"],
            config=self.config,
            url=data["url"],
            questions=questions,
            preset_name=preset_name,
        )
        self.prompt_text.setText(prompt)

        char_count = len(prompt)
        logger.info(
            f"Transkript-Prompt generiert: {char_count} Zeichen, "
            f"{data['word_count']} Wörter Transkript"
        )

        # API-Automatik
        if self.api_checkbox.isChecked():
            self._start_api_call(prompt)

    @pyqtSlot()
    def _on_copy_prompt(self):
        """Kopiert den generierten Prompt in die Zwischenablage."""
        prompt = self.prompt_text.toPlainText()
        if prompt:
            clipboard = QApplication.clipboard()
            clipboard.setText(prompt)
            # Kurzes visuelles Feedback
            original_text = self.btn_copy_prompt.text()
            self.btn_copy_prompt.setText("Copied!")
            self.btn_copy_prompt.setEnabled(False)
            # Nach 1 Sekunde zurücksetzen
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(1000, lambda: self._reset_copy_button(original_text))

    def _reset_copy_button(self, text: str):
        """Setzt den Copy-Button zurück."""
        self.btn_copy_prompt.setText(text)
        self.btn_copy_prompt.setEnabled(True)

    @pyqtSlot()
    def _on_paste_result(self):
        """Fügt Text aus der Zwischenablage ins Ergebnis-Feld ein."""
        clipboard = QApplication.clipboard()
        text = clipboard.text()
        if text:
            self.result_text.setText(text)

    @pyqtSlot()
    def _on_export_linkedin(self):
        """Exportiert das Analyse-Ergebnis für LinkedIn (Unicode-formatiert)."""
        result = self.result_text.toPlainText()
        if not result:
            QMessageBox.warning(self, "Fehler", "Kein Analyse-Ergebnis vorhanden.")
            return

        # Stale-Daten zurücksetzen vor neuem Export-Versuch
        self._detailed_sources = ""
        self.btn_sources_detail.setVisible(False)

        try:
            # Konvertiere zu LinkedIn-Format (mit Post-Header aus Video-Metadaten)
            video_title = self.video_info.title if self.video_info else ""
            video_channel = self.video_info.channel if self.video_info else ""

            # API-Modell/Provider-Info für Header
            model_name = ""
            provider_name = ""
            if self._last_api_response:
                model_name = self._get_model_display_name(
                    self._last_api_response.model_used
                )
                provider_name = self._last_api_response.provider_used

            # Quellen aus API-Response (z.B. Perplexity citations)
            api_citations = None
            if self._last_api_response and self._last_api_response.citations:
                api_citations = self._last_api_response.citations

            logger.info(f"LinkedIn-Export: {len(result)} Zeichen Eingabe")
            linkedin_text, detailed_sources = format_for_linkedin(
                result, video_title, video_channel, model_name, provider_name,
                citations=api_citations,
            )
            logger.info(f"LinkedIn-Export: {len(linkedin_text)} Zeichen Ausgabe")

            # In Zwischenablage kopieren
            clipboard = QApplication.clipboard()
            clipboard.setText(linkedin_text)
            logger.info("LinkedIn-Export: In Zwischenablage kopiert")

            # Detail-Quellen speichern und Button anzeigen
            self._detailed_sources = detailed_sources
            self.btn_sources_detail.setVisible(bool(detailed_sources))

            # Visuelles Feedback
            self._show_button_feedback(self.btn_export_linkedin, "Copied!")

        except Exception as e:
            logger.error(f"LinkedIn-Export fehlgeschlagen: {e}")
            QMessageBox.critical(self, "Fehler", f"LinkedIn-Export fehlgeschlagen:\n{e}")

    @pyqtSlot()
    def _on_export_markdown(self):
        """Exportiert das Analyse-Ergebnis als Markdown-Datei."""
        from PyQt6.QtWidgets import QFileDialog

        result = self.result_text.toPlainText()
        if not result:
            QMessageBox.warning(self, "Fehler", "Kein Analyse-Ergebnis vorhanden.")
            return

        # Dateiname vorschlagen (sanitized für sichere Dateinamen)
        preset_name = self.current_preset.name if self.current_preset else ""
        suggested = get_suggested_filename(self.video_info, preset_name)
        default_name = f"{suggested}.md"

        # Datei-Dialog
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Markdown exportieren",
            default_name,
            "Markdown Files (*.md);;All Files (*)"
        )

        if file_path:
            try:
                # API-Modell/Provider-Info und Quellen
                model_name = ""
                provider_name = ""
                sources = None
                if self._last_api_response:
                    model_name = self._get_model_display_name(
                        self._last_api_response.model_used
                    )
                    provider_name = self._last_api_response.provider_used
                    if self._last_api_response.citations:
                        sources = self._last_api_response.citations

                export_to_markdown(
                    result, self.video_info, file_path,
                    model_name, provider_name, sources,
                )
                self._show_button_feedback(self.btn_export_markdown, "Saved!")
            except Exception as e:
                QMessageBox.critical(self, "Fehler", f"Export fehlgeschlagen: {e}")
                logger.error(f"Markdown-Export fehlgeschlagen: {e}")

    @pyqtSlot()
    def _on_copy_sources_detail(self) -> None:
        """Kopiert die Detail-Quellen (mit vollen URLs) in die Zwischenablage."""
        if not self._detailed_sources:
            return

        clipboard = QApplication.clipboard()
        clipboard.setText(self._detailed_sources)
        logger.info("Detail-Quellen in Zwischenablage kopiert")

        # Visuelles Feedback
        self._show_button_feedback(self.btn_sources_detail, "Copied!")

    # --- API-Methoden ---

    def _get_model_display_name(self, model_id: str) -> str:
        """Gibt den Anzeigenamen für eine Modell-ID zurück."""
        for provider in self._api_providers.values():
            for model in provider.models:
                if model.id == model_id:
                    return model.name
        return model_id

    def _get_active_model_id(self) -> str | None:
        """Gibt die Model-ID des aktuell sichtbaren Modell-Selectors zurück."""
        provider_id = self.provider_combo.currentData()
        if provider_id == "openrouter":
            return self.model_selector.get_selected_model_id()
        return self.model_combo.currentData()

    def _convert_to_model_data(self, raw_models: list[dict]) -> list[ModelData]:
        """Konvertiert Roh-Modell-Dicts (von OpenRouter) zu ModelData-Objekten."""
        result = []
        for m in raw_models:
            try:
                price_prompt = float(m.get("pricing_prompt") or "0")
                price_completion = float(m.get("pricing_completion") or "0")
            except (ValueError, TypeError):
                price_prompt = 0.0
                price_completion = 0.0

            price_input = price_prompt * 1_000_000
            price_output = price_completion * 1_000_000

            result.append(ModelData(
                id=m["id"],
                name=m.get("name", m["id"].split("/")[-1]),
                provider=extract_provider(m["id"]),
                context_length=m.get("context_length", 0) or 0,
                price_input=price_input,
                price_output=price_output,
                is_free=(price_prompt == 0 and price_completion == 0),
            ))
        return result

    def _load_dynamic_models(self, provider_id: str) -> None:
        """Lädt Modell-Liste dynamisch von der API (z.B. OpenRouter /models).

        Aktualisiert die models-Liste im Provider, sodass das Dropdown
        immer die aktuelle Modell-Liste anzeigt. Speichert Roh-Daten
        für den FilterableModelSelector (Preise, Context-Length).
        """
        from src.config.api_config import ProviderModel

        api_key = get_api_key(provider_id)
        if not api_key:
            return

        if provider_id == "openrouter":
            client = OpenRouterClient(api_key)
        else:
            return

        try:
            models_data = client.get_available_models()
            if models_data:
                self._openrouter_raw_models = models_data
                provider = self._api_providers[provider_id]
                provider.models = [
                    ProviderModel(
                        id=m["id"],
                        name=m["name"],
                        description=m.get("description", ""),
                    )
                    for m in models_data
                ]
                logger.info(
                    f"Dynamische Modell-Liste für {provider_id}: "
                    f"{len(provider.models)} Modelle"
                )
        except Exception as e:
            logger.warning(
                f"Dynamische Modelle für {provider_id} nicht geladen: {e}"
            )

    def _set_api_controls_enabled(self, enabled: bool) -> None:
        """Aktiviert/deaktiviert die API-Controls (Provider, Modell, Settings)."""
        self.provider_combo.setEnabled(enabled)
        self.model_combo.setEnabled(enabled)
        self.model_selector.setEnabled(enabled)
        self.btn_settings.setEnabled(enabled)

    @pyqtSlot(bool)
    def _on_api_toggle(self, checked: bool) -> None:
        """Handler für API-Checkbox."""
        self._set_api_controls_enabled(checked)
        if checked:
            self._check_api_key_configured()
        else:
            self._update_api_status("idle")

    def _check_api_key_configured(self) -> None:
        """Prüft ob ein API-Key für den aktuellen Provider konfiguriert ist."""
        provider_id = self.provider_combo.currentData()
        if provider_id and not has_api_key(provider_id):
            self._update_api_status("error")
            self.api_status_label.setText("Kein API-Key")
            QMessageBox.information(
                self,
                "API-Key fehlt",
                f"Kein API-Key für {self.provider_combo.currentText()} konfiguriert.\n\n"
                "Bitte über 'Settings' einen Key eingeben.",
            )

    @pyqtSlot(int)
    def _on_provider_changed(self, index: int) -> None:
        """Handler für Provider-Dropdown-Änderung."""
        provider_id = self.provider_combo.currentData()
        if not provider_id or provider_id not in self._api_providers:
            return

        provider = self._api_providers[provider_id]

        # Dynamische Modell-Liste laden (z.B. OpenRouter /models)
        if provider.supports_dynamic_models and has_api_key(provider_id):
            self._load_dynamic_models(provider_id)
            provider = self._api_providers[provider_id]

        if provider_id == "openrouter":
            # OpenRouter: FilterableModelSelector anzeigen
            self.model_combo.setVisible(False)
            self.model_label.setVisible(False)
            self.model_selector.setVisible(True)

            # Roh-Daten zu ModelData konvertieren und an Widget übergeben
            model_data_list = self._convert_to_model_data(
                self._openrouter_raw_models or [
                    {
                        "id": m.id, "name": m.name,
                        "context_length": 0,
                        "pricing_prompt": "0", "pricing_completion": "0",
                    }
                    for m in provider.models
                ]
            )
            self.model_selector.set_models(model_data_list)

            # Letztes Modell wiederherstellen oder Default
            last_model = get_last_model(provider_id)
            if last_model:
                self.model_selector.set_selected_model_id(last_model)
            elif provider.default_model:
                self.model_selector.set_selected_model_id(provider.default_model)
            # Fallback: falls gespeichertes Modell nicht mehr verfügbar
            if not self.model_selector.get_selected_model_id() and model_data_list:
                self.model_selector.set_selected_model_id(model_data_list[0].id)
        else:
            # Andere Provider: Standard-QComboBox
            self.model_combo.setVisible(True)
            self.model_label.setVisible(True)
            self.model_selector.setVisible(False)

            self.model_combo.blockSignals(True)
            self.model_combo.clear()
            for model in provider.models:
                self.model_combo.addItem(
                    f"{model.name} - {model.description}", model.id
                )

            # Letztes Modell wiederherstellen oder Default
            last_model = get_last_model(provider_id)
            if last_model:
                for i in range(self.model_combo.count()):
                    if self.model_combo.itemData(i) == last_model:
                        self.model_combo.setCurrentIndex(i)
                        break
            else:
                for i in range(self.model_combo.count()):
                    if self.model_combo.itemData(i) == provider.default_model:
                        self.model_combo.setCurrentIndex(i)
                        break

            self.model_combo.blockSignals(False)

        # Key-Status prüfen wenn API aktiv
        if self.api_checkbox.isChecked():
            if has_api_key(provider_id):
                self._update_api_status("idle")
            else:
                self._update_api_status("error")
                self.api_status_label.setText("Kein API-Key")

    @pyqtSlot(str)
    def _on_openrouter_model_selected(self, model_id: str) -> None:
        """Handler für FilterableModelSelector-Auswahl."""
        provider_id = self.provider_combo.currentData()
        if provider_id and model_id:
            save_last_selection(provider_id, model_id)

    @pyqtSlot(int)
    def _on_model_changed(self, _index: int) -> None:
        """Handler für Modell-Dropdown-Änderung (Perplexity QComboBox)."""
        # Auswahl speichern
        provider_id = self.provider_combo.currentData()
        model_id = self.model_combo.currentData()
        if provider_id and model_id:
            save_last_selection(provider_id, model_id)

    @pyqtSlot()
    def _on_settings(self) -> None:
        """Öffnet den Settings-Dialog für API-Key-Verwaltung."""
        from src.gui.settings_dialog import SettingsDialog
        dialog = SettingsDialog(self)
        if dialog.exec():
            # Nach Speichern: Key-Status prüfen
            if self.api_checkbox.isChecked():
                provider_id = self.provider_combo.currentData()
                if provider_id and has_api_key(provider_id):
                    self._update_api_status("idle")
                else:
                    self._update_api_status("error")
                    self.api_status_label.setText("Kein API-Key")

            # Debug-Logger-Status aktualisieren
            prefs = load_preferences()
            self._debug_logger.enabled = prefs.get("debug_logging", False)
            self.debug_icon_label.setVisible(self._debug_logger.enabled)

    def _restore_api_selection(self) -> None:
        """Stellt die letzte Provider/Modell-Auswahl wieder her."""
        last_provider = get_last_provider()
        for i in range(self.provider_combo.count()):
            if self.provider_combo.itemData(i) == last_provider:
                self.provider_combo.setCurrentIndex(i)
                break
        # Manuell triggern (falls Index bereits 0 war, feuert kein Signal)
        self._on_provider_changed(self.provider_combo.currentIndex())

    def _update_api_status(self, status: str) -> None:
        """Aktualisiert die Status-Anzeige."""
        _, color, text = STATUS_DISPLAY.get(status, ("", "#808080", status))
        self.api_status_label.setText(text)
        self.api_status_label.setStyleSheet(
            f"padding: 4px 8px; border-radius: 4px; "
            f"background-color: {color}22; color: {color};"
        )

    def _start_api_call(self, prompt: str) -> None:
        """Startet einen API-Call im Worker-Thread."""
        provider_id = self.provider_combo.currentData()
        model_id = self._get_active_model_id()

        if not provider_id or not model_id:
            return

        api_key = get_api_key(provider_id)
        if not api_key:
            self._update_api_status("error")
            self.api_status_label.setText("Kein API-Key")
            QMessageBox.warning(
                self,
                "API-Key fehlt",
                f"Kein API-Key für {self.provider_combo.currentText()} konfiguriert.",
            )
            return

        # Laufenden Worker abbrechen
        if self._api_worker and self._api_worker.isRunning():
            self._api_worker.cancel()
            self._api_worker.wait(2000)

        # Client erstellen
        if provider_id == "perplexity":
            client = PerplexityClient(api_key)
        elif provider_id == "openrouter":
            client = OpenRouterClient(api_key)
        else:
            self._update_api_status("error")
            self.api_status_label.setText("Provider nicht unterstützt")
            return

        # Debug-Meta zusammenbauen
        debug_meta = {
            "app_version": APP_VERSION,
            "preset_name": self.current_preset.name if self.current_preset else "",
            "depth": self.config.depth,
            "language": self.config.language,
            "api_mode": "automatic",
            "video_url": self.video_info.url if self.video_info else "",
            "video_title": self.video_info.title if self.video_info else "",
            "questions": self.questions_text.toPlainText(),
        }

        # Worker starten
        self._api_worker = APIWorker(
            client, prompt, model_id,
            debug_logger=self._debug_logger,
            debug_meta=debug_meta,
        )
        self._api_worker.status_changed.connect(self._on_api_status_changed)
        self._api_worker.response_received.connect(self._on_api_response)
        self._api_worker.error_occurred.connect(self._on_api_error)
        self._api_worker.start()

        # UI während API-Call sperren
        self.btn_generate.setEnabled(False)
        self.btn_generate.setText("API-Aufruf läuft...")

    @pyqtSlot(str)
    def _on_api_status_changed(self, status: str) -> None:
        """Handler für API-Statusänderungen."""
        self._update_api_status(status)

    @pyqtSlot(object)
    def _on_api_response(self, response: APIResponse) -> None:
        """Handler für erfolgreiche API-Antwort."""
        self._last_api_response = response
        self._clear_stale_sources()
        self.result_text.setText(response.content)
        logger.info(
            f"API-Antwort: {len(response.content)} Zeichen, "
            f"{response.tokens_used} Tokens ({response.model_used})"
        )

        # UI entsperren
        self.btn_generate.setEnabled(True)
        self.btn_generate.setText("Generate Prompt")

    @pyqtSlot(str)
    def _on_api_error(self, error_message: str) -> None:
        """Handler für API-Fehler."""
        logger.error(f"API-Fehler: {error_message}")
        self.api_status_label.setText(f"Fehler: {error_message[:50]}")
        QMessageBox.warning(self, "API-Fehler", error_message)

        # UI entsperren
        self.btn_generate.setEnabled(True)
        self.btn_generate.setText("Generate Prompt")

    def _clear_stale_sources(self) -> None:
        """Setzt den Quellen-Button und -Puffer zurück (verhindert Stale-State)."""
        self._detailed_sources = ""
        self.btn_sources_detail.setVisible(False)

    def _show_button_feedback(self, button: QPushButton, message: str):
        """Zeigt kurzes Feedback auf einem Button."""
        from PyQt6.QtCore import QTimer
        original_text = button.text()
        button.setText(message)
        button.setEnabled(False)
        QTimer.singleShot(1500, lambda: self._reset_button(button, original_text))

    def _reset_button(self, button: QPushButton, text: str):
        """Setzt einen Button zurück."""
        button.setText(text)
        button.setEnabled(True)
