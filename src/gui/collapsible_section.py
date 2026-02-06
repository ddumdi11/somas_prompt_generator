"""Einklappbare Sektion mit kompakter Header-Zusammenfassung.

Wiederverwendbares Widget für Bereiche, die nach dem Befüllen
eingeklappt werden können, um Platz zu sparen.
"""

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel
from PyQt6.QtCore import pyqtSignal, Qt


class CollapsibleSection(QWidget):
    """Einklappbare Sektion mit kompakter Header-Zusammenfassung."""

    toggled = pyqtSignal(bool)  # True = expanded

    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._expanded = True
        self._title = title
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Erstellt Header und Body."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header (klickbar)
        self._header = QWidget()
        self._header.setCursor(Qt.CursorShape.PointingHandCursor)
        self._header.setStyleSheet(
            "background-color: #E8E8E8; border: 1px solid #C0C0C0; "
            "border-radius: 4px; padding: 6px 10px;"
        )
        header_layout = QHBoxLayout(self._header)
        header_layout.setContentsMargins(10, 6, 10, 6)

        # Pfeil
        self._arrow_label = QLabel("▼")
        self._arrow_label.setStyleSheet("color: #666; font-size: 10px;")
        self._arrow_label.setFixedWidth(16)
        header_layout.addWidget(self._arrow_label)

        # Titel
        self._title_label = QLabel(self._title)
        self._title_label.setStyleSheet(
            "font-weight: 500; font-size: 12px; background: transparent;"
        )
        header_layout.addWidget(self._title_label)

        header_layout.addStretch()

        # Zusammenfassung (rechts)
        self._summary_label = QLabel("")
        self._summary_label.setStyleSheet(
            "font-size: 11px; color: #888; background: transparent;"
        )
        header_layout.addWidget(self._summary_label)

        self._header.mousePressEvent = self._on_header_clicked
        layout.addWidget(self._header)

        # Body-Container
        self._body = QWidget()
        self._body.setStyleSheet(
            "background-color: white; "
            "border: 1px solid #C0C0C0; border-top: none; "
            "border-bottom-left-radius: 4px; border-bottom-right-radius: 4px;"
        )
        self._body_layout = QVBoxLayout(self._body)
        self._body_layout.setContentsMargins(10, 8, 10, 8)
        layout.addWidget(self._body)

    def _on_header_clicked(self, event) -> None:
        """Toggle bei Klick auf den Header."""
        if self._expanded:
            self.collapse()
        else:
            self.expand()

    def _update_arrow(self) -> None:
        """Aktualisiert den Pfeil-Indikator."""
        self._arrow_label.setText("▼" if self._expanded else "▶")
        # Header-Border anpassen
        if self._expanded:
            self._header.setStyleSheet(
                "background-color: #E8E8E8; border: 1px solid #C0C0C0; "
                "border-top-left-radius: 4px; border-top-right-radius: 4px; "
                "border-bottom-left-radius: 0px; border-bottom-right-radius: 0px;"
            )
        else:
            self._header.setStyleSheet(
                "background-color: #E8E8E8; border: 1px solid #C0C0C0; "
                "border-radius: 4px;"
            )

    def set_summary(self, text: str) -> None:
        """Kompakter Text im Header rechts."""
        self._summary_label.setText(text)
        if text and text not in ("", "Inaktiv"):
            self._summary_label.setStyleSheet(
                "font-size: 11px; color: #2E7D32; background: transparent;"
            )
        else:
            self._summary_label.setStyleSheet(
                "font-size: 11px; color: #888; background: transparent;"
            )

    def set_content_widget(self, widget: QWidget) -> None:
        """Setzt das Widget im aufklappbaren Body."""
        self._body_layout.addWidget(widget)

    def expand(self) -> None:
        """Klappt die Sektion auf."""
        self._expanded = True
        self._body.setVisible(True)
        self._update_arrow()
        self.toggled.emit(True)

    def collapse(self) -> None:
        """Klappt die Sektion ein."""
        self._expanded = False
        self._body.setVisible(False)
        self._update_arrow()
        self.toggled.emit(False)

    def is_expanded(self) -> bool:
        """Gibt zurück ob die Sektion aufgeklappt ist."""
        return self._expanded
