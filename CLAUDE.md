# CLAUDE.md – Instruktionen für Claude Code

> Dieses Dokument enthält projektspezifische Anweisungen für die Entwicklung mit Claude Code.

---

## 🎯 Projektkontext

**Name:** SOMAS Prompt Generator
**Version:** 0.14.1
**Zweck:** Desktop-App zur Generierung und automatischen Ausführung von SOMAS-Analyse-Prompts für YouTube-Videos und manuelle Transkripte
**Sprache:** Python 3.11+
**GUI-Framework:** PyQt6
**Entwickler:** Thorsten Diederichs

---

## 📁 Projektstruktur

```text
somas_prompt_generator/
├── main.py                 # Entry point – startet die PyQt6-App
├── requirements.txt        # Dependencies
├── README.md              # Projekt-Dokumentation
├── CLAUDE.md              # Diese Datei
│
├── src/
│   ├── gui/                # PyQt6-Komponenten
│   │   ├── main_window.py      # QMainWindow mit Tabs, Presets, API-Controls
│   │   ├── collapsible_section.py # Einklappbare UI-Sektionen
│   │   ├── model_selector.py   # FilterableModelSelector (OpenRouter-Modellauswahl)
│   │   ├── rating_widget.py    # Z-Skala Modell-Bewertung (-2 bis +2)
│   │   ├── channel_dialog.py   # Kanal-Bewertungsdialog (Fakten, Bias, Tags)
│   │   ├── settings_dialog.py  # Einstellungsdialog (API-Keys, CSV-Export)
│   │   ├── transcript_widget.py # Transkript-Eingabewidget
│   │   ├── batch_dialog.py     # Batch-Verarbeitung (2-5 URLs, non-modaler Dialog)
│   │   ├── prompt_edit_dialog.py # Prompt-Anpassungsdialog (System-Prompt + Modul)
│   │   ├── provider_model_picker.py # Provider+Modell-Auswahl (3× im Modellvergleich)
│   │   └── wordpress_dialog.py  # WordPress-Sende-Dialog (Intro/Analyse/Outro, Beitragsbild)
│   │
│   ├── core/               # Business-Logik
│   │   ├── youtube_client.py   # Metadaten via yt-dlp
│   │   ├── prompt_builder.py   # SOMAS-Prompt + Preset-Handling + Transkript-Builder
│   │   ├── ai_disclosure.py    # KI-Kennzeichnung (Art. 50 AI Act) — zentrale Quelle, 3 Formen
│   │   ├── linkedin_formatter.py # Unicode-Formatierung für LinkedIn
│   │   ├── export.py           # Markdown-Export
│   │   ├── api_client.py       # API-Abstraktion (Provider-Routing)
│   │   ├── api_worker.py       # QThread-Worker für async API-Calls
│   │   ├── perplexity_client.py # Perplexity Sonar/Deep Research
│   │   ├── openrouter_client.py # OpenRouter (200+ Modelle)
│   │   ├── anthropic_client.py # Anthropic API (Claude direkt, Messages API)
│   │   ├── openai_client.py    # OpenAI API (GPT/o-Series direkt)
│   │   ├── batch_item.py       # BatchItem/BatchConfig Datenmodelle
│   │   ├── batch_worker.py     # QThread-Worker für sequenzielle Batch-Verarbeitung
│   │   ├── batch_persistence.py # Crash-resistente Batch-Session-Persistenz (JSON)
│   │   ├── rating_store.py     # SQLite-Bewertungsspeicher (Schema-Versionierung, Kanal-DB)
│   │   ├── user_preset_store.py # Benutzerdefinierte Presets (JSON-CRUD)
│   │   ├── comparison_item.py  # ModelChoice/ComparisonConfig/ComparisonResult (Modellvergleich)
│   │   ├── comparison_worker.py # QThread-Worker: 2 Analysen + Synthese + Layout-Render
│   │   ├── verification_item.py # VerificationConfig/VerificationResult (Faktencheck Stufe 2)
│   │   ├── verification_worker.py # QThread-Worker: Behauptungen verifizieren (Verdikt + Quelle)
│   │   ├── factcheck_plus/     # Faktencheck Plus (v0.13.0) — Qt-frei, extrahierbar
│   │   │   ├── schemas.py          # JSON-Verträge S1/S2/S4/S5 + Wertemengen
│   │   │   ├── models.py           # RefinedClaim/ArgumentMapping/ResearchCard/ClaimVerdict
│   │   │   ├── prompts.py          # Prompt-Verträge (Nicht-Zuständigkeiten je Stufe)
│   │   │   ├── llm_stage.py        # Stufen-Mechanik: Retry, Extraktion (einzige Client-Naht)
│   │   │   ├── refiner.py          # S1: Atomisierung + Attributions-Split
│   │   │   ├── mapper.py           # S2: Rolle + Impact + Ratings
│   │   │   ├── policy_scorer.py    # S3: deterministische Auswahl (KEIN LLM)
│   │   │   ├── planner.py          # S4: Recherchekarten
│   │   │   ├── verifier.py         # S5: ein Call pro Claim
│   │   │   ├── verdict.py          # 8→4-Mapping + Leitplanken + Eigenbeleg-Riegel
│   │   │   └── aggregate.py        # Render-Kontext + Transparenz-Block
│   │   ├── factcheck_plus_item.py  # FactcheckPlusConfig/FactcheckPlusResult
│   │   ├── factcheck_plus_worker.py # QThread-Worker: orchestriert S1–S5 (Qt↔Package-Naht)
│   │   ├── debug_logger.py     # Debug-Logging mit Version/Session-Info
│   │   ├── wordpress_client.py # WordPress-REST-Client (Beitrag, Taxonomien, Media-Upload)
│   │   └── wordpress_worker.py # QThread-Worker für blockierende WordPress-Operationen
│   │
│   └── config/             # Konfiguration
│       ├── defaults.py         # SOMAS-Defaults (VideoInfo, SomasConfig, TimeRange)
│       ├── api_config.py       # API-Provider-Konfiguration
│       ├── prompt_presets.json  # 7 Preset-Varianten
│       ├── api_providers.json   # Provider-Definitionen (Perplexity, OpenRouter, Anthropic, OpenAI)
│       ├── user_presets.json    # Benutzerdefinierte Presets (Auto-Save)
│       └── user_preferences.json # Benutzereinstellungen
│
├── templates/
│   ├── somas_prompt.txt        # Basis-Prompt-Template (Jinja2)
│   ├── somas_prompt_transcript.txt # Transkript-Template (mit STT-Disclaimer)
│   ├── somas_standard.txt      # Standard-Preset (2.800 Zeichen)
│   ├── somas_linkedin.txt      # LinkedIn-Preset (2.200 Zeichen)
│   ├── somas_minimal.txt       # Minimal-Preset (800 Zeichen)
│   ├── somas_academia.txt      # Academia-Preset (3.000 Zeichen)
│   ├── somas_research.txt      # Research-Preset (unbegrenzt)
│   ├── somas_music.txt         # Musik-Preset (2.400 Zeichen, Songtext-Analyse)
│   ├── somas_songstruktur.txt  # Songstruktur-Preset (Formanalyse)
│   ├── somas_comparison.txt    # Modellvergleich-Layout (Jinja2-Dokumentlayout)
│   ├── somas_verification.txt  # Faktencheck-Verifikation-Abschnitt (Stufe 2)
│   └── somas_verification_plus.txt # Faktencheck Plus: Verdikte + Transparenz-Block
│
├── specs/                  # Entwicklungs-Spezifikationen
│   ├── API_INTEGRATION_SPEC.md
│   ├── api_providers.json
│   ├── SOMAS_v0.6.0_SPEC.md
│   ├── SOMAS_v0.9.0_SPEC_modellvergleich.md
│   └── SOMAS_v0.10.0_SPEC_faktencheck_verifikation.md
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

- `try/except` um externe API-Aufrufe (YouTube, Perplexity, OpenRouter, Anthropic, OpenAI)
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
youtube-transcript-api>=1.0.0
yt-dlp>=2024.1.0
Jinja2>=3.1.0
requests>=2.31.0
keyring>=24.0.0
anthropic>=0.40.0
openai>=1.50.0
```

