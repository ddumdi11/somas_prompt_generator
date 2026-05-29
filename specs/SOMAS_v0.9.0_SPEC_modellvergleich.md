# Feature: Modellvergleich – zwei SOMAS-Analysen + Synthese (v0.9.0)

> Branch: `feature/model-comparison-v090`
> Priorität: Hoch — nächste größere Funktionserweiterung nach Custom Prompt Editor (v0.8.0)
> Aufwand: Mittel-Hoch — neues Datenmodell, neuer Worker, neues Konfig-Widget, Jinja2-Layout-Template, Markdown-Export
> Abhängigkeit: v0.8.0 (Custom Prompt Editor, direkte Provider) abgeschlossen
> Ursprung: Manueller Workflow von Thorsten, prototypisiert mit Perplexity (GPT-5.4 Thinking);
> architektonisch eingeordnet durch Claude.ai (Cowork), freigegeben durch Thorsten (PO)

---

## Hintergrund

Thorsten erstellt aktuell **teilautomatisiert** Vergleichsdokumente: Er lässt dasselbe
YouTube-Video von zwei verschiedenen LLMs nach dem SOMAS-Schema analysieren, fasst die
beiden Analysen manuell zu einer Kurzbeschreibung zusammen und baut daraus ein
präsentationsfähiges Markdown-Dokument (inkl. Video-Thumbnail), das er anschließend über
einen Online-Markdown-zu-PDF-Konverter rendert. Zwei reale Beispiele liegen vor
(„Nick Fuentes…" / Jesse ON FIRE und „US-Iran Deal…" / The Daily Jagran).

Ziel dieser Erweiterung ist die **Vollautomatisierung** dieses Workflows innerhalb der App:
Ein Modus, der zu *einem* Video zwei Einzelanalysen mit zwei wählbaren Modellen fährt, ein
drittes Modell eine zusammenfassende Kurzbeschreibung erzeugen lässt und das fertige
Markdown-Dokument deterministisch zusammenbaut.

### Vom PO freigegebene Designentscheidungen

1. **Layout deterministisch:** Die App baut das Dokument via Jinja2-Template. Das
   Synthese-Modell liefert **ausschließlich** den Text der Kurzbeschreibung — kein
   Modell baut Layout/Struktur (Reproduzierbarkeit, kein Format-Glücksspiel).
2. **Provider-übergreifend:** Analyse-Modelle A/B und Synthese-Modell sind frei aus
   allen 4 Providern wählbar (Perplexity, OpenRouter, Anthropic, OpenAI).
3. **Synthese-Eingabe = beide vollständigen Analysen:** Das Synthese-Modell erhält die
   kompletten SOMAS-Texte von A und B (alle Module), **nicht** nur einzelne Abschnitte und
   **nicht** das Transkript. Begründung: Die Analysen sind bereits das verdichtete Produkt;
   das Transkript würde Tokens aufblähen, STT-Rauschen zurückbringen und das Modell zum
   Neu-Analysieren statt Zusammenfassen verleiten.
4. **Ausgabe nur Markdown:** v0.9.0 liefert sauberes Markdown. PDF-Erzeugung und
   Intro-/Post-Texte (z.B. LinkedIn) erstellt der PO nachgelagert selbst aus dem Markdown —
   kein App-seitiger PDF-Export in dieser Version (siehe Nicht-Ziele).

---

## Ziel-Ausgabe (Referenz-Layout)

Das erzeugte Markdown folgt exakt diesem Aufbau (aus den vorliegenden Beispielen abgeleitet):

