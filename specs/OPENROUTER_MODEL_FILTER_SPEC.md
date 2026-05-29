# OpenRouter Modell-Filter für SOMAS Prompt Generator

> **Entwicklungsanweisung für Claude Code — Feature: Modell-Suche & -Filter**
>
> Erstellt von: Claude.ai (Architekt)  
> Für: Claude Code (Implementierung)  
> Supervisor: Thorsten  
> Entscheidung: Ansatz B (QLineEdit + QListView mit Custom Delegate)

---

## 🎯 Problem & Ziel

### Das Problem

OpenRouter liefert 200+ Modelle. Das aktuelle QComboBox-Dropdown ist bei dieser Menge unbrauchbar — endloses Scrollen ohne Orientierung. Modelle sind unsortiert, ohne Preise, ohne Gruppierung.

### Die Lösung

Ein **Custom FilterableModelSelector-Widget** mit:

1. **Type-to-Filter Suchfeld** — Tippen filtert die Liste in Echtzeit
2. **Gruppierung nach Anbieter** — Sticky Group Headers (Anthropic, Google, Meta, ...)
3. **Preis- & Context-Anzeige** — Direkt in jeder Zeile sichtbar
4. **Magic Keywords** — `free`, `cheap`/`billig`/`günstig` als Schnellfilter

### Scope

- **Betrifft:** Nur das OpenRouter-Modell-Dropdown
- **Perplexity bleibt unverändert:** 3 Modelle → Standard-QComboBox reicht
- **Kein Breaking Change:** Alle bestehenden Funktionen (API-Modus, Settings, Export) bleiben intakt

---

## 🖼️ UX-Design

### Grundzustand (Suchfeld leer)

```
┌─────────────────────────────────────────────────────────┐
│  🔍 Modell suchen... (free, cheap = Schnellfilter)     │
├─────────────────────────────────────────────────────────┤
│  ── Anthropic ──────────────────────────────────────    │
│  Claude Sonnet 4.5          200K        $3 / $15       │
│  Claude Haiku 4.5           200K      $0.80 / $4       │
│  Claude Opus 4              200K       $15 / $75       │
│                                                         │
│  ── Google ─────────────────────────────────────────    │
│  Gemini 2.5 Pro             1M         $1.25 / $10     │
│  Gemini 2.5 Flash           1M       $0.15 / $0.60     │
│  Gemini 3 Pro Preview       1M         $2.50 / $15     │
│                                                         │
│  ── xAI ────────────────────────────────────────────    │
│  Grok 4.1                   128K        $3 / $15       │
│  Grok 4.1 Fast              128K      $0.60 / $3       │
│                                                         │
│  ── DeepSeek ───────────────────────────────────────    │
│  DeepSeek R1                128K      $0.55 / $2.19    │
│  DeepSeek V3                128K      $0.27 / $1.10    │
│                                                         │
│  ── Meta ───────────────────────────────────────────    │
│  Llama 4 Scout              512K       FREE             │
│  Llama 4 Maverick           512K       FREE             │
│  ...                                                    │
└─────────────────────────────────────────────────────────┘
```

### Nach Eingabe von "claude"

```
┌─────────────────────────────────────────────────────────┐
│  🔍 claude                                        [✕]  │
├─────────────────────────────────────────────────────────┤
│  ── Anthropic ──────────────────────────────────────    │
│  Claude Sonnet 4.5          200K        $3 / $15       │
│  Claude Haiku 4.5           200K      $0.80 / $4       │
│  Claude Opus 4              200K       $15 / $75       │
│  Claude Sonnet 4            200K        $3 / $15       │
│  Claude Haiku 4             200K     $0.40 / $2        │
└─────────────────────────────────────────────────────────┘
```

### Nach Eingabe von "free"

```
┌─────────────────────────────────────────────────────────┐
│  🔍 free                                          [✕]  │
├─────────────────────────────────────────────────────────┤
│  ── Meta ───────────────────────────────────────────    │
│  Llama 4 Scout              512K       FREE             │
│  Llama 4 Maverick           512K       FREE             │
│                                                         │
│  ── Qwen ───────────────────────────────────────────    │
│  Qwen3 235B A22B            128K       FREE             │
│                                                         │
│  ── DeepSeek ───────────────────────────────────────    │
│  DeepSeek V3 (Free)         128K       FREE             │
│  ...                                                    │
└─────────────────────────────────────────────────────────┘
```