**Installation:**
```bash
# Submodul mit klonen (oder nachträglich initialisieren)
git clone --recurse-submodules <repo-url>
# git submodule update --init --recursive   # falls ohne --recurse-submodules geklont

pip install -r requirements.txt

# Optional: YouTube-Intake-Core (opt-in, nur Core ohne [server]-Extra)
pip install ./external/youtube-intake-service
```

> **Submodul `external/youtube-intake-service`** (auf Tag gepinnt): der wiederverwendbare
> YouTube-Baustein. SOMAS importiert den **Core** in-process (`youtube_intake_core`,
> via `src/core/intake_adapter.py` → Router `resolve_video_info`), NIE den Server.
> Aktivierung über Settings-Toggle `use_intake_core` (Default aus); ohne Aktivierung/Install
> läuft der bisherige direkte Weg. Nach Pin-Wechsel Core neu installieren.

---

## 📝 SOMAS-Prompt-Template

Das Template in `templates/somas_prompt.txt` verwendet Jinja2 mit kontextabhängigem Zeitbereich-Rendering:

```jinja2
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
4. **Auto-Transkripte** – YouTube-STT ist bei Gesang/schnellem Sprechen unzuverlässig → Disclaimer im Prompt warnt KI-Modelle

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

### Phase 6: UI-Optimierung ✅ (v0.4.1)

- [x] Einklappbare Metadaten- und Zeitbereich-Sektionen (`CollapsibleSection`)
- [x] Transkript-Brücke: YouTube-Transkript automatisch in Transkript-Tab übernehmen
- [x] Tab-Umbenennung: "Manuelles Transkript" → "Transkript"

### Phase 7: Musik-Preset & Transkript-Qualität ✅ (v0.5.0)

- [x] Zeichenlimit-Kontrolle (Traffic-Light-Counter, Sandwich-Technik, Rework-Button)
- [x] Bewertungssystem (Modell-Sterne, Quellen-Daumen, SQLite-Speicherung)
- [x] Musik-Preset mit eigenem 4-Teil-Schema (Songtext-Analyse)
- [x] Transkript-Disclaimer (STT-Hinweis, geschlechtsneutrale Sprache, SOMAS-Unterdrückung)
- [x] Stale-State-Bugfix (Transkript/Ergebnis bei neuem Video zurücksetzen)

### Phase 7b: Bewertungs-Redesign & Songstruktur ✅ (v0.5.2)

- [x] Z-Skala (-2 bis +2) statt 1-5 Sterne (gegen Rating-Inflation)
- [x] Kanal-Bewertungsdialog (Faktenqualität, Argumentationsqualität, Bias-Spektrum, Modus-Tags, Notizen)
- [x] Separate `channels`-Tabelle mit Schema-Versionierung (automatische Migration v1→v2)
- [x] CSV Export/Import für Kanal-Bewertungen (UTF-8-sig BOM, Semikolon-Delimiter)
- [x] Kanal-Meta-Anzeige Toggle in Einstellungen
- [x] Songstruktur-Preset für musikalische Formanalyse (Web-Search erforderlich)

### Phase 8: SOMAS Schema-Erweiterung ✅ (v0.6.0)

- [x] Perspektive-Parameter (neutral/critical/empathic) mit UI-Dropdown und Preset-Defaults
- [x] Modulpool-Erweiterung 4→6 (SUBTEXT, FAKTENCHECK) in allen relevanten Templates
- [x] Modul-Statistik (DB-Schema v3, chosen_module Tracking, Regex-Extraktion)
- [x] Anti-Monotonie-Mechanismus (Lookback über letzte 3 Analysen, Variationshinweis)
- [x] README, CLAUDE.md, Landing Page aktualisiert
- [x] Spec dokumentiert (SOMAS_v0.6.0_SPEC.md)

### Phase 9: Batch & Direkte APIs ✅ (v0.7.0)

- [x] Batch-Verarbeitung: 2-5 YouTube-URLs sequenziell analysieren (non-modaler Dialog)
- [x] BatchItem/BatchConfig Datenmodelle, BatchWorker (QThread), Batch-Persistenz (JSON in %TEMP%)
- [x] Tab-basierte Ergebnisansicht mit integrierter Bewertung pro Video
- [x] Anthropic API direkt (Claude Opus 4.6, Sonnet 4.6, Haiku 4.5) via `anthropic` SDK
- [x] OpenAI API direkt (GPT-4o, GPT-4o mini, o3, o4-mini) via `openai` SDK
- [x] 4 Provider in api_providers.json (Perplexity, OpenRouter, Anthropic, OpenAI)

### Phase 10: Custom Prompt Editor ✅ (v0.8.0)

- [x] UserPresetStore mit JSON-Persistenz (user_presets.json, CRUD-Operationen)
- [x] PromptEditDialog: System-Prompt + Modul-Fixierung vor Generierung
- [x] prompt_builder: custom_system_prompt/custom_module als Prepend-Overrides
- [x] main_window: "Anpassen…"-Button, Auto-Save nach API-Analyse, Checkbox für User-Presets
- [x] Rechtsklick-Kontextmenü: Umbenennen/Löschen von User-Presets
- [x] Export-Branding: "Analyse · SOMAS" in LinkedIn- und Markdown-Export

### Phase 11: Modellvergleich ✅ (v0.9.0)

- [x] Datenmodelle ModelChoice/ComparisonConfig/ComparisonResult (`comparison_item.py`)
- [x] Client-Factory `create_client()` aus batch_worker nach `api_client.py` extrahiert
- [x] Thumbnail-Helfer (`build_thumbnail_urls`) + Synthese-Prompt (`build_synthesis_prompt`/`clean_synthesis_output`)
- [x] Deterministisches Jinja2-Layout `somas_comparison.txt` (YouTube + Transkript)
- [x] `ComparisonWorker` (QThread): Metadaten → Analyse A → Analyse B → Synthese → Render
- [x] YouTube-Transkript wird (wie Batch) eingebettet, wenn vorhanden (PO-Entscheidung)
- [x] Synthese-Fehler nicht fatal (Platzhalter + Warnung)
- [x] `ProviderModelPicker`-Widget (3× im Vergleichsbereich)
- [x] GUI: Toggle "Zwei Modell-Analysen vergleichen" + CollapsibleSection, Abbrechen, Fortschritt
- [x] Export ohne Header via `export.save_markdown()` → `exports/…_Modellvergleich.md`
- [x] Spec dokumentiert (SOMAS_v0.9.0_SPEC_modellvergleich.md)

### Phase 11b: Hotfix leerer Modell-Content ✅ (v0.9.1)

- [x] OpenRouter/Perplexity: `content == None` (HTTP 200) führte zu `len(None)`-Crash
  („object of type 'NoneType' has no len()") → jetzt sauberer `APIResponse(ERROR,
  "Modell lieferte leeren Inhalt (finish_reason=…)")` statt Absturz
- [x] `reasoning`-Fallback für Reasoning-Modelle; Leer-Guard auch in OpenAI/Anthropic
  (Anthropic filtert zusätzlich `None`-Text-Blocks)
- [x] Regressionstest `tests/test_empty_content.py` (None/reasoning/Whitespace/Normalfall/
  fehlende `message`) — grün
- [x] Versionskonstante + README-Changelog auf 0.9.1 (PR #38)

### Phase 12: Faktencheck-Verifikation ✅ (v0.10.0)

- [x] Stufe 1 (Dekonstruktion): FAKTENCHECK trennt Meinungen/Interpretationen/Behauptungen,
  relevanz-sortiert. `FAKTENCHECK_FORMAT`-Konstante + Injektion via `_apply_custom_overrides`
  (deckt alle Presets ab, Header bleibt exakt `### FAKTENCHECK`)
