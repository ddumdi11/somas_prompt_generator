# CLAUDE.md – Instruktionen für Claude Code

> Dieses Dokument enthält projektspezifische Anweisungen für die Entwicklung mit Claude Code.

---

## 🎯 Projektkontext

**Name:** SOMAS Prompt Generator
**Version:** 0.12.1
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
│   └── somas_verification.txt  # Faktencheck-Verifikation-Abschnitt (Stufe 2)
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
- [ ] Deferiert (Item 3, PO-Kosten-Tradeoff): OpenRouter-Reasoning-Budget deckeln
  (`reasoning: {"max_tokens": 4096, "exclude": true}`) — würde die Ursache adressieren,
  aber `reasoning.max_tokens` wird nicht von allen Modellen gestützt (effort- vs.
  token-basiert); Risiko, andere Modelle zu stören → separater PR nach Recherche

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

Letzte Aktualisierung: 2026-07-12