```markdown
# {{ video_title }}
**{{ channel }}, YT**

![Thumbnail zum Video „{{ video_title }}"]({{ thumbnail_url }})

> Falls das Bild nicht angezeigt wird, diese Varianten testen:
> - {{ thumbnail_url_sd }}
> - {{ thumbnail_url_hq }}

## Modellvergleich – Zwei Analysen (SOMAS) eines YouTube-Videos

### Verwendete Modelle

- {{ model_a_provider }}: {{ model_a_name }}
- {{ model_b_provider }}: {{ model_b_name }}

## Kurzbeschreibung des Videos

{{ synthesis_summary }}

---

# Analyse · SOMAS: {{ video_title }}

**Kanal:** {{ channel }}
**Dauer:** {{ duration_formatted }}
**URL:** {{ url }}
**Modell:** {{ model_a_name }} ({{ model_a_provider }})

---

{{ analysis_a }}

---

# Analyse · SOMAS: {{ video_title }}

**Kanal:** {{ channel }}
**Dauer:** {{ duration_formatted }}
**URL:** {{ url }}
**Modell:** {{ model_b_name }} ({{ model_b_provider }})

---

{{ analysis_b }}

---

*Analyse · SOMAS · Synthese durch {{ synthesis_model_name }} ({{ synthesis_provider }})*
```

Bei Transkript-Modus (kein YouTube-Video) entfällt der Thumbnail-Block; statt `URL` wird
die optionale Quellenangabe verwendet bzw. weggelassen (siehe PR 3, Template-Konditionale).

---

## Übersicht der Änderungen

### A. UI: Toggle + aufklappbarer Konfigurationsbereich (im Hauptfenster)
Eine `QCheckBox` „Zwei Modell-Analysen vergleichen" blendet eine `CollapsibleSection`
„Modellvergleich" ein/aus. Darin: drei Provider-/Modell-Picker (A, B, Synthese).
Bei aktivem Toggle steuert der bestehende Analyse-Button den Vergleichslauf.

### B. Neues wiederverwendbares Widget `ProviderModelPicker`
Kombiniert Provider-Auswahl (`QComboBox` über alle 4 Provider) + Modellauswahl in einem
kompakten Widget. Wird 3× im Vergleichsbereich genutzt. Kapselt das bestehende
Provider→Modell-Mapping (statisch via `api_providers.json`, dynamisch für OpenRouter).

### C. Datenmodell `ComparisonConfig` / `ComparisonResult`
Neues Modul `src/core/comparison_item.py` analog zu `batch_item.py`.

### D. Worker `ComparisonWorker(QThread)`
Neues Modul `src/core/comparison_worker.py`. Führt **sequenziell** aus:
Metadaten → Analyse A → Analyse B → Synthese → Layout-Render. Sequenziell (nicht parallel),
um die bewährte Worker-Logik, Rate-Limits und Debug-Logging einfach zu halten; Parallelität
ist ausdrücklich Nicht-Ziel für v0.9.0 (siehe unten).

### E. Layout-Template + Synthese-Prompt
`templates/somas_comparison.txt` (Jinja2-Dokumentlayout) und ein dedizierter
Synthese-Prompt, der aus beiden Analysen **nur** die Kurzbeschreibung erzeugt.

### F. Thumbnail-Helfer
`youtube_client.extract_video_id()` existiert bereits; daraus werden die
`i.ytimg.com`-URLs gebaut. Kein Download nötig (Markdown bettet per URL ein).

### G. Export & Ergebnisanzeige
Das fertige Markdown wird im Ergebnisbereich angezeigt und über den bestehenden
Markdown-Export gespeichert (kein neuer Header durch `export.py` — das Dokument ist
bereits vollständig; siehe PR 6).

---

## Bestehende Schnittstellen (verifiziert, zur Wiederverwendung)

Diese Signaturen wurden im aktuellen Code verifiziert und sind die Basis der Implementierung:

```python
# src/config/defaults.py
@dataclass
class VideoInfo:
    title: str; channel: str; duration: int; url: str; transcript: str = ""
    @property
    def duration_formatted(self) -> str

@dataclass
class SomasConfig:
    depth: int = 2; language: str = "Deutsch"; time_range: Optional[TimeRange] = None

# src/core/youtube_client.py
def get_video_info(url: str) -> VideoInfo          # wirft ValueError bei Fehler
def extract_video_id(url: str) -> str              # bereits vorhanden, intern genutzt

# src/core/prompt_builder.py
def build_prompt(video_info, config, questions="", preset_name=None, perspective=None,
                 anti_monotony_hint="", custom_system_prompt=None, custom_module=None) -> str
def build_prompt_from_transcript(title, author, transcript, config, url=None, questions="",
                 preset_name=None, is_auto_transcript=False, perspective=None,
                 anti_monotony_hint="", custom_system_prompt=None, custom_module=None) -> str

# src/core/api_client.py
class LLMClient(ABC):
    def get_available_models(self) -> list[dict]
    def send_prompt(self, prompt: str, model: str) -> APIResponse
    def validate_key(self) -> bool

@dataclass
class APIResponse:
    status: APIStatus; content: str = ""; error_message: str = ""; model_used: str = ""
    provider_used: str = ""; tokens_used: int = 0; citations: list[str] = []
    duration_seconds: float = 0.0

# src/core/batch_worker.py  (Client-Factory — siehe PR 4: in api_client.py extrahieren)
def _create_client(provider_id: str, api_key: str) -> LLMClient

# src/config/api_config.py
def load_providers() -> dict[str, ProviderDefinition]
def get_api_key(provider_id: str) -> str           # OS-Keyring, nicht JSON
def get_last_provider() / get_last_model(provider_id)

# src/gui/model_selector.py
class FilterableModelSelector(QWidget):
    model_selected = pyqtSignal(str)
    def set_models(self, models: list[ModelData]) -> None
    def get_selected_model_id(self) -> str | None
    def get_selected_model_data(self) -> ModelData | None

# src/gui/collapsible_section.py
class CollapsibleSection(QWidget):
    toggled = pyqtSignal(bool)
    def __init__(self, title: str, parent=None)
    def set_content_widget(self, widget: QWidget) -> None
    def set_summary(self, text: str, color="#888888") -> None
    def expand() / collapse() / is_expanded()
```

---

## Implementierung

### PR 1: Datenmodell `comparison_item.py`

Neues Modul `src/core/comparison_item.py`:

```python
@dataclass
class ModelChoice:
    provider_id: str        # "openrouter" | "anthropic" | "openai" | "perplexity"
    model_id: str           # z.B. "deepseek/deepseek-chat-v3.2"
    model_name: str         # Anzeigename, z.B. "DeepSeek V3.2"
    provider_name: str      # Anzeigename, z.B. "OpenRouter"

@dataclass
class ComparisonConfig:
    input_mode: str                 # "youtube" | "transcript"
    url: str = ""                   # bei youtube
    # Transkript-Felder (bei input_mode == "transcript"):
    transcript_title: str = ""
    transcript_author: str = ""
    transcript_text: str = ""
    is_auto_transcript: bool = False
    # Gemeinsame SOMAS-Parameter (gelten für BEIDE Analysen identisch):
    preset_name: str = "standard"
    perspective: str = "neutral"
    depth: int = 2
    language: str = "Deutsch"
    questions: str = ""
    # Modellauswahl:
    model_a: ModelChoice = ...
    model_b: ModelChoice = ...
    model_synth: ModelChoice = ...
    def to_dict(self) -> dict        # API-Keys NICHT serialisieren
    @classmethod
    def from_dict(cls, data) -> "ComparisonConfig"

@dataclass
class ComparisonResult:
    config: ComparisonConfig
    status: str = "pending"          # pending|meta|analysis_a|analysis_b|synth|render|done|error
    video_info: Optional[VideoInfo] = None
    analysis_a_text: str = ""
    analysis_b_text: str = ""
    synthesis_summary: str = ""
    final_markdown: str = ""
    # Meta pro Schritt (Tokens/Dauer aus APIResponse):
    tokens_a: int = 0; tokens_b: int = 0; tokens_synth: int = 0
    error_message: str = ""
    error_step: str = ""             # "meta"|"a"|"b"|"synth"
```

**Hinweis:** SOMAS-Parameter (Preset, Perspektive, Tiefe) gelten bewusst für **beide**
Analysen identisch — variiert wird nur das Modell. Das hält den Vergleich fair (gleiche
Aufgabe, anderes Modell).

---

### PR 2: Thumbnail-Helfer + Synthese-Prompt