- [x] Parser `extract_claims_from_faktencheck` (zeilen- UND inline-nummeriert, robust gegen
  interne Zahlen), `cap_claims` (Top-N, Default 10, 0=unbegrenzt), `build_verification_prompt`
  (nur Behauptungen, Riegel gegen erfundene Quellen), `clean_verification_output`
- [x] Stufe 2 (Verifikation, optional): `verification_item.py`, `VerificationWorker`,
  `somas_verification.txt` (Verdikt + Quelle pro Behauptung, 4-stufige Skala)
- [x] GUI: Toggle + Verifikationsmodell-Picker + Max-Behauptungen-SpinBox + `:online`-Schalter
  (OpenRouter) + Web-Disclaimer; Auto-Anhang an die Analyse; Ausschluss mit Modellvergleich
- [x] Race-Fix (Quelle während Verifikation gesperrt) + CollapsibleSection-Stylesheet gescoped
- [x] Tests `tests/test_faktencheck_parser.py`; headless + real-web getestet
- [x] Spec dokumentiert (SOMAS_v0.10.0_SPEC_faktencheck_verifikation.md)

### Phase 12b: Faktencheck-Härtung & Fixes ✅ (v0.10.1)

- [x] Unabhängigkeits-Riegel im Verifikations-Prompt: das geprüfte Video zählt nicht als
  Beleg (nur externe Quellen); `source_hint` als verbotene Eigenquelle + gegen Prompt-
  Injection saniert