### Nach Eingabe von "cheap" / "billig" / "günstig"

Zeigt Modelle mit Input-Preis **unter $1.00 pro Million Tokens:**

```
┌─────────────────────────────────────────────────────────┐
│  🔍 cheap                                         [✕]  │
├─────────────────────────────────────────────────────────┤
│  ── Anthropic ──────────────────────────────────────    │
│  Claude Haiku 4.5           200K      $0.80 / $4       │
│  Claude Haiku 4             200K      $0.40 / $2       │
│                                                         │
│  ── Google ─────────────────────────────────────────    │
│  Gemini 2.5 Flash           1M       $0.15 / $0.60     │
│                                                         │
│  ── xAI ────────────────────────────────────────────    │
│  Grok 4.1 Fast              128K      $0.60 / $3       │
│                                                         │
│  ── DeepSeek ───────────────────────────────────────    │
│  DeepSeek R1                128K      $0.55 / $2.19    │
│  DeepSeek V3                128K      $0.27 / $1.10    │
│  ...                                                    │
│  + alle FREE-Modelle                                    │
└─────────────────────────────────────────────────────────┘
```

### Modell-Auswahl und Anzeige

Nach Klick auf ein Modell:
- Liste klappt zu
- Suchfeld zeigt ausgewähltes Modell: `Claude Sonnet 4.5 · 200K · $3/$15`
- Signal `model_selected(model_id: str)` wird emittiert

---

## 🏗️ Technische Architektur

### Neue Datei

```
src/
└── gui/
    └── model_selector.py     # NEU: FilterableModelSelector Widget
```

### Klassen-Übersicht

```python
# src/gui/model_selector.py

class ModelData:
    """Datenklasse für ein einzelnes Modell."""
    id: str                    # "anthropic/claude-3-sonnet"
    name: str                  # "Claude 3 Sonnet"  
    provider: str              # "Anthropic" (extrahiert aus id)
    context_length: int        # 200000
    price_input: float         # Preis pro Million Input-Tokens ($)
    price_output: float        # Preis pro Million Output-Tokens ($)
    is_free: bool              # True wenn beide Preise == 0

class ModelItemDelegate(QStyledItemDelegate):
    """Custom Rendering für Modell-Einträge und Group-Headers."""
    # Zeichnet:
    # - Group Headers: Fette Linie mit Provider-Name
    # - Modell-Zeilen: Name links, Context+Preis rechts
    # - FREE-Badge: Grüner Text für kostenlose Modelle

class FilterableModelSelector(QWidget):
    """Hauptwidget: Suchfeld + filterbare Modell-Liste."""
    
    # Signals
    model_selected = pyqtSignal(str)  # Emittiert model_id
    
    # Komponenten
    # - QLineEdit (Suchfeld mit Placeholder und Clear-Button)
    # - QListView (Modell-Liste mit Custom Delegate)
    # - QStandardItemModel + QSortFilterProxyModel (Daten + Filter)
    
    # Öffentliche Methoden
    def set_models(self, models: list[ModelData]) -> None: ...
    def get_selected_model_id(self) -> str | None: ...
    def set_selected_model_id(self, model_id: str) -> None: ...
```

---

## 📐 Widget-Verhalten

### Suchfeld (QLineEdit)

- **Placeholder:** `"🔍 Modell suchen... (free, cheap = Schnellfilter)"`
- **Clear-Button:** Standard Qt `setClearButtonEnabled(True)` → ✕ erscheint bei Text
- **Focus:** Klick ins Feld öffnet die Liste (falls nicht bereits offen)
- **Escape:** Schließt die Liste, Suchtext bleibt
- **Enter:** Wählt das erste sichtbare (nicht-header) Modell aus

### Liste (QListView)

