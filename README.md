# SOMAS Prompt Generator

> **S**ource **O**verview **M**apping **A**nd extraction **S**chema – Prompt Generator
>
> Eine Desktop-App zur automatischen Generierung und KI-gestützten Ausführung von SOMAS-Analyse-Prompts für YouTube-Videos und manuelle Transkripte.

---

## 🎯 Projektziel

Diese App automatisiert den Workflow zur Erstellung strukturierter Quellenanalysen nach dem SOMAS-Schema. Sie nimmt YouTube-URLs oder manuell eingefügte Transkripte entgegen, generiert fertige Prompts und kann diese direkt über integrierte KI-Modelle analysieren lassen.

---

## ✨ Features

### Aktuell (v0.8.0) — Custom Prompt Editor

- **Prompt-Anpassung** – System-Prompt und Modul vor der Generierung anpassen ("Anpassen…"-Button). Benutzerdefinierte Anweisungen werden dem Template vorangestellt
- **Modul-Fixierung** – Eines der 6 Module fest wählen (PFLICHT-MODUL), Anti-Monotonie wird automatisch unterdrückt
- **Benutzerdefinierte Presets** – Auto-Save nach API-Analyse, JSON-Persistenz, Umbenennen/Löschen per Rechtsklick
- **Export-Branding** – Titel in LinkedIn- und Markdown-Export: "Analyse · SOMAS"

### Seit v0.7.0

- **Batch-Verarbeitung** – 2-5 YouTube-URLs in einem Durchlauf analysieren. Non-modaler Dialog mit Fortschrittsanzeige, Tab-basierte Ergebnisansicht, integrierte Bewertung pro Video, Crash-resistente Persistenz (JSON in %TEMP%)
- **Anthropic API (direkt)** – Claude-Modelle ohne Umweg über OpenRouter: Opus 4.6, Sonnet 4.6, Haiku 4.5
- **OpenAI API (direkt)** – GPT-4o, GPT-4o mini, o3, o4-mini über die Chat Completions API
- **4 API-Provider** – Perplexity (Web-Search), OpenRouter (200+ Modelle), Anthropic (direkt), OpenAI (direkt)

### Seit v0.6.0

- **Perspektive-Parameter** – Drei Analysehaltungen: Neutral-Deskriptiv, Kritisch-Analytisch, Empathisch-Rekonstruktiv. Jedes Preset hat einen Default, jederzeit manuell überschreibbar via UI-Dropdown
- **6 Analyse-Module** – Modulpool von 4 auf 6 erweitert: SUBTEXT (implizite Botschaften dekodieren) und FAKTENCHECK (überprüfungsbedürftige Aussagen priorisieren)
- **Modul-Statistik** – Gewähltes Modul wird pro Analyse in SQLite gespeichert (Schema v3, automatische Migration)
- **Anti-Monotonie** – Erkennt wenn 3x hintereinander dasselbe Modul gewählt wurde und gibt dem Modell einen Variationshinweis

### Seit v0.5.2

- **Bewertungs-Redesign** – Z-Skala (-2 bis +2) statt 1-5 Sterne, separater Kanal-Bewertungsdialog mit Fakten-/Argumentationsqualität, Bias-Spektrum (10 Richtungen), Modus-Tags (11 Kategorien), Freitext-Notizen
- **Kanal-Datenbank** – Eigene `channels`-Tabelle mit Schema-Versionierung und automatischer Migration
- **CSV Export/Import** – Kanal-Bewertungen als CSV exportieren/importieren (UTF-8-sig für Excel)
- **Kanal-Meta-Anzeige** – Bekannte Kanäle zeigen ihr Profil in den Metadaten (Toggle in Einstellungen)
- **Songstruktur-Preset** – Neues Preset für musikalische Formanalyse (Songform, Arrangements, Dynamik)

### Seit v0.5.0

- **Musik-Preset** – Eigenes 4-Teil-Schema für Songtext-Analysen (KONTEXT → SONGTEXT-ANALYSE → EINORDNUNG → BEWERTUNG)
- **Zeichenlimit-Kontrolle** – Traffic-Light-Counter, Sandwich-Technik im Prompt, Rework-Button zum Kürzen
- **Transkript-Disclaimer** – Automatischer STT-Hinweis für maschinelle Transkripte, geschlechtsneutrale Sprache, SOMAS-Selbstreferenz-Unterdrückung

