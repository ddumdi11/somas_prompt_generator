"""Widget für manuelle Transkript-Eingabe.

Ermöglicht die SOMAS-Analyse von Texten ohne YouTube-URL,
z.B. eigene Transkriptionen, Podcast-Mitschnitte oder Vorträge.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QGroupBox,
    QLabel, QLineEdit, QTextEdit, QPushButton,
)
from PyQt6.QtCore import pyqtSignal, pyqtSlot


class TranscriptInputWidget(QWidget):
    """Widget für manuelle Transkript-Eingabe mit Quellen-Informationen."""

    # Signal wenn sich Daten ändern
    data_changed = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._auto_source = False
        self._original_transcript = ""
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self) -> None:
        """Erstellt das UI-Layout."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Quellen-Informationen
        info_group = QGroupBox("Quellen-Informationen")
        info_layout = QFormLayout(info_group)

        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("Titel der Quelle")
        info_layout.addRow("Titel:", self.title_edit)

        self.author_edit = QLineEdit()
        self.author_edit.setPlaceholderText("Autor, Kanal oder Sprecher")
        info_layout.addRow("Autor/Kanal:", self.author_edit)

        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("https://... (optional)")
        info_layout.addRow("URL:", self.url_edit)

        layout.addWidget(info_group)

        # Transkript
        transcript_label = QLabel("Transkript:")
        layout.addWidget(transcript_label)

        self.transcript_edit = QTextEdit()
        self.transcript_edit.setPlaceholderText(
            "Transkript hier einfügen...\n\n"
            "Unterstützt: Eigene Transkriptionen, Podcast-Mitschnitte, "
            "Vortragsnotizen, korrigierte Untertitel etc."
        )
        self.transcript_edit.setMinimumHeight(200)
        layout.addWidget(self.transcript_edit)

        # Statistik-Zeile
        self.stats_label = QLabel("Zeichen: 0 | Wörter: 0")
        self.stats_label.setStyleSheet("color: gray; font-style: italic;")
        layout.addWidget(self.stats_label)

        # Quellen-Hinweis + Zurücksetzen-Button (nur bei auto-fetched sichtbar)
        source_row = QHBoxLayout()
        self.source_label = QLabel("")
        source_row.addWidget(self.source_label)
        source_row.addStretch()
        self.reset_btn = QPushButton("Zurücksetzen")
        self.reset_btn.setMaximumWidth(120)
        self.reset_btn.setVisible(False)
        source_row.addWidget(self.reset_btn)
        layout.addLayout(source_row)

    def _connect_signals(self) -> None:
        """Verbindet interne Signals."""
        self.transcript_edit.textChanged.connect(self._on_text_changed)
        self.title_edit.textChanged.connect(self.data_changed.emit)
        self.author_edit.textChanged.connect(self.data_changed.emit)
        self.url_edit.textChanged.connect(self.data_changed.emit)
        self.reset_btn.clicked.connect(self.reset_transcript)

    @pyqtSlot()
    def _on_text_changed(self) -> None:
        """Aktualisiert die Statistik-Anzeige bei Textänderung."""
        text = self.transcript_edit.toPlainText()
        chars = len(text)
        words = len(text.split()) if text.strip() else 0
        reading_time = max(1, words // 200) if words > 0 else 0

        if reading_time > 0:
            self.stats_label.setText(
                f"Zeichen: {chars:,} | Wörter: {words:,} | "
                f"~{reading_time} Min. Lesezeit"
            )
        else:
            self.stats_label.setText(f"Zeichen: {chars:,} | Wörter: {words:,}")

        self.data_changed.emit()

    def get_data(self) -> dict | None:
        """Gibt die eingegebenen Daten zurück oder None wenn unvollständig.

        Returns:
            Dict mit title, author, url, transcript, word_count
            oder None wenn Pflichtfelder (Titel, Transkript) leer sind.
        """
        title = self.title_edit.text().strip()
        transcript = self.transcript_edit.toPlainText().strip()

        if not title or not transcript:
            return None

        return {
            "title": title,
            "author": self.author_edit.text().strip() or "Unbekannt",
            "url": self.url_edit.text().strip() or None,
            "transcript": transcript,
            "word_count": len(transcript.split()),
        }

    def has_valid_data(self) -> bool:
        """Prüft ob Pflichtfelder ausgefüllt sind."""
        return bool(
            self.title_edit.text().strip()
            and self.transcript_edit.toPlainText().strip()
        )

    def clear(self) -> None:
        """Setzt alle Felder zurück."""
        self.title_edit.clear()
        self.author_edit.clear()
        self.url_edit.clear()
        self.transcript_edit.clear()
        self._auto_source = False
        self._original_transcript = ""
        self.source_label.setText("")
        self.reset_btn.setVisible(False)

    def set_auto_transcript(
        self, transcript: str, title: str, author: str, url: str = ""
    ) -> None:
        """Befüllt das Widget mit einem automatisch geholten Transkript."""
        self._original_transcript = transcript
        self._auto_source = True
        self.title_edit.setText(title)
        self.author_edit.setText(author)
        if url:
            self.url_edit.setText(url)
        self.transcript_edit.setPlainText(transcript)
        self.source_label.setText(
            "\u2713 Automatisch von YouTube geladen \u00b7 editierbar"
        )
        self.source_label.setStyleSheet("color: #2E7D32; font-size: 10px;")
        self.reset_btn.setVisible(True)

    def reset_transcript(self) -> None:
        """Stellt das Original-Transkript wieder her."""
        if self._original_transcript:
            self.transcript_edit.setPlainText(self._original_transcript)
