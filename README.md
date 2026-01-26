# SOMAS Prompt Generator

> **S**ource **O**verview **M**apping **A**nd extraction **S**chema – Prompt Generator
>
> Eine Desktop-App zur automatischen Generierung von SOMAS-Analyse-Prompts für YouTube-Videos.

---

## 🎯 Projektziel

Diese App automatisiert den Workflow zur Erstellung strukturierter Quellenanalysen nach dem SOMAS-Schema (v0.5). Sie nimmt YouTube-URLs entgegen, extrahiert Metadaten und generiert fertige Prompts für LLM-basierte Analysen.

---

## ✨ Features

### MVP (v0.1)

- **YouTube-URL-Eingabe** – URL einfügen, Metadaten abrufen
- **Meta-Information-Anzeige** – Titel, Kanal, Dauer, Thumbnail (editierbares Textfeld)
- **Fragen-Eingabe** – Optionale Anschlussfragen für die Analyse
- **Prompt-Generierung** – Fertiger SOMAS-Prompt zum Kopieren
- **Analyse-Ausgabe** – Großes Textfeld für das LLM-Ergebnis (mit Lock/Unlock)
- **Export-Formate:**
  - LinkedIn-optimiert (Unicode-Formatierung: **fett**, •Aufzählungen)
  - Markdown (.md)
  - PDF (.pdf) – später

### Geplant (v0.2+)

- API-Integration (Gemini/Claude via Kilo-Code)
- Konfigurierbare SOMAS-Parameter (depth, modules, time_range)
- Batch-Verarbeitung mehrerer URLs
- Englisch-Support

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
│   ├── __init__.py
│   ├── gui/
│   │   ├── __init__.py
│   │   ├── main_window.py      # Hauptfenster (PyQt6)
│   │   ├── meta_panel.py       # Metadaten-Anzeige
│   │   ├── prompt_panel.py     # Prompt-Generierung
│   │   └── result_panel.py     # Analyse-Ergebnis
│   │
│   ├── core/
│   │   ├── __init__.py
│   │   ├── youtube_client.py   # YouTube-Metadaten & Transkript
│   │   ├── prompt_builder.py   # SOMAS-Prompt-Konstruktion
│   │   ├── linkedin_formatter.py # LinkedIn-Formatierung
│   │   └── export.py           # MD/PDF-Export
│   │
│   └── config/
│       ├── __init__.py
│       ├── defaults.py         # Default-Konfiguration
│       └── somas_schema.py     # SOMAS v0.5 Schema-Definition
│
├── templates/
│   └── somas_prompt.txt        # Basis-Prompt-Template
│
└── tests/
    └── test_youtube_client.py
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
| 0.1.0 | TBD | Initial MVP – URL-Eingabe, Metadaten, Prompt-Generierung |

---

## 🔗 Verwandte Projekte

- **SOMAS Schema** – `SOMAS_v0.5.md` (Projekt-Root)
- **VidScalerSubtitleAdder** – PyQt6-basiertes Video-Tool
- **DocReducter** – PDF-Verarbeitungstool

---

## 📄 Lizenz

Privates Projekt – Thorsten Diederichs