**Thumbnail (`src/core/comparison_worker.py` oder Helfer in `youtube_client.py`):**

```python
def build_thumbnail_urls(video_id: str) -> dict:
    base = f"https://i.ytimg.com/vi/{video_id}"
    return {
        "maxres": f"{base}/maxresdefault.jpg",
        "sd":     f"{base}/sddefault.jpg",
        "hq":     f"{base}/hqdefault.jpg",
    }
```

`video_id` via bestehendes `extract_video_id(url)`. Kein Download — die URL wird direkt
ins Markdown eingebettet (so auch in den Referenzbeispielen). `maxresdefault.jpg` als
Primär-URL, `sd`/`hq` als Fallback-Hinweis im Blockquote.

**Synthese-Prompt** (neuer Konstante in `prompt_builder.py`, z.B.
`build_synthesis_prompt(...)`):

> **Entscheidung (PO):** Eingabe sind die **vollständigen** Analysetexte A und B (alle
> Module), **ohne** Transkript. Das Modell gibt **nur** einen Fließtext (1 Absatz,
> ~4–6 Sätze) zurück — keine Überschriften, keine Aufzählungen, keine Modell-Meta.

Vorschlag:

```
Du erhältst zwei unabhängige SOMAS-Analysen DESSELBEN Videos, erstellt von zwei
verschiedenen KI-Modellen. Schreibe eine neutrale, zusammenfassende Kurzbeschreibung
des Videos in {{ language }} (ein zusammenhängender Absatz, 4–6 Sätze).

Regeln:
- Gib AUSSCHLIESSLICH den Absatz aus – keine Überschrift, keine Liste, keine Meta-Hinweise.
- Stütze dich nur auf die Inhalte beider Analysen; erfinde nichts hinzu.
- Wo sich die Analysen einig sind, formuliere bestätigend; wo sie abweichen, formuliere
  vorsichtig ("das Video legt nahe", "dargestellt wird").
- Neutraler, sachlicher Ton. Keine Wertung der Modelle.

VIDEO: {{ title }} – {{ channel }} ({{ duration_formatted }})

ANALYSE A ({{ model_a_name }}):
{{ analysis_a }}

ANALYSE B ({{ model_b_name }}):
{{ analysis_b }}
```

Robustheit: Ausgabe nachträglich säubern (führende Überschriften-Zeilen `#`,
umschließende Code-Fences entfernen), damit das Layout sauber bleibt.

---

### PR 3: Layout-Template `templates/somas_comparison.txt`

Jinja2-Template gemäß „Ziel-Ausgabe". Variablen:
`video_title, channel, duration_formatted, url, thumbnail_url, thumbnail_url_sd,
thumbnail_url_hq, model_a_name, model_a_provider, model_b_name, model_b_provider,
analysis_a, analysis_b, synthesis_summary, synthesis_model_name, synthesis_provider,
is_youtube` (bool).

Konditionale:
- `{% if is_youtube %}` → Thumbnail-Block + `**URL:**`-Zeile.
- `{% else %}` (Transkript) → kein Thumbnail; optionale Quellenangabe statt URL.

Rendering analog zur bestehenden Template-Nutzung in `prompt_builder.py` (Jinja2
`Environment`/`Template`). Unicode-Bereinigung für Export: bestehende
`export.sanitize_unicode_for_export()` auf das Endergebnis anwenden (NFC, problematische
Zeichen), Speicherung mit `utf-8-sig` (Pandoc-Kompatibilität) wie in `export.py`.

---

### PR 4: Client-Factory extrahieren (Refactor)

`_create_client(provider_id, api_key)` lebt aktuell privat in `batch_worker.py`. Für
Wiederverwendung durch `ComparisonWorker` nach `src/core/api_client.py` ziehen:

```python
# api_client.py
def create_client(provider_id: str, api_key: str) -> LLMClient: ...
```

`batch_worker.py` ruft künftig diese Funktion auf (kein Verhalten ändern, nur Ort).
Damit nutzen Batch- und Vergleichs-Worker dieselbe Factory.

---

### PR 5: `ComparisonWorker(QThread)`

