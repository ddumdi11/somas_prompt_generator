"""Dialog zur Bewertung eines YouTube-Kanals."""

import logging

from PyQt6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QRadioButton,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
)

from src.core.rating_store import RatingStore

logger = logging.getLogger(__name__)

# Bias-Richtungen für Dropdown (erweitertes Spektrum)
BIAS_DIRECTIONS = [
    ("", "keine Einschätzung"),
    ("links", "links"),
    ("mitte-links", "mitte-links"),
    ("neutral", "neutral"),
    ("mitte-rechts", "mitte-rechts"),
    ("rechts", "rechts"),
    ("libertär", "libertär"),
    ("religiös-konservativ", "religiös-konservativ"),
    ("anti-systemisch", "anti-systemisch"),
    ("nationalistisch", "nationalistisch"),
]

# Modus-Tags (Checkboxen)
MODE_TAGS = [
    "Unterhaltung",
    "Bildung",
    "Interview",
    "Nachrichten",
    "Meinung",
    "Wissenschaft",
    "Musik/Art",
    "Satire/Meme",
    "Kommentar",
    "Analyse",
    "Tutorial",
]

# Z-Skala Labels für Radio-Buttons
_Z_LABELS = [
    ("-2", "sehr schlecht"),
    ("-1", "schlecht"),
    ("0", "neutral"),
    ("+1", "gut"),
    ("+2", "sehr gut"),
]

# ID-Offsets für QButtonGroup (PyQt6: -1 = "keine Auswahl")
_FACTUAL_ID_OFFSET = 10
_ARGUMENT_ID_OFFSET = 20


