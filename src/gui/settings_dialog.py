"""Settings-Dialog für API-Key-Verwaltung."""

import logging

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QGroupBox, QFormLayout, QMessageBox, QComboBox,
)
from PyQt6.QtCore import pyqtSlot
from PyQt6.QtGui import QFont

from src.config.api_config import (
    load_providers, get_api_key, save_api_key, delete_api_key, has_api_key,
    get_default_provider_id, get_last_provider, get_last_model,
    save_last_selection, save_preferences, load_preferences,
)
from src.core.perplexity_client import PerplexityClient

logger = logging.getLogger(__name__)


class SettingsDialog(QDialog):
    """Dialog für API-Einstellungen und Key-Verwaltung."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("API-Einstellungen")
        self.setMinimumWidth(550)
        self._providers = load_providers()
        self._key_inputs: dict[str, QLineEdit] = {}
        self._visibility_buttons: dict[str, QPushButton] = {}
        self._status_labels: dict[str, QLabel] = {}

        self._setup_ui()
        self._load_current_keys()

    def _setup_ui(self) -> None:
        """Erstellt das Dialog-Layout."""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)

        # Provider-Gruppen
        for provider_id, provider in self._providers.items():
            group = self._create_provider_group(provider_id, provider.name)
            layout.addWidget(group)

        # Default-Einstellungen
        layout.addWidget(self._create_defaults_group())

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.btn_save = QPushButton("Speichern")
        self.btn_save.setMinimumWidth(100)
        self.btn_save.clicked.connect(self._on_save)
        btn_layout.addWidget(self.btn_save)

        self.btn_cancel = QPushButton("Abbrechen")
        self.btn_cancel.setMinimumWidth(100)
        self.btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(self.btn_cancel)

        layout.addLayout(btn_layout)

    def _create_provider_group(self, provider_id: str, provider_name: str) -> QGroupBox:
        """Erstellt eine Provider-Gruppe mit Key-Eingabe und Test-Button."""
        group = QGroupBox(provider_name)
        group_layout = QFormLayout(group)

        # API-Key Zeile
        key_layout = QHBoxLayout()

        key_input = QLineEdit()
        key_input.setEchoMode(QLineEdit.EchoMode.Password)
        key_input.setPlaceholderText("API-Key eingeben...")
        key_input.setMinimumWidth(300)
        self._key_inputs[provider_id] = key_input
        key_layout.addWidget(key_input)

        # Sichtbarkeit-Toggle
        btn_visibility = QPushButton("Zeigen")
        btn_visibility.setMaximumWidth(70)
        btn_visibility.setCheckable(True)
        btn_visibility.toggled.connect(
            lambda checked, pid=provider_id: self._toggle_visibility(pid, checked)
        )
        self._visibility_buttons[provider_id] = btn_visibility
        key_layout.addWidget(btn_visibility)

        # Test-Button
        btn_test = QPushButton("Test")
        btn_test.setMaximumWidth(60)
        btn_test.clicked.connect(lambda: self._on_test_key(provider_id))
        key_layout.addWidget(btn_test)

        # Löschen-Button
        btn_delete = QPushButton("X")
        btn_delete.setMaximumWidth(30)
        btn_delete.setToolTip("API-Key löschen")
        btn_delete.clicked.connect(lambda: self._on_delete_key(provider_id))
        key_layout.addWidget(btn_delete)

        group_layout.addRow("API-Key:", key_layout)

        # Status-Label
        status_label = QLabel("")
        status_label.setStyleSheet("color: gray; font-style: italic;")
        self._status_labels[provider_id] = status_label
        group_layout.addRow("Status:", status_label)

        return group

    def _create_defaults_group(self) -> QGroupBox:
        """Erstellt die Default-Einstellungen-Gruppe."""
        group = QGroupBox("Default-Einstellungen")
        group_layout = QFormLayout(group)

        # Default-Provider
        self.default_provider_combo = QComboBox()
        for provider in self._providers.values():
            self.default_provider_combo.addItem(provider.name, provider.id)

        # Aktuellen Default setzen
        current_default = get_last_provider()
        for i in range(self.default_provider_combo.count()):
            if self.default_provider_combo.itemData(i) == current_default:
                self.default_provider_combo.setCurrentIndex(i)
                break

        group_layout.addRow("Default-Provider:", self.default_provider_combo)

        return group

    def _load_current_keys(self) -> None:
        """Lädt vorhandene API-Keys und zeigt Status an."""
        for provider_id in self._providers:
            key = get_api_key(provider_id)
            if key:
                self._key_inputs[provider_id].setText(key)
                self._status_labels[provider_id].setText("Key vorhanden")
                self._status_labels[provider_id].setStyleSheet(
                    "color: #4CAF50; font-style: italic;"
                )
            else:
                self._status_labels[provider_id].setText("Kein API-Key konfiguriert")
                self._status_labels[provider_id].setStyleSheet(
                    "color: #808080; font-style: italic;"
                )

    def _toggle_visibility(self, provider_id: str, visible: bool) -> None:
        """Zeigt/versteckt den API-Key."""
        key_input = self._key_inputs[provider_id]
        btn = self._visibility_buttons[provider_id]
        if visible:
            key_input.setEchoMode(QLineEdit.EchoMode.Normal)
            btn.setText("Verbergen")
        else:
            key_input.setEchoMode(QLineEdit.EchoMode.Password)
            btn.setText("Zeigen")

    @pyqtSlot()
    def _on_test_key(self, provider_id: str) -> None:
        """Testet den eingegebenen API-Key."""
        key = self._key_inputs[provider_id].text().strip()
        if not key:
            QMessageBox.warning(self, "Test", "Bitte zuerst einen API-Key eingeben.")
            return

        status_label = self._status_labels[provider_id]
        status_label.setText("Teste...")
        status_label.setStyleSheet("color: #2196F3; font-style: italic;")
        # Force UI update
        status_label.repaint()

        if provider_id == "perplexity":
            client = PerplexityClient(api_key=key)
            success = client.validate_key()
        else:
            # Andere Provider: Einfacher HTTP-Test
            status_label.setText("Test nicht verfügbar für diesen Provider")
            status_label.setStyleSheet("color: #FFC107; font-style: italic;")
            return

        if success:
            status_label.setText("Verbindung erfolgreich!")
            status_label.setStyleSheet("color: #4CAF50; font-weight: bold;")
        else:
            status_label.setText("Verbindung fehlgeschlagen - Key ungültig?")
            status_label.setStyleSheet("color: #F44336; font-weight: bold;")

    @pyqtSlot()
    def _on_delete_key(self, provider_id: str) -> None:
        """Löscht den API-Key für einen Provider."""
        provider_name = self._providers[provider_id].name
        reply = QMessageBox.question(
            self,
            "Key löschen",
            f"API-Key für {provider_name} wirklich löschen?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            delete_api_key(provider_id)
            self._key_inputs[provider_id].clear()
            self._status_labels[provider_id].setText("Key gelöscht")
            self._status_labels[provider_id].setStyleSheet(
                "color: #808080; font-style: italic;"
            )

    @pyqtSlot()
    def _on_save(self) -> None:
        """Speichert alle eingegebenen API-Keys."""
        saved_count = 0
        for provider_id, key_input in self._key_inputs.items():
            key = key_input.text().strip()
            if key:
                save_api_key(provider_id, key)
                saved_count += 1
                logger.info(f"API-Key für '{provider_id}' gespeichert")

        # Default-Provider speichern
        default_provider = self.default_provider_combo.currentData()
        if default_provider:
            prefs = load_preferences()
            prefs["last_provider"] = default_provider
            save_preferences(prefs)

        logger.info(f"{saved_count} API-Key(s) gespeichert")
        self.accept()