- [x] Perplexity-Modelle aktualisiert (`sonar-reasoning-pro`, `sonar-deep-research`)
- [x] `DEFAULT_MAX_TOKENS = 8192` zentral in allen 4 Clients (behebt OpenRouter-HTTP-402)
- [x] Zeichenlimit-Zeilen bei erzwungenem FAKTENCHECK entfernt (Regex), `:online`-Tooltip präzisiert
- [x] Einheitlicher Export-Kopf für Einzelanalyse (Titel + „Kanal, YT" + Thumbnail)
- [x] „Verifikation erneut versuchen"-Button: nur Stufe 2, Modellwechsel möglich, ersetzt Abschnitt
- [x] Tests `tests/test_export_header.py` + erweiterte Parser-Tests

### Phase 13: Reasoning-Leak-Härtung ✅ (v0.11.0)

Behebt einen realen Final-Answer-Leak (DeepSeek-V4-Pro, 2026-07-01): Modell kippte
sein Reasoning in den sichtbaren Content, fraß das Token-Budget, finale Analyse
wurde abgeschnitten. Spec: `SOMAS_v0.11.0_SPEC_reasoning_leak_haertung.md`.

- [x] Increment A · PR 1: OpenRouter `reasoning.exclude=true` (Reasoning bleibt intern,
  verunreinigt `content` nicht) — nur OpenRouter, andere Provider unangetastet
- [x] Increment A · PR 2: `finish_reason` durch `APIResponse` + alle 4 Clients (Anthropic
  `stop_reason`, `max_tokens`→`length`) + im Debug-Log persistiert
- [x] Increment A · PR 3: `finish_reason`-Gate — trunkierte Antwort (`length`/`max_tokens`/
  `truncated`) gilt nicht als gültige Analyse
- [x] Increment A · PR 4: FAKTENCHECK-Prompt-Widerspruch aufgelöst (`_apply_custom_overrides`:
  „Erzwinge X als 5. Abschnitt…") + Final-Only-Zaun (`FINAL_ONLY_FENCE`)
- [x] Increment B · PR 5 / B1: preamble-scoped Struktur-/Trunkierungs-Validator
  `validate_analysis_structure` → `ValidationResult{ok, reason}` (Start-Anker, Template-
  Echo-Guard, Header-Reihenfolge, FAKTENCHECK-Sub-Header, Trunkierungs-Heuristik)
- [x] Increment B · PR 5 / B2: Retry-Eskalation (1× sichtbarer Auto-Retry, dann offener
  „Modelllauf fehlgeschlagen" statt Scheinanalyse) + Abbrechen-Button für den Analyse-Call;
  Verifikation (Stufe 2) nur auf gültiger Analyse
- [x] Iran-Fixture + `tests/test_reasoning_leak_validator.py` (Leak/Trunkierung ungültig,
  Clean gültig, False-Positive-Guards)

### Phase 14: WordPress-Anbindung ✅ (v0.12.0)

Sendet eine SOMAS-Analyse als Beitrag an eine selbstgehostete WordPress-Seite über
die REST-API (`/wp-json/wp/v2/`). Desktop-App → kein CORS; HTTP Basic Auth mit
**Application Password**. Voraussetzungen: WP-User mit Veröffentlichungsrecht
(fürs Beitragsbild zusätzlich `upload_files`, also Autor/Admin) und ein gültiges
Application Password. **Wordfence-Hinweis:** Wordfence (o.ä. Security-Plugins)
können REST-/App-Password-Requests blocken → ggf. XML-RPC/REST bzw. Application
Passwords in Wordfence freigeben.

- [x] Basis (PR #43, Variante A): `wordpress_client.py` (Config/Keyring-Passwort,
  `markdown_to_html`, `resolve_terms`, `WordPressClient.post`, `publish_post`),
  `wordpress_worker.py` (QThread), `wordpress_dialog.py` (Intro/Analyse/Outro,
  Status/Kategorie/Tags, HTML-Vorschau). Passwort im OS-Keyring, Config in
  `user_preferences.json`.
- [x] Beitragsbild (featured image): YouTube-Thumbnail des Videos als **echtes
  Beitragsbild** (nicht inline). `WordPressClient.upload_media` (POST `/media`),
  `post(featured_media=…)`, `publish_post(featured_image_urls=[maxres,hq,sd],
  video_id=…)` mit Fallback-Kette; **nicht fatal** (scheitert Laden/Upload, wird
  der Text trotzdem gepostet + Warnung im Rückgabewert). Dialog-Checkbox
  „YouTube-Thumbnail als Beitragsbild verwenden" (aktiv bei Video, ausgeblendet im
  Transkript-Modus). Tests: `tests/test_wordpress_media.py`.
- [ ] Backlog: Media-Dedup (vorhandenes Thumbnail per Suche wiederverwenden statt
  bei jedem Senden neu hochzuladen → vermeidet Media-Dubletten).

### Phase 15: Zeitanker im Prompt ✅ (v0.12.1)

Behebt eine „Real-als-Fiktion"-Fehlrahmung: `deepseek/deepseek-v4-pro` (Cutoff ~2024)
stufte ein reales 2026-Nachrichtenvideo (Khamenei-Begräbnis) in der FRAMING als
„fiktives/dystopisches Szenario" ein, weil dem Prompt jeder Zeitbezug fehlte.

- [x] `_build_temporal_anchor(current_date, video_published=None)` + locale-sicheres
  `_format_german_date` (deutsche Monats-Map, kein `strftime("%B")`-Verlass) +
  `_prepend_temporal_anchor` — zentral vor `_apply_custom_overrides` in **beiden**
  Build-Pfaden (forget-proof, preset-/template-unabhängig)
- [x] Anti-Fiktions-Leitplanke mit „es sei denn, der Beitrag kennzeichnet sich SELBST
  … als Fiktion/Satire/Spekulation" (bewahrt echte Fiktion + Musikanalysen)
- [x] Tests `tests/test_temporal_anchor.py` (beide Pfade, alle 7 Presets, locale-sicher,
  Transkript ohne `video_published`, Koexistenz mit erzwungenem FAKTENCHECK)
- [ ] Follow-up: Veröffentlichungsdatum in den Anker (`video_published`) — braucht ein
  Upload-/Publish-Datum in `VideoInfo` (yt-dlp `upload_date`); für v1 weggelassen

### Phase 16: Faktencheck Stufe 1 – Basisfakt-Sortierung ✅ (Quick Win, kein Versions-Bump)

Behebt „prüfbar ≠ prüfwürdig" (Grundlage: `specs/FAKTENCHECK_THEORIE.md` §3): Leicht
prüfbare Basisfakten verdrängten tragende strittige Claims unter die Cap-Grenze.

- [x] `FAKTENCHECK_FORMAT`: Behauptungen nach argumentativem Gewicht/Recherchewert ordnen
  (nicht nach Prüfbarkeit) + Basisfakt-Suffix `[Basisfakt]` ans Listenende + Attributions-
  Hinweis; Meinungen/Interpretationen-Sortierregel unverändert
- [x] `FAKTENCHECK_NO_LIMIT_HINT` entschärft (Vollständigkeit nicht zulasten der Priorisierung)
- [x] `strip_basisfakt_marker` (tolerant, bracket-gebunden gegen False Positives) + `cap_claims`
  schließt Basisfakten aus (auch bei `0 = unbegrenzt`), zählen nicht in `total`;
  `extract_claims_from_faktencheck` unangetastet; Stufe 2 unberührt
- [x] Tests erweitert (`tests/test_faktencheck_parser.py`): Suffix/Toleranz/Cap-Ausschluss +
  Regression (ohne Suffix unverändert)

### Phase 17: Leer-Inhalt in den Retry-Pfad + Abbrechen-Fix ✅ (Robustheit, kein Versions-Bump)

Realtest 2026-07-12 (DeepSeek V4 Pro, 24k-Prompt): Leer-Inhalt (`finish_reason=length`,
Reasoning fraß das 8192-Budget) endete hart ohne Retry — Asymmetrie zur Trunkierung, die
seit v0.11.0 einen sichtbaren Ein-Retry bekommt.

- [x] Einheitlicher Leer-Inhalt-Marker in `api_client.py` (`EMPTY_CONTENT_ERROR_PREFIX`,
  `build_empty_content_error`, `is_empty_content_error`); alle 4 Clients nutzen ihn +
  setzen `finish_reason` und `http_status=200` auf der Leer-Inhalt-`APIResponse`
- [x] `main_window._on_api_error`: Leer-Inhalt → `_escalate_failed_analysis` (1× sichtbarer
  Auto-Retry, dann offener „Modelllauf fehlgeschlagen"; Fehlertext inkl. `finish_reason`
  bleibt als Grund erhalten) statt sofortigem QMessageBox
- [x] Abbrechen-Härtung: `_on_api_cancel` neutralisiert den Retry-Kontext vollständig
  (`_analysis_prompt=""`), `_escalate_failed_analysis` mit Guard `active_request_id != 0`
  → greift auch WÄHREND des Auto-Retrys; verspätete Antworten weiterhin per Request-ID
  verworfen. Diagnose: Cancel-Handler war korrekt verdrahtet — die eigentliche Lücke war,
  dass der Leer-Inhalt gar nicht erst in den (abbrechbaren) Retry-Pfad kam
- [x] `api_worker` loggt echten HTTP-Status (`response.http_status`, 200 bei Leer-Inhalt)
  statt pauschal 500
- [x] Tests: `tests/test_analysis_retry_cancel.py` (Leer-Inhalt-Retry, 2. Leer→offener
  Fehlschlag, Abbruch während Retry, Trunkierungs-Regression, harter Fehler ohne Retry) +
  Classifier/`http_status` in `tests/test_empty_content.py`
- [x] ~~Deferiert (Item 3, PO-Kosten-Tradeoff): OpenRouter-Reasoning-Budget deckeln~~
  → **umgesetzt in Phase 24 (v0.13.2)**. Recherche bestätigte den effort-/token-
  Vorbehalt: token-basiert (`max_tokens`) trägt nicht für alle Familien; gewählt
  wurde die `effort`-Variante (das reale Zielmodell DeepSeek V4 ist effort-gesteuert)

### Phase 18: Anthropic-Direktmodelle aktualisieren ✅ (v0.12.2)

- [x] `anthropic_client.MODELS` + `api_providers.json` (`anthropic`-Block) synchron auf 6
  Modelle: Fable 5, Opus 4.8, Sonnet 5, Sonnet 4.6 (Default), Opus 4.6, Haiku 4.5
  (4.6er bleiben als Kontinuität, PO-Wunsch); `default_model` = `claude-sonnet-4-6`
- [x] Konsistenztest `tests/test_model_lists_consistency.py` (IDs/Namen/Beschreibungen/
  Reihenfolge + Default beider Listen identisch) — schützt vor künftigem Drift
- [x] `APP_VERSION` → 0.12.2; „Unreleased"-Changelog (#52/#53) in 0.12.2 überführt +
  README-Features-Prosa entlagt (WordPress → „Seit v0.12.0", neuer „Aktuell (v0.12.2)")
- [ ] OpenRouter-Fallback-Slugs (`anthropic/claude-*` in `openrouter_client.FALLBACK_MODELS`
  + OpenRouter-Block in `api_providers.json`) bewusst NICHT geändert — nicht gegen die
  Live-Liste verifizierbar (Startprompt: keine geratenen Slugs); OpenRouter lädt dynamisch

### Phase 19: Perplexity in der Verifikation konkurrenzfähig ✅ (v0.12.3)

Sonar wich in der Verifikation öfter auf „nicht überprüfbar" aus, wo GPT-5.3-Codex
Belege fand und differenzierte. Zwei kleine Ursachen, beide behoben.

- [x] Teil A: `perplexity_client` setzt `web_search_options.search_context_size`
  (Attribut `self._search_context_size`, Default „high"; Perplexity-Default wäre „low")
  in **inhaltlichen** Calls; `validate_key` (Verbindungstest) bleibt schlank
- [x] Teil B: Verdikt-Leitplanke in `build_verification_prompt` — „Kern belegt, Detail
  offen → teilweise bestätigt" (Kern + offenes Detail benennen) statt pauschal „nicht
  überprüfbar"; bestehende Riegel + exakt 4 Verdikt-Werte unverändert
- [x] Tests: `tests/test_perplexity_search_context.py` (Payload „high", Verbindungstest
  ohne Parameter, Attribut steuerbar) + Leitplanken-Test in `tests/test_faktencheck_parser.py`
- [x] `APP_VERSION` → 0.12.3; README-Changelog + „Aktuell"-Spotlight
- [ ] Follow-up: `search_context_size` als vollwertige UI-Einstellung
  (`perplexity_search_context`, low/medium/high) — derzeit Default „high" fest,
  programmatisch überschreibbar
- [ ] Backlog (Startprompt): Claim-Atomisierung in Stufe 1 (gebündelte Behauptungen
  splitten) — tieferer Umbau, separat (Teil von Faktencheck Plus, v0.13.0)

### Phase 20: Faktencheck Plus PR 2 — ClaimRefiner (S1) + ArgumentMapper (S2) ✅ (kein Versions-Bump)

Die beiden LLM-Stufen, die den (seit PR 1 vorhandenen) PolicyScorer füttern.
Offline grün, alles gemockt — kein Netzwerk im Test.

- [x] `prompts.py`: Prompt-Verträge mit den **Nicht-Zuständigkeiten als expliziten
  Verbotssätzen** (Theorie §8.5) — Refiner bewertet weder Relevanz noch Wahrheit;
  Mapper wählt nicht aus und gewichtet nicht (kennt die Policy-Gewichte gar nicht,
  eigener Gegenprobe-Test). Kontext (Kernthese/Quelle) injection-saniert wie
  `source_hint`; stufenspezifische Kontextnote (S1 ordnet ein, S2 misst daran).
- [x] `refiner.py` (S1): Atomisierung, **Attributions-Split als Pflicht** (Gate 4
  des Scorers verlässt sich darauf), Normalisierung, Typisierung. ID-Konvention
  `c01` → `c01a`/`c01b` + `parent_id` hart validiert inkl. Vollständigkeit (kein
  Claim verschwindet still). Meinungen werden NICHT gefiltert — dafür ist Gate 1 da.
- [x] `mapper.py` (S2): Rolle + kontrafaktischer Impact + 0–5-Ratings; ID-Echo
  (Bijektion) wird VOR `join_claims` geprüft, damit der Bruch noch in den
  Reparatur-Retry läuft statt in einen nackten ValueError.
- [x] `llm_stage.py`: Schema-Validierung außerhalb des LLM, **1× Reparatur-Retry**
  mit konkreter Fehlermeldung, danach offener `StageError` (v0.11-Linie).
  Transport-/API-Fehler lösen bewusst KEINEN Reparatur-Retry aus. Einzige
  Kopplungsnaht des Packages zum SOMAS-Client (sonst weiter Qt- und importfrei).
- [x] Fixtures **eigenständig in `tests/fixtures/`** (kein Verweis auf das
  gitignorierte `notizen/`): IRGC (1 Claim → 4 Prüfeinheiten) und Katar-747
  (Flugdatum + Geschenk + Boeing-Zitat, letzteres nochmals attributions-gesplittet)
- [x] Tests `tests/test_claim_refiner_contract.py` + `tests/test_argument_mapper_contract.py`
  (57 Fälle) inkl. Kette S1→S2→S3 an beiden Referenzfällen
- [ ] Befund für PO/Architekt (Policy, nicht Code): Bei kleinem Budget wirken die
  Klassenkontingente als **Obergrenze** — bei Budget 2 verdrängt im IRGC-Fall der
  Subclaim `c01b` (priority 0.433) den Kernclaim „Kausalzurechnung" `c01d` (0.489),
  weil A nur `round(2 × 0.6) = 1` Platz bekommt. Zudem quantifiziert der Fall den
  bekannten `checkability`-Tuning-Kandidaten: `c01d` verliert ⅓ (kein `metric` —
  eine Kausalaussage hat keine), `c01a` sogar ⅔. Beides erst nach Realtests
  entscheiden (zusammen mit dem Gewichte-Tuning).

### Phase 21: Faktencheck Plus PR 3 — ResearchPlanner (S4) + Pro-Claim-Verifikation (S5) ✅ (kein Versions-Bump)

Die Recherche-Hälfte der Pipeline. Offline grün (gemockt); der E2E-Realtest braucht
die GUI aus PR 4.

- [x] `planner.py` (S4): eine Recherchekarte je selektiertem Claim, ein Call für alle.
  `research_questions` + `counter_hypotheses` dürfen NIE leer sein (Riegel gegen
  Bestätigungsfehler — „Ist das wahr?" ist kein Rechercheauftrag, Theorie §5.1).
  Pflichtfelder `canonical_targets` (direktes Prüfziel statt Suchbegriffen) und
  `language_hints` (Originalsprache + Transliteration) — anwesend Pflicht, leer erlaubt.
  Quellenhierarchie (§5.2) und verbotene Abkürzungen als Policy im Prompt.
- [x] `verifier.py` (S5): **ein Call PRO Claim** (das ist D6a) mit Rechercheauftrag,
  Scope-Check (§5.3) und den unverändert übernommenen Riegeln des Classic-Wegs.
  Einzelfehler nicht fatal (sichtbarer „Prüfung fehlgeschlagen"-Vermerk, Rest läuft);
  `should_cancel`/`on_progress` als Callbacks — PR 4 reicht Button/Fortschritt durch,
  ohne dass das Package Qt kennt.
- [x] `verdict.py`: interne 8-stufige Taxonomie (§6.3) → 4 UI-Verdikte, Vollständigkeit
  per Import-Assertion. Das Mapping ist verlustbehaftet (4 Werte → „nicht überprüfbar"),
  deshalb ist die Begründungszeile Pflicht und trägt den internen Grund. Leitplanken
  werden DURCHGESETZT (kein positives Teilverdikt ohne benannten Teilclaim + Quelle),
  nicht nur im Prompt erbeten. `UI_VERDICTS` bewusst gespiegelt statt importiert —
  Drift-Schutz per Konsistenztest gegen `prompt_builder.VERDICT_VALUES`.
- [x] `aggregate.py` + `templates/somas_verification_plus.txt`: Verdikt-Abschnitt,
  Basisfakt-Titelzeilen (PO §8.2) und Transparenz-Block (§8.7). Package baut nur
  Daten, Jinja2-Rendering bleibt beim Worker — wie beim Classic-Weg.
- [x] Tests: `test_verdict_mapping.py` (29), `test_research_planner_contract.py` (21),
  `test_verification_plus.py` (25). Gesamtsuite 214 grün.
- [x] Zwei Fehler, die erst der gerenderte Bericht zeigte: `trim_blocks` fraß den
  Umbruch nach der Quellenzeile (→ `join`-Filter); und ein gescheiterter Call wurde
  als „unbelegt — keine belastbare Evidenz gefunden" ausgegeben — sachlich falsch,
  es wurde nichts gesucht. Beides mit Regressionstest.
- [x] Review-Härtung (#59): **Unabhängigkeits-Riegel jetzt server-seitig** — `source_hint`
  wird gegen jede gemeldete Quelle geprüft (Video-ID, URL, Titelrest; fängt auch
  `youtu.be` vs. `youtube.com` und Tracking-Suffixe), Eigenbeleg → Reparatur-Retry.
  Bis dahin war der Riegel nur Prompt-Text — Widerspruch zur eigenen §6.3-Linie.
  Dazu: alle S1-Felder sanitisiert (`_claim_fields`), Prompt-Verdiktlisten aus
  `VERDICTS_REQUIRING_SOURCE/_SUBCLAIM` statt handgepflegt, `forbidden_shortcuts`
  deterministisch vom Code gesetzt statt vom Modell geechot (Theorie §8.4),
  Reparatur-Prompt fordert das Format der jeweiligen Stufe (Objekt vs. Array),
  `build_skipped_rows` meldet kaputte Zuordnungen statt still zu filtern.
- [ ] Offen für PR 4: E2E-Realtest an einem Fall (braucht GUI/Worker); Eskalationsroute
  für „unbelegt" bei nicht-leerem `canonical_targets` ist laut Spec spätere Ausbaustufe.
- [ ] Design-Spannung für PO: „unbelegt" hat in den 4 UI-Verdikten kein Zuhause
  (§5.1 unterscheidet es von „nicht überprüfbar"); lebt derzeit nur in der
  Begründungszeile. Sauber wäre ein 5. UI-Verdikt — berührt den Classic-Weg.

### Phase 22: Faktencheck Plus PR 4 — GUI, Worker, Release ✅ (v0.13.0)

Schließt Faktencheck Plus ab: Die fünf Stufen sind verdrahtet, sichtbar und
abbrechbar. Der Classic-Weg bleibt unverändert (Parallelbetrieb, Theorie §8.1).

- [x] `factcheck_plus_item.py`: `FactcheckPlusConfig` (zwei Modelle — Analyse für
  S1/S2/S4, Web für S5; Claims **ungekappt**, Budget statt Cap) + `FactcheckPlusResult`
- [x] `factcheck_plus_worker.py`: orchestriert S1–S5, ist die **Qt↔Package-Naht**
  (Fortschritt/Abbruch als Callbacks rein, Signale raus; Jinja2-Rendering hier,
  nicht im Package). `_TokenCountingClient` hüllt die Stufen für Debug-Log und
  Token-Summe, ohne dass das Package davon weiß.
- [x] GUI: Plus-Checkbox in der Verifikations-Sektion (erbt damit den Ausschluss
  mit dem Modellvergleich); die vorhandene SpinBox wechselt Label/Range/Wert
  zwischen Cap (0–100, 0=unbegrenzt) und Budget (1–50, Default 8) — **zwei
  getrennte Preference-Keys**, damit kein Wert den anderen überschreibt;
  Stufen-Fortschritt im Sektions-Header; `verify_plus_checkbox`/
  `verify_online_checkbox` während des Laufs gesperrt
- [x] `_verification_is_running()` zentralisiert den Race-Schutz über BEIDE Worker
  (Abbruch, Retry, Quellenwechsel) — die Bedingung war vorher pro Aufrufstelle
  dupliziert und hätte den Plus-Worker vergessen
- [x] `extract_core_thesis()` (prompt_builder): liefert S2 den Maßstab für
  `thesis_proximity` aus dem `### KERNTHESE`-Abschnitt; fehlt er, läuft Plus
  ohne Kontext weiter (kein harter Fehler)
- [x] **Befund aus dem Test:** Der Worker verifizierte in Refiner- statt in
  Auswahlrang-Reihenfolge → im Bericht stand der schwächste Claim oben, und ein
  Abbruch nach 2 von 8 hätte zwei beliebige statt der zwei wichtigsten geprüft.
  Behoben + eigener Regressionstest.
- [x] `APP_VERSION` → 0.13.0, README (Changelog + „Aktuell"-Spotlight), CLAUDE.md
- [x] Tests: `test_factcheck_plus_worker.py` (14), `test_factcheck_plus_gui.py` (19),
  `extract_core_thesis` in `test_faktencheck_parser.py`. Gesamtsuite 273 grün.
- [ ] PO-Realtest (Merge-Kriterium) — deckt zugleich den in PR 3 offenen E2E-Test ab
- [ ] Offen für den PO: „unbelegt" hat in den 4 UI-Verdikten kein Zuhause
  (§5.1 unterscheidet es von „nicht überprüfbar"); lebt derzeit nur in der
  Begründungszeile. Sauber wäre ein 5. UI-Verdikt — berührt den Classic-Weg.
- [ ] Backlog Plus: Crash-Recovery-Persistenz (analog Batch); Eskalationsroute für
  „unbelegt" bei nicht-leerem `canonical_targets` (Spec: spätere Ausbaustufe);
  die zwei Tuning-Kandidaten (checkability, Quoten-Semantik) nach Realtests

### Phase 23: Faktencheck Plus — Trunkierungs-Härtung der Stufen ✅ (v0.13.1)

PO-Realtest 2026-07-16 (Fable 5 UND Opus 4.8): Plus scheiterte bei einem
claim-reichen Video (21 Roh-Claims) in S1 mit „kein parsebares JSON-Array". Wahre
Ursache: **Trunkierung**, kein Formatfehler. Der S1-Output skaliert mit der
Claim-Zahl (jede Prüfeinheit echot `original_text` + `normalized_claim`), plus
Anthropic-Thinking gegen `max_tokens` (8192) → valides, aber mitten im String
abgeschnittenes JSON; der Reparatur-Retry lief mit demselben Budget deterministisch
erneut ins Limit. Die Debug-Logs bestätigten es (S1-Content 17k Zeichen, doppelt so
lang wie die 8,5k-Analyse; mid-JSON abgeschnitten).

- [x] Teil A · Trunkierungs-Gate in `llm_stage.run_json_stage`: `finish_reason`
  wird VOR der JSON-Extraktion geprüft; bei Trunkierung (`length`/`max_tokens`/
  `truncated`) sofort offener `StageError` mit ehrlicher Meldung, **kein**
  Reparatur-Retry (das gleiche Budget schnitte erneut ab). Gilt für alle Stufen
  S1/S2/S4/S5 — der Fix sitzt in der Stufen-Mechanik. Transport-/Leer-Inhalt-
  Verhalten unverändert (weiterhin kein Reparatur-Retry). Trunkierungs-Werte
  jetzt zentral in `api_client` (`TRUNCATION_FINISH_REASONS`/
  `is_truncated_finish_reason`); `main_window` delegiert dorthin (Drift-Schutz)
- [x] Teil B · `_TokenCountingClient` reicht `response.finish_reason` an
  `debug_logger.log_response` durch (Parameter existierte, wurde nicht bespielt) —
  genau diese Lücke hatte die Diagnose verschleppt (Log zeigte immer `""`)
- [x] Teil C · Ursachen-Fix: Stufen-Calls dürfen bis `STAGE_MAX_TOKENS = 16384`
  antworten. `send_prompt` aller 4 Clients um optionalen `max_tokens`-Parameter
  erweitert (Default weiter `DEFAULT_MAX_TOKENS` — kein Verhalten außerhalb von
  Plus geändert); `_TokenCountingClient` reicht ihn durch. Erhöhung NUR für
  Stufen-Calls (OpenRouter/Perplexity pre-authen gegen `max_tokens` → HTTP 402,
  v0.10.1); Teil A bleibt Sicherheitsnetz, falls 16384 dort ein 402 provoziert
- [x] Tests `tests/test_stage_truncation_gate.py`: Trunkierung → StageError +
  genau 1 Call (A); kaputtes JSON ohne Trunkierung → weiterhin 1 Reparatur-Retry;
  Transport-Fehler → kein Retry; `finish_reason` erreicht das Log (B);
  Stufen-Call setzt 16384, normaler Call weiter Default (C)
- [x] `APP_VERSION` → 0.13.1, README-Spotlight + „Seit v0.13.0"-Demotion
- [ ] NICHT in diesem PR (Folge-Kandidaten): Thinking für Struktur-Stufen
  deaktivieren (braucht Provider-Recherche, gleiche Klasse wie Phase-17-Item 3);
  S1-Schema verschlanken (`original_text`-Echo halbieren)

### Phase 24: Reasoning-Cap für OpenRouter-Stage-Calls ✅ (v0.13.2)

Setzt das in Phase 17 deferierte Item 3 um (Bedingung war: Recherche zuerst).
Realtest 2026-07-17 (DeepSeek V4 Pro via OpenRouter): S1 scheiterte **trotz**
`STAGE_MAX_TOKENS = 16384` — nicht die Output-Größe, sondern das (durch
`exclude: true` unsichtbare) Reasoning fraß ~14,7k von ~16,4k Tokens, nur ~1,6k
sichtbares JSON, mid-Objekt gekappt (`finish_reason=length`). Das Trunkierungs-Gate
aus v0.13.1 hat korrekt und ehrlich gemeldet — jetzt die Ursache adressiert.

- [x] Recherche (OpenRouter-`reasoning`-Doku, live): `effort` XOR `max_tokens`
  (nicht beide), `exclude` orthogonal kombinierbar. OpenRouter normalisiert
  zwischen effort und Budget; die **effort→Budget-Richtung ist dokumentiert**, die
  `max_tokens`→effort-Rückabbildung nur vage. **DeepSeek V4 ist auf OpenRouter
  effort-gesteuert** (belegt via Issue earendil-works/pi#4055: nutzt effort-Enum,
  `xhigh`→`max`). Fehlerverhalten bei Mismatch/Non-Reasoning-Modellen: **Doku-Lücke**
  (nicht explizit; offen als Risiko notiert — Sicherheitsnetz greift, s.u.)
- [x] Entscheidung: **`effort` statt `max_tokens`** (Startprompt gab die Wahl frei).
  Das reale Zielmodell ist effort-gesteuert → nativer Konsum statt vager
  Rückabbildung. `REASONING_CAP_EFFORT = "low"` (≈ 0.2 × max_tokens ≈ 3,3k für
  token-basierte Familien, über Anthropics 1024-Minimum); `"max"` gemieden
  (bekannter Mapping-Bug aus #4055)
- [x] `send_prompt` aller 4 Clients um `cap_reasoning: bool = False` erweitert; **nur
  `openrouter_client` wertet es aus** (`reasoning: {effort: "low", exclude: true}`),
  die anderen ignorieren es dokumentiert. `_TokenCountingClient` reicht durch,
  `run_json_stage` fordert `cap_reasoning=True` für alle Stage-Calls (S1/S2/S4/S5)
- [x] Normaler Analyse-Call bleibt **ungecappt** (Reasoning erwünscht; v0.11-Gate+
  Retry deckt Trunkierung); `STAGE_MAX_TOKENS` unverändert (16384); Trunkierungs-Gate
  (v0.13.1 Teil A) bleibt Sicherheitsnetz, falls ein Modell den Cap ignoriert
- [x] Nebeneffekt: Reasoning-Tokens werden berechnet → der Cap spart bei
  reasoning-lastigen Modellen direkt Geld (README-Changelog)
- [x] Tests `tests/test_reasoning_cap.py` (7): Stage-Call sendet Effort-Cap +
  `exclude`; normaler Call unverändert; Perplexity/OpenAI/Anthropic ignorieren das
  Flag (kein Payload-Feld, kein Fehler); `run_json_stage` fordert den Cap an.
  Gesamtsuite 297 grün
- [x] `APP_VERSION` → 0.13.2, README-Spotlight + „Seit v0.13.1"-Demotion
- [ ] Offene Risiken (Doku-Lücke, PO-Realtest = Merge-Kriterium): exaktes
  Reasoning-Budget für „low" bei DeepSeek V4 nicht garantiert (empirisch << 14,7k);
  Mismatch-/Non-Reasoning-Verhalten unspezifiziert — ein Fehler degradiert aber zu
  einem ehrlichen `StageError`, nicht zu stiller Korruption
- [ ] NICHT in diesem PR: Thinking-Steuerung für Anthropic direkt (eigene
  API-Semantik, separater PR nach Recherche)

### Phase 25: 32k-Stage-Budget für OpenRouter + Token-Split im Log ✅ (v0.13.3)

Realtest 2026-07-17 08:02 (DeepSeek V4 Pro via OpenRouter, v0.13.2): Der
Reasoning-Cap wurde korrekt gesendet (Verdrahtung geprüft), aber der **Upstream-
Host respektierte ihn nicht** — S1 verbrauchte erneut exakt das volle Budget
(tokens_total 18.348 ≈ ~1,96k Input + 16.384), davon ~11,4k Reasoning, nur ~4,6k
sichtbarer Content, `finish_reason=length`. Das in v0.13.2 als Doku-Lücke notierte
Risiko (Compliance = Glückssache bei wechselnden Hosts) ist damit empirisch
bestätigt. Das Gate (v0.13.1) hat korrekt gemeldet — jetzt braucht der Content mehr
Luft, unabhängig von Host-Kooperation.

- [x] Teil A · OpenRouter-Stage-Budget `STAGE_MAX_TOKENS_OPENROUTER = 32768`:
  greift für S1/S2/S4/S5, **wenn der Stufen-Client OpenRouter ist**
  (~21k Worst Case → ~11k Reserve). `STAGE_MAX_TOKENS = 16384` bleibt für alle
  anderen Provider. **Ort der Entscheidung:** die Qt↔Package-Naht
  (`_TokenCountingClient` prüft `PROVIDER_ID == "openrouter"` und hebt das Budget,
  reicht es wie bisher als `max_tokens` durch) — `llm_stage`/Package bleiben
  provider-agnostisch. Reasoning-Cap (v0.13.2) bleibt aktiv (schadet nie, spart bei
  kooperativen Hosts); Trunkierungs-Gate (v0.13.1) bleibt Sicherheitsnetz. Normaler
  Analyse-Call unverändert (`DEFAULT_MAX_TOKENS`). 402-Vorauth gegen 32768 bei
  DeepSeek-Preisen akzeptiert (PO); echtes 402 bliebe offener Fehler (v0.13.2-Linie)
- [x] Teil B · Token-Split im Debug-Log: `APIResponse` trägt jetzt
  `tokens_input`/`tokens_output`/`reasoning_tokens` (+ `token_log_dict()`-Helfer);
  alle 4 Clients füllen input/output aus dem `usage`-Objekt (Feldnamen live
  geprüft: OpenAI-kompatibel `prompt_tokens`/`completion_tokens`, Anthropic
  `input_tokens`/`output_tokens`), OpenRouter/OpenAI zusätzlich
  `completion_tokens_details.reasoning_tokens`. `log_response` persistiert
  `tokens_reasoning` (leer=`null`, wenn nicht geliefert). Alle 5 Log-Aufrufstellen
  mit echter Response (api/comparison/verification/factcheck_plus_worker) schreiben
  den Split; die Reasoning-Anteile mussten bisher per Zeichen-Arithmetik geschätzt
  werden
- [x] Tests `tests/test_stage_budget_and_tokens.py` (11): OpenRouter-Stage → 32768
  + Cap; Perplexity/Anthropic-Stage → 16384; normaler OpenRouter-Call → DEFAULT;
  Token-Split je Provider (inkl. reasoning_tokens); fehlendes `usage` → 0/None kein
  Crash; Log persistiert den Split. Gesamtsuite 308 grün
- [x] `APP_VERSION` → 0.13.3, README-Spotlight + „Seit v0.13.2"-Demotion
- [ ] NICHT in diesem PR: Entkopplung Stufen-/Analyse-Modell (struktureller
  Folge-PR, PO entscheidet nach mehr Modell-Daten); S1-Schema verschlanken;
  weitere Cap-Varianten (`effort: "minimal"` — gleiche Compliance-Lotterie)

### Phase 26: KI-Kennzeichnung in allen Output-Formen ✅ (v0.14.0)

Seit 2026-08-02 gilt Art. 50 EU AI Act (Transparenzpflichten). Rechtlich geprüft:
SOMAS-Beiträge fallen unter die **Ausnahme (Art. 50(4))** (menschliche Prüfung/
Kuration + redaktionelle Verantwortung) — die Kennzeichnung ist **freiwillige
Transparenz**, keine Pflichterfüllung. PO will sie trotzdem, in allen Output-Formen,
immer an. PO-Entscheidungen (final): Fuß-Platzierung überall · EU-Icon per Hotlink ·
eine Zeile Text überall.

- [x] Zentrales Modul `src/core/ai_disclosure.py` (eine Quelle der Wahrheit, drei
  Formen): `AI_DISCLOSURE_TEXT` (LinkedIn, nur Text), `AI_DISCLOSURE_MARKDOWN`
  (EU-`<img>` width=90 + `alt` + `**Label**`-Zeile), `AI_DISCLOSURE_HTML` (`<p>`-
  Block, Inline-Icon + `<strong>`). Alle drei teilen `_CORE` (Drift-Schutz). Kein
  GUI-Toggle (PO-Linie: Transparenz ist Standard). Docstring mit Rechtsgrundlage +
  Quellen (Art. 50, EU-Icon-Seite, „freiwillig — Ausnahme greift")
- [x] Auffindbarkeit: jede Einbaustelle trägt das grepbare Tag
  `# KI-Kennzeichnung (Art. 50 AI Act) — zentral in ai_disclosure.py` →
  `grep "Art. 50"` findet Modul + alle drei Integrationspunkte
- [x] LinkedIn (`linkedin_formatter.format_for_linkedin`): Textzeile als letzte
  Zeile (Fuß), NUR Text — kein `<img>`/keine URL (LinkedIn kann keine Icons im
  Text; nackte Bild-URL wäre Linkmüll)
- [x] Markdown (`export.py`): Fußblock mit `---`-Trenner. **Beide Pfade** explizit
  (kein gemeinsamer Chokepoint): `get_markdown_content` (Einzelanalyse) UND
  `save_markdown` (Modellvergleich); Konsistenztest sichert Gleichlauf.
  `sanitize_unicode_for_export` lässt den `<img>`-Tag intakt (getestet)
- [x] WordPress (`wordpress_client.assemble_content`): `AI_DISCLOSURE_HTML` am Fuß
  nach dem Outro — deckt Vorschau UND Senden ab (beide über `_assembled_markdown`).
  Der `<p>`-Block überlebt `markdown_to_html` (Roh-HTML durchgereicht, getestet)
- [x] Tests `tests/test_ai_disclosure.py` (9): LinkedIn nur Text; Markdown Einzel+
  Vergleich mit Icon+Text; WordPress hängt an + leeres Outro; Konsistenz aller drei
  Formen; Sanitize lässt `<img>` intakt; HTML überlebt Markdown-Konvertierung.
  Gesamtsuite 317 grün
- [x] `APP_VERSION` → 0.14.0, README-Spotlight + Feature-Absatz, CLAUDE.md
- [ ] NICHT in diesem PR: PDF-Export (erbt Kennzeichnung später über Markdown-Pfad);
  prozentuale Mensch/KI-Anteilsberechnung (bewusst verworfen); Icon lokal bündeln/
  WP-Mediathek (PO: Hotlink; bricht die EU-URL, bleibt der Text stehen)

### Phase 27: WordPress-Sende-Dialog — Sicherheits-Vorwahl „Privat" ✅ (v0.14.1)

PO-Realtest v0.14.0: Der Sende-Dialog „An Blog senden" öffnete den Status auf dem
in den Settings gespeicherten Default (`wordpress_default_status`, beim PO
„publish") → ein versehentlicher Klick hätte sofort öffentlich gepostet. PO-Linie:
grundsätzlich „Privat", damit erst auf der Blog-Seite geprüft und dort manuell
freigeschaltet wird.

- [x] `wordpress_dialog._build_options_group`: Status-Combo wird beim Öffnen fest
  auf `_SAFE_DEFAULT_STATUS = "private"` vorgewählt — unabhängig vom Settings-
  Default. Minimaler Eingriff (nur `wordpress_dialog.py`); der Settings-Regler
  „Default-Status" bleibt unangetastet (steuert nur nicht mehr die Vorwahl), alle
  Status bleiben im Dialog manuell wählbar (PO-Entscheidung: „Regler bleibt")
- [x] Tests `tests/test_wordpress_dialog_default_status.py` (3): Vorwahl „private"
  trotz gespeichertem „publish" bzw. „draft"; „publish" bleibt manuell wählbar.
  Gesamtsuite 320 grün
- [x] `APP_VERSION` → 0.14.1, README-Spotlight + „Seit v0.14.0"-Demotion, CLAUDE.md

### Backlog

- [ ] A4-Feinschliff: erzwungenes Modul aus der `MODUL-AUSWAHL`-Liste entfernen
  (generisches Entfernen würde Beschreibung anderer Module löschen; ggf. FAKTENCHECK-Sonderfall)
- [ ] FAKTENCHECK-Zweiteilung (getrennte Calls für eigenes Token-Budget) — nur bei Bedarf
- [ ] Docstring-Coverage auf ≥80 % (Test-Funktionen) — CodeRabbit-Gate, niedrige Priorität
- [ ] Wochentags-basierte Perspektive-Defaults (nach Recherche)
- [ ] Englisch-Support
- [ ] PDF-Export (auch für Modellvergleich)
- [ ] Crash-Recovery-Persistenz für Modellvergleich (analog Batch)
- [ ] N-Wege-Vergleich (mehr als zwei Analyse-Modelle)
- [ ] GitHub-Issue #6: `user_preferences.json` ins User-Datenverzeichnis verschieben
  (`%APPDATA%/somas_prompt_generator/`, appdirs) — Nutzerdatei liegt derzeit im Repo,
  wird bei Updates überschrieben; relevant spätestens bei Distribution/Installern
- [ ] GitHub-Issue #7: Synchrone HTTP-Calls im UI-Thread async machen
  (`_load_dynamic_models`, `_on_test_key` → QThread-Worker) — niedrige Priorität

---

## 🗒️ Zwischennotizen (`notizen/`)

Jeder Projekt-Chat pflegt **eine fortgeschriebene** Zwischennotiz (Versionszähler +
Änderungsvermerk) in `notizen/`. Vorlagen: `Vorlage_Zwischennotiz.md` (Einzelchats)
und `Vorlage_Projekt-Zwischennotiz_Hauptchat.md` (Hauptchat, konsolidiert den
Projektstand). Bei Chat-Abschluss wird die Notiz zur **Übergabenotiz** (Status
ABGESCHLOSSEN, Abschnitte 3/4 auflösen, Wiedereinstiegspunkt → „Übergabe an: …").

**Chat-Lebenszyklus:** Spezialisierte Chats werden abgeschlossen, sobald ihr Ziel
erreicht ist. Angestrebt: ein aktiver Hauptstrang (übergibt bei Bedarf an einen
Nachfolge-Chat) plus wenige aktive Nebenstränge.

---

## 🤝 Entwicklungs-Setup (3er-Team)

| Rolle | Akteur | Aufgabe |
| ------- | -------- | --------- |
| **Architekt/Berater** | Claude.ai | Planung, README/CLAUDE.md pflegen, Konzeption, Debugging-Support |
| **Programmierer** | Claude Code (VS Code) | Implementierung, Code schreiben, Tests ausführen |
| **Supervisor/PO** | Thorsten | Entscheidungen, manuelles Testing, Feedback, Richtung vorgeben |

---

## 📞 Kontakt / Fragen

Bei Unklarheiten: Frag nach! Lieber einmal zu viel als eine falsche Annahme treffen.

---

Letzte Aktualisierung: 2026-08-17 (v0.14.1)
