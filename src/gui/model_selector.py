"""FilterableModelSelector — Durchsuchbares Modell-Widget für OpenRouter.

Ersetzt die QComboBox bei 200+ Modellen durch ein Widget mit:
- Type-to-Filter Suchfeld (kompakt, in der Controls-Zeile)
- Popup-Liste mit Gruppierung nach Anbieter
- Preis- und Context-Anzeige pro Modell
- Magic Keywords: free, cheap/billig/günstig
"""

import logging
from dataclasses import dataclass

from PyQt6.QtCore import (
    QModelIndex, QPoint, QSize, QSortFilterProxyModel, Qt, pyqtSignal, pyqtSlot,
)
from PyQt6.QtGui import (
    QColor, QPainter, QPen, QStandardItem, QStandardItemModel,
)
from PyQt6.QtWidgets import (
    QAbstractItemView, QFrame, QLineEdit, QListView, QStyledItemDelegate,
    QStyleOptionViewItem, QVBoxLayout, QWidget,
)

logger = logging.getLogger(__name__)

# Custom data roles
ROLE_MODEL_ID = Qt.ItemDataRole.UserRole
ROLE_IS_HEADER = Qt.ItemDataRole.UserRole + 1
ROLE_MODEL_DATA = Qt.ItemDataRole.UserRole + 2
ROLE_DISPLAY_RIGHT = Qt.ItemDataRole.UserRole + 3  # Pre-computed right-side text

# Provider display name mapping
PROVIDER_DISPLAY_NAMES: dict[str, str] = {
    "anthropic": "Anthropic",
    "google": "Google",
    "meta-llama": "Meta",
    "x-ai": "xAI",
    "deepseek": "DeepSeek",
    "mistralai": "Mistral",
    "qwen": "Qwen",
    "moonshotai": "Moonshot",
    "cohere": "Cohere",
    "openai": "OpenAI",
    "microsoft": "Microsoft",
    "nousresearch": "Nous Research",
    "perplexity": "Perplexity",
}

CHEAP_THRESHOLD = 1.0  # $1 pro Million Input-Tokens

MAGIC_KEYWORDS_FREE = {"free"}
MAGIC_KEYWORDS_CHEAP = {"cheap", "billig", "günstig"}


@dataclass
class ModelData:
    """Datenklasse für ein einzelnes Modell."""

    id: str                    # "anthropic/claude-sonnet-4.5"
    name: str                  # "Claude Sonnet 4.5"
    provider: str              # "Anthropic"
    context_length: int        # 200000
    price_input: float         # Preis pro Million Input-Tokens ($)
    price_output: float        # Preis pro Million Output-Tokens ($)
    is_free: bool              # True wenn beide Preise == 0


def extract_provider(model_id: str) -> str:
    """Extrahiert den Anbieter-Anzeigenamen aus einer Model-ID.

    Args:
        model_id: z.B. 'anthropic/claude-sonnet-4.5'

    Returns:
        Anzeigename z.B. 'Anthropic'
    """
    parts = model_id.split("/", maxsplit=1)
    if len(parts) < 2:
        return model_id.capitalize()
    provider_key = parts[0].lower()
    return PROVIDER_DISPLAY_NAMES.get(provider_key, parts[0].capitalize())


def format_price(price_per_million: float) -> str:
    """Konvertiert Preis pro Million Tokens zu Anzeige-String.

    Args:
        price_per_million: Preis in $ pro Million Tokens.

    Returns:
        z.B. '$3', '$0.80', 'FREE'
    """
    if price_per_million == 0:
        return "FREE"
    if price_per_million < 0.01:
        return f"${price_per_million:.4f}"
    if price_per_million < 1:
        return f"${price_per_million:.2f}"
    if price_per_million == int(price_per_million):
        return f"${int(price_per_million)}"
    return f"${price_per_million:.2f}"


def format_context(context_length: int) -> str:
    """Konvertiert Context-Length zu lesbarer Anzeige.

    Args:
        context_length: Token-Fenstergröße.

    Returns:
        z.B. '200K', '1M'
    """
    if context_length >= 1_000_000:
        val = context_length / 1_000_000
        return f"{int(val)}M" if val == int(val) else f"{val:.1f}M"
    if context_length >= 1000:
        return f"{context_length // 1000}K"
    return str(context_length)