### Seit v0.4.1

- **Kompaktes UI** – Einklappbare Sektionen (Metadaten, Zeitbereich) mit kompakter Zusammenfassung
- **Transkript-Brücke** – YouTube-Transkripte automatisch im Transkript-Tab verfügbar, editierbar
- **Smarte Prompt-Einbettung** – Verfügbare Transkripte werden direkt in den Prompt eingebettet (Modelle ohne Web-Zugriff analysieren tatsächlichen Inhalt)
- **Dual-Input-Modus** – YouTube-URL oder manuelles Transkript (Tab-basiert)
- **YouTube-Integration** – URL einfügen, Metadaten automatisch abrufen
- **Zeitbereich-Analyse** – Nur einen bestimmten Abschnitt des Videos analysieren (MM:SS oder HH:MM:SS)
- **Manuelles Transkript** – Podcasts, Vorträge, Interviews – jede Textquelle analysierbar
- **Integrierte KI-Analyse** – Ein-Klick-Analyse über API:
  - **Perplexity AI** – Sonar, Sonar Pro, Sonar Reasoning (Web-Search)
  - **OpenRouter** – 200+ Modelle (Claude, Gemini, GPT, Llama, DeepSeek...)
  - **Anthropic** – Claude direkt (Opus 4.6, Sonnet 4.6, Haiku 4.5)
  - **OpenAI** – GPT-4o, GPT-4o mini, o3, o4-mini direkt
  - Suchbare Modell-Liste mit dynamischer Preisanzeige
- **7 Prompt-Presets:**
  - **Standard** – Ausgewogene Analyse (2.800 Zeichen, ~2 Min Lesezeit)
  - **LinkedIn** – Social-Media-optimiert (2.200 Zeichen, ~90 Sek)
  - **Minimal** – Blitz-Überblick (800 Zeichen, ~30 Sek)
  - **Academia** – Wissenschaftlich (3.000 Zeichen, ~2,5 Min)
  - **Research** – Umfassende Tiefenrecherche (unbegrenzt)
  - **Musik** – Songtext-Analyse (2.400 Zeichen, ~75 Sek)
  - **Songstruktur** – Musikalische Formanalyse (Web-Search erforderlich)
- **Export-Formate:**
  - LinkedIn-optimiert (Unicode-Bold, Post-Header, Aufzählungen)
  - Markdown (.md)
- **Debug-Logging** – Session-Tracking mit Versionsinformation

### Nächste Schritte

- Wochentags-basierte Perspektive-Defaults (nach Recherche)
- Englisch-Support
- PDF-Export

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
│   │   ├── collapsible_section.py # Einklappbare UI-Sektionen
│   │   ├── model_selector.py   # FilterableModelSelector (OpenRouter)
│   │   ├── rating_widget.py    # Z-Skala Modell-Bewertung (-2 bis +2)
│   │   ├── channel_dialog.py   # Kanal-Bewertungsdialog (Fakten, Bias, Tags)
│   │   ├── settings_dialog.py  # Einstellungsdialog (API-Keys, CSV-Export)
│   │   ├── transcript_widget.py # Transkript-Eingabewidget
│   │   ├── batch_dialog.py     # Batch-Verarbeitung (2-5 URLs, non-modaler Dialog)
│   │   └── prompt_edit_dialog.py # Prompt-Anpassungsdialog (System-Prompt + Modul)
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
│   │   ├── anthropic_client.py # Anthropic API (Claude direkt)
│   │   ├── openai_client.py    # OpenAI API (GPT/o-Series direkt)
│   │   ├── batch_item.py       # BatchItem/BatchConfig Datenmodelle
│   │   ├── batch_worker.py     # QThread-Worker für Batch-Verarbeitung
│   │   ├── batch_persistence.py # Crash-resistente Batch-Persistenz (JSON)
│   │   ├── rating_store.py     # SQLite-Bewertungsspeicher (Schema-Versionierung, Kanal-DB)
│   │   ├── user_preset_store.py # Benutzerdefinierte Presets (JSON-Persistenz)
│   │   └── debug_logger.py     # Debug-Logging
│   │
│   └── config/
│       ├── defaults.py         # VideoInfo, SomasConfig, TimeRange
│       ├── api_config.py       # API-Provider-Konfiguration
│       ├── prompt_presets.json  # 7 Preset-Konfigurationen
│       ├── api_providers.json   # Provider-Definitionen
│       ├── user_presets.json    # Benutzerdefinierte Presets
│       └── user_preferences.json # Benutzereinstellungen
│
├── templates/
│   ├── somas_prompt.txt        # Basis-Prompt-Template (Jinja2)
│   ├── somas_prompt_transcript.txt # Transkript-Template (mit STT-Disclaimer)
│   ├── somas_standard.txt      # Standard-Preset
│   ├── somas_linkedin.txt      # LinkedIn-Preset
│   ├── somas_minimal.txt       # Minimal-Preset
│   ├── somas_academia.txt      # Academia-Preset
│   ├── somas_research.txt      # Research-Preset
│   ├── somas_music.txt         # Musik-Preset (Songtext-Analyse)
│   └── somas_songstruktur.txt  # Songstruktur-Preset (Formanalyse)
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
| **API-Calls** | `requests`, `anthropic`, `openai` | HTTP-Kommunikation mit Perplexity/OpenRouter + native SDKs für Anthropic/OpenAI |
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
anthropic>=0.40.0
openai>=1.50.0
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

