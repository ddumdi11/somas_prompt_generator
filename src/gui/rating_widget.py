"""Kompaktes Bewertungswidget für Modell-Qualität (Z-Skala)."""

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

# Z-Skala Labels für die 5 Sterne
_Z_LABELS = ["-2", "-1", "0", "+1", "+2"]


class RatingWidget(QWidget):
    """Bewertungspanel mit 5 Sternen auf Z-Skala (-2 bis +2).

    Die Sterne bewerten die Qualität der Modell-Analyse:
      ★☆☆☆☆ = -2 (sehr schlecht)
      ★★☆☆☆ = -1 (schlecht)
      ★★★☆☆ =  0 (okay)
      ★★★★☆ = +1 (gut)
      ★★★★★ = +2 (sehr gut)

    Signals:
        rating_submitted(int): z_score (-2 bis +2)
    """

    rating_submitted = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._z_score: int | None = None  # None = nicht bewertet
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
        panel_layout.setSpacing(4)
        panel_layout.setContentsMargins(8, 6, 8, 6)

        # Stern-Zeile
        star_row = QHBoxLayout()
        star_row.addWidget(QLabel("Modell:"))
        self.star_buttons: list[QPushButton] = []
        for i in range(5):
            btn = QPushButton("\u2606")
            btn.setFixedSize(28, 28)
            btn.setStyleSheet("border: none; font-size: 18px; padding: 0;")
            btn.setToolTip(f"Z-Score: {_Z_LABELS[i]}")
            btn.clicked.connect(
                lambda checked, idx=i: self._on_star_clicked(idx)
            )
            self.star_buttons.append(btn)
            star_row.addWidget(btn)
        star_row.addStretch()

        # OK-Button in der Stern-Zeile
        self.btn_ok = QPushButton("OK")
        self.btn_ok.setFixedWidth(40)
        self.btn_ok.setStyleSheet("font-size: 11px;")
        self.btn_ok.clicked.connect(self._on_ok)
        star_row.addWidget(self.btn_ok)
        panel_layout.addLayout(star_row)

        # Orientierungs-Labels
        label_row = QHBoxLayout()
        label_row.addSpacing(48)  # Platz für "Modell:" Label
        lbl_bad = QLabel("schlecht")
        lbl_bad.setStyleSheet("color: #999; font-size: 9px; border: none;")
        label_row.addWidget(lbl_bad)
        label_row.addStretch()
        lbl_ok = QLabel("okay")
        lbl_ok.setStyleSheet("color: #999; font-size: 9px; border: none;")
        label_row.addWidget(lbl_ok)
        label_row.addStretch()
        lbl_good = QLabel("gut")
        lbl_good.setStyleSheet("color: #999; font-size: 9px; border: none;")
        label_row.addWidget(lbl_good)
        label_row.addSpacing(52)  # Platz für OK-Button
        panel_layout.addLayout(label_row)

        layout.addWidget(self.panel)

    def _toggle_panel(self):
        """Öffnet/schließt das Bewertungspanel."""
        self._expanded = not self._expanded
        self.panel.setVisible(self._expanded)
        if self._expanded:
            self.summary_btn.setVisible(False)

    def _on_star_clicked(self, star_index: int):
        """Stern angeklickt — Toggle: erneuter Klick = abwählen.

        Args:
            star_index: 0-4, wird zu Z-Score -2 bis +2 gemappt.
        """
        z_score = star_index - 2
        if self._z_score == z_score:
            self._z_score = None  # Abwählen
        else:
            self._z_score = z_score
        self._update_star_display()

    def _on_ok(self):
        """OK geklickt — sendet Z-Score wenn bewertet."""
        if self._z_score is not None:
            self.rating_submitted.emit(self._z_score)

        self._expanded = False
        self.panel.setVisible(False)
        self._update_summary()
        self.summary_btn.setVisible(True)

    def _update_star_display(self):
        """Aktualisiert die visuelle Stern-Anzeige."""
        if self._z_score is None:
            for btn in self.star_buttons:
                btn.setText("\u2606")
            return
        star_count = self._z_score + 3  # z=-2→1 Star, z=+2→5 Stars
        for i, btn in enumerate(self.star_buttons):
            btn.setText("\u2605" if i < star_count else "\u2606")

    def _update_summary(self):
        """Aktualisiert den Summary-Button nach Bewertung."""
        if self._z_score is not None:
            star_count = self._z_score + 3
            stars = "\u2605" * star_count + "\u2606" * (5 - star_count)
            sign = "+" if self._z_score > 0 else ""
            self.summary_btn.setText(f"{stars} ({sign}{self._z_score})")
        else:
            self.summary_btn.setText("\u2b50 Bewerten")

    def reset(self):
        """Setzt alles zurück (für neue Analyse)."""
        self._z_score = None
        self._expanded = False
        self.panel.setVisible(False)
        self.summary_btn.setText("\u2b50 Bewerten")
        self.summary_btn.setVisible(True)
        self._update_star_display()

    def set_visible_after_analysis(self, visible: bool):
        """Zeigt/versteckt das Widget nach API-Response."""
        self.setVisible(visible)
        if visible and self._z_score is None:
            self.summary_btn.setText("\u2b50 Bewerten")