def _build_right_text(model: ModelData) -> str:
    """Baut den rechts-ausgerichteten Anzeige-Text für eine Modell-Zeile."""
    ctx = format_context(model.context_length) if model.context_length else ""
    if model.is_free:
        price = "FREE"
    else:
        price = f"{format_price(model.price_input)} / {format_price(model.price_output)}"
    parts = [p for p in (ctx, price) if p]
    return "     ".join(parts)


# ---------------------------------------------------------------------------
# Filter Proxy Model
# ---------------------------------------------------------------------------

class ModelFilterProxyModel(QSortFilterProxyModel):
    """Filter-Proxy mit Magic-Keyword-Unterstützung.

    Filtert Modell-Zeilen nach Suchtext und blendet leere
    Gruppen-Header automatisch aus.
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._filter_text = ""

    def set_filter_text(self, text: str) -> None:
        """Setzt den Filter-Text und aktualisiert die Anzeige."""
        self._filter_text = text.strip().lower()
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
        """Entscheidet ob eine Zeile sichtbar ist."""
        source_model = self.sourceModel()
        index = source_model.index(source_row, 0, source_parent)
        is_header = index.data(ROLE_IS_HEADER)

        if is_header:
            return self._has_visible_children(source_row, source_parent)

        model_data: ModelData | None = index.data(ROLE_MODEL_DATA)
        if model_data is None:
            return False

        return self._matches_filter(model_data)

    def _matches_filter(self, model: ModelData) -> bool:
        """Prüft ob ein Modell den aktuellen Filter passiert."""
        text = self._filter_text
        if not text:
            return True

        if text in MAGIC_KEYWORDS_FREE:
            return model.is_free
        if text in MAGIC_KEYWORDS_CHEAP:
            return model.is_free or model.price_input < CHEAP_THRESHOLD

        return (
            text in model.name.lower()
            or text in model.provider.lower()
            or text in model.id.lower()
        )

    def _has_visible_children(self, header_row: int, parent: QModelIndex) -> bool:
        """Prüft ob nach diesem Header mindestens ein sichtbares Modell kommt."""
        source_model = self.sourceModel()
        row_count = source_model.rowCount(parent)

        for row in range(header_row + 1, row_count):
            idx = source_model.index(row, 0, parent)
            if idx.data(ROLE_IS_HEADER):
                break
            model_data: ModelData | None = idx.data(ROLE_MODEL_DATA)
            if model_data and self._matches_filter(model_data):
                return True
        return False


# ---------------------------------------------------------------------------
# Item Delegate
# ---------------------------------------------------------------------------

class ModelItemDelegate(QStyledItemDelegate):
    """Custom Rendering für Modell-Einträge und Group-Headers."""

    HEADER_HEIGHT = 28
    MODEL_HEIGHT = 32
    HEADER_BG = QColor("#F0F0F0")
    HEADER_TEXT_COLOR = QColor("#1e3a5f")
    HEADER_LINE_COLOR = QColor("#CCCCCC")
    HOVER_BG = QColor("#E8F0FE")
    SELECTED_BG = QColor("#2563EB")
    FREE_COLOR = QColor("#10B981")
    PRICE_COLOR = QColor("#808080")

    def paint(
        self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex
    ) -> None:
        """Zeichnet eine Zeile (Header oder Modell)."""
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = option.rect
        is_header = index.data(ROLE_IS_HEADER)

        if is_header:
            self._paint_header(painter, rect, index)
        else:
            self._paint_model(painter, rect, option, index)

        painter.restore()

    def _paint_header(
        self, painter: QPainter, rect, index: QModelIndex
    ) -> None:
        """Zeichnet einen Gruppen-Header."""
        painter.fillRect(rect, self.HEADER_BG)

        painter.setPen(QPen(self.HEADER_LINE_COLOR, 1))
        painter.drawLine(rect.left(), rect.bottom(), rect.right(), rect.bottom())

        font = painter.font()
        font.setBold(True)
        font.setPointSize(10)
        painter.setFont(font)
        painter.setPen(self.HEADER_TEXT_COLOR)

        provider_name = index.data(Qt.ItemDataRole.DisplayRole) or ""
        text_rect = rect.adjusted(12, 0, -8, 0)
        painter.drawText(
            text_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            f"── {provider_name} ──",
        )

    def _paint_model(
        self, painter: QPainter, rect, option: QStyleOptionViewItem,
        index: QModelIndex,
    ) -> None:
        """Zeichnet eine Modell-Zeile."""
        is_selected = bool(option.state & option.state.State_Selected)
        is_hover = bool(option.state & option.state.State_MouseOver)

        if is_selected:
            painter.fillRect(rect, self.SELECTED_BG)
        elif is_hover:
            painter.fillRect(rect, self.HOVER_BG)

        model_data: ModelData | None = index.data(ROLE_MODEL_DATA)
        if model_data is None:
            return

        name_font = painter.font()
        name_font.setPointSize(10)
        name_font.setBold(False)
        painter.setFont(name_font)
        painter.setPen(QColor("white") if is_selected else QColor("black"))

        name_rect = rect.adjusted(12, 0, -200, 0)
        painter.drawText(
            name_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            model_data.name,
        )

        right_text = index.data(ROLE_DISPLAY_RIGHT) or ""
        info_font = painter.font()
        info_font.setPointSize(9)
        painter.setFont(info_font)

        if is_selected:
            painter.setPen(QColor("#E0E0E0"))
        elif model_data.is_free:
            painter.setPen(self.FREE_COLOR)
        else:
            painter.setPen(self.PRICE_COLOR)

        info_rect = rect.adjusted(0, 0, -12, 0)
        painter.drawText(
            info_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight,
            right_text,
        )

    def sizeHint(self, _option: QStyleOptionViewItem, index: QModelIndex) -> QSize:
        """Gibt die bevorzugte Zeilenhöhe zurück."""
        is_header = index.data(ROLE_IS_HEADER)
        if is_header:
            return QSize(0, self.HEADER_HEIGHT)
        return QSize(0, self.MODEL_HEIGHT)


# ---------------------------------------------------------------------------
# Popup-Frame für die Modell-Liste
# ---------------------------------------------------------------------------

class _ModelListPopup(QFrame):
    """Popup-Fenster für die gefilterte Modell-Liste.

    Erscheint unterhalb des Suchfelds und überlagert den restlichen
    App-Inhalt (wie ein QComboBox-Dropdown). Verwendet Tool-Window-Flags
    statt Popup, damit der Fokus beim Suchfeld bleibt und Tippen
    weiterhin funktioniert.
    """

    item_clicked = pyqtSignal(QModelIndex)

    def __init__(self, parent=None) -> None:
        super().__init__(
            parent,
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint,
        )
        # Fokus nicht stehlen — Suchfeld soll Tastatureingabe behalten
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(1, 1, 1, 1)
        layout.setSpacing(0)

        self.list_view = QListView()
        self.list_view.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.list_view.setMouseTracking(True)
        self.list_view.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        # Fokus-Policy: Kein Fokus — bleibt beim Suchfeld
        self.list_view.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        layout.addWidget(self.list_view)

        self.list_view.clicked.connect(self.item_clicked.emit)

    def show_below(self, widget: QWidget) -> None:
        """Positioniert und zeigt das Popup unterhalb eines Widgets."""
        pos = widget.mapToGlobal(QPoint(0, widget.height()))
        self.move(pos)
        width = max(widget.width(), 550)
        self.setFixedWidth(width)
        self.setMaximumHeight(450)
        self.show()


# ---------------------------------------------------------------------------
# FilterableModelSelector Widget
# ---------------------------------------------------------------------------

class FilterableModelSelector(QWidget):
    """Kompaktes Suchfeld mit Popup-Modell-Liste für OpenRouter.

    Das Suchfeld ist ein kompakter QLineEdit, der in der Controls-Zeile
    neben dem Provider-Dropdown sitzt. Bei Klick/Fokus öffnet sich ein
    Popup-Dropdown mit der gefilterten Modell-Liste.

    Signals:
        model_selected: Emittiert die Model-ID bei Auswahl.
    """

    model_selected = pyqtSignal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._selected_model_id: str | None = None
        self._showing_selection = False
        self._popup_visible = False

        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self) -> None:
        """Erstellt das kompakte Layout (nur Suchfeld sichtbar)."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Suchfeld (kompakt, in der Controls-Zeile)
        self.search_field = QLineEdit()
        self.search_field.setPlaceholderText(
            "Modell suchen... (free, cheap)"
        )
        self.search_field.setClearButtonEnabled(True)
        self.search_field.setMinimumWidth(350)
        layout.addWidget(self.search_field)

        # Source Model + Filter Proxy
        self._source_model = QStandardItemModel(self)
        self._proxy_model = ModelFilterProxyModel(self)
        self._proxy_model.setSourceModel(self._source_model)

        # Popup mit ListView
        self._popup = _ModelListPopup(self)
        self._popup.list_view.setModel(self._proxy_model)
        self._popup.list_view.setItemDelegate(ModelItemDelegate(self))

    def _connect_signals(self) -> None:
        """Verbindet interne Signals."""
        self.search_field.textEdited.connect(self._on_search_text_edited)
        self.search_field.returnPressed.connect(self._on_enter_pressed)
        self._popup.item_clicked.connect(self._on_item_clicked)
        # Event-Filter für Fokus-Überwachung und Keyboard-Navigation
        self.search_field.installEventFilter(self)

    # --- Event Handling ---

    def eventFilter(self, obj, event) -> bool:
        """Event-Filter für das Suchfeld: Popup-Steuerung und Tastaturnavigation."""
        if obj is not self.search_field:
            return super().eventFilter(obj, event)

        event_type = event.type()

        # Suchfeld bekommt Fokus → Popup öffnen
        if event_type == event.Type.FocusIn:
            self._show_popup()
            return False

        # Suchfeld verliert Fokus → Popup schließen (verzögert, damit
        # Klick auf Popup-ListView noch ankommt)
        if event_type == event.Type.FocusOut:
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(150, self._close_popup_if_unfocused)
            return False

        # Keyboard-Navigation im Suchfeld
        if event_type == event.Type.KeyPress:
            key = event.key()
            if key in (Qt.Key.Key_Down, Qt.Key.Key_Up):
                if not self._popup_visible:
                    self._show_popup()
                else:
                    self._navigate_list(1 if key == Qt.Key.Key_Down else -1)
                return True
            if key == Qt.Key.Key_Escape:
                self._hide_popup()
                return True

        return super().eventFilter(obj, event)

    def _close_popup_if_unfocused(self) -> None:
        """Schließt Popup wenn weder Suchfeld noch Popup den Fokus haben."""
        if not self.search_field.hasFocus():
            self._hide_popup()

    # --- Search & Filter ---

    @pyqtSlot(str)
    def _on_search_text_edited(self, text: str) -> None:
        """Handler für Texteingabe im Suchfeld."""
        self._showing_selection = False
        self._proxy_model.set_filter_text(text)
        if not self._popup_visible:
            self._show_popup()

    def _on_enter_pressed(self) -> None:
        """Handler für Enter im Suchfeld — wählt erstes sichtbares Modell."""
        current = self._popup.list_view.currentIndex()
        if current.isValid() and not current.data(ROLE_IS_HEADER):
            self._on_item_clicked(current)
        else:
            self._select_first_visible_model()
            current = self._popup.list_view.currentIndex()
            if current.isValid():
                self._on_item_clicked(current)

    # --- Popup ---

    def _show_popup(self) -> None:
        """Zeigt das Popup-Dropdown unterhalb des Suchfelds."""
        if self._source_model.rowCount() == 0:
            return
        # Wenn Auswahl-Summary angezeigt wird, beim Fokus den Text selektieren
        if self._showing_selection:
            self.search_field.selectAll()
        self._popup.show_below(self.search_field)
        self._popup_visible = True

    def _hide_popup(self) -> None:
        """Versteckt das Popup-Dropdown."""
        self._popup.hide()
        self._popup_visible = False

    # --- Item Selection ---

    @pyqtSlot(QModelIndex)
    def _on_item_clicked(self, proxy_index: QModelIndex) -> None:
        """Handler für Klick auf ein Listen-Item."""
        source_index = self._proxy_model.mapToSource(proxy_index)
        is_header = source_index.data(ROLE_IS_HEADER)
        if is_header:
            return

        model_id = source_index.data(ROLE_MODEL_ID)
        model_data: ModelData | None = source_index.data(ROLE_MODEL_DATA)
        if not model_id:
            return

        self._selected_model_id = model_id

        if model_data:
            summary = self._build_summary(model_data)
            self._showing_selection = True
            self.search_field.setText(summary)
            self._proxy_model.set_filter_text("")

        self._hide_popup()
        self.model_selected.emit(model_id)
        logger.info(f"Modell ausgewählt: {model_id}")

    def _build_summary(self, model: ModelData) -> str:
        """Baut den Zusammenfassungs-Text für das Suchfeld."""
        parts = [model.name]
        if model.context_length:
            parts.append(format_context(model.context_length))
        if model.is_free:
            parts.append("FREE")
        else:
            parts.append(
                f"{format_price(model.price_input)}/{format_price(model.price_output)}"
            )
        return " · ".join(parts)

    def _navigate_list(self, step: int) -> None:
        """Navigiert in der Liste (überspringt Header)."""
        current = self._popup.list_view.currentIndex()
        if not current.isValid():
            self._select_first_visible_model()
            return

        new_row = current.row() + step
        row_count = self._proxy_model.rowCount()

        while 0 <= new_row < row_count:
            idx = self._proxy_model.index(new_row, 0)
            if not idx.data(ROLE_IS_HEADER):
                self._popup.list_view.setCurrentIndex(idx)
                return
            new_row += step

    def _select_first_visible_model(self) -> None:
        """Selektiert das erste sichtbare (nicht-header) Modell."""
        for row in range(self._proxy_model.rowCount()):
            idx = self._proxy_model.index(row, 0)
            if not idx.data(ROLE_IS_HEADER):
                self._popup.list_view.setCurrentIndex(idx)
                return

    # --- Public API ---

    def set_models(self, models: list[ModelData]) -> None:
        """Befüllt die Liste mit Modellen, gruppiert nach Provider.

        Args:
            models: Liste von ModelData-Objekten.
        """
        self._source_model.clear()
        self._selected_model_id = None
        self._showing_selection = False
        self.search_field.clear()

        if not models:
            return

        # Gruppieren nach Provider
        groups: dict[str, list[ModelData]] = {}
        for model in models:
            groups.setdefault(model.provider, []).append(model)

        # Sortierung: Gruppen alphabetisch, Modelle nach Preis aufsteigend
        for provider in sorted(groups.keys()):
            group_models = sorted(groups[provider], key=lambda m: m.price_input)

            header_item = QStandardItem(provider)
            header_item.setData(None, ROLE_MODEL_ID)
            header_item.setData(True, ROLE_IS_HEADER)
            header_item.setData(provider, ROLE_MODEL_DATA)
            header_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            self._source_model.appendRow(header_item)

            for model in group_models:
                item = QStandardItem(model.name)
                item.setData(model.id, ROLE_MODEL_ID)
                item.setData(False, ROLE_IS_HEADER)
                item.setData(model, ROLE_MODEL_DATA)
                item.setData(_build_right_text(model), ROLE_DISPLAY_RIGHT)
                item.setFlags(
                    Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
                )
                self._source_model.appendRow(item)

        logger.info(f"ModelSelector: {len(models)} Modelle in {len(groups)} Gruppen")

    def get_selected_model_id(self) -> str | None:
        """Gibt die Model-ID des aktuell gewählten Modells zurück."""
        return self._selected_model_id

    def set_selected_model_id(self, model_id: str) -> None:
        """Setzt die Auswahl auf ein bestimmtes Modell.

        Args:
            model_id: Die Model-ID (z.B. 'anthropic/claude-sonnet-4.5').
        """
        for row in range(self._source_model.rowCount()):
            index = self._source_model.index(row, 0)
            if index.data(ROLE_MODEL_ID) == model_id:
                self._selected_model_id = model_id
                model_data: ModelData | None = index.data(ROLE_MODEL_DATA)

                proxy_index = self._proxy_model.mapFromSource(index)
                if proxy_index.isValid():
                    self._popup.list_view.setCurrentIndex(proxy_index)

                if model_data and isinstance(model_data, ModelData):
                    self._showing_selection = True
                    self.search_field.setText(self._build_summary(model_data))
                    self._proxy_model.set_filter_text("")
                return

        logger.warning(f"ModelSelector: Model-ID '{model_id}' nicht gefunden")

    def setEnabled(self, enabled: bool) -> None:
        """Aktiviert/deaktiviert Suchfeld."""
        super().setEnabled(enabled)
        self.search_field.setEnabled(enabled)
        if not enabled:
            self._hide_popup()
