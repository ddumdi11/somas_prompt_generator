# SOMAS v0.4.0 — Zeitbereich & Manuelles Transkript

> **Entwicklungsanweisung für Claude Code — Release 0.4.0**
>
> Erstellt von: Claude.ai (Architekt)  
> Für: Claude Code (Implementierung)  
> Supervisor: Thorsten  
> Ziel-Release: Ende KW 06 / 2026

---

## 🎯 Überblick

Release 0.4.0 bringt zwei Features zur besseren Quellenkontrolle:

| Feature | Nutzen | Aufwand |
|---------|--------|---------|
| **Zeitbereich** | Fokus auf Video-Ausschnitt (z.B. 05:00–12:30) | Niedrig |
| **Manuelles Transkript** | Analyse ohne YouTube-URL, eigene Texte | Niedrig-Mittel |

Beide Features sind bereits im SOMAS-Schema v0.5 spezifiziert und müssen "nur" in die App-UI übernommen werden.

---

## 📋 Feature 1: Zeitbereich (time_range)

### Hintergrund

SOMAS v0.5 definiert bereits den Parameter:
```yaml
time_range:
  start: "00:00:00"
  end: "00:13:45"
```

Das Prompt-Template (`somas_prompt.txt`) enthält bereits die Zeile:
```
{% if time_range %}- Zeitbereich: Analysiere AUSSCHLIESSLICH {{ time_range.start }} bis {{ time_range.end }}
{% endif %}
```

### UI-Design

**Position:** Unterhalb der Meta-Informationen, oberhalb der Fragen

```
┌─────────────────────────────────────────────────────────────┐
│  META-INFORMATIONEN                              [🔓 Edit]  │
│  ┌─────────────────────────────────────────────────────────┐
│  │ Titel: Example Video Title                              │
│  │ Kanal: Channel Name                                     │
│  │ Dauer: 45:32                                            │
│  │ URL: https://youtube.com/...                            │
│  └─────────────────────────────────────────────────────────┘
│                                                             │
│  ┌─ ZEITBEREICH (optional) ────────────────────────────────┐
│  │  ☐ Nur Ausschnitt analysieren                          │
│  │                                                         │
│  │  Start: [00:05:00]    Ende: [00:12:30]                 │
│  │                                                         │
│  │  ☐ Kontext des Gesamtvideos einbeziehen               │
│  │    (Modell weiß, dass es Teil eines längeren Videos ist)│
│  └─────────────────────────────────────────────────────────┘
│                                                             │
│  FRAGEN (optional):                                         │
│  ...                                                        │
└─────────────────────────────────────────────────────────────┘
```

### Verhalten

| Zustand | Prompt-Ausgabe |
|---------|----------------|
| Checkbox deaktiviert | Kein time_range im Prompt |
| Checkbox aktiviert, nur Start/Ende | `Analysiere AUSSCHLIESSLICH 00:05:00 bis 00:12:30` |
| + Kontext-Checkbox | `Analysiere den Ausschnitt 00:05:00 bis 00:12:30 im Kontext des Gesamtvideos (Dauer: 45:32)` |

### Validierung

- **Format:** `HH:MM:SS` oder `MM:SS` (automatisch zu HH:MM:SS konvertieren)
- **Start < Ende:** Fehlermeldung wenn Start ≥ Ende
- **Ende ≤ Videodauer:** Warnung wenn Ende > Videodauer (aus Meta-Informationen)
- **Leere Felder:** Wenn Checkbox aktiv aber Felder leer → Fehlermeldung

### Implementierung

**Änderungen in `main_window.py`:**

```python
# Neue UI-Elemente
self.time_range_checkbox = QCheckBox("Nur Ausschnitt analysieren")
self.time_start_edit = QLineEdit()
self.time_start_edit.setPlaceholderText("00:00:00")
self.time_start_edit.setMaximumWidth(80)
self.time_end_edit = QLineEdit()
self.time_end_edit.setPlaceholderText("00:00:00")
self.time_end_edit.setMaximumWidth(80)
self.time_context_checkbox = QCheckBox("Kontext des Gesamtvideos einbeziehen")

# Enable/Disable basierend auf Haupt-Checkbox
self.time_range_checkbox.toggled.connect(self._toggle_time_range_fields)

def _toggle_time_range_fields(self, enabled: bool):
    self.time_start_edit.setEnabled(enabled)
    self.time_end_edit.setEnabled(enabled)
    self.time_context_checkbox.setEnabled(enabled)
```

