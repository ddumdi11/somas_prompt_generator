# SOMAS Prompt Generator

> **S**ource **O**verview **M**apping **A**nd extraction **S**chema – Prompt Generator
>
> Eine Desktop-App zur automatischen Generierung von SOMAS-Analyse-Prompts für YouTube-Videos.

---

## 🎯 Projektziel

Diese App automatisiert den Workflow zur Erstellung strukturierter Quellenanalysen nach dem SOMAS-Schema (v0.5). Sie nimmt YouTube-URLs entgegen, extrahiert Metadaten und generiert fertige Prompts für LLM-basierte Analysen.

---

## ✨ Features

### Aktuell implementiert (v0.2)

- **YouTube-URL-Eingabe** – URL einfügen, Metadaten abrufen
- **Meta-Information-Anzeige** – Titel, Kanal, Dauer (editierbares Textfeld)
- **Fragen-Eingabe** – Optionale Anschlussfragen für die Analyse
- **Prompt-Generierung** – Fertiger SOMAS-Prompt zum Kopieren
- **4 Prompt-Presets:**
  - **Standard** – Ausgewogene Analyse (2.800 Zeichen, ~2 Min Lesezeit)
  - **LinkedIn** – Social-Media-optimiert (2.200 Zeichen, ~90 Sek)
  - **Minimal** – Blitz-Überblick (800 Zeichen, ~30 Sek)
  - **Academia** – Wissenschaftlich (3.000 Zeichen, ~2,5 Min)
- **Analyse-Ausgabe** – Großes Textfeld für das LLM-Ergebnis
- **Export-Formate:**
  - LinkedIn-optimiert (Unicode-Bold, Post-Header, •Aufzählungen)
  - Markdown (.md)

### Geplant (v0.3+)

- API-Integration (Gemini/Claude)
- PDF-Export
- Konfigurationsdialog
- Batch-Verarbeitung mehrerer URLs

---

## 🏗️ Architektur

```
somas_prompt_generator/
├── main.py                 # Entry point
├── requirements.txt        # Dependencies
├── README.md              # Diese Datei
├── CLAUDE.md              # Instruktionen für Claude Code
│
├── src/
│   ├── gui/
│   │   └── main_window.py      # Hauptfenster mit Preset-Dropdown
│   │
│   ├── core/
│   │   ├── youtube_client.py   # YouTube-Metadaten via yt-dlp
│   │   ├── prompt_builder.py   # SOMAS-Prompt + Preset-Handling
│   │   ├── linkedin_formatter.py # Unicode-Bold, Post-Formatierung
│   │   └── export.py           # Markdown-Export
│   │
│   └── config/
│       ├── defaults.py         # VideoInfo, SomasConfig
│       └── prompt_presets.json # 4 Preset-Konfigurationen
│
├── templates/
│   ├── somas_prompt.txt        # Basis-Prompt-Template
│   ├── somas_standard.txt      # Standard-Preset
│   ├── somas_linkedin.txt      # LinkedIn-Preset
│   ├── somas_minimal.txt       # Minimal-Preset
│   └── somas_academia.txt      # Academia-Preset
│
└── tests/                  # Test-Analyse-Beispiele (lokal)
```

---

## 🛠️ Tech Stack

| Komponente | Technologie | Begründung |
|------------|-------------|------------|
| **GUI** | PyQt6 | Konsistent mit anderen Projekten (VidScaler, DocReducter) |
| **YouTube** | `youtube-transcript-api` | Leichtgewichtig, direkter Transkript-Zugriff |
| **YouTube Metadaten** | `yt-dlp` | Robuste Metadaten-Extraktion (Titel, Dauer, Thumbnail) |
| **PDF Export** | `reportlab` | Später implementieren |
| **Markdown** | Built-in | Keine externe Abhängigkeit |

---

## 📋 Abhängigkeiten

```txt
PyQt6>=6.4.0
youtube-transcript-api>=0.6.0
yt-dlp>=2024.1.0
```

---

## 🚀 Installation & Start

```bash
# Repository klonen (oder Ordner erstellen)
cd C:\Users\diede\source\ClaudeProjekte\somas_prompt_generator

# Virtual Environment erstellen
python -m venv venv
venv\Scripts\activate  # Windows

# Dependencies installieren
pip install -r requirements.txt

# App starten
python main.py
```

---

## 📖 Nutzung

1. **YouTube-URL eingeben** → Feld oben
2. **"Get Meta-Information" klicken** → Metadaten erscheinen im editierbaren Feld
3. **Optional: Fragen eingeben** → Für Anschlussfragen nach der Analyse
4. **"Generate Prompt" klicken** → SOMAS-Prompt wird generiert
5. **Prompt kopieren** → In Gemini/Claude/Kilo-Code einfügen
6. **Analyse einfügen** → Ergebnis ins Textfeld kopieren
7. **Export** → LinkedIn / Markdown / PDF

---

## 🔧 Konfiguration (Defaults)

Die App startet mit folgenden SOMAS-Defaults:

```python
SOMAS_DEFAULTS = {
    "depth": "standard",           # 2 Sätze pro Abschnitt
    "modules": ["auto"],           # Automatische Modulwahl
    "language": "de",              # Deutsch
    "include_timestamps": False,   # Keine Zeitmarken
}
```

Änderungen erfolgen zunächst manuell im Code (`src/config/defaults.py`).

---

## 📝 LinkedIn-Formatierung

LinkedIn unterstützt nur eingeschränkte Formatierung:

| Element | LinkedIn-Syntax | Beispiel |
|---------|-----------------|----------|
| **Fett** | Unicode-Zeichen | 𝗙𝗿𝗮𝗺𝗶𝗻𝗴 |
| *Kursiv* | Unicode-Zeichen | 𝘒𝘦𝘳𝘯𝘵𝘩𝘦𝘴𝘦 |
| Aufzählung | • Bullet | • Punkt 1 |
| Zeilenumbruch | Doppelter Enter | ↵↵ |
| Emojis | Direkt | 🎯 📌 |

**Nicht unterstützt:** Markdown-Headers, Links mit Text, Code-Blöcke

---

## 📊 SOMAS-Schema (v0.5)

Die App implementiert das SOMAS-Schema mit 4 Basis-Abschnitten:

1. **FRAMING** – Wer spricht, Format, Kontext
2. **KERNTHESE** – Zentrale Aussage/Position
3. **ELABORATION** – Vertiefung, Belege, Details
4. **IMPLIKATION** – Fazit, Empfehlung, Bedeutung

Plus optionale Module: `[KRITIK]`, `[ZITATE]`, `[OFFENE_FRAGEN]`, etc.

Siehe: `SOMAS_v0.5.md` im Projekt-Root.

---

## 🧪 Testing

```bash
# Einzelner Test
python -m pytest tests/test_youtube_client.py -v

# Alle Tests
python -m pytest tests/ -v
```

---

## 📜 Changelog

| Version | Datum | Änderungen |
|---------|-------|------------|
| 0.2.0 | 2025-01-28 | Prompt-Presets (4 Varianten), LinkedIn-Export mit Post-Header |
| 0.1.0 | 2025-01-26 | Initial MVP – URL-Eingabe, Metadaten, Prompt-Generierung |

---

## 🔗 Verwandte Projekte

- **SOMAS Schema** – `SOMAS_v0.5.md` (Projekt-Root)
- **VidScalerSubtitleAdder** – PyQt6-basiertes Video-Tool
- **DocReducter** – PDF-Verarbeitungstool

---

## 📄 Lizenz

Privates Projekt – Thorsten Diederichs
