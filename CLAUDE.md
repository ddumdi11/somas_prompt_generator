# CLAUDE.md – Instruktionen für Claude Code

> Dieses Dokument enthält projektspezifische Anweisungen für die Entwicklung mit Claude Code.

---

## 🎯 Projektkontext

**Name:** SOMAS Prompt Generator  
**Zweck:** Desktop-App zur Generierung von SOMAS-Analyse-Prompts für YouTube-Videos  
**Sprache:** Python 3.11+  
**GUI-Framework:** PyQt6  
**Entwickler:** Thorsten Diederichs  

---

## 📁 Projektstruktur

```
somas_prompt_generator/
├── main.py                 # Entry point – startet die PyQt6-App
├── requirements.txt        # Dependencies
├── README.md              # Projekt-Dokumentation
├── CLAUDE.md              # Diese Datei
│
├── src/
│   ├── gui/                # PyQt6-Komponenten
│   │   ├── main_window.py      # QMainWindow mit allen Panels
│   │   ├── meta_panel.py       # Metadaten-Anzeige (QTextEdit, editierbar)
│   │   ├── prompt_panel.py     # Prompt-Ausgabe (QTextEdit, read-only)
│   │   └── result_panel.py     # Analyse-Ergebnis (QTextEdit mit Lock-Toggle)
│   │
│   ├── core/               # Business-Logik
│   │   ├── youtube_client.py   # Metadaten + Transkript via yt-dlp & youtube-transcript-api
│   │   ├── prompt_builder.py   # SOMAS-Prompt aus Template + Config
│   │   ├── linkedin_formatter.py # Unicode-Formatierung für LinkedIn
│   │   └── export.py           # Markdown & PDF Export
│   │
│   └── config/             # Konfiguration
│       ├── defaults.py         # SOMAS-Defaults (depth, modules, language)
│       └── somas_schema.py     # Schema-Definition als Python-Objekt
│
├── templates/
│   └── somas_prompt.txt        # Basis-Prompt-Template (Jinja2-Style)
│
└── tests/
    └── test_youtube_client.py
```

---

## 🔧 Entwicklungsrichtlinien

### Code-Stil

- **PEP 8** befolgen
- **Type Hints** verwenden (`def get_metadata(url: str) -> dict:`)
- **Docstrings** für alle öffentlichen Funktionen (Google-Style)
- **Deutsche Kommentare** sind OK, Code und Variablennamen auf Englisch

### GUI-Konventionen (PyQt6)

- Layouts: `QVBoxLayout`, `QHBoxLayout`, `QGridLayout`
- Widgets:
  - `QLineEdit` für URL-Eingabe
  - `QTextEdit` für mehrzeilige Felder (mit `setReadOnly()` bei Bedarf)
  - `QPushButton` für Aktionen
  - `QCheckBox` für Lock/Unlock-Toggle
- Signals/Slots: Verwende `@pyqtSlot` Decorator

### Fehlerbehandlung

- `try/except` um externe API-Aufrufe (YouTube)
- Benutzerfreundliche Fehlermeldungen in der GUI (`QMessageBox`)
- Logging für Debug-Zwecke (`logging` Modul)

---

## 📦 Dependencies

```txt
PyQt6>=6.4.0
youtube-transcript-api>=0.6.0
yt-dlp>=2024.1.0
```

**Installation:**
```bash
pip install -r requirements.txt
```

---

## 🎨 GUI-Layout (Mockup)

```
┌─────────────────────────────────────────────────────────────┐
│  SOMAS Prompt Generator                              [_][□][X]│
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  YouTube URL: [________________________________] [Get Meta] │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│  META-INFORMATIONEN                              [🔓 Edit]  │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Titel: Example Video Title                          │   │
│  │ Kanal: Channel Name                                 │   │
│  │ Dauer: 15:32                                        │   │
│  │ URL: https://youtube.com/...                        │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│  FRAGEN (optional):                                         │
│  ┌─────────────────────────────────────────────────────┐   │
│  │                                                     │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  [Generate Prompt]                                          │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│  GENERIERTER PROMPT                                [Copy]   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Analysiere das folgende YouTube-Video nach dem     │   │
│  │ SOMAS-Schema...                                    │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│  ANALYSE-ERGEBNIS                          [🔒 Lock] [Paste]│
│  ┌─────────────────────────────────────────────────────┐   │
│  │                                                     │   │
│  │                                                     │   │
│  │                                                     │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  [Export: LinkedIn] [Export: Markdown] [Export: PDF]        │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 📝 SOMAS-Prompt-Template

Das Template in `templates/somas_prompt.txt`:

```
Analysiere das folgende YouTube-Video nach dem SOMAS-Schema (Source Overview Mapping And extraction Schema).

KONFIGURATION:
- Tiefe: {{ depth }} ({{ depth_description }})
- Abschnitte: FRAMING, KERNTHESE, ELABORATION, IMPLIKATION + 1 passendes Erweiterungsmodul
- Sprache: {{ language }}
{% if time_range %}
- Zeitbereich: {{ time_range.start }} bis {{ time_range.end }}
{% endif %}

