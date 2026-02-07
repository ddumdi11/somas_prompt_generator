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

# Quellen-Dimensionen: (key, label)
CHANNEL_DIMS = [
    ("informative", "Informativ:"),
    ("balanced", "Ausgewogen:"),
    ("sourced", "Quellenbasiert:"),
    ("entertaining", "Unterhaltung:"),
]


class RatingWidget(QWidget):
    """Bewertungspanel mit Sternen (Analyse) und 4 Quellen-Dimensionen.

    Signals:
        rating_submitted(int, dict): (quality_score, channel_dims)
            quality_score: 0 = nicht bewertet, 1-5 = Sterne
            channel_dims: {"informative": 0/1/-1, "balanced": ..., ...}
    """

    rating_submitted = pyqtSignal(int, dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._quality_score: int = 0
        self._channel_dims: dict[str, int] = {k: 0 for k, _ in CHANNEL_DIMS}
        self._expanded: bool = False
        self._dim_buttons: dict[str, tuple[QPushButton, QPushButton]] = {}
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

        # 4 Quellen-Dimensionen
        for dim_key, dim_label in CHANNEL_DIMS:
            dim_row = QHBoxLayout()
            label = QLabel(dim_label)
            label.setMinimumWidth(100)
            dim_row.addWidget(label)

            btn_up = QPushButton("\U0001f44d")
            btn_up.setFixedSize(32, 28)
            btn_up.setStyleSheet(
                "border: 1px solid #ccc; border-radius: 3px; font-size: 14px;"
            )
            btn_up.clicked.connect(
                lambda checked, k=dim_key: self._on_channel_clicked(k, 1)
            )
            dim_row.addWidget(btn_up)

            btn_down = QPushButton("\U0001f44e")
            btn_down.setFixedSize(32, 28)
            btn_down.setStyleSheet(
                "border: 1px solid #ccc; border-radius: 3px; font-size: 14px;"
            )
            btn_down.clicked.connect(
                lambda checked, k=dim_key: self._on_channel_clicked(k, -1)
            )
            dim_row.addWidget(btn_down)

            dim_row.addStretch()
            panel_layout.addLayout(dim_row)

            self._dim_buttons[dim_key] = (btn_up, btn_down)

        # OK-Button (eigene Zeile)
        ok_row = QHBoxLayout()
        ok_row.addStretch()
        self.btn_ok = QPushButton("OK")
        self.btn_ok.setFixedWidth(50)
        self.btn_ok.clicked.connect(self._on_ok)
        ok_row.addWidget(self.btn_ok)
        panel_layout.addLayout(ok_row)

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

    def _on_channel_clicked(self, dim_key: str, value: int):
        """Daumen einer Dimension angeklickt — Toggle."""
        if self._channel_dims[dim_key] == value:
            self._channel_dims[dim_key] = 0
        else:
            self._channel_dims[dim_key] = value
        self._update_channel_display()

    def _on_ok(self):
        """OK geklickt — speichert nur was ausgewählt ist."""
        has_quality = self._quality_score != 0
        has_channel = any(v != 0 for v in self._channel_dims.values())

        if has_quality or has_channel:
            self.rating_submitted.emit(
                self._quality_score, dict(self._channel_dims)
            )

        self._expanded = False
        self.panel.setVisible(False)
        self._update_summary()
        self.summary_btn.setVisible(True)

    def _update_star_display(self):
        """Aktualisiert die visuelle Stern-Anzeige."""
        for i, btn in enumerate(self.star_buttons):
            btn.setText("\u2605" if i < self._quality_score else "\u2606")

    def _update_channel_display(self):
        """Aktualisiert die visuelle Daumen-Anzeige aller Dimensionen."""
        for dim_key, (btn_up, btn_down) in self._dim_buttons.items():
            value = self._channel_dims[dim_key]
            up_active = value == 1
            down_active = value == -1
            btn_up.setStyleSheet(
                f"border: 1px solid {'#4CAF50' if up_active else '#ccc'}; "
                f"border-radius: 3px; font-size: 14px; "
                f"background: {'#E8F5E9' if up_active else 'transparent'};"
            )
            btn_down.setStyleSheet(
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

        ups = sum(1 for v in self._channel_dims.values() if v == 1)
        downs = sum(1 for v in self._channel_dims.values() if v == -1)
        if ups > 0:
            parts.append(f"\U0001f44d{ups}")
        if downs > 0:
            parts.append(f"\U0001f44e{downs}")

        if parts:
            self.summary_btn.setText(" ".join(parts))
        else:
            self.summary_btn.setText("\u2b50 Bewerten")

    def reset(self):
        """Setzt alles zurück (für neue Analyse)."""
        self._quality_score = 0
        self._channel_dims = {k: 0 for k, _ in CHANNEL_DIMS}
        self._expanded = False
        self.panel.setVisible(False)
        self.summary_btn.setText("\u2b50 Bewerten")
        self.summary_btn.setVisible(True)
        self._update_star_display()
        self._update_channel_display()

    def set_visible_after_analysis(self, visible: bool):
        """Zeigt/versteckt das Widget nach API-Response."""
        self.setVisible(visible)
        if visible and self._quality_score == 0:
            self.summary_btn.setText("\u2b50 Bewerten")