- **Maximale Höhe:** ~400px (ca. 15 Zeilen sichtbar), dann Scrollbar
- **Sichtbarkeit:** Immer sichtbar wenn OpenRouter aktiv (kein Popup — festes Element im Layout)
- **Group Headers:** Nicht klickbar, visuell abgesetzt (fette Schrift, Hintergrundfarbe)
- **Modell-Zeilen:** Klick → Auswahl, Doppelklick → Auswahl + Liste-Fokus-Verlust
- **Keyboard:** Pfeiltasten navigieren (überspringen Headers), Enter wählt aus

### Filter-Logik

```python
def matches_filter(self, model: ModelData, search_text: str) -> bool:
    """Entscheidet ob ein Modell den Filter passiert."""
    text = search_text.strip().lower()
    
    if not text:
        return True  # Kein Filter → alles zeigen
    
    # Magic Keywords
    if text == "free":
        return model.is_free
    
    if text in ("cheap", "billig", "günstig"):
        return model.is_free or model.price_input < 1.0  # < $1/M Input-Tokens
    
    # Textsuche: Name ODER Provider ODER Model-ID
    return (text in model.name.lower() 
            or text in model.provider.lower()
            or text in model.id.lower())
```

### Gruppierung

- **Provider-Extraktion aus Model-ID:** `"anthropic/claude-3-sonnet"` → `"Anthropic"`
- **Sortierung der Gruppen:** Alphabetisch nach Provider-Name
- **Sortierung innerhalb der Gruppe:** Nach Preis aufsteigend (günstigste zuerst)
- **Leere Gruppen:** Ausblenden wenn kein Modell den Filter passiert

### Provider-Name-Mapping

```python
PROVIDER_DISPLAY_NAMES = {
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
    # Fallback: Erster Teil der ID capitalized
}
```

---

## 💰 Preisanzeige

### Format

```
Name                    Context     Input / Output
Claude Sonnet 4.5       200K        $3 / $15
Gemini 2.5 Flash        1M          $0.15 / $0.60
Llama 4 Scout           512K        FREE
```

### Umrechnung

OpenRouter liefert Preise **pro Token**. Anzeige in **$ pro Million Tokens:**

```python
def format_price(price_per_token: float) -> str:
    """Konvertiert Token-Preis zu $/M-Anzeige."""
    price_per_million = price_per_token * 1_000_000
    
    if price_per_million == 0:
        return "FREE"
    elif price_per_million < 0.01:
        return f"${price_per_million:.4f}"
    elif price_per_million < 1:
        return f"${price_per_million:.2f}"
    else:
        return f"${price_per_million:.0f}" if price_per_million == int(price_per_million) \
               else f"${price_per_million:.2f}"

def format_context(context_length: int) -> str:
    """Konvertiert Context-Length zu lesbarer Anzeige."""
    if context_length >= 1_000_000:
        return f"{context_length / 1_000_000:.0f}M"
    else:
        return f"{context_length / 1_000:.0f}K"
```

---

## 🎨 Visuelles Design (ModelItemDelegate)

### Group Header

```python
# Hintergrund: Leichtes Grau (#F0F0F0)
# Text: Fett, dunkles Blau (#1e3a5f), 10pt
# Höhe: 28px
# Linie: 1px solid #CCCCCC unten
# Nicht selektierbar, nicht klickbar
```

### Modell-Zeile

```python
# Höhe: 32px
# Links: Modellname (normal, 10pt)
# Rechts: Context-Badge + Preis (grau, 9pt, right-aligned)
# Hover: Leicht hervorgehoben (#E8F0FE)
# Selected: Blauer Hintergrund (#2563EB), weißer Text
# FREE-Modelle: Preis in Grün (#10B981) statt Grau
```

### Layout einer Modell-Zeile

```
┌──────────────────────────────────────────────────────┐
│  Claude Sonnet 4.5              200K     $3 / $15    │
│  ↑ Name (left-aligned)         ↑ rechts aligned     │
└──────────────────────────────────────────────────────┘
```

---

## 🔗 Integration in main_window.py

### Aktuelles Verhalten (beibehalten)

```python
# Provider-Wechsel: Perplexity → QComboBox (3 Modelle, wie bisher)
# Provider-Wechsel: OpenRouter → FilterableModelSelector (NEU)
```

