# SOMAS Prompt Generator

> **S**ource **O**verview **M**apping **A**nd extraction **S**chema – Prompt Generator
>
> Eine Desktop-App zur automatischen Generierung und KI-gestützten Ausführung von SOMAS-Analyse-Prompts für YouTube-Videos und manuelle Transkripte.

---

## 🎯 Projektziel

Diese App automatisiert den Workflow zur Erstellung strukturierter Quellenanalysen nach dem SOMAS-Schema. Sie nimmt YouTube-URLs oder manuell eingefügte Transkripte entgegen, generiert fertige Prompts und kann diese direkt über integrierte KI-Modelle analysieren lassen.

---

## ✨ Features

### Aktuelle Version (v0.4.1)

- **Kompaktes UI** – Einklappbare Sektionen (Metadaten, Zeitbereich) mit kompakter Zusammenfassung
- **Transkript-Brücke** – YouTube-Transkripte automatisch im Transkript-Tab verfügbar, editierbar
- **Smarte Prompt-Einbettung** – Verfügbare Transkripte werden direkt in den Prompt eingebettet (Modelle ohne Web-Zugriff analysieren tatsächlichen Inhalt)
- **Dual-Input-Modus** – YouTube-URL oder manuelles Transkript (Tab-basiert)
- **YouTube-Integration** – URL einfügen, Metadaten automatisch abrufen
- **Zeitbereich-Analyse** – Nur einen bestimmten Abschnitt des Videos analysieren (MM:SS oder HH:MM:SS)
- **Manuelles Transkript** – Podcasts, Vorträge, Interviews – jede Textquelle analysierbar
- **Integrierte KI-Analyse** – Ein-Klick-Analyse über API:
  - **Perplexity AI** – Sonar, Sonar Pro, Deep Research
  - **OpenRouter** – 200+ Modelle (Claude, Gemini, GPT, Llama, DeepSeek...)
  - Suchbare Modell-Liste mit dynamischer Preisanzeige
- **5 Prompt-Presets:**
  - **Standard** – Ausgewogene Analyse (2.800 Zeichen, ~2 Min Lesezeit)
  - **LinkedIn** – Social-Media-optimiert (2.200 Zeichen, ~90 Sek)
  - **Minimal** – Blitz-Überblick (800 Zeichen, ~30 Sek)
  - **Academia** – Wissenschaftlich (3.000 Zeichen, ~2,5 Min)
  - **Research** – Umfassende Tiefenrecherche (unbegrenzt)
- **Export-Formate:**
  - LinkedIn-optimiert (Unicode-Bold, Post-Header, Aufzählungen)
  - Markdown (.md)
- **Debug-Logging** – Session-Tracking mit Versionsinformation

### Nächste Schritte

- **v0.5** – Modell-Bewertungssystem
- PDF-Export
- Batch-Verarbeitung

---

## 🏗️ Architektur

```text
somas_prompt_generator/
├── main.py                 # Entry point
├── requirements.txt        # Dependencies
├── README.md              # Diese Datei
├── CLAUDE.md              # Instruktionen für Claude Code
│
├── src/
│   ├── gui/
│   │   ├── main_window.py      # Hauptfenster mit Tabs, Presets, API-Controls
│   │   ├── model_selector.py   # FilterableModelSelector (OpenRouter)
│   │   ├── settings_dialog.py  # Einstellungsdialog (API-Keys)
│   │   └── transcript_widget.py # Transkript-Eingabewidget
│   │
│   ├── core/
│   │   ├── youtube_client.py   # YouTube-Metadaten via yt-dlp
│   │   ├── prompt_builder.py   # SOMAS-Prompt + Preset-Handling
│   │   ├── linkedin_formatter.py # Unicode-Bold, Post-Formatierung
│   │   ├── export.py           # Markdown-Export
│   │   ├── api_client.py       # API-Abstraktion (Provider-Routing)
│   │   ├── api_worker.py       # QThread-Worker für async API-Calls
│   │   ├── perplexity_client.py # Perplexity Sonar/Deep Research
│   │   ├── openrouter_client.py # OpenRouter (200+ Modelle)
│   │   └── debug_logger.py     # Debug-Logging
│   │
│   └── config/
│       ├── defaults.py         # VideoInfo, SomasConfig, TimeRange
│       ├── api_config.py       # API-Provider-Konfiguration
│       ├── prompt_presets.json  # 5 Preset-Konfigurationen
│       ├── api_providers.json   # Provider-Definitionen
│       └── user_preferences.json # Benutzereinstellungen
│
├── templates/
│   ├── somas_prompt.txt        # Basis-Prompt-Template (Jinja2)
│   ├── somas_prompt_transcript.txt # Transkript-Template
│   ├── somas_standard.txt      # Standard-Preset
│   ├── somas_linkedin.txt      # LinkedIn-Preset
│   ├── somas_minimal.txt       # Minimal-Preset
│   ├── somas_academia.txt      # Academia-Preset
│   └── somas_research.txt      # Research-Preset
│
├── docs/                   # GitHub Pages Landing Page
│   ├── index.html
│   ├── style.css
│   └── assets/
│
└── tests/                  # Test-Analyse-Beispiele
```

