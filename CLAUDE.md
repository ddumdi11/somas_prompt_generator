# CLAUDE.md – Instruktionen für Claude Code

> Dieses Dokument enthält projektspezifische Anweisungen für die Entwicklung mit Claude Code.

---

## 🎯 Projektkontext

**Name:** SOMAS Prompt Generator
**Version:** 0.4.0
**Zweck:** Desktop-App zur Generierung und automatischen Ausführung von SOMAS-Analyse-Prompts für YouTube-Videos und manuelle Transkripte
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
│   │   ├── main_window.py      # QMainWindow mit Tabs, Preset-Dropdown, API-Controls
│   │   ├── model_selector.py   # FilterableModelSelector (OpenRouter-Modellauswahl)
│   │   ├── settings_dialog.py  # Einstellungsdialog (API-Keys)
│   │   └── transcript_widget.py # Manuelles Transkript-Eingabewidget
│   │
│   ├── core/               # Business-Logik
│   │   ├── youtube_client.py   # Metadaten via yt-dlp
│   │   ├── prompt_builder.py   # SOMAS-Prompt + Preset-Handling + Transkript-Builder
│   │   ├── linkedin_formatter.py # Unicode-Formatierung für LinkedIn
│   │   ├── export.py           # Markdown-Export
│   │   ├── api_client.py       # API-Abstraktion (Provider-Routing)
│   │   ├── api_worker.py       # QThread-Worker für async API-Calls
│   │   ├── perplexity_client.py # Perplexity Sonar/Deep Research
│   │   ├── openrouter_client.py # OpenRouter (200+ Modelle)
│   │   └── debug_logger.py     # Debug-Logging mit Version/Session-Info
│   │
│   └── config/             # Konfiguration
│       ├── defaults.py         # SOMAS-Defaults (VideoInfo, SomasConfig, TimeRange)
│       ├── api_config.py       # API-Provider-Konfiguration
│       ├── prompt_presets.json  # 5 Preset-Varianten
│       ├── api_providers.json   # Provider-Definitionen (Perplexity, OpenRouter)
│       └── user_preferences.json # Benutzereinstellungen
│
├── templates/
│   ├── somas_prompt.txt        # Basis-Prompt-Template (Jinja2)
│   ├── somas_prompt_transcript.txt # Transkript-spezifisches Template
│   ├── somas_standard.txt      # Standard-Preset (2.800 Zeichen)
│   ├── somas_linkedin.txt      # LinkedIn-Preset (2.200 Zeichen)
│   ├── somas_minimal.txt       # Minimal-Preset (800 Zeichen)
│   ├── somas_academia.txt      # Academia-Preset (3.000 Zeichen)
│   └── somas_research.txt      # Research-Preset (unbegrenzt)
│
├── docs/                   # GitHub Pages Landing Page
│   ├── index.html
│   ├── style.css
│   └── assets/
│
└── tests/                  # Test-Dateien (lokal)
    └── *.md                    # SOMAS-Analyse-Beispiele
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
  - `QTabWidget` für Eingabemodus-Wechsel (YouTube / Transkript)
  - `QLineEdit` für URL-Eingabe und Zeitbereich
  - `QTextEdit` für mehrzeilige Felder (mit `setReadOnly()` bei Bedarf)
  - `QPushButton` für Aktionen
  - `QCheckBox` für Toggles (Zeitbereich, API-Automatik, Kontext)
  - `QComboBox` für Preset- und Provider-Auswahl
- Signals/Slots: Verwende `@pyqtSlot` Decorator

### Fehlerbehandlung

- `try/except` um externe API-Aufrufe (YouTube, Perplexity, OpenRouter)
- Benutzerfreundliche Fehlermeldungen in der GUI (`QMessageBox`)
- Logging über `debug_logger.py` (`logging` Modul)

### State-Management

- `self.video_info_source` ("youtube" | "transcript") trackt die Metadaten-Herkunft
- Verhindert stale Metadata bei Tab-Wechsel
- `_update_generate_enabled()` zentralisiert die Button-State-Logik

---

## 📦 Dependencies

```txt
PyQt6>=6.4.0
youtube-transcript-api>=0.6.0
yt-dlp>=2024.1.0
Jinja2>=3.1.0
requests>=2.31.0
keyring>=24.0.0
```

