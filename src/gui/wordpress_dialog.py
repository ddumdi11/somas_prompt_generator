"""Sende-Dialog: SOMAS-Analyse als WordPress-Beitrag (Variante A).

Getrennte Felder für Intro / Analyse / Outro. Das Intro-/Outro-Feld ist optional
– bleibt es leer, wird nur die Analyse gesendet. Status, Kategorie und Tags sind
einstellbar; Default-Status kommt aus den Einstellungen (üblicherweise „Entwurf").
"""

import logging
from typing import Optional

from PyQt6.QtCore import Qt, pyqtSlot
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtCore import QUrl
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QLineEdit,
    QTextEdit, QComboBox, QPushButton, QGroupBox, QMessageBox, QWidget,
    QApplication,
)

from src.core.wordpress_client import (
    WordPressClient, WordPressError, WP_STATUSES,
    assemble_content, markdown_to_html,
    get_wp_config, get_wp_app_password, has_wp_credentials,
)

logger = logging.getLogger(__name__)

#: Benutzerfreundliche Beschriftungen für die Status-Auswahl.
_STATUS_LABELS = {
    "draft": "Entwurf (draft)",
    "private": "Privat (private)",
    "publish": "Veröffentlichen (publish)",
    "pending": "Ausstehend (pending)",
}