Neues Modul `src/core/comparison_worker.py`:

```python
class ComparisonWorker(QThread):
    step_status_changed = pyqtSignal(str)        # "meta"|"a"|"b"|"synth"|"render"|"done"
    metadata_loaded     = pyqtSignal(object)     # VideoInfo
    analysis_completed  = pyqtSignal(str, str, object)  # step("a"|"b"), text, APIResponse
    synthesis_completed = pyqtSignal(str)        # summary
    comparison_finished = pyqtSignal(str)        # final_markdown
    error_occurred      = pyqtSignal(str, str)   # step, message

    def __init__(self, config: ComparisonConfig, rating_store=None,
                 debug_logger=None) -> None: ...

    def run(self) -> None:
        # 1) Clients bauen: create_client(provider, get_api_key(provider)) für A, B, Synth
        # 2) Metadaten:
        #    - youtube: video_info = get_video_info(url) -> metadata_loaded.emit
        #    - transcript: VideoInfo aus transcript_title/author/text konstruieren
        # 3) Analyse A: prompt_a = build_prompt(...) ODER build_prompt_from_transcript(...)
        #               client_a.send_prompt(prompt_a, model_a) -> analysis_completed("a", ...)
        # 4) Analyse B: analog mit model_b
        # 5) Synthese: synth_prompt aus A+B; client_synth.send_prompt(...) -> synthesis_completed
        #              Ausgabe säubern (Überschriften/Fences entfernen)
        # 6) Render: Jinja2 somas_comparison.txt -> final_markdown -> comparison_finished
    def cancel(self) -> None
```

**Prompt-Bau:** Bei `input_mode == "youtube"` → `build_prompt(video_info, SomasConfig(...),
preset_name=..., perspective=..., questions=...)`. Bei Transkript →
`build_prompt_from_transcript(...)`. Preset/Perspektive/Tiefe aus `config` (für A und B
identisch). Anti-Monotonie-Hinweis hier **nicht** anwenden (zwei verschiedene Modelle, eine
einzige Quelle — Variation kommt vom Modellwechsel).