### Änderungen in main_window.py

```python
# In __init__ oder _setup_api_section:

# 1. Beide Widgets erstellen
self.model_combo = QComboBox()                          # Perplexity (bleibt)
self.model_selector = FilterableModelSelector()          # OpenRouter (NEU)

# 2. In einen QStackedWidget packen
self.model_stack = QStackedWidget()
self.model_stack.addWidget(self.model_combo)             # Index 0: Perplexity
self.model_stack.addWidget(self.model_selector)          # Index 1: OpenRouter

# 3. Provider-Wechsel steuert welches Widget sichtbar ist
def on_provider_changed(self, provider_id: str):
    if provider_id == "openrouter":
        self.model_stack.setCurrentIndex(1)
    else:
        self.model_stack.setCurrentIndex(0)

# 4. Signal-Verbindung
self.model_selector.model_selected.connect(self._on_model_selected)
```

### Daten laden

```python
# Wenn OpenRouter-Modelle geladen werden (bestehender Code in openrouter_client.py):
# Die /models-Antwort wird zu List[ModelData] konvertiert und an das Widget übergeben:

models = self.openrouter_client.get_available_models()
model_data_list = [
    ModelData(
        id=m["id"],
        name=m.get("name", m["id"].split("/")[-1]),
        provider=extract_provider(m["id"]),
        context_length=m.get("context_length", 0),
        price_input=float(m.get("pricing", {}).get("prompt", 0)) * 1_000_000,
        price_output=float(m.get("pricing", {}).get("completion", 0)) * 1_000_000,
        is_free=(float(m.get("pricing", {}).get("prompt", 0)) == 0)
    )
    for m in models
]
self.model_selector.set_models(model_data_list)
```

### Kompatibilität mit bestehendem Code

Überall wo aktuell `self.model_combo.currentData()` den model_id liefert, muss eine Hilfsmethode her:

```python
def get_selected_model_id(self) -> str | None:
    """Gibt die Model-ID des aktuell gewählten Modells zurück (provider-agnostisch)."""
    if self.model_stack.currentIndex() == 0:  # Perplexity
        return self.model_combo.currentData()
    else:  # OpenRouter
        return self.model_selector.get_selected_model_id()
```

---

## 📊 Datenfluss

```
OpenRouter /models API
        │
        ▼
openrouter_client.py: get_available_models()
        │
        ▼ List[dict] (raw API response)
        │
main_window.py: Konvertierung zu List[ModelData]
        │
        ▼
FilterableModelSelector.set_models()
        │
        ├──▶ QStandardItemModel (alle Modelle + Group Headers)
        │
        ├──▶ QSortFilterProxyModel (Filter-Logik)
        │
        └──▶ QListView + ModelItemDelegate (Rendering)
        
User tippt "claude"
        │
        ▼
QLineEdit.textChanged → FilterProxyModel.setFilterFixedString()
        │
        ▼
Nur passende Modelle + deren Group Headers sichtbar
        
User klickt Modell
        │
        ▼
model_selected Signal → main_window._on_model_selected()
        │
        ▼
Model-ID steht für API-Call bereit
```

---

## 🚀 Implementierungsreihenfolge

### Schritt 1: ModelData + Grundstruktur (~30 Zeilen)
1. `model_selector.py` anlegen
2. `ModelData` Dataclass
3. `PROVIDER_DISPLAY_NAMES` Dict
4. `format_price()` und `format_context()` Hilfsfunktionen

### Schritt 2: FilterableModelSelector Widget (~50 Zeilen)
1. QWidget mit QVBoxLayout
2. QLineEdit (Suchfeld) mit Placeholder und Clear-Button
3. QListView mit QStandardItemModel
4. `set_models()` — befüllt das Model mit Group Headers + Modell-Einträgen
5. Basis-Filterung (textChanged → Filter aktualisieren)

### Schritt 3: ModelItemDelegate (~40 Zeilen)
1. Group Header Rendering (Hintergrund, fette Schrift, Linie)
2. Modell-Zeile Rendering (Name links, Context+Preis rechts)
3. FREE-Badge in Grün
4. Hover-/Selection-Styling

