"""Kompaktes Bewertungswidget für Analyse-Qualität und Quellen-Bewertung."""

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class RatingWidget(QWidget):
    """Bewertungspanel mit Sternen (Analyse) und Daumen (Quelle).

    Signals:
        rating_submitted(int, int): (quality_score, channel_score)
            quality_score: 0 = nicht bewertet, 1-5 = Sterne
            channel_score: 0 = nicht bewertet, 1 = gut, -1 = schlecht
    """

    rating_submitted = pyqtSignal(int, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._quality_score: int = 0
        self._channel_score: int = 0
        self._expanded: bool = False
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Kompakt-Button (Normalzustand)
        self.summary_btn = QPushButton("\u2b50 Bewerten")
        self.summary_btn.setStyleSheet(
            "padding: 2px 8px; border: 1px solid #FFD54F; "
            "border-radius: 3px; background: #FFFDE7; "
            "color: #F57F17; font-size: 11px;"
        )
        self.summary_btn.clicked.connect(self._toggle_panel)
        layout.addWidget(self.summary_btn)

        # Bewertungspanel (initial versteckt)
        self.panel = QFrame()
        self.panel.setFrameStyle(QFrame.Shape.StyledPanel)
        self.panel.setStyleSheet(
            "QFrame { background: #FFFDE7; border: 1px solid #FFD54F; "
            "border-radius: 4px; padding: 6px; }"
        )
        self.panel.setVisible(False)
        panel_layout = QVBoxLayout(self.panel)
        panel_layout.setSpacing(6)
        panel_layout.setContentsMargins(8, 6, 8, 6)

        # Zeile 1: Analyse-Sterne
        star_row = QHBoxLayout()
        star_row.addWidget(QLabel("Analyse:"))
        self.star_buttons: list[QPushButton] = []
        for i in range(5):
            btn = QPushButton("\u2606")
            btn.setFixedSize(24, 24)
            btn.setStyleSheet("border: none; font-size: 16px;")
            btn.clicked.connect(lambda checked, idx=i + 1: self._on_star_clicked(idx))
            self.star_buttons.append(btn)
            star_row.addWidget(btn)
        star_row.addStretch()
        panel_layout.addLayout(star_row)

        # Zeile 2: Quellen-Daumen + OK
        channel_row = QHBoxLayout()
        channel_row.addWidget(QLabel("Quelle:"))

        self.btn_thumbs_up = QPushButton("\U0001f44d")
        self.btn_thumbs_up.setFixedSize(32, 28)
        self.btn_thumbs_up.setStyleSheet(
            "border: 1px solid #ccc; border-radius: 3px; font-size: 14px;"
        )
        self.btn_thumbs_up.clicked.connect(lambda: self._on_channel_clicked(1))
        channel_row.addWidget(self.btn_thumbs_up)

        self.btn_thumbs_down = QPushButton("\U0001f44e")
        self.btn_thumbs_down.setFixedSize(32, 28)
        self.btn_thumbs_down.setStyleSheet(
            "border: 1px solid #ccc; border-radius: 3px; font-size: 14px;"
        )
        self.btn_thumbs_down.clicked.connect(lambda: self._on_channel_clicked(-1))
        channel_row.addWidget(self.btn_thumbs_down)

        channel_row.addStretch()

        self.btn_ok = QPushButton("OK")
        self.btn_ok.setFixedWidth(50)
        self.btn_ok.clicked.connect(self._on_ok)
        channel_row.addWidget(self.btn_ok)

        panel_layout.addLayout(channel_row)
        layout.addWidget(self.panel)

    def _toggle_panel(self):
        """Öffnet/schließt das Bewertungspanel."""
        self._expanded = not self._expanded
        self.panel.setVisible(self._expanded)
        if self._expanded:
            self.summary_btn.setVisible(False)

    def _on_star_clicked(self, score: int):
        """Stern angeklickt — Toggle: erneuter Klick auf gleichen = abwählen."""
        if self._quality_score == score:
            self._quality_score = 0
        else:
            self._quality_score = score
        self._update_star_display()

    def _on_channel_clicked(self, value: int):
        """Daumen angeklickt — Toggle: erneuter Klick = abwählen."""
        if self._channel_score == value:
            self._channel_score = 0
        else:
            self._channel_score = value
        self._update_channel_display()

    def _on_ok(self):
        """OK geklickt — speichert nur was ausgewählt ist."""
        if self._quality_score != 0 or self._channel_score != 0:
            self.rating_submitted.emit(self._quality_score, self._channel_score)

        self._expanded = False
        self.panel.setVisible(False)
        self._update_summary()
        self.summary_btn.setVisible(True)

    def _update_star_display(self):
        """Aktualisiert die visuelle Stern-Anzeige."""
        for i, btn in enumerate(self.star_buttons):
            btn.setText("\u2605" if i < self._quality_score else "\u2606")

    def _update_channel_display(self):
        """Aktualisiert die visuelle Daumen-Anzeige."""
        up_active = self._channel_score == 1
        down_active = self._channel_score == -1
        self.btn_thumbs_up.setStyleSheet(
            f"border: 1px solid {'#4CAF50' if up_active else '#ccc'}; "
            f"border-radius: 3px; font-size: 14px; "
            f"background: {'#E8F5E9' if up_active else 'transparent'};"
        )
        self.btn_thumbs_down.setStyleSheet(
            f"border: 1px solid {'#F44336' if down_active else '#ccc'}; "
            f"border-radius: 3px; font-size: 14px; "
            f"background: {'#FFEBEE' if down_active else 'transparent'};"
        )

    def _update_summary(self):
        """Aktualisiert den Summary-Button nach Bewertung."""
        parts = []
        if self._quality_score > 0:
            parts.append(
                "\u2605" * self._quality_score
                + "\u2606" * (5 - self._quality_score)
            )
        if self._channel_score == 1:
            parts.append("\U0001f44d")
        elif self._channel_score == -1:
            parts.append("\U0001f44e")

        if parts:
            self.summary_btn.setText(" ".join(parts))
        else:
            self.summary_btn.setText("\u2b50 Bewerten")

    def reset(self):
        """Setzt alles zurück (für neue Analyse)."""
        self._quality_score = 0
        self._channel_score = 0
        self._expanded = False
        self.panel.setVisible(False)
        self.summary_btn.setText("\u2b50 Bewerten")
        self.summary_btn.setVisible(True)
        self._update_star_display()
        self._update_channel_display()

    def set_visible_after_analysis(self, visible: bool):
        """Zeigt/versteckt das Widget nach API-Response."""
        self.setVisible(visible)
        if visible and self._quality_score == 0 and self._channel_score == 0:
            self.summary_btn.setText("\u2b50 Bewerten")
