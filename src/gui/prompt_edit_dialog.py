"""Dialog für strukturiertes Editieren eines SOMAS-Prompts vor der Generierung.

Zeigt den System-Prompt des gewählten Presets und eine Modul-Vorgabe.
Der User kann beides anpassen. Bei "Übernehmen & Generieren" werden
die Werte per Signal zurückgegeben.
"""

import logging

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)

from src.core.user_preset_store import VALID_MODULES

logger = logging.getLogger(__name__)


class PromptEditDialog(QDialog):
    """Dialog zum Editieren der Prompt-Bestandteile vor der Generierung.

    Signals:
        apply_clicked: Emittiert (system_prompt, fixed_module) wenn
                       "Übernehmen & Generieren" geklickt wird.
                       fixed_module ist None wenn "Automatisch" gewählt.
    """

    apply_clicked = pyqtSignal(str, object)  # system_prompt, module|None

    def __init__(
        self,
        parent,
        preset_name: str,
        system_prompt: str,
        fixed_module: str | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Prompt anpassen")
        self.setMinimumWidth(600)
        self.setMinimumHeight(450)

        self._original_system_prompt = system_prompt
        self._original_module = fixed_module

        self._setup_ui(preset_name, system_prompt, fixed_module)

    def _setup_ui(
        self,
        preset_name: str,
        system_prompt: str,
        module: str | None,
    ) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # Header
        header = QLabel(f"Basiert auf Preset: <b>{preset_name}</b>")
        layout.addWidget(header)

        # System-Prompt
        label = QLabel("System-Prompt (Rollenanweisung + Analyseanweisung)")
        label.setFont(QFont("", -1, QFont.Weight.Bold))
        layout.addWidget(label)

        self.system_prompt_edit = QTextEdit()
        # Formatiere einzeilige Preset-Strings für bessere Lesbarkeit
        display_prompt = system_prompt.replace(". ", ".\n")
        self.system_prompt_edit.setPlainText(display_prompt)
        self.system_prompt_edit.setMinimumHeight(180)
        layout.addWidget(self.system_prompt_edit)

        # Modul-Vorgabe
        module_label = QLabel("Modul-Vorgabe")
        module_label.setFont(QFont("", -1, QFont.Weight.Bold))
        layout.addWidget(module_label)

        self.module_combo = QComboBox()
        self.module_combo.addItem("Automatisch (Modell wählt)", None)
        for m in sorted(VALID_MODULES):
            self.module_combo.addItem(m, m)
        if module and module in VALID_MODULES:
            idx = self.module_combo.findData(module)
            if idx >= 0:
                self.module_combo.setCurrentIndex(idx)
        layout.addWidget(self.module_combo)

        # Info-Box
        info = QLabel(
            "\u2139\uFE0F  Video-Metadaten und Transkript werden automatisch "
            "angehängt und sind hier nicht editierbar."
        )
        info.setStyleSheet("color: #888; font-size: 11px;")
        info.setWordWrap(True)
        layout.addWidget(info)

        layout.addStretch()

        # Button-Zeile
        btn_layout = QHBoxLayout()

        btn_reset = QPushButton("Zurücksetzen")
        btn_reset.clicked.connect(self._on_reset)
        btn_layout.addWidget(btn_reset)

        btn_layout.addStretch()

        btn_cancel = QPushButton("Abbrechen")
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)

        btn_apply = QPushButton("Übernehmen && Generieren")
        btn_apply.setDefault(True)
        btn_apply.clicked.connect(self._on_apply)
        btn_layout.addWidget(btn_apply)

        layout.addLayout(btn_layout)

    def _on_reset(self) -> None:
        """Setzt alle Felder auf die ursprünglichen Preset-Werte zurück."""
        display_prompt = self._original_system_prompt.replace(". ", ".\n")
        self.system_prompt_edit.setPlainText(display_prompt)
        idx = self.module_combo.findData(self._original_module)
        self.module_combo.setCurrentIndex(max(0, idx))

    def _on_apply(self) -> None:
        """Emittiert die Werte und schließt den Dialog."""
        system_prompt = self.system_prompt_edit.toPlainText().strip()
        module = self.module_combo.currentData()  # None oder Modulname
        self.apply_clicked.emit(system_prompt, module)
        self.accept()