### Batch-Modus

1. **"Batch" klicken** im Hauptfenster
2. **2-5 YouTube-URLs** einfügen (eine pro Zeile)
3. **Preset und Provider** wählen → Alle Videos werden sequenziell analysiert
4. **Ergebnisse** in Tabs anzeigen, einzeln bewerten und exportieren

### API-Integration

- API-Keys werden sicher im System-Keyring gespeichert
- 4 Provider wählbar: Perplexity, OpenRouter, Anthropic, OpenAI
- Modellauswahl mit Suchfeld und Preisanzeige (OpenRouter)

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

Die App implementiert das SOMAS-Framework mit Content-Type-spezifischen Analyse-Schemata:

### Standard-Schema (Vorträge, Interviews, Nachrichten)

1. **FRAMING** – Wer spricht, Format, Kontext
2. **KERNTHESE** – Zentrale Aussage/Position
3. **ELABORATION** – Vertiefung, Belege, Details
4. **IMPLIKATION** – Fazit, Empfehlung, Bedeutung
5. **[MODUL]** – Automatisch gewählt: Kritik · Zitate · Offene Fragen · Verbindungen · Subtext · Faktencheck

### Musik-Schema (Songtexte, Musikvideos)

1. **KONTEXT** – Künstler, Genre, Einordnung
2. **SONGTEXT-ANALYSE** – Thema, Erzählperspektive, sprachliche Mittel
3. **EINORDNUNG** – Genre-Vergleich, kulturelle Bezüge
4. **BEWERTUNG** – Stärken, Schwächen, Gesamteindruck

---

## 📜 Changelog

| Version | Datum | Änderungen |
| --------- | ------- | ------------ |
| 0.8.0 | 2026-03-30 | Custom Prompt Editor (System-Prompt + Modul anpassen), Benutzerdefinierte Presets (Auto-Save, Rename, Delete), Export-Branding "Analyse · SOMAS" |
| 0.7.0 | 2026-03-08 | Batch-Verarbeitung (2-5 URLs), Anthropic API direkt, OpenAI API direkt, 4 Provider |
| 0.6.0 | 2026-03-01 | Schema-Erweiterung: Perspektive-Parameter (3 Haltungen), Modulpool 4→6 (SUBTEXT, FAKTENCHECK), Modul-Statistik, Anti-Monotonie |
| 0.5.2 | 2026-02-20 | Bewertungs-Redesign (Z-Skala, Kanal-Dialog, CSV Export/Import, Meta-Toggle), Songstruktur-Preset |
| 0.5.0 | 2026-02-14 | Musik-Preset, Bewertungssystem (Sterne+Daumen), Zeichenlimit-Kontrolle (Counter, Sandwich, Rework), Transkript-Disclaimer, Stale-State-Fix |
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
