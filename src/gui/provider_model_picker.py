"""ProviderModelPicker — wiederverwendbares Provider+Modell-Auswahlwidget (v0.9.0).

Kombiniert eine Provider-QComboBox (alle 4 Provider) mit der Modellauswahl:
- statische Provider (Perplexity/Anthropic/OpenAI): einfache QComboBox
- OpenRouter: der bestehende FilterableModelSelector (dynamische Liste, Filter)

Wird im Modellvergleich 3× genutzt (Analyse A, Analyse B, Synthese). Kapselt
das Provider→Modell-Mapping aus dem Hauptfenster zur Wiederverwendung.
"""

import logging

from PyQt6.QtCore import pyqtSignal, pyqtSlot
from PyQt6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QWidget

from src.config.api_config import (
    ProviderDefinition,
    get_api_key,
    get_last_model,
    has_api_key,
)
from src.core.comparison_item import ModelChoice
from src.gui.model_selector import (
    FilterableModelSelector,
    ModelData,
    extract_provider,
)

logger = logging.getLogger(__name__)


class ProviderModelPicker(QWidget):
    """Provider- und Modellauswahl in einem kompakten Widget.

    Signals:
        selection_changed: Emittiert bei jeder Änderung von Provider oder Modell.
    """

    selection_changed = pyqtSignal()

    def __init__(
        self,
        label: str,
        providers: dict[str, ProviderDefinition],
        parent=None,
        openrouter_raw_models: list[dict] | None = None,
    ) -> None:
        """Initialisiert den Picker.

        Args:
            label: Anzeigetext (z.B. "Modell A (Analyse)").
            providers: Provider-Definitionen (geteiltes Dict aus dem Hauptfenster).
            parent: Optionaler Qt-Parent.
            openrouter_raw_models: Optional vorgeladene OpenRouter-Rohdaten
                (Preise/Context), um wiederholte API-Calls zu vermeiden.
        """
        super().__init__(parent)
        self._providers = providers
        self._openrouter_raw: list[dict] = openrouter_raw_models or []

        self._setup_ui(label)
        self._connect_signals()
        self._init_provider()

    # --- UI ---

    def _setup_ui(self, label: str) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.label = QLabel(label)
        self.label.setMinimumWidth(150)
        layout.addWidget(self.label)

        self.provider_combo = QComboBox()
        self.provider_combo.setMinimumWidth(130)
        for provider in self._providers.values():
            self.provider_combo.addItem(provider.name, provider.id)
        layout.addWidget(self.provider_combo)

        # Statische Modellauswahl (Nicht-OpenRouter)
        self.model_combo = QComboBox()
        self.model_combo.setMinimumWidth(320)
        layout.addWidget(self.model_combo)

        # OpenRouter: FilterableModelSelector (initial versteckt)
        self.model_selector = FilterableModelSelector()
        self.model_selector.setVisible(False)
        layout.addWidget(self.model_selector)

        layout.addStretch()

    def _connect_signals(self) -> None:
        self.provider_combo.currentIndexChanged.connect(self._on_provider_changed)
        self.model_combo.currentIndexChanged.connect(self._emit_changed)
        self.model_selector.model_selected.connect(self._emit_changed)

    def _init_provider(self) -> None:
        """Lädt die Modelle für den initial gewählten Provider."""
        self._on_provider_changed(self.provider_combo.currentIndex())

    # --- Provider/Modell-Logik (gespiegelt aus main_window._on_provider_changed) ---

    @pyqtSlot(int)
    def _on_provider_changed(self, _index: int) -> None:
        provider_id = self.provider_combo.currentData()
        if not provider_id or provider_id not in self._providers:
            return

        provider = self._providers[provider_id]

        if provider_id == "openrouter":
            if provider.supports_dynamic_models and has_api_key(provider_id):
                self._ensure_openrouter_models(provider_id)
                provider = self._providers[provider_id]

            self.model_combo.setVisible(False)
            self.model_selector.setVisible(True)

            raw = self._openrouter_raw or [
                {
                    "id": m.id, "name": m.name,
                    "context_length": 0,
                    "pricing_prompt": "0", "pricing_completion": "0",
                }
                for m in provider.models
            ]
            model_data_list = self._convert_to_model_data(raw)
            self.model_selector.set_models(model_data_list)

            last_model = get_last_model(provider_id)
            if last_model:
                self.model_selector.set_selected_model_id(last_model)
            elif provider.default_model:
                self.model_selector.set_selected_model_id(provider.default_model)
            if not self.model_selector.get_selected_model_id() and model_data_list:
                self.model_selector.set_selected_model_id(model_data_list[0].id)
        else:
            self.model_selector.setVisible(False)
            self.model_combo.setVisible(True)

            self.model_combo.blockSignals(True)
            self.model_combo.clear()
            for model in provider.models:
                self.model_combo.addItem(f"{model.name} - {model.description}", model.id)

            last_model = get_last_model(provider_id)
            target = last_model or provider.default_model
            if target:
                for i in range(self.model_combo.count()):
                    if self.model_combo.itemData(i) == target:
                        self.model_combo.setCurrentIndex(i)
                        break
            self.model_combo.blockSignals(False)

        self._emit_changed()

    def _ensure_openrouter_models(self, provider_id: str) -> None:
        """Lädt OpenRouter-Modelle dynamisch (einmalig, mit Cache)."""
        if self._openrouter_raw:
            return
        from src.config.api_config import ProviderModel
        from src.core.openrouter_client import OpenRouterClient

        api_key = get_api_key(provider_id)
        if not api_key:
            return
        try:
            client = OpenRouterClient(api_key)
            models_data = client.get_available_models()
            if models_data:
                self._openrouter_raw = models_data
                self._providers[provider_id].models = [
                    ProviderModel(
                        id=m["id"], name=m["name"], description=m.get("description", "")
                    )
                    for m in models_data
                ]
        except Exception as e:  # noqa: BLE001 — Netzwerkfehler nicht fatal
            logger.warning(f"OpenRouter-Modelle nicht geladen: {e}")

    def _convert_to_model_data(self, raw_models: list[dict]) -> list[ModelData]:
        """Konvertiert OpenRouter-Rohdaten zu ModelData (analog main_window)."""
        result = []
        for m in raw_models:
            try:
                price_prompt = float(m.get("pricing_prompt") or "0")
                price_completion = float(m.get("pricing_completion") or "0")
            except (ValueError, TypeError):
                price_prompt = 0.0
                price_completion = 0.0
            result.append(ModelData(
                id=m["id"],
                name=m.get("name", m["id"].split("/")[-1]),
                provider=extract_provider(m["id"]),
                context_length=m.get("context_length", 0) or 0,
                price_input=price_prompt * 1_000_000,
                price_output=price_completion * 1_000_000,
                is_free=(price_prompt == 0 and price_completion == 0),
            ))
        return result

    def _emit_changed(self, *args) -> None:
        self.selection_changed.emit()

    # --- Public API ---

    def get_selection(self) -> ModelChoice | None:
        """Gibt die aktuelle Auswahl zurück (None wenn nichts gewählt)."""
        provider_id = self.provider_combo.currentData()
        if not provider_id or provider_id not in self._providers:
            return None
        provider_name = self._providers[provider_id].name

        if provider_id == "openrouter":
            model_id = self.model_selector.get_selected_model_id()
            if not model_id:
                return None
            data = self.model_selector.get_selected_model_data()
            model_name = data.name if data else model_id.split("/")[-1]
        else:
            model_id = self.model_combo.currentData()
            if not model_id:
                return None
            model_name = self._model_name_for(provider_id, model_id)

        return ModelChoice(
            provider_id=provider_id,
            model_id=model_id,
            model_name=model_name,
            provider_name=provider_name,
        )

    def _model_name_for(self, provider_id: str, model_id: str) -> str:
        """Sucht den Anzeigenamen eines Modells im Provider."""
        provider = self._providers.get(provider_id)
        if provider:
            for m in provider.models:
                if m.id == model_id:
                    return m.name
        return model_id

    def set_selection(self, choice: ModelChoice) -> None:
        """Setzt Provider und Modell auf die gegebene Auswahl."""
        if not choice:
            return
        for i in range(self.provider_combo.count()):
            if self.provider_combo.itemData(i) == choice.provider_id:
                self.provider_combo.setCurrentIndex(i)
                break
        # _on_provider_changed wurde durch setCurrentIndex bereits ausgelöst;
        # jetzt das konkrete Modell setzen.
        if choice.provider_id == "openrouter":
            self.model_selector.set_selected_model_id(choice.model_id)
        else:
            for i in range(self.model_combo.count()):
                if self.model_combo.itemData(i) == choice.model_id:
                    self.model_combo.setCurrentIndex(i)
                    break

    def set_enabled(self, enabled: bool) -> None:
        """Aktiviert/deaktiviert alle Teil-Widgets."""
        self.provider_combo.setEnabled(enabled)
        self.model_combo.setEnabled(enabled)
        self.model_selector.setEnabled(enabled)