**Änderungen in `prompt_builder.py`:**

```python
def build_prompt(..., time_range: dict | None = None, include_context: bool = False):
    # time_range = {"start": "00:05:00", "end": "00:12:30"}
    if time_range:
        if include_context:
            # Angepasster Text für Kontext-Modus
            time_instruction = f"Analysiere den Ausschnitt {time_range['start']} bis {time_range['end']} im Kontext des Gesamtvideos"
        else:
            time_instruction = f"Analysiere AUSSCHLIESSLICH {time_range['start']} bis {time_range['end']}"
```

**Hilfsfunktion für Zeitformat:**

```python
import re

def parse_time_input(time_str: str) -> str | None:
    """Konvertiert MM:SS oder HH:MM:SS zu HH:MM:SS. Gibt None bei ungültigem Format."""
    time_str = time_str.strip()
    
    # HH:MM:SS
    if re.match(r'^\d{1,2}:\d{2}:\d{2}$', time_str):
        parts = time_str.split(':')
        return f"{int(parts[0]):02d}:{parts[1]}:{parts[2]}"
    
    # MM:SS → 00:MM:SS
    if re.match(r'^\d{1,2}:\d{2}$', time_str):
        parts = time_str.split(':')
        return f"00:{int(parts[0]):02d}:{parts[1]}"
    
    return None

def time_to_seconds(time_str: str) -> int:
    """Konvertiert HH:MM:SS zu Sekunden für Vergleiche."""
    parts = time_str.split(':')
    return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
```

---

## 📋 Feature 2: Manuelles Transkript

### Hintergrund

Anwendungsfälle:
- Video ohne automatisches Transkript
- Eigene Transkription (z.B. von Audio-Datei)
- Korrigiertes/bereinigtes Transkript
- Analyse von Nicht-YouTube-Quellen (Podcast, Vortrag)

### UI-Design

**Option A: Button neben URL-Feld**

```
┌─────────────────────────────────────────────────────────────┐
│  YouTube URL: [________________________________] [Get Meta] │
│                                          [📝 Transkript...] │
└─────────────────────────────────────────────────────────────┘
```

**Option B: Tab-Ansicht (empfohlen)**

```
┌─────────────────────────────────────────────────────────────┐
│  [YouTube URL] | [Manuelles Transkript]                     │
├─────────────────────────────────────────────────────────────┤
│  (Tab 1: Bestehende URL-Eingabe)                            │
│  ODER                                                       │
│  (Tab 2: Transkript-Textarea + manuelle Meta-Eingabe)       │
└─────────────────────────────────────────────────────────────┘
```

### Tab 2: Manuelles Transkript

```
┌─────────────────────────────────────────────────────────────┐
│  [YouTube URL] | [📝 Manuelles Transkript]                  │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  QUELLEN-INFORMATIONEN                                      │
│  ┌─────────────────────────────────────────────────────────┐
│  │ Titel: [________________________________]               │
│  │ Autor/Kanal: [________________________________]         │
│  │ URL (optional): [________________________________]      │
│  │ Dauer (optional): [__:__:__]                            │
│  └─────────────────────────────────────────────────────────┘
│                                                             │
│  TRANSKRIPT                                                 │
│  ┌─────────────────────────────────────────────────────────┐
│  │                                                         │
│  │  (Großes Textfeld, ~10-15 Zeilen sichtbar)             │
│  │                                                         │
│  │                                                         │
│  │                                                         │
│  └─────────────────────────────────────────────────────────┘
│  Zeichen: 0 | Wörter: 0 | Geschätzte Lesezeit: 0 Min.      │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Prompt-Anpassung

Bei manuellem Transkript wird der Prompt erweitert:

```
QUELLE:
Titel: "{{ title }}" von {{ author }}
{% if url %}URL: {{ url }}{% endif %}

TRANSKRIPT:
"""
{{ transcript }}
"""

