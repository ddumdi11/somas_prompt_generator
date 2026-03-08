"""Non-modaler Dialog für die Batch-Verarbeitung von YouTube-URLs."""

import logging

from PyQt6.QtCore import Qt, pyqtSignal, pyqtSlot
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from src.core.batch_item import BatchConfig, BatchItem
from src.gui.rating_widget import RatingWidget

logger = logging.getLogger(__name__)

# Maximale Anzahl URLs im Batch
MAX_BATCH_URLS = 5
MIN_BATCH_URLS = 2

# Status-Icons
STATUS_ICONS = {
    "pending": "\u23F3",   # ⏳
    "loading": "\U0001F4E5",  # 📥
    "prompting": "\U0001F4DD",  # 📝
    "calling": "\u2699\uFE0F",  # ⚙️
    "done": "\u2705",      # ✅
    "error": "\u274C",     # ❌
}


class BatchDialog(QDialog):
    """Batch-Verarbeitungsdialog für 2-5 YouTube-URLs.

    Non-modal: Hauptfenster bleibt zugänglich.
    Erhält eine BatchConfig mit den gemeinsamen Einstellungen
    und orchestriert die sequenzielle Verarbeitung.

    Signals:
        batch_completed: Alle Items verarbeitet.
        batch_dismissed: Alle Items als erledigt markiert, Dialog schließt.
    """

    batch_completed = pyqtSignal()
    batch_dismissed = pyqtSignal()

    def __init__(
        self,
        parent,
        config: BatchConfig,
        rating_store,
        debug_logger=None,
    ):
        super().__init__(parent)
        self._config = config
        self._rating_store = rating_store
        self._debug_logger = debug_logger

        # Zustand
        self._items: list[BatchItem] = []
        self._batch_worker = None
        self._is_running = False
        self._session_dir = None  # Wird bei Start gesetzt

        # Erledigt-Checkboxen pro Tab
        self._done_checks: list[QCheckBox] = []
        # Rating-Widgets pro Tab
        self._rating_widgets: list[RatingWidget] = []
        # Result-TextEdits pro Tab
        self._result_edits: list[QTextEdit] = []
        # Char-Counter-Labels pro Tab
        self._char_labels: list[QLabel] = []

        self._setup_ui()
        self.setWindowTitle("SOMAS Batch-Verarbeitung")
        self.setMinimumSize(800, 650)
        self.resize(900, 750)

    # --- UI Setup ---

    def _setup_ui(self):
        """Baut das Dialog-Layout auf."""
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # 1. Settings-Summary
        layout.addWidget(self._create_settings_summary())

        # 2. URL-Eingabe
        layout.addWidget(self._create_url_section())

        # 3. Progress
        self._create_progress_section(layout)

        # 4. Ergebnis-Tabs
        self.result_tabs = QTabWidget()
        self.result_tabs.setVisible(False)
        layout.addWidget(self.result_tabs, stretch=1)

        # 5. Buttons unten
        layout.addWidget(self._create_bottom_buttons())

    def _create_settings_summary(self) -> QFrame:
        """Erstellt die Settings-Zusammenfassung (read-only)."""
        frame = QFrame()
        frame.setFrameStyle(QFrame.Shape.StyledPanel)
        frame.setStyleSheet(
            "QFrame { background: #F5F5F5; border: 1px solid #DDD; "
            "border-radius: 6px; padding: 8px; }"
        )
        hlayout = QHBoxLayout(frame)
        hlayout.setContentsMargins(12, 8, 12, 8)

        info_parts = [
            f"Preset: {self._config.preset_name}",
            f"Perspektive: {self._config.perspective}",
            f"Provider: {self._config.provider_id}",
            f"Modell: {self._config.model_name or self._config.model_id}",
            f"Tiefe: {self._config.depth}",
        ]
        label = QLabel(" \u00B7 ".join(info_parts))
        label.setStyleSheet("font-size: 11px; color: #555;")
        label.setWordWrap(True)
        hlayout.addWidget(label)

        return frame

    def _create_url_section(self) -> QWidget:
        """Erstellt den URL-Eingabebereich mit +/- Buttons."""
        widget = QWidget()
        vlayout = QVBoxLayout(widget)
        vlayout.setContentsMargins(0, 0, 0, 0)
        vlayout.setSpacing(6)

        # Header mit +/- Buttons
        header = QHBoxLayout()
        header.addWidget(QLabel("YouTube-URLs (2\u20135):"))
        header.addStretch()

        self.btn_add_url = QPushButton("+ URL")
        self.btn_add_url.setFixedWidth(70)
        self.btn_add_url.clicked.connect(self._add_url_field)
        header.addWidget(self.btn_add_url)

        self.btn_remove_url = QPushButton("\u2212 URL")
        self.btn_remove_url.setFixedWidth(70)
        self.btn_remove_url.clicked.connect(self._remove_url_field)
        header.addWidget(self.btn_remove_url)

        vlayout.addLayout(header)

        # URL-Felder Container
        self._url_fields: list[QLineEdit] = []
        self._url_container = QVBoxLayout()
        self._url_container.setSpacing(4)
        vlayout.addLayout(self._url_container)

        # Starte mit 2 Feldern
        for _ in range(MIN_BATCH_URLS):
            self._add_url_field()

        return widget

    def _add_url_field(self):
        """Fügt ein neues URL-Eingabefeld hinzu."""
        if len(self._url_fields) >= MAX_BATCH_URLS:
            return

        idx = len(self._url_fields) + 1
        field = QLineEdit()
        field.setPlaceholderText(f"URL {idx}: https://www.youtube.com/watch?v=...")
        self._url_fields.append(field)
        self._url_container.addWidget(field)
        self._update_url_buttons()

    def _remove_url_field(self):
        """Entfernt das letzte URL-Eingabefeld."""
        if len(self._url_fields) <= MIN_BATCH_URLS:
            return

        field = self._url_fields.pop()
        self._url_container.removeWidget(field)
        field.deleteLater()
        self._update_url_buttons()

    def _update_url_buttons(self):
        """Aktualisiert den Enable-Status der +/- Buttons."""
        self.btn_add_url.setEnabled(len(self._url_fields) < MAX_BATCH_URLS)
        self.btn_remove_url.setEnabled(len(self._url_fields) > MIN_BATCH_URLS)

    def _create_progress_section(self, parent_layout):
        """Erstellt Progress-Bar und Status-Zeile."""
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setTextVisible(True)
        parent_layout.addWidget(self.progress_bar)

        self.status_label = QLabel("")
        self.status_label.setStyleSheet("font-size: 11px; color: #666;")
        self.status_label.setVisible(False)
        parent_layout.addWidget(self.status_label)

    def _create_bottom_buttons(self) -> QWidget:
        """Erstellt die Buttons am unteren Rand."""
        widget = QWidget()
        hlayout = QHBoxLayout(widget)
        hlayout.setContentsMargins(0, 0, 0, 0)

        self.btn_start = QPushButton("\u25B6 Batch starten")
        self.btn_start.setMinimumHeight(36)
        self.btn_start.setStyleSheet(
            "QPushButton { background: #2E7D32; color: white; "
            "font-weight: bold; border-radius: 4px; padding: 4px 16px; }"
            "QPushButton:hover { background: #1B5E20; }"
            "QPushButton:disabled { background: #CCC; color: #888; }"
        )
        self.btn_start.clicked.connect(self._on_start_batch)
        hlayout.addWidget(self.btn_start)

        self.btn_cancel = QPushButton("\u23F9 Abbrechen")
        self.btn_cancel.setMinimumHeight(36)
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.clicked.connect(self._on_cancel_batch)
        hlayout.addWidget(self.btn_cancel)

        hlayout.addStretch()

        self.btn_all_done = QPushButton("Alle erledigt")
        self.btn_all_done.setMinimumHeight(36)
        self.btn_all_done.setVisible(False)
        self.btn_all_done.clicked.connect(self._on_all_done)
        hlayout.addWidget(self.btn_all_done)

        return widget

    # --- Ergebnis-Tabs ---

    def _create_result_tabs(self, items: list[BatchItem]):
        """Erstellt Ergebnis-Tabs für alle Batch-Items."""
        self.result_tabs.clear()
        self._done_checks.clear()
        self._rating_widgets.clear()
        self._result_edits.clear()
        self._char_labels.clear()

        for item in items:
            tab = self._create_single_result_tab(item)
            label = f"{item.position}. {STATUS_ICONS.get(item.status, '')}"
            if item.video_info:
                title = item.video_info.title
                if len(title) > 25:
                    title = title[:22] + "..."
                label = f"{item.position}. {title}"
            self.result_tabs.addTab(tab, label)

        self.result_tabs.setVisible(True)

    def _create_single_result_tab(self, item: BatchItem) -> QWidget:
        """Erstellt den Inhalt eines einzelnen Ergebnis-Tabs."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(8)

        # Ergebnis-Text
        result_edit = QTextEdit()
        result_edit.setReadOnly(True)
        if item.result_text:
            result_edit.setText(item.result_text)
        elif item.error_message:
            result_edit.setText(f"\u274C Fehler: {item.error_message}")
            result_edit.setStyleSheet("color: #C62828;")
        else:
            result_edit.setPlaceholderText("Ergebnis wird hier angezeigt...")
        self._result_edits.append(result_edit)
        layout.addWidget(result_edit, stretch=1)

        # Zeichenzähler
        char_label = QLabel("")
        char_label.setStyleSheet("font-size: 11px; color: #888;")
        self._char_labels.append(char_label)
        if item.result_text:
            self._update_char_counter(len(self._char_labels) - 1)
        layout.addWidget(char_label)

        # Untere Zeile: Rating + Erledigt
        bottom = QHBoxLayout()

        rating = RatingWidget()
        rating.setVisible(item.status == "done")
        # Rating-Signal verbinden
        idx = len(self._rating_widgets)
        rating.rating_submitted.connect(
            lambda z, i=idx: self._on_item_rating(i, z)
        )
        self._rating_widgets.append(rating)
        bottom.addWidget(rating)

        bottom.addStretch()

        done_check = QCheckBox("Erledigt")
        done_check.setVisible(item.status == "done")
        self._done_checks.append(done_check)
        bottom.addWidget(done_check)

        layout.addLayout(bottom)

        return tab

    # --- Batch-Steuerung ---

    def _on_start_batch(self):
        """Startet die Batch-Verarbeitung."""
        urls = self._collect_urls()
        if not urls:
            return

        # Items erstellen
        self._items = [
            BatchItem(url=url, position=i + 1)
            for i, url in enumerate(urls)
        ]

        # UI umschalten
        self._set_running_state(True)
        self._create_result_tabs(self._items)
        self.progress_bar.setMaximum(len(self._items))
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(True)
        self.status_label.setVisible(True)
        self.status_label.setText(
            f"Verarbeitung gestartet: {len(self._items)} URLs"
        )

        # Session erstellen (Crash-Resistenz)
        from src.core.batch_persistence import create_batch_session
        self._session_dir = create_batch_session(self._config, urls)

        # Worker starten (wird in PR 3 implementiert)
        self._start_worker()

    def _start_worker(self):
        """Erstellt und startet den BatchWorker."""
        from src.core.batch_worker import BatchWorker

        self._batch_worker = BatchWorker(
            config=self._config,
            items=self._items,
            rating_store=self._rating_store,
            session_dir=self._session_dir,
            debug_logger=self._debug_logger,
        )

        # Signals verdrahten
        self._batch_worker.item_status_changed.connect(
            self.on_item_status_changed
        )
        self._batch_worker.item_metadata_loaded.connect(
            self.on_item_metadata_loaded
        )
        self._batch_worker.item_completed.connect(self.on_item_completed)
        self._batch_worker.item_error.connect(self.on_item_error)
        self._batch_worker.batch_finished.connect(self.on_batch_finished)

        self._batch_worker.start()
        logger.info(
            f"BatchWorker gestartet: {len(self._items)} URLs, "
            f"Modell: {self._config.model_name}"
        )

    def _collect_urls(self) -> list[str]:
        """Sammelt und validiert die eingegebenen URLs."""
        urls = []
        for field in self._url_fields:
            url = field.text().strip()
            if url:
                urls.append(url)

        if len(urls) < MIN_BATCH_URLS:
            QMessageBox.warning(
                self,
                "Zu wenige URLs",
                f"Bitte mindestens {MIN_BATCH_URLS} YouTube-URLs eingeben.",
            )
            return []

        return urls

    def _set_running_state(self, running: bool):
        """Setzt den UI-Zustand je nach Verarbeitungsstatus."""
        self._is_running = running
        self.btn_start.setEnabled(not running)
        self.btn_cancel.setEnabled(running)
        self.btn_all_done.setVisible(not running and bool(self._items))

        # URL-Felder sperren während der Verarbeitung
        for field in self._url_fields:
            field.setEnabled(not running)
        self.btn_add_url.setEnabled(not running)
        self.btn_remove_url.setEnabled(not running)

    def _on_cancel_batch(self):
        """Bricht die laufende Batch-Verarbeitung ab."""
        if self._batch_worker:
            self._batch_worker.cancel()
        self._set_running_state(False)
        self.status_label.setText("Batch abgebrochen.")

    def _on_all_done(self):
        """Markiert alle Items als erledigt und schließt den Dialog."""
        from src.core.batch_persistence import delete_batch_session

        if self._session_dir:
            delete_batch_session(self._session_dir)

        self.batch_dismissed.emit()
        self.close()

    # --- Worker-Callbacks (Slots für PR 3) ---

    @pyqtSlot(int, str)
    def on_item_status_changed(self, index: int, status: str):
        """Aktualisiert den Status-Icon im Tab-Header."""
        if 0 <= index < len(self._items):
            self._items[index].status = status
            icon = STATUS_ICONS.get(status, "")
            title = f"{index + 1}. {icon}"
            if self._items[index].video_info:
                name = self._items[index].video_info.title
                if len(name) > 25:
                    name = name[:22] + "..."
                title = f"{index + 1}. {name} {icon}"
            self.result_tabs.setTabText(index, title)

    @pyqtSlot(int, object)
    def on_item_metadata_loaded(self, index: int, video_info):
        """Aktualisiert Tab-Label mit Video-Titel."""
        if 0 <= index < len(self._items):
            self._items[index].video_info = video_info
            title = video_info.title
            if len(title) > 25:
                title = title[:22] + "..."
            icon = STATUS_ICONS.get(self._items[index].status, "")
            self.result_tabs.setTabText(index, f"{index + 1}. {title} {icon}")

    @pyqtSlot(int, str, object)
    def on_item_completed(self, index: int, result_text: str, _response):
        """Zeigt das Ergebnis im Tab und aktiviert Rating/Erledigt.

        _response is reserved for future use (e.g. token stats display).
        """
        if 0 <= index < len(self._items):
            self._items[index].result_text = result_text
            self._items[index].status = "done"

            # Ergebnis anzeigen
            if index < len(self._result_edits):
                self._result_edits[index].setText(result_text)
                self._result_edits[index].setStyleSheet("")

            # Zeichenzähler aktualisieren
            self._update_char_counter(index)

            # Rating + Erledigt sichtbar machen
            if index < len(self._rating_widgets):
                self._rating_widgets[index].setVisible(True)
                self._rating_widgets[index].reset()
            if index < len(self._done_checks):
                self._done_checks[index].setVisible(True)

            # Tab-Header aktualisieren
            self.on_item_status_changed(index, "done")

            # Progress-Bar aktualisieren
            done_count = sum(
                1 for item in self._items if item.status == "done"
            )
            self.progress_bar.setValue(done_count)

    @pyqtSlot(int, str)
    def on_item_error(self, index: int, error_message: str):
        """Zeigt den Fehler im Tab."""
        if 0 <= index < len(self._items):
            self._items[index].error_message = error_message
            self._items[index].status = "error"

            if index < len(self._result_edits):
                self._result_edits[index].setText(
                    f"\u274C Fehler: {error_message}"
                )
                self._result_edits[index].setStyleSheet("color: #C62828;")

            self.on_item_status_changed(index, "error")

            # Progress trotzdem weiter zählen
            processed = sum(
                1 for item in self._items
                if item.status in ("done", "error")
            )
            self.progress_bar.setValue(processed)

    @pyqtSlot()
    def on_batch_finished(self):
        """Wird aufgerufen wenn alle Items verarbeitet sind."""
        self._set_running_state(False)

        done = sum(1 for item in self._items if item.status == "done")
        errors = sum(1 for item in self._items if item.status == "error")
        total = len(self._items)

        self.status_label.setText(
            f"Batch abgeschlossen: {done}/{total} erfolgreich"
            + (f", {errors} Fehler" if errors else "")
        )

        self.batch_completed.emit()

    # --- Hilfsmethoden ---

    def _update_char_counter(self, index: int):
        """Aktualisiert den Zeichenzähler für ein Item."""
        if index >= len(self._char_labels) or index >= len(self._items):
            return

        item = self._items[index]
        char_count = len(item.result_text)
        if char_count == 0:
            self._char_labels[index].setText("")
            return

        # Preset-Limit holen
        from src.core.prompt_builder import get_preset_by_name
        preset = get_preset_by_name(self._config.preset_name)
        max_chars = preset.max_chars if preset else 0

        if max_chars == 0:
            self._char_labels[index].setText(f"{char_count:,} Zeichen")
            self._char_labels[index].setStyleSheet(
                "font-size: 11px; color: #888;"
            )
            return

        ratio = char_count / max_chars
        if ratio <= 0.9:
            color = "#2E7D32"
            icon = "\u2713"
        elif ratio <= 1.0:
            color = "#F57F17"
            icon = "\u26A0"
        else:
            color = "#C62828"
            icon = "\u2717"

        if ratio > 1.0:
            over = char_count - max_chars
            display = (
                f"{icon} {char_count:,} / {max_chars:,} Zeichen"
                f" \u2014 {over:,} \u00fcber Limit"
            )
        else:
            display = f"{icon} {char_count:,} / {max_chars:,} Zeichen"

        self._char_labels[index].setText(display)
        self._char_labels[index].setStyleSheet(
            f"font-size: 11px; color: {color};"
            f" font-weight: {'bold' if ratio > 1.0 else 'normal'};"
        )

    def _on_item_rating(self, index: int, z_score: int):
        """Speichert die Bewertung eines Batch-Items."""
        if index >= len(self._items):
            return

        item = self._items[index]
        if item.analysis_id is not None:
            try:
                self._rating_store.update_model_rating_z(
                    item.analysis_id, z_score
                )
                logger.info(
                    f"Batch-Item #{item.position}: "
                    f"Rating {z_score:+d} gespeichert"
                )
            except Exception as e:
                logger.warning(f"Rating-Speicherung fehlgeschlagen: {e}")

    # --- Recovery-Support ---

    def load_recovered_items(self, items: list[BatchItem]):
        """Lädt wiederhergestellte Items aus einer früheren Session.

        Wird von main_window aufgerufen bei Crash-Recovery.
        """
        self._items = items
        self._create_result_tabs(items)

        done = sum(1 for item in items if item.status == "done")
        errors = sum(1 for item in items if item.status == "error")

        self._set_running_state(False)
        self.progress_bar.setMaximum(len(items))
        self.progress_bar.setValue(done + errors)
        self.progress_bar.setVisible(True)
        self.status_label.setText(
            f"Session wiederhergestellt: {done} erledigt, "
            f"{errors} Fehler, {len(items) - done - errors} ausstehend"
        )
        self.status_label.setVisible(True)

        # URL-Felder ausblenden bei Recovery
        for field in self._url_fields:
            field.setVisible(False)
        self.btn_add_url.setVisible(False)
        self.btn_remove_url.setVisible(False)

    # --- Fenster-Events ---

    def closeEvent(self, event):
        """Bricht laufenden Worker ab beim Schließen."""
        if self._is_running and self._batch_worker:
            reply = QMessageBox.question(
                self,
                "Batch läuft noch",
                "Die Batch-Verarbeitung läuft noch.\n"
                "Abbrechen und schließen?",
                QMessageBox.StandardButton.Yes
                | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.No:
                event.ignore()
                return

            self._batch_worker.cancel()

        super().closeEvent(event)