**Installation:**
```bash
pip install -r requirements.txt
```

---

## 📝 SOMAS-Prompt-Template

Das Template in `templates/somas_prompt.txt` verwendet Jinja2 mit kontextabhängigem Zeitbereich-Rendering:

```
{% if time_range %}
{% if time_range.include_context %}
- Zeitbereich: Fokus auf {{ time_range.start }} bis {{ time_range.end }}
  (mit Gesamtkontext des Videos von {{ time_range.video_duration_formatted }})
{% else %}
- Zeitbereich: Nur {{ time_range.start }} bis {{ time_range.end }} analysieren
{% endif %}
{% endif %}
```

Für manuelles Transkript wird `templates/somas_prompt_transcript.txt` verwendet mit den Variablen `title`, `author`, `transcript` (+ Aliase `video_title`, `channel_name`, `video_url`).

---

## ⚠️ Bekannte Einschränkungen

1. **YouTube Shorts** – Sehr kurze Videos (< 60s) haben oft kein ausreichendes Transkript
2. **Neue Videos** – Transkripte sind erst nach einigen Stunden verfügbar
3. **LinkedIn** – Keine echte Markdown-Unterstützung, nur Unicode-Workarounds
4. **Window-Sizing** – Meta-Bereich erfordert ggf. Fenstervergrößerung (Design-Frage für spätere Releases)

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

### Phase 1: Grundgerüst (MVP) ✅

- [x] `main.py` – App-Start
- [x] `main_window.py` – Basis-Layout mit Preset-Dropdown
- [x] `youtube_client.py` – Metadaten-Abruf
- [x] `prompt_builder.py` – Prompt-Generierung mit Preset-Unterstützung
- [x] Templates-Ordner mit 5 Templates (Basis + 4 Presets)

### Phase 2: Vollständige GUI ✅

- [x] Meta-Eingabe – Editierbares Metadaten-Feld
- [x] Prompt-Anzeige – Mit Copy-Button
- [x] Ergebnis-Feld – Mit Paste-Button
- [x] Preset-Auswahl – Dropdown mit Beschreibung, Lesezeit, Zeichenlimit
- [x] 5 Presets (Standard, LinkedIn, Minimal, Academia, Research)

### Phase 3: Export ✅

- [x] `linkedin_formatter.py` – Unicode-Bold, Header-Entfernung, Post-Formatierung
- [x] `export.py` – Markdown-Export
- [ ] PDF-Export (später/optional)

### Phase 4: API-Integration ✅ (v0.3.0)

- [x] Perplexity AI (Sonar, Sonar Pro, Deep Research)
- [x] OpenRouter (200+ Modelle, dynamische Preisanzeige)
- [x] FilterableModelSelector mit Suchfeld und Filtern
- [x] API-Keys im System-Keyring (Windows Credential Manager)
- [x] Ein-Klick-Analyse (API-Automatik)
- [x] Debug-Logger mit Session-Tracking

### Phase 5: Präzise Analyse ✅ (v0.4.0)

- [x] Zeitbereich-Analyse (Start/Ende, Kontext-Option)
- [x] Manuelles Transkript (Podcasts, Vorträge, etc.)
- [x] Tab-basierte Eingabe (YouTube / Transkript)
- [x] video_info_source Tracking
- [x] Landing Page aktualisiert

### Phase 6: Geplant

- [ ] Konfigurationsdialog erweitern
- [ ] Batch-Modus
- [ ] Window-Sizing optimieren

---

## 🤝 Entwicklungs-Setup (3er-Team)

| Rolle | Akteur | Aufgabe |
|-------|--------|---------|
| **Architekt/Berater** | Claude.ai | Planung, README/CLAUDE.md pflegen, Konzeption, Debugging-Support |
| **Programmierer** | Claude Code (VS Code) | Implementierung, Code schreiben, Tests ausführen |
| **Supervisor/PO** | Thorsten | Entscheidungen, manuelles Testing, Feedback, Richtung vorgeben |

---

## 📞 Kontakt / Fragen

Bei Unklarheiten: Frag nach! Lieber einmal zu viel als eine falsche Annahme treffen.

---

*Letzte Aktualisierung: 2026-02-06*