Analysiere das obige Transkript nach dem SOMAS-Schema...
```

### Implementierung

**Neue Datei: `src/gui/transcript_tab.py`** (optional, kann auch in main_window.py)

```python
class TranscriptInputWidget(QWidget):
    """Widget für manuelle Transkript-Eingabe."""
    
    # Signal wenn sich Daten ändern
    data_changed = pyqtSignal()
    
    def __init__(self):
        super().__init__()
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Quellen-Info
        info_group = QGroupBox("Quellen-Informationen")
        info_layout = QFormLayout(info_group)
        
        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("Titel der Quelle")
        info_layout.addRow("Titel:", self.title_edit)
        
        self.author_edit = QLineEdit()
        self.author_edit.setPlaceholderText("Autor, Kanal oder Sprecher")
        info_layout.addRow("Autor/Kanal:", self.author_edit)
        
        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("https://... (optional)")
        info_layout.addRow("URL:", self.url_edit)
        
        layout.addWidget(info_group)
        
        # Transkript
        transcript_label = QLabel("Transkript:")
        layout.addWidget(transcript_label)
        
        self.transcript_edit = QTextEdit()
        self.transcript_edit.setPlaceholderText("Transkript hier einfügen...")
        self.transcript_edit.setMinimumHeight(200)
        layout.addWidget(self.transcript_edit)
        
        # Statistik
        self.stats_label = QLabel("Zeichen: 0 | Wörter: 0")
        layout.addWidget(self.stats_label)
        
        # Statistik aktualisieren
        self.transcript_edit.textChanged.connect(self._update_stats)
    
    def _update_stats(self):
        text = self.transcript_edit.toPlainText()
        chars = len(text)
        words = len(text.split()) if text.strip() else 0
        reading_time = max(1, words // 200)  # ~200 Wörter/Minute
        self.stats_label.setText(f"Zeichen: {chars:,} | Wörter: {words:,} | ~{reading_time} Min. Lesezeit")
    
    def get_data(self) -> dict | None:
        """Gibt die eingegebenen Daten zurück oder None wenn unvollständig."""
        title = self.title_edit.text().strip()
        transcript = self.transcript_edit.toPlainText().strip()
        
        if not title or not transcript:
            return None
        
        return {
            "title": title,
            "author": self.author_edit.text().strip() or "Unbekannt",
            "url": self.url_edit.text().strip() or None,
            "transcript": transcript,
            "word_count": len(transcript.split())
        }
    
    def clear(self):
        """Setzt alle Felder zurück."""
        self.title_edit.clear()
        self.author_edit.clear()
        self.url_edit.clear()
        self.transcript_edit.clear()
```

**Änderungen in `main_window.py`:**

```python
from PyQt6.QtWidgets import QTabWidget

# In _setup_ui():
self.input_tabs = QTabWidget()

# Tab 1: YouTube URL (bestehend)
url_widget = QWidget()
# ... bestehende URL-Eingabe hier rein ...
self.input_tabs.addTab(url_widget, "YouTube URL")

# Tab 2: Manuelles Transkript
self.transcript_widget = TranscriptInputWidget()
self.input_tabs.addTab(self.transcript_widget, "📝 Manuelles Transkript")
```

**Änderungen in `prompt_builder.py`:**

```python
def build_prompt_from_transcript(
    title: str,
    author: str,
    transcript: str,
    config: SomasConfig,
    url: str | None = None,
    questions: str = ""
) -> str:
    """Generiert SOMAS-Prompt aus manuellem Transkript."""
    
    # Anderes Template oder Template-Variante
    template = load_template('somas_prompt_transcript.txt')
    
    return template.render(
        title=title,
        author=author,
        url=url,
        transcript=transcript,
        depth=config.depth,
        # ... weitere Parameter
    )
```

**Neues Template: `templates/somas_prompt_transcript.txt`**

```
Analysiere das folgende Transkript nach dem SOMAS-Schema (Source Overview Mapping And extraction Schema).

KONFIGURATION:
- Tiefe: {{ depth }} ({{ depth_description }})
- Abschnitte: FRAMING, KERNTHESE, ELABORATION, IMPLIKATION + 1 passendes Erweiterungsmodul
- Sprache: {{ language }}

MODUL-AUSWAHL:
Wähle das Erweiterungsmodul basierend auf dem Inhalt:
- KRITIK (bei werblichen/einseitigen Inhalten)
- OFFENE_FRAGEN (bei komplexen/unvollständigen Themen)
- ZITATE (bei Interviews mit starken O-Tönen)
- VERBINDUNGEN (bei Themen mit historischen Bezügen)

OUTPUT-FORMAT:
Erstelle genau 5 Absätze mit jeweils {{ sentences_per_section }} Sätzen.

### FRAMING
[Wer spricht, welches Format, welcher Kontext – {{ sentences_per_section }} Sätze]

### KERNTHESE
[Zentrale Aussage oder Position des Inhalts – {{ sentences_per_section }} Sätze]

### ELABORATION
[Vertiefung, Mechanismen, Belege oder Wendepunkte – {{ sentences_per_section }} Sätze]

### IMPLIKATION
[Fazit, Empfehlung, Zielgruppe, Bedeutung – {{ sentences_per_section }} Sätze]

### [GEWÄHLTES MODUL]
[Inhalt des gewählten Erweiterungsmoduls – {{ sentences_per_section }} Sätze]

QUELLE:
Titel: "{{ title }}" von {{ author }}
{% if url %}URL: {{ url }}{% endif %}

TRANSKRIPT:
"""
{{ transcript }}
"""
{% if questions %}
---
WICHTIG: Analysiere ZUERST das Transkript vollständig. Anschlussfragen werden NACH der Analyse bearbeitet:
{{ questions }}
{% endif %}
```

---

## 🔄 Zusammenspiel der Features

### Zeitbereich + YouTube URL
→ Standard-Fall, Prompt enthält time_range

### Zeitbereich + Manuelles Transkript
→ Zeitbereich-Felder werden **ausgeblendet** (ergibt keinen Sinn bei manuellem Text)

### Manuelles Transkript + Fragen
→ Funktioniert wie bei YouTube, Fragen werden angehängt

---

## 🚀 Implementierungsreihenfolge

### Phase 1: Zeitbereich (2-3 Stunden)
1. UI-Elemente hinzufügen (Checkbox, Start/Ende-Felder)
2. Validierung implementieren
3. Prompt-Builder anpassen
4. Testen

### Phase 2: Manuelles Transkript (3-4 Stunden)
1. TranscriptInputWidget erstellen
2. QTabWidget in main_window.py integrieren
3. Neues Prompt-Template erstellen
4. Prompt-Builder erweitern
5. Generate-Button Logik anpassen (welcher Tab aktiv?)
6. Testen

### Phase 3: Polish & Release
1. Edge Cases testen
2. README aktualisieren
3. Version bump → 0.4.0
4. Release Notes

---

## ✅ Akzeptanzkriterien

### Zeitbereich
- [ ] Checkbox aktiviert/deaktiviert die Eingabefelder
- [ ] MM:SS wird automatisch zu 00:MM:SS konvertiert
- [ ] Fehlermeldung wenn Start ≥ Ende
- [ ] Warnung wenn Ende > Videodauer
- [ ] Prompt enthält korrekten Zeitbereich-Text
- [ ] Kontext-Option ändert den Prompt-Text

### Manuelles Transkript
- [ ] Tab-Wechsel funktioniert
- [ ] Titel und Transkript sind Pflichtfelder
- [ ] Zeichenzähler aktualisiert sich live
- [ ] Prompt wird korrekt generiert
- [ ] API-Modus funktioniert auch mit manuellem Transkript
- [ ] Export (LinkedIn/Markdown) funktioniert

---

## ⚠️ Hinweise

1. **Zeitbereich nur bei YouTube-Tab:** Die Felder sollten im Transkript-Tab nicht erscheinen
2. **Preset-Kompatibilität:** Alle 4 Presets müssen mit beiden Eingabe-Methoden funktionieren
3. **Debug-Logging:** Auch manuelle Transkripte sollten geloggt werden (ohne das volle Transkript, nur Metadaten)
4. **Kein Breaking Change:** Bestehende Workflows dürfen nicht beeinträchtigt werden

---

*Erstellt: 2026-02-03 | Ziel-Release: Ende KW 06*
