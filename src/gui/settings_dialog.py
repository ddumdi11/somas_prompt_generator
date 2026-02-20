"""Settings-Dialog für API-Key-Verwaltung und Debug-Einstellungen."""

import logging
import os
import subprocess
import sys

from typing import Optional

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QGroupBox, QFormLayout, QMessageBox, QComboBox, QWidget,
    QCheckBox, QFileDialog,
)
from PyQt6.QtCore import pyqtSlot
from PyQt6.QtGui import QFont

from src.config.api_config import (
    load_providers, get_api_key, save_api_key, delete_api_key, has_api_key,
    get_default_provider_id, get_last_provider, get_last_model,
    save_last_selection, save_preferences, load_preferences,
)
from src.core.perplexity_client import PerplexityClient
from src.core.openrouter_client import OpenRouterClient
from src.core.debug_logger import DebugLogger
from src.core.rating_store import RatingStore

logger = logging.getLogger(__name__)


class SettingsDialog(QDialog):
    """Dialog für API-Einstellungen und Key-Verwaltung."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Initialisiert den Settings-Dialog.

        Args:
            parent: Optionales Parent-Widget.
        """
        super().__init__(parent)
        self.setWindowTitle("API-Einstellungen")
        self.setMinimumWidth(550)
        self._providers = load_providers()
        self._key_inputs: dict[str, QLineEdit] = {}
        self._visibility_buttons: dict[str, QPushButton] = {}
        self._status_labels: dict[str, QLabel] = {}
        self._debug_logger = DebugLogger()
        self._rating_store = RatingStore()

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

        # Debug-Einstellungen
        layout.addWidget(self._create_debug_group())

        # Bewertungsdaten
        layout.addWidget(self._create_ratings_group())

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

        # Kanal-Meta-Anzeige
        self.channel_meta_checkbox = QCheckBox(
            "Kanal-Bewertung bei bekannten Kanälen anzeigen"
        )
        prefs = load_preferences()
        self.channel_meta_checkbox.setChecked(
            prefs.get("show_channel_meta", False)
        )
        group_layout.addRow(self.channel_meta_checkbox)

        return group

    def _create_debug_group(self) -> QGroupBox:
        """Erstellt die Debug-Logging-Gruppe."""
        group = QGroupBox("Debug-Logging")
        group_layout = QFormLayout(group)

        # Checkbox
        self.debug_checkbox = QCheckBox("Debug-Logging aktivieren")
        prefs = load_preferences()
        self.debug_checkbox.setChecked(prefs.get("debug_logging", False))
        group_layout.addRow(self.debug_checkbox)

        # Pfadanzeige
        debug_dir = self._debug_logger.base_dir
        path_label = QLabel(str(debug_dir))
        path_label.setStyleSheet("color: gray; font-size: 11px;")
        path_label.setWordWrap(True)
        group_layout.addRow("Speicherort:", path_label)

        # Log-Count + Buttons
        btn_layout = QHBoxLayout()

        self.debug_log_count_label = QLabel("")
        self._update_debug_log_count()
        btn_layout.addWidget(self.debug_log_count_label)

        btn_layout.addStretch()

        btn_open = QPushButton("Ordner öffnen")
        btn_open.setMaximumWidth(120)
        btn_open.clicked.connect(self._on_open_debug_folder)
        btn_layout.addWidget(btn_open)

        btn_clear = QPushButton("Logs löschen")
        btn_clear.setMaximumWidth(120)
        btn_clear.clicked.connect(self._on_clear_debug_logs)
        btn_layout.addWidget(btn_clear)

        group_layout.addRow(btn_layout)

        return group

    def _create_ratings_group(self) -> QGroupBox:
        """Erstellt die Bewertungsdaten-Gruppe mit CSV Export/Import."""
        group = QGroupBox("Bewertungsdaten")
        group_layout = QFormLayout(group)

        # Info
        channel_count = len(self._rating_store.get_all_channels())
        self._channel_count_label = QLabel(
            f"{channel_count} Kanal-Bewertungen"
            if channel_count > 0 else "Keine Kanal-Bewertungen vorhanden"
        )
        self._channel_count_label.setStyleSheet("color: gray; font-style: italic;")
        group_layout.addRow(self._channel_count_label)

        # Export/Import Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        btn_export = QPushButton("Kanal-Bewertungen exportieren (CSV)")
        btn_export.setMaximumWidth(280)
        btn_export.clicked.connect(self._on_export_channels)
        btn_layout.addWidget(btn_export)

        btn_import = QPushButton("Kanal-Bewertungen importieren (CSV)")
        btn_import.setMaximumWidth(280)
        btn_import.clicked.connect(self._on_import_channels)
        btn_layout.addWidget(btn_import)

        group_layout.addRow(btn_layout)

        return group

    @pyqtSlot()
    def _on_export_channels(self) -> None:
        """Exportiert Kanal-Bewertungen als CSV."""
        from pathlib import Path

        channels = self._rating_store.get_all_channels()
        if not channels:
            QMessageBox.information(
                self, "Export",
                "Keine Kanal-Bewertungen zum Exportieren vorhanden."
            )
            return

        path, _ = QFileDialog.getSaveFileName(
            self, "Kanal-Bewertungen exportieren",
            "somas_channels.csv",
            "CSV-Dateien (*.csv)"
        )
        if not path:
            return

        try:
            count = self._rating_store.export_channels_csv(Path(path))
            QMessageBox.information(
                self, "Export erfolgreich",
                f"{count} Kanal-Bewertungen exportiert nach:\n{path}"
            )
            logger.info(f"{count} Kanal-Bewertungen nach {path} exportiert")
        except Exception as e:
            logger.exception(f"Export fehlgeschlagen: {e}")
            QMessageBox.critical(
                self, "Export fehlgeschlagen",
                f"Fehler beim Export:\n{e}"
            )

    @pyqtSlot()
    def _on_import_channels(self) -> None:
        """Importiert Kanal-Bewertungen aus CSV."""
        from pathlib import Path

        path, _ = QFileDialog.getOpenFileName(
            self, "Kanal-Bewertungen importieren",
            "",
            "CSV-Dateien (*.csv)"
        )
        if not path:
            return

        try:
            imported, skipped = self._rating_store.import_channels_csv(Path(path))
            msg = f"{imported} Kanal-Bewertungen importiert."
            if skipped > 0:
                msg += f"\n{skipped} Einträge übersprungen (ungültige Daten)."
            QMessageBox.information(self, "Import erfolgreich", msg)
            logger.info(f"Import: {imported} importiert, {skipped} übersprungen")
            # Count aktualisieren
            channel_count = len(self._rating_store.get_all_channels())
            self._channel_count_label.setText(f"{channel_count} Kanal-Bewertungen")
        except Exception as e:
            logger.exception(f"Import fehlgeschlagen: {e}")
            QMessageBox.critical(
                self, "Import fehlgeschlagen",
                f"Fehler beim Import:\n{e}"
            )

    def _update_debug_log_count(self) -> None:
        """Aktualisiert die Anzeige der Debug-Log-Anzahl."""
        count = self._debug_logger.get_log_count()
        self.debug_log_count_label.setText(
            f"{count} Log-Einträge" if count > 0 else "Keine Logs vorhanden"
        )
        self.debug_log_count_label.setStyleSheet(
            "color: gray; font-style: italic;"
        )

    @pyqtSlot()
    def _on_open_debug_folder(self) -> None:
        """Öffnet den Debug-Log-Ordner im Dateimanager."""
        debug_dir = self._debug_logger.base_dir
        debug_dir.mkdir(parents=True, exist_ok=True)
        normalized_path = os.path.normpath(str(debug_dir))
        try:
            if sys.platform in ("win32", "cygwin"):
                subprocess.Popen(["explorer", normalized_path])
            elif sys.platform == "darwin":
                subprocess.run(["open", normalized_path], check=True)
            else:
                subprocess.run(["xdg-open", normalized_path], check=True)
        except Exception as e:
            logger.warning(f"Ordner konnte nicht geöffnet werden: {e}")
            QMessageBox.warning(
                self, "Fehler",
                f"Ordner konnte nicht geöffnet werden:\n{normalized_path}"
            )

    @pyqtSlot()
    def _on_clear_debug_logs(self) -> None:
        """Löscht alle Debug-Logs nach Bestätigung."""
        count = self._debug_logger.get_log_count()
        if count == 0:
            QMessageBox.information(self, "Debug-Logs", "Keine Logs vorhanden.")
            return

        reply = QMessageBox.question(
            self,
            "Logs löschen",
            f"{count} Debug-Log-Einträge wirklich löschen?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            deleted = self._debug_logger.clear_logs()
            self._update_debug_log_count()
            QMessageBox.information(
                self, "Debug-Logs", f"{deleted} Log-Einträge gelöscht."
            )

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
        elif provider_id == "openrouter":
            client = OpenRouterClient(api_key=key)
            success = client.validate_key()
        else:
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

        # Default-Provider und Debug-Setting speichern
        prefs = load_preferences()
        default_provider = self.default_provider_combo.currentData()
        if default_provider:
            prefs["last_provider"] = default_provider
        prefs["debug_logging"] = self.debug_checkbox.isChecked()
        prefs["show_channel_meta"] = self.channel_meta_checkbox.isChecked()
        save_preferences(prefs)

        logger.info(f"{saved_count} API-Key(s) gespeichert")
        self.accept()