class ChannelRatingDialog(QDialog):
    """Dialog für detaillierte Kanal-Bewertung.

    Felder:
    - Faktenqualität: Z-Skala (-2 bis +2)
    - Argumentationsqualität: Z-Skala (-2 bis +2)
    - Bias-Richtung + Stärke
    - Modus-Tags (Mehrfachauswahl)
    - Notizen (Freitext)
    """

    def __init__(
        self,
        channel_name: str,
        rating_store: RatingStore,
        parent=None,
    ):
        super().__init__(parent)
        self._channel_name = channel_name
        self._rating_store = rating_store
        self.setWindowTitle(f"Kanal bewerten: {channel_name}")
        self.setMinimumWidth(560)
        self._setup_ui()
        self._load_existing()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # --- Faktenqualität ---
        layout.addWidget(QLabel("<b>Faktenqualität</b>"))
        self._factual_group = QButtonGroup(self)
        factual_row = QHBoxLayout()
        for i, (value, label) in enumerate(_Z_LABELS):
            rb = QRadioButton(f"{value} ({label})")
            # ID = offset + index, so checkedId() - offset = z_score_index
            self._factual_group.addButton(rb, _FACTUAL_ID_OFFSET + i)
            factual_row.addWidget(rb)
        factual_row.addStretch()
        layout.addLayout(factual_row)

        # --- Argumentationsqualität ---
        layout.addWidget(QLabel("<b>Argumentationsqualität</b>"))
        self._argument_group = QButtonGroup(self)
        argument_row = QHBoxLayout()
        for i, (value, label) in enumerate(_Z_LABELS):
            rb = QRadioButton(f"{value} ({label})")
            self._argument_group.addButton(rb, _ARGUMENT_ID_OFFSET + i)
            argument_row.addWidget(rb)
        argument_row.addStretch()
        layout.addLayout(argument_row)

        # --- Bias ---
        layout.addWidget(QLabel("<b>Bias</b>"))
        bias_grid = QGridLayout()

        bias_grid.addWidget(QLabel("Richtung:"), 0, 0)
        self._bias_combo = QComboBox()
        for value, display in BIAS_DIRECTIONS:
            self._bias_combo.addItem(display, value)
        self._bias_combo.currentIndexChanged.connect(self._on_bias_direction_changed)
        bias_grid.addWidget(self._bias_combo, 0, 1)

        bias_grid.addWidget(QLabel("Stärke (0-3):"), 1, 0)
        self._bias_strength = QSpinBox()
        self._bias_strength.setRange(0, 3)
        self._bias_strength.setEnabled(False)  # Aktiv nur wenn Richtung gewählt
        bias_grid.addWidget(self._bias_strength, 1, 1)

        layout.addLayout(bias_grid)

        # --- Modus-Tags (zwei Reihen wegen 11 Tags) ---
        layout.addWidget(QLabel("<b>Modus-Tags</b>"))
        self._tag_checkboxes: dict[str, QCheckBox] = {}
        tags_grid = QGridLayout()
        tags_grid.setSpacing(4)
        for i, tag in enumerate(MODE_TAGS):
            cb = QCheckBox(tag)
            self._tag_checkboxes[tag] = cb
            row = i // 6  # 6 pro Reihe
            col = i % 6
            tags_grid.addWidget(cb, row, col)
        layout.addLayout(tags_grid)

        # --- Notizen ---
        layout.addWidget(QLabel("<b>Notizen</b>"))
        self._notes_edit = QTextEdit()
        self._notes_edit.setMaximumHeight(80)
        self._notes_edit.setPlaceholderText("Freitext-Notizen zum Kanal (max. 500 Zeichen)")
        self._notes_edit.textChanged.connect(self._enforce_notes_limit)
        layout.addWidget(self._notes_edit)

        # --- Buttons ---
        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        btn_box.accepted.connect(self._on_save)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    def _on_bias_direction_changed(self, index: int):
        """Aktiviert Bias-Stärke nur wenn eine Richtung gewählt ist."""
        has_direction = bool(self._bias_combo.currentData())
        self._bias_strength.setEnabled(has_direction)
        if not has_direction:
            self._bias_strength.setValue(0)

    def _enforce_notes_limit(self):
        """Begrenzt Notizen auf 500 Zeichen."""
        text = self._notes_edit.toPlainText()
        if len(text) > 500:
            self._notes_edit.setPlainText(text[:500])
            cursor = self._notes_edit.textCursor()
            cursor.movePosition(cursor.MoveOperation.End)
            self._notes_edit.setTextCursor(cursor)

    def _load_existing(self):
        """Füllt den Dialog mit bestehender Kanal-Bewertung vor."""
        existing = self._rating_store.get_channel_rating(self._channel_name)
        if existing is None:
            return

        # Faktenqualität
        factual = existing.get("factual_score", 0)
        factual_idx = factual + 2  # -2→0, +2→4
        if 0 <= factual_idx <= 4:
            btn = self._factual_group.button(_FACTUAL_ID_OFFSET + factual_idx)
            if btn:
                btn.setChecked(True)

        # Argumentationsqualität
        argument = existing.get("argument_score", 0)
        argument_idx = argument + 2
        if 0 <= argument_idx <= 4:
            btn = self._argument_group.button(_ARGUMENT_ID_OFFSET + argument_idx)
            if btn:
                btn.setChecked(True)

        # Bias-Richtung
        bias_dir = existing.get("bias_direction", "")
        for i in range(self._bias_combo.count()):
            if self._bias_combo.itemData(i) == bias_dir:
                self._bias_combo.setCurrentIndex(i)
                break

        # Bias-Stärke
        self._bias_strength.setValue(existing.get("bias_strength", 0))

        # Modus-Tags
        tags_str = existing.get("mode_tags", "")
        if tags_str:
            tags = [t.strip() for t in tags_str.split(",")]
            for tag, cb in self._tag_checkboxes.items():
                cb.setChecked(tag in tags)

        # Notizen
        notes = existing.get("notes", "")
        if notes:
            self._notes_edit.setPlainText(notes)

    def _on_save(self):
        """Speichert die Kanal-Bewertung."""
        # Faktenqualität aus ButtonGroup
        factual_id = self._factual_group.checkedId()
        factual_score = (factual_id - _FACTUAL_ID_OFFSET) - 2 if factual_id >= 0 else 0

        # Argumentationsqualität
        argument_id = self._argument_group.checkedId()
        argument_score = (argument_id - _ARGUMENT_ID_OFFSET) - 2 if argument_id >= 0 else 0

        # Bias
        bias_direction = self._bias_combo.currentData() or ""
        bias_strength = self._bias_strength.value() if bias_direction else 0

        # Tags
        selected_tags = [
            tag for tag, cb in self._tag_checkboxes.items() if cb.isChecked()
        ]
        mode_tags = ",".join(selected_tags)

        # Notizen
        notes = self._notes_edit.toPlainText().strip()[:500]

        try:
            self._rating_store.save_channel_rating(
                channel_name=self._channel_name,
                factual_score=factual_score,
                argument_score=argument_score,
                bias_direction=bias_direction,
                bias_strength=bias_strength,
                mode_tags=mode_tags,
                notes=notes,
            )
            logger.info(
                f"Kanal '{self._channel_name}' bewertet: "
                f"Fakten={factual_score}, Argument={argument_score}, "
                f"Bias={bias_direction}({bias_strength}), Tags={mode_tags}"
            )
            self.accept()
        except Exception as e:
            logger.exception(f"Kanal-Bewertung fehlgeschlagen: {e}")