**Fehlerstrategie:**
- Metadaten- oder Analyse-A/B-Fehler → Abbruch, `error_occurred(step, msg)`, kein Render.
- Synthese-Fehler → **nicht** abbrechen: Kurzbeschreibung durch Platzhalter ersetzen
  („_Automatische Kurzbeschreibung fehlgeschlagen — bitte manuell ergänzen._"),
  trotzdem `comparison_finished` mit beiden Analysen. Warnung in der GUI anzeigen.
- API-Keys vor Start prüfen (`validate_key()` bzw. vorhandener Key je Provider); fehlt
  einer → klare `QMessageBox`, kein Start.

**Persistenz:** Für v0.9.0 optional/Nice-to-have. Falls implementiert, analog
`batch_persistence.py` (JSON in `%TEMP%`), sonst bewusst weggelassen (nur 3 Schritte,
kurze Laufzeit). Als Backlog markieren, MVP ohne Crash-Recovery.

---

### PR 6: GUI-Integration `main_window.py` + `ProviderModelPicker`

**Neues Widget `src/gui/provider_model_picker.py`:**

```python
class ProviderModelPicker(QWidget):
    selection_changed = pyqtSignal()
    def __init__(self, label: str, providers: dict[str, ProviderDefinition], parent=None)
    def get_selection(self) -> ModelChoice | None   # None wenn nichts gewählt
    def set_selection(self, choice: ModelChoice) -> None
    def set_enabled(self, enabled: bool) -> None
```

Aufbau pro Picker: `QLabel(label)` + Provider-`QComboBox` (alle 4 Provider) + Modellauswahl.
Für OpenRouter den bestehenden `FilterableModelSelector` einbetten (dynamische Liste,
Such-/Free-Filter); für statische Provider eine einfache Modell-`QComboBox` aus
`api_providers.json`. Bei Provider-Wechsel passende Modellliste laden (gleiche Logik wie
im Hauptfenster, Zeilen ~1470–1496 — dort als Referenz/ggf. extrahierbar).

**Hauptfenster-Verdrahtung:**
1. `QCheckBox` „Zwei Modell-Analysen vergleichen" (`self.compare_checkbox`) nahe den
   bestehenden API-Controls anlegen.
2. `CollapsibleSection("Modellvergleich")` (`self.compare_section`) mit Inhalts-Widget,
   das drei `ProviderModelPicker` enthält: „Modell A (Analyse)", „Modell B (Analyse)",
   „Modell C (Zusammenfassung)". Section initial versteckt.
3. `compare_checkbox.toggled` → Section ein-/ausblenden (`setVisible`) und
   `compare_section.expand()`. Bei aktivem Toggle: Einzel-Modell-Auswahl + „API-Automatik"
   deaktivieren/ausgrauen (gegenseitiger Ausschluss), Analyse-Button-Label ggf. zu
   „Modellvergleich starten".
4. Analyse-Start-Slot (`_on_generate_prompt` / `_start_api_call`) erweitern: Wenn
   `compare_checkbox.isChecked()` → `ComparisonConfig` aus UI bauen, drei Picker-Selektionen
   validieren (alle gesetzt; A≠B empfohlen, sonst Hinweis), `ComparisonWorker` starten und
   Signals verbinden (siehe unten). Sonst unveränderter Einzelpfad.
5. Fortschritt: kompakter Status über `compare_section.set_summary(...)` aktualisieren
   (z.B. „Analyse A läuft… (Modell X)") + optional `QProgressBar`. Controls während des
   Laufs deaktivieren; „Abbrechen" ruft `worker.cancel()`.
6. `comparison_finished(markdown)` → Markdown in bestehenden Ergebnisbereich
   (`self.result_text`) schreiben; Button „Als Markdown exportieren" aktivieren.

**Slots (neu):**
```python
def _on_compare_toggled(self, checked: bool) -> None
def _start_comparison(self) -> None
def _on_compare_step(self, step: str) -> None
def _on_compare_meta(self, video_info) -> None
def _on_compare_analysis(self, step: str, text: str, response) -> None
def _on_compare_synth(self, summary: str) -> None
def _on_compare_finished(self, markdown: str) -> None
def _on_compare_error(self, step: str, message: str) -> None
```

---

### PR 7: Export der Vergleichs-Ausgabe

Das Vergleichs-Markdown ist bereits ein **vollständiges Dokument** (eigene Header,
Thumbnail, beide Analysen). Daher **nicht** durch `export_to_markdown()` mit dem
Standard-`# Analyse · SOMAS`-Header umschließen. Stattdessen:

- Neue schlanke Funktion `export.save_markdown(content: str, suggested_title: str,
  output_path: Optional[str]=None) -> str`, die nur `sanitize_unicode_for_export()` +
  `sanitize_filename()` anwendet und mit `utf-8-sig` speichert.
- Dateiname aus Videotitel, Suffix `_Modellvergleich`.
- In Cowork/Desktop: Datei im Arbeitsordner ablegen und dem Nutzer zugänglich machen.

Optionaler späterer Schritt (Backlog, nicht v0.9.0): PDF-Erzeugung aus diesem Markdown.

---

## Reihenfolge

1. **PR 1** Datenmodell `comparison_item.py`
2. **PR 4** Client-Factory `create_client()` extrahieren (klein, entkoppelt)
3. **PR 2** Thumbnail-Helfer + Synthese-Prompt
4. **PR 3** Layout-Template `somas_comparison.txt`
5. **PR 5** `ComparisonWorker`
6. **PR 6** GUI: `ProviderModelPicker` + Toggle/Section + Verdrahtung
7. **PR 7** Export

PRs 1–5 sind ohne GUI testbar (Worker-Lauf headless mit Dummy-/echten Keys). GUI (PR 6)
zuletzt, gegen den fertigen Worker.

---

## Verification (pro PR)

- **PR 1:** `to_dict()`/`from_dict()` Roundtrip; API-Keys nicht in dict.
- **PR 2:** Thumbnail-URLs korrekt aus diversen URL-Formen (`watch?v=`, `youtu.be/`,
  `/shorts/`); Synthese-Prompt enthält beide Analysen + Sprache.
- **PR 3:** Template rendert für YouTube **und** Transkript korrekt (Thumbnail-Block
  bedingt); Sonderzeichen/Umlaute sauber.
- **PR 4:** Bestehende Batch-Tests laufen unverändert (Factory nur verschoben).
- **PR 5:** End-to-end-Lauf mit echtem Video + zwei kostenlosen OpenRouter-Modellen +
  Synthese-Modell; Fehlerpfade: ungültige URL, fehlender Key, Synthese-Fehler (Platzhalter).
- **PR 6:** Toggle blendet Section ein/aus; gegenseitiger Ausschluss mit Einzelanalyse;
  Abbrechen funktioniert; Ergebnis erscheint; Provider-Wechsel lädt richtige Modelle.
- **PR 7:** Exportierte `.md` öffnet im Online-Konverter ohne Encoding-Probleme; Thumbnail
  wird im gerenderten PDF angezeigt.

Manuelle Referenz: Beispiel „Nick Fuentes / Jesse ON FIRE" (Video-ID `niBe6WqG0A4`) und
„US-Iran / The Daily Jagran" (`q7qCWgj4rps`) nachstellen und mit den vorliegenden
PDF-Beispielen vergleichen.

---

## Definition of Done (Doku & Versionierung)

- Versionsbump auf **v0.9.0** (Titelleiste / zentrale Versionskonstante).
- `CLAUDE.md`: neue Phase 11 „Modellvergleich" in die Phasenliste; Modul-Liste um
  `comparison_item.py`, `comparison_worker.py`, `provider_model_picker.py`,
  `somas_comparison.txt` ergänzen.
- `README.md`: Feature-Beschreibung + Screenshot.
- `docs/` (Landing Page): Abschnitt zum Modellvergleich.
- Diese Spec verbleibt in `specs/`.

---

## Nicht-Ziele (bewusst ausgeschlossen für v0.9.0)

1. **Parallele Ausführung** der beiden Analysen — sequenziell ist robuster (Rate-Limits,
   Debug-Logging, Abbruch). Mögliche spätere Optimierung.
2. **Direkter PDF-Export** — der PO erzeugt PDF und Intro-/Post-Texte (z.B. LinkedIn)
   nachgelagert selbst aus dem Markdown; kein App-seitiger PDF-Export. (Mögliche spätere
   Synergie: bestehender `linkedin_formatter.py` für einen Intro-Post aus der
   Kurzbeschreibung — Backlog, nicht v0.9.0.)
3. **Mehr als zwei Analyse-Modelle** (N-Wege-Vergleich) — Datenmodell ist erweiterbar
   gehalten, UI bleibt vorerst bei genau zwei.
4. **Diff-/Gegenüberstellungs-Ansicht** der beiden Analysen Modul-für-Modul — v0.9.0 stellt
   die Analysen untereinander dar (wie in den Referenzbeispielen), keine synoptische Tabelle.
5. **Crash-Recovery-Persistenz** — optional; MVP ohne.

---

## Geklärte Entscheidungen (PO)

1. **Synthese-Eingabe:** Beide vollständigen Analysen, kein Transkript (s.o.). ✅
2. **Provider-Umfang:** Alle 4 Provider für A, B und Synthese. ✅
3. **Ausgabe:** Nur Markdown; PDF/Intro-Posts erstellt der PO nachgelagert selbst. ✅
4. **Synthese-Default-Modell:** Kein hartkodierter Default — der Synthese-Picker merkt sich
   die letzte Auswahl (analog `get_last_model()`); beim ersten Start leer/letzter Provider.
5. **Kurzbeschreibung-Sprache:** Gleiche Sprache wie die Analysen (`config.language`,
   Default Deutsch); in v0.9.0 nicht separat konfigurierbar.
6. **Dateiablage:** `.md` wird nach `exports/` gespeichert (Dateiname aus Videotitel +
   `_Modellvergleich`); zusätzlich „Speichern unter…"-Möglichkeit pro Lauf.