### Schritt 4: Filter-Logik (~20 Zeilen)
1. Magic Keywords: `free`, `cheap`, `billig`, `günstig`
2. Textsuche in Name, Provider, Model-ID
3. Leere Gruppen ausblenden

### Schritt 5: Integration in main_window.py (~30 Zeilen)
1. QStackedWidget für Perplexity-Combo / OpenRouter-Selector
2. Provider-Wechsel-Logik
3. `get_selected_model_id()` Hilfsmethode
4. Signal-Verbindungen

### Schritt 6: Test & Polish
1. Manueller Test mit echten OpenRouter-Daten (API-Key erforderlich)
2. Keyboard-Navigation (Pfeiltasten, Enter, Escape)
3. Edge Cases: 0 Modelle, API-Fehler, leere Suche

---

## ⚠️ Wichtige Hinweise

1. **Perplexity nicht anfassen:** Das bestehende QComboBox für Perplexity bleibt 1:1 erhalten
2. **Kein neuer API-Call:** Die Modell-Liste kommt aus dem bestehenden `get_available_models()` — nur die Darstellung ändert sich
3. **Cached Modelle:** Die Liste wird einmal geladen (beim Provider-Wechsel oder App-Start) und bleibt im Speicher. Kein erneuter API-Call bei jedem Suchbuchstaben
4. **Zuletzt gewähltes Modell:** Muss weiterhin in `user_preferences.json` gespeichert und beim Start wiederhergestellt werden
5. **QStackedWidget statt Widget-Swap:** Sauberer als Widgets dynamisch hinzuzufügen/entfernen — beide existieren gleichzeitig, nur eins ist sichtbar
6. **Group Headers im Model:** Als Items mit einer speziellen Qt.UserRole-Flag (z.B. `"is_header": True`) — der Delegate erkennt daran, ob er einen Header oder ein Modell zeichnet

---

## 🧪 Test-Szenarios

| # | Szenario | Erwartung |
|---|----------|-----------|
| 1 | App starten, OpenRouter wählen | FilterableModelSelector erscheint mit allen Modellen, gruppiert |
| 2 | "claude" eintippen | Nur Anthropic-Modelle sichtbar |
| 3 | "free" eintippen | Nur kostenlose Modelle sichtbar |
| 4 | "cheap" eintippen | Modelle < $1/M Input + alle FREE-Modelle |
| 5 | "billig" eintippen | Identisch zu "cheap" |
| 6 | "günstig" eintippen | Identisch zu "cheap" |
| 7 | "xyz123" eintippen | Leere Liste (kein Treffer) |
| 8 | Text löschen (✕ oder Backspace) | Alle Modelle wieder sichtbar |
| 9 | Modell anklicken | Suchfeld zeigt Modellname + Preis, Signal emittiert |
| 10 | Zu Perplexity wechseln | QComboBox erscheint (3 Modelle), FilterableModelSelector versteckt |
| 11 | Zurück zu OpenRouter | FilterableModelSelector erscheint, letzte Auswahl erhalten |
| 12 | Kein Internet / API-Fehler | Fallback auf hardcoded Modell-Liste aus api_providers.json |
| 13 | Generate Prompt mit API-Automatik | Gewähltes Modell-ID wird korrekt an API-Worker übergeben |
| 14 | Pfeiltasten im Suchfeld | Navigation in der Liste, Header werden übersprungen |
| 15 | Enter drücken | Erstes sichtbares Modell wird ausgewählt |

---

## 📞 Fragen an Thorsten (für Claude Code)

Falls während der Implementierung Unklarheiten auftreten:

1. Soll die Liste immer sichtbar sein (festes Element) oder als Popup aufklappen?
   → **Empfehlung: Festes Element** — bei 200+ Modellen ist ein Popup unpraktisch
2. Maximale Höhe der Liste? → **Empfehlung: ~400px (ca. 12-15 Einträge)**
3. Sollen "Zuletzt verwendet"-Modelle oben angepinnt werden? → **Erstmal nein, kann später ergänzt werden**

---

*Erstellt: 02. Februar 2026 | Version: 1.0*
*Basiert auf: Prototyp-Vergleich A vs. B vom gleichen Tag*
