"""Hauptfenster der SOMAS Prompt Generator App."""

import logging
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QTextEdit, QMessageBox,
    QFrame, QApplication, QComboBox
)
from PyQt6.QtCore import Qt, pyqtSlot
from PyQt6.QtGui import QFont

from src.config.defaults import VideoInfo, SomasConfig
from src.core.youtube_client import get_video_info
from src.core.prompt_builder import (
    build_prompt, load_presets, get_preset_by_name, PromptPreset
)
from src.core.linkedin_formatter import format_for_linkedin
from src.core.export import export_to_markdown


logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """Hauptfenster der SOMAS Prompt Generator Anwendung."""

    def __init__(self):
        super().__init__()
        self.video_info: VideoInfo | None = None
        self.config = SomasConfig()
        self.current_preset: PromptPreset | None = None

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

        # URL-Eingabe
        main_layout.addLayout(self._create_url_section())

        # Meta-Informationen
        main_layout.addWidget(self._create_meta_section())

        # Fragen-Sektion
        main_layout.addWidget(self._create_questions_section())

        # Preset-Auswahl
        main_layout.addLayout(self._create_preset_section())

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
            # Max-Zeichen aktualisieren
            self.max_chars_label.setText(
                f"Max: {self.current_preset.max_chars:,} Zeichen".replace(",", ".")
            )
        else:
            # Keine Presets verfügbar
            self.preset_description.setText("Keine Presets verfügbar")
            self.reading_time_label.setText("")
            self.max_chars_label.setText("")

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
        if not self.video_info:
            QMessageBox.warning(self, "Fehler", "Bitte zuerst Metadaten abrufen.")
            return

        questions = self.questions_text.toPlainText()

        # Verwende das ausgewählte Preset
        preset_name = self.current_preset.name if self.current_preset else None
        prompt = build_prompt(self.video_info, self.config, questions, preset_name)
        self.prompt_text.setText(prompt)

        # Zeige Zeichenzahl im Prompt-Header
        char_count = len(prompt)
        max_chars = self.current_preset.max_chars if self.current_preset else 2800
        logger.info(f"Prompt generiert: {char_count} Zeichen (Max: {max_chars})")

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

        try:
            # Konvertiere zu LinkedIn-Format (mit Post-Header aus Video-Metadaten)
            video_title = self.video_info.title if self.video_info else ""
            video_channel = self.video_info.channel if self.video_info else ""

            logger.info(f"LinkedIn-Export: {len(result)} Zeichen Eingabe")
            linkedin_text, detailed_sources = format_for_linkedin(
                result, video_title, video_channel
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

        # Dateiname vorschlagen
        if self.video_info:
            default_name = f"{self.video_info.title[:40]}.md"
        else:
            default_name = "somas_analyse.md"

        # Datei-Dialog
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Markdown exportieren",
            default_name,
            "Markdown Files (*.md);;All Files (*)"
        )

        if file_path:
            try:
                export_to_markdown(result, self.video_info, file_path)
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