---

## 🛠️ Tech Stack

| Komponente | Technologie | Begründung |
| ------------ | ------------- | ------------ |
| **GUI** | PyQt6 | Konsistent mit anderen Projekten (VidScaler, DocReducter) |
| **YouTube** | `youtube-transcript-api` | Leichtgewichtig, direkter Transkript-Zugriff |
| **YouTube Metadaten** | `yt-dlp` | Robuste Metadaten-Extraktion (Titel, Dauer, Thumbnail) |
| **Templates** | `Jinja2` | Flexible Prompt-Generierung mit Conditionals |
| **API-Calls** | `requests` | HTTP-Kommunikation mit Perplexity/OpenRouter |
| **Key-Storage** | `keyring` | Sichere API-Key-Verwaltung (Windows Credential Manager) |
| **Markdown** | Built-in | Keine externe Abhängigkeit |

---

## 📋 Abhängigkeiten

```txt
PyQt6>=6.4.0
youtube-transcript-api>=1.0.0
yt-dlp>=2024.1.0
Jinja2>=3.1.0
requests>=2.31.0
keyring>=24.0.0
```

---

## 🚀 Installation & Start

```bash
# Repository klonen
git clone https://github.com/ddumdi11/somas_prompt_generator.git
cd somas_prompt_generator

# Virtual Environment erstellen
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # macOS/Linux

# Dependencies installieren
pip install -r requirements.txt

# App starten
python main.py
```

---

## 📖 Nutzung

### YouTube-Modus

1. **YouTube-URL eingeben** und "Get Meta" klicken
2. **Optional: Zeitbereich** aktivieren (Start/Ende im Format MM:SS oder HH:MM:SS)
3. **Preset wählen** (Standard, LinkedIn, Minimal, Academia, Research)
4. **"Generate Prompt" klicken** → SOMAS-Prompt wird generiert
5. **API-Automatik** → KI analysiert direkt (oder manuell kopieren)
6. **Export** → LinkedIn / Markdown

### Transkript-Modus

1. Auf **Tab "Transkript"** wechseln
2. **Titel, Autor** und **Transkript-Text** eingeben
3. **"Generate Prompt" klicken** → Analyse aus dem Transkript

### API-Integration

- API-Keys werden sicher im System-Keyring gespeichert
- Perplexity oder OpenRouter als Provider wählbar
- Modellauswahl mit Suchfeld und Preisanzeige

---

## 📝 LinkedIn-Formatierung

LinkedIn unterstützt nur eingeschränkte Formatierung:

| Element | LinkedIn-Syntax | Beispiel |
| --------- | ----------------- | ---------- |
| **Fett** | Unicode-Zeichen | 𝗙𝗿𝗮𝗺𝗶𝗻𝗴 |
| *Kursiv* | Unicode-Zeichen | 𝘒𝘦𝘳𝘯𝘵𝘩𝘦𝘴𝘦 |
| Aufzählung | Bullet | - Punkt 1 |
| Zeilenumbruch | Doppelter Enter | |
| Emojis | Direkt | 📌 |

**Nicht unterstützt:** Markdown-Headers, Links mit Text, Code-Blöcke

---

## 📊 SOMAS-Schema

Die App implementiert das SOMAS-Schema mit 4 Basis-Abschnitten:

1. **FRAMING** – Wer spricht, Format, Kontext
2. **KERNTHESE** – Zentrale Aussage/Position
3. **ELABORATION** – Vertiefung, Belege, Details
4. **IMPLIKATION** – Fazit, Empfehlung, Bedeutung

Plus automatisch gewähltes Modul: `[KRITIK]`, `[ZITATE]`, `[OFFENE_FRAGEN]`, `[VERBINDUNGEN]`

---

## 📜 Changelog

| Version | Datum | Änderungen |
| --------- | ------- | ------------ |
| 0.4.1 | 2026-02-07 | UI-Redesign (Collapsible Sections), Transkript-Brücke, Transkript-Einbettung in Prompts |
| 0.4.0 | 2026-02-03 | Zeitbereich-Analyse, Manuelles Transkript, Tab-basierte Eingabe, Landing Page v0.4.0 |
| 0.3.1 | 2026-01-31 | FilterableModelSelector, OpenRouter-Suchfeld mit Filtern |
| 0.3.0 | 2026-01-29 | API-Integration (Perplexity + OpenRouter), Debug-Logger, Research-Preset |
| 0.2.0 | 2025-01-28 | Prompt-Presets (4 Varianten), LinkedIn-Export mit Post-Header |
| 0.1.0 | 2025-01-26 | Initial MVP – URL-Eingabe, Metadaten, Prompt-Generierung |

---

## 🔗 Verwandte Projekte

- **VidScalerSubtitleAdder** – PyQt6-basiertes Video-Tool
- **DocReducter** – PDF-Verarbeitungstool

---

## 📄 Lizenz

MIT - Open Source – Thorsten Diederichs