class WordPressSendDialog(QDialog):
    """Dialog zum Senden einer Analyse an WordPress (Intro/Analyse/Outro)."""

    def __init__(
        self,
        analysis_md: str,
        suggested_title: str = "",
        parent: Optional[QWidget] = None,
    ) -> None:
        """Initialisiert den Sende-Dialog.

        Args:
            analysis_md: Die Analyse als Markdown (vorbefüllt, editierbar).
            suggested_title: Vorschlag für den Beitragstitel (z.B. Videotitel).
            parent: Optionales Parent-Widget.
        """
        super().__init__(parent)
        self.setWindowTitle("An Blog senden (WordPress)")
        self.setMinimumSize(640, 640)

        self._config = get_wp_config()
        self._last_link: str = ""

        self._setup_ui(analysis_md, suggested_title)

    # ------------------------------------------------------------------ UI -- #

    def _setup_ui(self, analysis_md: str, suggested_title: str) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # Ziel-Hinweis
        target = self._config.url or "(keine WordPress-URL konfiguriert)"
        info = QLabel(f"Ziel: <b>{target}</b>")
        info.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(info)

        # Titel
        form = QFormLayout()
        self.title_input = QLineEdit(suggested_title)
        self.title_input.setPlaceholderText("Beitragstitel…")
        form.addRow("Titel:", self.title_input)
        layout.addLayout(form)

        # Intro (optional)
        layout.addWidget(self._field_label(
            "Intro (optional, Markdown – z.B. Kommentar/Emoji-Einleitung 😉)"
        ))
        self.intro_edit = QTextEdit()
        self.intro_edit.setPlaceholderText("Optionaler Einleitungstext…")
        self.intro_edit.setMaximumHeight(90)
        layout.addWidget(self.intro_edit)

        # Analyse (vorbefüllt, editierbar)
        layout.addWidget(self._field_label("Analyse (Markdown):"))
        self.analysis_edit = QTextEdit()
        self.analysis_edit.setPlainText(analysis_md)
        self.analysis_edit.setMinimumHeight(220)
        layout.addWidget(self.analysis_edit, stretch=1)

        # Outro (optional)
        layout.addWidget(self._field_label("Outro (optional, Markdown):"))
        self.outro_edit = QTextEdit()
        self.outro_edit.setPlaceholderText("Optionaler Ausleitungstext…")
        self.outro_edit.setMaximumHeight(90)
        layout.addWidget(self.outro_edit)

        # Publikations-Optionen
        layout.addWidget(self._build_options_group())

        # Status-Zeile
        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet("color: gray; font-style: italic;")
        layout.addWidget(self.status_label)

        # Buttons
        btn_row = QHBoxLayout()
        self.btn_preview = QPushButton("HTML-Vorschau")
        self.btn_preview.clicked.connect(self._on_preview)
        btn_row.addWidget(self.btn_preview)
        btn_row.addStretch()

        self.btn_open = QPushButton("Im Browser öffnen")
        self.btn_open.setEnabled(False)
        self.btn_open.clicked.connect(self._on_open_link)
        btn_row.addWidget(self.btn_open)

        self.btn_send = QPushButton("An Blog senden")
        self.btn_send.setDefault(True)
        self.btn_send.clicked.connect(self._on_send)
        btn_row.addWidget(self.btn_send)

        self.btn_close = QPushButton("Schließen")
        self.btn_close.clicked.connect(self.reject)
        btn_row.addWidget(self.btn_close)

        layout.addLayout(btn_row)

        if not has_wp_credentials():
            self._set_status(
                "WordPress ist noch nicht vollständig konfiguriert. "
                "Bitte URL, Benutzer und Application Password unter 'Settings' "
                "hinterlegen.",
                error=True,
            )
            self.btn_send.setEnabled(False)

    def _build_options_group(self) -> QGroupBox:
        group = QGroupBox("Veröffentlichung")
        grid = QFormLayout(group)

        # Status
        self.status_combo = QComboBox()
        for status in WP_STATUSES:
            self.status_combo.addItem(_STATUS_LABELS.get(status, status), status)
        # Default-Status vorwählen
        idx = self.status_combo.findData(self._config.default_status)
        if idx >= 0:
            self.status_combo.setCurrentIndex(idx)
        grid.addRow("Status:", self.status_combo)

        # Kategorie (Default aus Config)
        self.category_input = QLineEdit(self._config.default_category)
        self.category_input.setPlaceholderText("z.B. YouTube-Analysen (optional)")
        grid.addRow("Kategorie:", self.category_input)

        # Tags
        self.tags_input = QLineEdit()
        self.tags_input.setPlaceholderText("Tag1, Tag2, … (optional)")
        grid.addRow("Tags:", self.tags_input)

        return group

    @staticmethod
    def _field_label(text: str) -> QLabel:
        label = QLabel(text)
        label.setStyleSheet("font-weight: bold;")
        return label

    # --------------------------------------------------------------- Logik -- #

    def _assembled_markdown(self) -> str:
        return assemble_content(
            self.intro_edit.toPlainText(),
            self.analysis_edit.toPlainText(),
            self.outro_edit.toPlainText(),
        )

    @pyqtSlot()
    def _on_preview(self) -> None:
        """Zeigt das konvertierte HTML in einem Vorschau-Dialog."""
        try:
            html = markdown_to_html(self._assembled_markdown())
        except RuntimeError as exc:
            QMessageBox.critical(self, "Vorschau", str(exc))
            return

        dlg = QDialog(self)
        dlg.setWindowTitle("HTML-Vorschau")
        dlg.setMinimumSize(560, 480)
        v = QVBoxLayout(dlg)
        view = QTextEdit()
        view.setReadOnly(True)
        view.setHtml(html)
        v.addWidget(view)
        btn = QPushButton("Schließen")
        btn.clicked.connect(dlg.accept)
        v.addWidget(btn)
        dlg.exec()

    @pyqtSlot()
    def _on_send(self) -> None:
        """Konvertiert, löst Kategorie/Tags auf und postet den Beitrag."""
        title = self.title_input.text().strip()
        if not title:
            QMessageBox.warning(self, "Senden", "Bitte einen Titel eingeben.")
            return

        analysis = self.analysis_edit.toPlainText().strip()
        if not analysis:
            QMessageBox.warning(self, "Senden", "Die Analyse ist leer.")
            return

        app_password = get_wp_app_password()
        if not self._config.is_complete or not app_password:
            QMessageBox.warning(
                self, "Senden",
                "WordPress ist nicht vollständig konfiguriert (URL, Benutzer, "
                "Application Password). Bitte unter 'Settings' hinterlegen.",
            )
            return

        status = self.status_combo.currentData()
        category_names = [self.category_input.text()] if self.category_input.text().strip() else []
        tag_names = [t for t in self.tags_input.text().split(",") if t.strip()]

        self.btn_send.setEnabled(False)
        self._set_status("Sende an WordPress…", error=False)
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            client = WordPressClient(self._config, app_password)
            html = markdown_to_html(self._assembled_markdown())

            category_ids = client.resolve_terms(category_names, "categories")
            tag_ids = client.resolve_terms(tag_names, "tags")

            post_id, link = client.post(
                title=title,
                html_content=html,
                status=status,
                category_ids=category_ids or None,
                tag_ids=tag_ids or None,
            )
        except (WordPressError, RuntimeError) as exc:
            QApplication.restoreOverrideCursor()
            logger.error("WordPress-Senden fehlgeschlagen: %s", exc)
            self._set_status(str(exc), error=True)
            QMessageBox.critical(self, "Senden fehlgeschlagen", str(exc))
            self.btn_send.setEnabled(True)
            return
        else:
            QApplication.restoreOverrideCursor()

        self._last_link = link
        self.btn_open.setEnabled(bool(link))
        status_word = _STATUS_LABELS.get(status, status)
        self._set_status(
            f"Gesendet ✓ (Beitrag #{post_id}, Status: {status_word}).",
            error=False,
        )
        self.btn_send.setEnabled(True)
        logger.info("WordPress-Beitrag #%s erstellt (%s)", post_id, status)

    @pyqtSlot()
    def _on_open_link(self) -> None:
        if self._last_link:
            QDesktopServices.openUrl(QUrl(self._last_link))

    def _set_status(self, message: str, error: bool) -> None:
        self.status_label.setText(message)
        color = "#C62828" if error else "#2E7D32"
        self.status_label.setStyleSheet(f"color: {color};")