MODUL-AUSWAHL:
Wähle das Erweiterungsmodul basierend auf dem Inhalt:
- KRITIK (bei werblichen/einseitigen Inhalten)
- OFFENE_FRAGEN (bei komplexen/unvollständigen Themen)
- ZITATE (bei Interviews mit starken O-Tönen)
- VERBINDUNGEN (bei Themen mit historischen Bezügen)

OUTPUT-FORMAT:
Erstelle genau 5 Absätze mit jeweils {{ sentences_per_section }} Sätzen:

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
YouTube-Video: "{{ video_title }}" von {{ channel_name }}
URL: {{ video_url }}
{% if questions %}

---
ANSCHLUSSFRAGEN (nach der Analyse separat beantworten):
{{ questions }}
{% endif %}
```

---

## 🔄 Workflow

### 1. URL eingeben → Metadaten abrufen

```python
# youtube_client.py
def get_video_info(url: str) -> VideoInfo:
    """Holt Metadaten via yt-dlp."""
    ydl_opts = {'quiet': True, 'no_warnings': True}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
    return VideoInfo(
        title=info['title'],
        channel=info['uploader'],
        duration=info['duration'],
        url=url
    )
```

### 2. Prompt generieren

```python
# prompt_builder.py
def build_prompt(video_info: VideoInfo, config: SomasConfig, questions: str = "") -> str:
    """Generiert SOMAS-Prompt aus Template."""
    template = load_template('somas_prompt.txt')
    return template.render(
        video_title=video_info.title,
        channel_name=video_info.channel,
        video_url=video_info.url,
        depth=config.depth,
        depth_description=DEPTH_DESCRIPTIONS[config.depth],
        sentences_per_section=DEPTH_SENTENCES[config.depth],
        language=config.language,
        time_range=config.time_range,
        questions=questions
    )
```

### 3. LinkedIn-Formatierung

```python
# linkedin_formatter.py
UNICODE_BOLD = {
    'A': '𝗔', 'B': '𝗕', 'C': '𝗖', ...
}

def format_for_linkedin(text: str) -> str:
    """Konvertiert Markdown zu LinkedIn-kompatiblem Format."""
    # ### HEADING → 𝗛𝗘𝗔𝗗𝗜𝗡𝗚
    # **bold** → 𝗯𝗼𝗹𝗱
    # - item → • item
    pass
```

---

## ⚠️ Bekannte Einschränkungen

1. **YouTube Shorts** – Sehr kurze Videos (< 60s) haben oft kein ausreichendes Transkript
2. **Neue Videos** – Transkripte sind erst nach einigen Stunden verfügbar
3. **LinkedIn** – Keine echte Markdown-Unterstützung, nur Unicode-Workarounds

---

## 🧪 Test-URLs

Für Entwicklungstests:

```python
TEST_URLS = [
    # Standard-Video (lang genug für Standard-Analyse)
    "https://www.youtube.com/watch?v=2yVJffNplJc",  # Taylor Lorenz
    
    # Kürzeres Video
    "https://www.youtube.com/watch?v=MZWansUMeS8",  # Based Camp Collins
    
    # YouTube Short (für Kurzquellen-Handling)
    "https://www.youtube.com/shorts/8tYx3kJNnhI",  # Candace Owens Short
]
```

---

## 🚀 Entwicklungsschritte

### Phase 1: Grundgerüst (MVP)
- [ ] `main.py` – App-Start
- [ ] `main_window.py` – Basis-Layout
- [ ] `youtube_client.py` – Metadaten-Abruf
- [ ] `prompt_builder.py` – Einfache Prompt-Generierung
- [ ] Templates-Ordner mit `somas_prompt.txt`

### Phase 2: Vollständige GUI
- [ ] `meta_panel.py` – Editierbares Metadaten-Feld
- [ ] `prompt_panel.py` – Prompt-Anzeige mit Copy-Button
- [ ] `result_panel.py` – Ergebnis-Feld mit Lock-Toggle

### Phase 3: Export
- [ ] `linkedin_formatter.py` – Unicode-Konvertierung
- [ ] `export.py` – Markdown-Export
- [ ] PDF-Export (später)

### Phase 4: Erweiterungen
- [ ] API-Integration via Kilo-Code (Gemini/Claude – Modell wählbar)
- [ ] Konfigurationsdialog
- [ ] Batch-Modus

---

## 🤝 Entwicklungs-Setup (3er-Team)

| Rolle | Akteur | Aufgabe |
|-------|--------|---------|
| **Architekt/Berater** | Claude.ai | Planung, README/CLAUDE.md pflegen, Konzeption, Debugging-Support |
| **Programmierer** | Claude Code (VS Code) | Implementierung, Code schreiben, Tests ausführen |
| **Supervisor/PO** | Thorsten | Entscheidungen, manuelles Testing, Feedback, Richtung vorgeben |

**Kilo-Code** = API-Anbindung im fertigen Produkt (nicht Entwicklungstool)

---

## 📞 Kontakt / Fragen

Bei Unklarheiten: Frag nach! Lieber einmal zu viel als eine falsche Annahme treffen.

---

*Letzte Aktualisierung: 2025-01-26*
