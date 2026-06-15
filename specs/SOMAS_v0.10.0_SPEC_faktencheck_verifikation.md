# Feature: Faktencheck-Verifikation – Hybrid (Trennung im Hauptlauf + optionale Web-Verifikation) (v0.10.0)

> Branch: `feature/faktencheck-verification-v0100`
> Priorität: Hoch — nächste Funktionserweiterung nach Modellvergleich (v0.9.x)
> Aufwand: Mittel — FAKTENCHECK-Modul umbauen, Claim-Parser, neuer Verifikations-Worker, ein Konfig-Toggle + ProviderModelPicker, Ergebnis-Anhang
> Abhängigkeit: v0.9.x (ProviderModelPicker, `create_client()`, CollapsibleSection) abgeschlossen
> Ursprung: Idee Thorsten, vorbesprochen mit Perplexity; architektonisch eingeordnet & spezifiziert durch Claude.ai (Cowork), Entscheidungen freigegeben durch Thorsten (PO)

---

## Hintergrund

Das SOMAS-Schema entschlüsselt heute vor allem, *wie* ein Narrativ aufgebaut ist (FRAMING,
KERNTHESE …). Es gibt bereits ein FAKTENCHECK-Modul, das aber bewusst nur eine **Vorstufe**
ist: Es benennt die 3–4 überprüfungsbedürftigsten Aussagen und sagt, *wonach* man suchen
müsste — fällt aber explizit **kein** Wahr/Falsch-Urteil und prüft nichts.

Diese Erweiterung schließt die Lücke zwischen rhetorischer Analyse und harter empirischer
Überprüfung in **zwei Stufen**:

- **Stufe 1 (Dekonstruktion):** Das FAKTENCHECK-Modul wird ausgebaut. Es trennt im Transkript
  strikt **Meinungen**, **Interpretationen** und **falsifizierbare Behauptungen** und liefert
  die Behauptungen als sauber abgegrenzte, maschinell parsbare Liste.
- **Stufe 2 (Verifikation):** **Ausschließlich** die nackten Behauptungen werden an ein vom
  Nutzer gewähltes, web-fähiges Modell übergeben, das jede Behauptung prüft und pro Behauptung
  ein **Verdikt + Quelle** zurückgibt.

Der zentrale Qualitätsgewinn: In Stufe 2 stehen im Prompt **keine Meinungen mehr** — das
Verifikationsmodell kann nicht durch emotionale/rhetorische Sprache „verführt" werden, weil
es nur prüfbare Tatsachenaussagen sieht (Perplexity-Insight, vom PO bestätigt).

### Vom PO freigegebene Designentscheidungen

1. **Architektur = Hybrid.** Die **Trennung** (Stufe 1) wandert fest in den Haupt-SOMAS-Lauf
   (als ausgebautes FAKTENCHECK-Modul) und liegt damit in jeder so erzeugten Analyse vor. Die
   **Verifikation** (Stufe 2) ist davon entkoppelt und **optional**.
2. **FAKTENCHECK wird erweitert/ersetzt**, **kein** zweites paralleles Modul. Der
   Modul-Bezeichner bleibt aus Kompatibilitätsgründen `FAKTENCHECK` (siehe „Harte Constraints").
3. **Nutzer wählt das Verifikationsmodell pro Lauf** (ProviderModelPicker, alle 4 Provider),
   analog zum Modellvergleich. Kein hartkodiertes Default-Modell; letzte Auswahl wird gemerkt.
4. **Stufe-2-Ausgabe = Verdikt + Quelle pro Behauptung.** Verdikt-Skala (4 Stufen):
   `bestätigt` · `teilweise bestätigt` · `widerlegt` · `nicht überprüfbar`.
6. **Relevanz-Priorisierung statt willkürlicher Kappung.** Stufe 1 listet **alle**
   Behauptungen auf, ordnet sie aber **nach Prüf-Relevanz absteigend** (zentral für
   Kernthese/Hauptthema und/oder strittig/folgenreich im Diskurs; triviale
   Selbstverständlichkeiten ans Ende). Die **Kappung auf die Top-N** erfolgt erst beim
   Übergang zu Stufe 2 und **app-seitig deterministisch** (Parser nimmt die ersten N) — nicht
   im Vertrauen darauf, dass das Modell zählt. Default **N = 10**, in den Einstellungen
   konfigurierbar (`0 = unbegrenzt`). Die Kappung betrifft **nur Behauptungen** (sie treiben
   die Stufe-2-Kosten). **Meinungen und Interpretationen** werden ebenfalls nach Relevanz
   geordnet, aber **vollständig angezeigt** (kein Cap — reine Anzeige, keine Web-Kosten).
5. **Auslöser = Toggle (Checkbox **oder** Aktivieren/Deaktivieren-Button — Implementierer-Wahl).**
   Verhalten ist identisch und folgt dem vom PO bestätigten Ablauf:
   - **Toggle aus:** Analyse läuft wie immer; im Ergebnis steht der FAKTENCHECK-Block jetzt als
     getrennte Liste Meinungen / Interpretationen / Behauptungen. Keine Web-Verifikation.
   - **Toggle an:** Nach der Analyse startet **automatisch** ein zweiter Durchlauf
     (Fortschritt + Abbrechen), der **nur** die Behauptungen prüft; das Ergebnis wird als
     zusätzlicher Abschnitt an die Analyse angehängt.

---

## Begriffe & Benennung

| Begriff | Bedeutung |
| --- | --- |
| **Stufe 1 / Dekonstruktion** | Das ausgebaute `FAKTENCHECK`-Modul im Haupt-SOMAS-Lauf. Trennt Meinung/Interpretation/Behauptung. |
| **Stufe 2 / Verifikation** | Separater Web-Recherche-Lauf, der nur die Behauptungen prüft. Ausgabe-Überschrift im Dokument: `### FAKTENCHECK · VERIFIKATION`. |
| **Verifikationsmodell** | Das vom Nutzer pro Lauf gewählte Modell für Stufe 2 (sollte web-fähig sein). |

> **Hinweis zur Namenswahl:** Perplexity schlug „VERIFIKATION/DEKONSTRUKTION" als neuen
> Modulnamen vor. Wir behalten bewusst `FAKTENCHECK` als **Modul-Identifier** (Statistik-/
> Kompatibilitätsgründe) und nutzen „VERIFIKATION" nur als **Label des Stufe-2-Abschnitts**.

---

## Harte Constraints (nicht brechen)

1. **Modul-Statistik bleibt intakt.** `rating_store.VALID_MODULES` enthält `FAKTENCHECK`, und
   `extract_module_from_result()` erkennt das Modul per Regex `^###\s*FAKTENCHECK\b`
   (case-insensitive, MULTILINE). Der **Modul-Header in Stufe 1 muss exakt `### FAKTENCHECK`
   bleiben** (Sub-Header der Trennung darunter sind frei). Sonst bricht die Modul-Statistik
   (DB-Schema v3). Kein neuer Modulname, keine geänderte Header-Form.
2. **Anti-Monotonie/Modulpool unverändert.** `ALL_MODULES` (prompt_builder) und `VALID_MODULES`
   (rating_store) bleiben 6 Module mit denselben Namen.
3. **Erzwingen des Moduls** bei aktiver Verifikation läuft über den **bestehenden**
   `custom_module`-Mechanismus (`_apply_custom_overrides` → „PFLICHT-MODUL: …"). Keine neue
   Forcing-Logik erfinden — nur erweitern: bei `custom_module == "FAKTENCHECK"` zusätzlich die
   Konstante `FAKTENCHECK_FORMAT` injizieren (s. PR 1). So ist das parsbare Format in **jedem**
   Preset garantiert, auch in den namens-only-Templates.
4. **API-Keys** kommen zur Laufzeit aus dem Keyring (`get_api_key`); niemals serialisieren.

---

## Ziel-Ausgabe (Referenz-Layout)

### Stufe 1 – neues FAKTENCHECK-Output-Format (im Analyse-Ergebnis)

```markdown
### FAKTENCHECK
**Meinungen:**
1. <subjektive Wertung des Sprechers, nicht prüfbar>
2. …

**Interpretationen:**
1. <Deutung/Schlussfolgerung des Sprechers, nicht direkt prüfbar>
2. …

**Behauptungen (überprüfbar):**
1. <wichtigste/prüfrelevanteste falsifizierbare Tatsachenaussage>
2. <nächstrelevante …>
3. <…>
```

Regeln (im Modultext zu verankern): Eine Behauptung = ein nummerierter Punkt, je eine
**einzelne, in sich abgeschlossene, falsifizierbare** Aussage; keine Meinungswörter, kein
Konjunktiv der Wertung; das Modell fällt hier **noch kein Urteil**. **Alle drei Blöcke werden
nach Prüf-/Diskurs-Relevanz absteigend geordnet** (wichtigste zuerst); triviale, unstrittige
Selbstverständlichkeiten kommen ans Ende bzw. werden weggelassen.

### Stufe 2 – Verifikations-Abschnitt (wird an die Analyse angehängt)

```markdown
---

### FAKTENCHECK · VERIFIKATION
*Geprüft mit {{ model_name }} ({{ provider_name }}) am {{ date }}*
{% if claims_capped %}*Geprüft: die {{ checked_count }} von {{ total_count }} nach Relevanz priorisierten Behauptungen.*{% endif %}

**1. „<Behauptung 1>"**
- **Verdikt:** bestätigt
- **Begründung:** <1–2 Sätze>
- **Quelle:** <URL / Titel>

**2. „<Behauptung 2>"**
- **Verdikt:** nicht überprüfbar
- **Begründung:** <…>
- **Quelle:** —

#### Quellen
1. <url>
2. <url>
```

Verdikt-Werte exakt: `bestätigt` | `teilweise bestätigt` | `widerlegt` | `nicht überprüfbar`.

---

## Bestehende Schnittstellen (verifiziert, zur Wiederverwendung)

```python
# src/core/api_client.py
def create_client(provider_id: str, api_key: str) -> LLMClient        # bereits extrahiert (v0.9.0)
class LLMClient(ABC):
    def send_prompt(self, prompt: str, model: str) -> APIResponse
@dataclass
class APIResponse:
    status: APIStatus; content: str = ""; error_message: str = ""; model_used: str = ""
    provider_used: str = ""; tokens_used: int = 0; citations: list[str] = []
    duration_seconds: float = 0.0

# src/config/api_config.py
def get_api_key(provider_id: str) -> str

# src/core/prompt_builder.py
def build_prompt(video_info, config, questions="", preset_name=None, perspective=None,
                 anti_monotony_hint="", custom_system_prompt=None, custom_module=None) -> str
def build_prompt_from_transcript(title, author, transcript, config, url=None, questions="",
                 preset_name=None, is_auto_transcript=False, perspective=None,
                 anti_monotony_hint="", custom_system_prompt=None, custom_module=None) -> str
def normalize_markdown_headings(text: str) -> str
def _apply_custom_overrides(rendered, custom_system_prompt=None, custom_module=None) -> str  # PFLICHT-MODUL

# src/core/rating_store.py
VALID_MODULES = frozenset({... "FAKTENCHECK"})
def extract_module_from_result(store, analysis_id, result_text) -> str | None  # Regex ^###\s*FAKTENCHECK\b

# src/gui/provider_model_picker.py  (aus v0.9.0)
class ProviderModelPicker(QWidget):
    selection_changed = pyqtSignal()
    def get_selection(self) -> ModelChoice | None
    def set_selection(self, choice: ModelChoice) -> None
    def set_enabled(self, enabled: bool) -> None

# src/gui/collapsible_section.py
class CollapsibleSection(QWidget): ...  # set_content_widget / set_summary / expand / collapse

# src/core/comparison_item.py
@dataclass
class ModelChoice:  # provider_id, model_id, model_name, provider_name  → wiederverwenden
```

---

## Übersicht der Änderungen

| # | Bereich | Datei(en) |
| --- | --- | --- |
| A | `FAKTENCHECK_FORMAT`-Konstante + Injektion via `_apply_custom_overrides`; nur die zwei beschreibenden Templates aktualisieren | `src/core/prompt_builder.py`, `templates/somas_prompt.txt`, `somas_prompt_transcript.txt` |
| B | Claim-Parser + Cap + Verifikations-Prompt + Output-Cleaner | `src/core/prompt_builder.py` |
| C | Datenmodell Verifikation | `src/core/verification_item.py` (neu) |
| D | Worker Stufe 2 | `src/core/verification_worker.py` (neu) |
| E | Rendering-Template Stufe 2 | `templates/somas_verification.txt` (neu) |
| F | GUI-Integration (Toggle + Picker + Auto-Anhang) | `src/gui/main_window.py`, ggf. `settings`-Defaults |
| G | Doku & Version | `CLAUDE.md`, `README.md`, `docs/`, Versionskonstante |

---

## Implementierung

### PR 1: FAKTENCHECK-Format als Konstante + Injektion (Stufe 1)

> **Wichtige Bestandsaufnahme (verifiziert im Code).** Die Module werden NICHT überall gleich
> beschrieben:
> - `somas_prompt.txt`, `somas_prompt_transcript.txt`: jedes Modul **mit voller Beschreibung**
>   (FAKTENCHECK hat dort vollständigen Anweisungstext).
> - `somas_standard.txt`, `somas_linkedin.txt`, `somas_minimal.txt`, `somas_academia.txt`:
>   Module **nur als Namen** in einer Komma-Zeile (z. B. „MODUL-AUSWAHL: KRITIK, ZITATE, …,
>   FAKTENCHECK"). **Kein** Beschreibungstext zum Ersetzen vorhanden.
>
> Daher NICHT „in allen Templates den Eintrag ersetzen", sondern: **eine Quelle der Wahrheit +
> gezielte Injektion** (Begründung: das parsbare 3-Block-Format ist strikt nur im
> Verifikationsfall nötig, und dort wird das Modul ohnehin erzwungen → ein einziger Code-Pfad).

**1) Konstante (Single Source of Truth) in `prompt_builder.py`:**

```python
FAKTENCHECK_FORMAT = (
    "FAKTENCHECK-FORMAT — gib den Abschnitt GENAU so aus (Header exakt '### FAKTENCHECK'):\n"
    "**Meinungen:** subjektive Wertungen (nicht prüfbar), nummeriert.\n"
    "**Interpretationen:** Deutungen/Schlussfolgerungen (nicht direkt prüfbar), nummeriert.\n"
    "**Behauptungen (überprüfbar):** je eine einzelne, in sich abgeschlossene, falsifizierbare\n"
    "Tatsachenaussage pro Punkt, nummeriert; neutral und kontextfrei formuliert (ohne\n"
    "Meinungswörter); KEIN Urteil über Wahr/Falsch.\n"
    "Ordne JEDEN Block nach Relevanz absteigend (wichtigste zuerst): zentral für Kernthese/\n"
    "Hauptthema und/oder strittig bzw. folgenreich im Diskurs. Triviale Selbstverständlichkeiten\n"
    "NICHT auflisten bzw. ans Ende stellen."
)
```

Hier — und **nur hier** — leben die exakten Vertrags-Marker (`**Meinungen:**`,
`**Interpretationen:**`, `**Behauptungen (überprüfbar):**`), auf die der Parser (PR 2) angewiesen
ist. Kein Duplikat in mehreren Dateien → kein stiller Marker-Drift.

**2) Injektion beim erzwungenen Modul (kritischer Pfad = Verifikation):**
`_apply_custom_overrides()` erweitern: Wenn `custom_module == "FAKTENCHECK"`, nicht nur die
„PFLICHT-MODUL: …"-Zeile voranstellen, sondern zusätzlich `FAKTENCHECK_FORMAT` einfügen. So
erhält das Modell das vollständige Format **in JEDEM Preset** (auch den namens-only-Presets),
unabhängig vom Template. Für andere erzwungene Module bleibt das Verhalten unverändert.

**2b) Zeichenlimit für den Verifikationslauf aufheben.** Problem: Das Antwort-Zeichenlimit
eines Presets (z. B. Minimal 800, LinkedIn 2.200) begrenzt, *wie viele* Behauptungen das Modell
ausgibt — und schneidet die Liste ab, bevor das Top-N-Capping (PR 2) greifen kann. Lösung:
Dieselbe FAKTENCHECK-Injektion ergänzt eine explizite, **vorangestellte** Klausel, die das
Gesamtzeichenlimit **nur für diesen Lauf** aufhebt, z. B.:

```
HINWEIS: Für diesen Lauf ist ein etwaiges Gesamtzeichenlimit AUFGEHOBEN. Die Vollständigkeit
der relevanz-sortierten Behauptungsliste hat Vorrang vor Kürze.
```

Da diese Klausel **vor** dem (im Template späteren) `GESAMTZEICHENLIMIT`-Text steht und
spezifischer formuliert ist, überschreibt sie das Limit zuverlässig — **ohne** dass die vier
namens-only-Template-Limitzeilen editiert werden müssen. Greift ausschließlich bei aktiver
Verifikation (Modul erzwungen); **normale Analysen behalten ihr Preset-Limit unverändert.**

**3) Organische Wahl (Verifikation aus, Modell wählt frei):** Nur die zwei beschreibenden
Templates `somas_prompt.txt` und `somas_prompt_transcript.txt` bekommen die FAKTENCHECK-Modul-
beschreibung auf das neue Format aktualisiert (gleicher Wortlaut wie die Konstante). Die vier
namens-only-Presets bleiben unverändert (sie listen *alle* Module nur per Name — Status quo).

**Constraint:** Header bleibt exakt `### FAKTENCHECK` (Modul-Statistik, s. o.).

> **Bewusst dokumentierte Grenze:** Wird bei *ausgeschalteter* Verifikation in einem
> namens-only-Preset organisch FAKTENCHECK gewählt, erscheint NICHT zwingend das strukturierte
> 3-Block-Format (nur der Modulname ist bekannt) — das ist akzeptiert, da die Verifikation (der
> einzige Konsument des Formats) dann ohnehin aus ist. Bei *eingeschalteter* Verifikation ist
> das Format über die Injektion (Punkt 2) in allen Presets garantiert.
>
> **Zeichenlimit:** Die Limits (Minimal 800, LinkedIn 2.200 …) gelten für die ANTWORT, nicht für
> den Prompt — die Injektion bläht also den Prompt, nicht das Antwortbudget. Bei aktiver
> Verifikation in sehr knappen Presets soll das Modell den Block **Behauptungen** priorisieren;
> der Parser toleriert fehlende/kürzere Meinungen-/Interpretationen-Blöcke (s. PR 2).

---

### PR 2: prompt_builder — Claim-Parser, Verifikations-Prompt, Cleaner

Neue Funktionen in `src/core/prompt_builder.py`:

```python
def extract_claims_from_faktencheck(analysis_text: str) -> list[str]:
    """Extrahiert NUR die nummerierten Punkte unter '**Behauptungen (überprüfbar):**'
    aus dem FAKTENCHECK-Abschnitt einer SOMAS-Analyse.

    - Findet den '### FAKTENCHECK'-Block (bis zur nächsten '### …'-Überschrift oder EOF).
    - Innerhalb des Blocks: ab Marker 'Behauptungen' bis zum nächsten '**…:**'-Sub-Header
      bzw. Blockende die nummerierten Zeilen (`^\s*\d+[\.\)]\s+`) einsammeln.
    - Reihenfolge bleibt erhalten = bereits nach Relevanz sortiert (Stufe 1 ordnet
      absteigend). KEINE Kappung hier — die Liste ist VOLLSTÄNDIG.
    - Whitespace/Markup säubern; leere Einträge verwerfen.
    - Robust: Marker case-insensitive; toleriert fehlende Meinungen/Interpretationen.

    Returns: Liste ALLER Behauptungs-Strings in Relevanz-Reihenfolge (kann leer sein).
    """

def cap_claims(claims: list[str], max_claims: int) -> tuple[list[str], int]:
    """Wendet die konfigurierbare Obergrenze deterministisch an.

    Args:
        claims: Vollständige, relevanz-sortierte Behauptungsliste.
        max_claims: Obergrenze (0 = unbegrenzt).
    Returns:
        (gekappte_liste, total_count). Bei max_claims==0 oder len<=max: unverändert.
        Die App entscheidet anhand len(capped) < total_count, ob 'claims_capped' True ist.
    """

def build_verification_prompt(claims: list[str], language: str = "Deutsch",
                              source_hint: str = "") -> str:
    """Baut den Stufe-2-Prompt. Enthält AUSSCHLIESSLICH die Behauptungen (keine Meinungen,
    kein Transkript) → sauberer Handoff an das Web-Modell.

    Vorgaben an das Modell:
    - Prüfe jede Behauptung per Websuche/aktuellem Wissen.
    - Pro Behauptung EXAKT: Verdikt (eines von: bestätigt | teilweise bestätigt | widerlegt |
      nicht überprüfbar), 1–2 Sätze Begründung, mindestens eine Quelle (URL/Titel) bzwingend
      bei bestätigt/teilweise/widerlegt; bei 'nicht überprüfbar' Quelle '—'.
    - Festes Markdown-Format (siehe Ziel-Ausgabe Stufe 2), KEIN Vorspann, keine Meta.
    - Keine neuen Behauptungen erfinden; nur die vorgelegten prüfen, in gegebener Reihenfolge.
    Sprache der Ausgabe = `language`.
    """

def clean_verification_output(text: str) -> str:
    """Analog clean_synthesis_output(): umschließende Code-Fences und führende Leer-/
    Überschriftenzeilen entfernen, damit der Abschnitt sauber angehängt werden kann."""
```

**Hinweis:** Behauptungen werden als nummerierte Liste in den Prompt geschrieben, der Header
`### FAKTENCHECK · VERIFIKATION` selbst wird **nicht** vom Modell verlangt, sondern beim
Rendern (PR 3) deterministisch gesetzt — Modell liefert nur die Pro-Behauptung-Blöcke.

---

### PR 3: Datenmodell + Rendering-Template

**`src/core/verification_item.py` (neu):**

```python
from dataclasses import dataclass, field
from typing import Optional
from .comparison_item import ModelChoice   # wiederverwenden

@dataclass
class VerificationConfig:
    claims: list[str]             # bereits gekappte Liste (Top-N), die geprüft wird
    model: ModelChoice
    language: str = "Deutsch"
    total_claims: int = 0         # Gesamtzahl VOR Kappung (für Transparenzzeile)
    source_title: str = ""        # für Anzeige/Debug
    source_url: str = ""

@dataclass
class VerificationResult:
    config: VerificationConfig
    status: str = "pending"       # pending|running|done|error|skipped
    raw_output: str = ""          # bereinigte Modell-Ausgabe (Pro-Behauptung-Blöcke)
    rendered_section: str = ""    # fertiger Markdown-Abschnitt inkl. Header
    citations: list[str] = field(default_factory=list)
    tokens_used: int = 0
    error_message: str = ""
```

**Kappung:** Sie passiert **vor** dem Worker (in `main_window`, s. PR 5): die GUI ruft
`extract_claims_from_faktencheck()` → `cap_claims(..., max_claims)`, setzt `claims` =
gekappte Liste und `total_claims` = Gesamtzahl. So bleibt der Worker frei von UI-/
Settings-Wissen und ist headless testbar.

**`templates/somas_verification.txt` (neu, Jinja2):**

```jinja2
---

### FAKTENCHECK · VERIFIKATION
*Geprüft mit {{ model_name }} ({{ provider_name }}){% if date %} am {{ date }}{% endif %}*
{% if claims_capped %}
*Geprüft: die {{ checked_count }} von {{ total_count }} nach Relevanz priorisierten Behauptungen.*
{% endif %}

{{ verification_body }}
{% if citations %}

#### Quellen
{% for c in citations %}
{{ loop.index }}. {{ c }}
{% endfor %}
{% endif %}
```

`verification_body` = `clean_verification_output(response.content)`. `citations` =
dedupliziert aus `APIResponse.citations` (falls der Provider welche liefert; Perplexity tut
das). Unicode-Bereinigung für Export wie gehabt (`export.sanitize_unicode_for_export()`),
Speicherung `utf-8-sig`.

---

### PR 4: `VerificationWorker(QThread)`

**`src/core/verification_worker.py` (neu)** — bewusst schlank (ein API-Call), Muster wie
`ComparisonWorker`/`APIWorker`:

```python
class VerificationWorker(QThread):
    status_changed   = pyqtSignal(str)        # "running" | "done" | "error"
    finished_ok      = pyqtSignal(str, object)  # rendered_section, VerificationResult
    error_occurred   = pyqtSignal(str)        # message

    def __init__(self, config: VerificationConfig, debug_logger=None) -> None: ...

    def run(self) -> None:
        # 0) Guard: keine Behauptungen → finished_ok mit Hinweis-Abschnitt
        #    ("_Keine überprüfbaren Behauptungen gefunden._") ODER status "skipped".
        # 1) Key prüfen (get_api_key(model.provider_id)); fehlt → error_occurred.
        # 2) client = create_client(provider, key)
        # 3) prompt = build_verification_prompt(claims, language, source_hint)
        # 4) resp = client.send_prompt(prompt, model.model_id)   (+ Debug-Logging wie ComparisonWorker._send)
        # 5) Leer-/Fehler-Guard (status != RECEIVED oder leerer content) → error_occurred.
        # 6) body = clean_verification_output(resp.content)
        # 7) rendered = Jinja2 somas_verification.txt (model_name/provider_name/date/body/citations)
        # 8) finished_ok.emit(rendered, result)
    def cancel(self) -> None: ...
```

**Fehlerstrategie (nicht fatal für die Analyse):** Stufe 2 ist ein optionaler Anhang. Schlägt
sie fehl (Key fehlt, leerer Content, Exception), bleibt die **Analyse erhalten**; es wird ein
deutlich gekennzeichneter Platzhalter-Abschnitt angehängt
(`_Verifikation fehlgeschlagen: <Grund>. Behauptungen siehe FAKTENCHECK-Block oben._`) und
eine GUI-Warnung gezeigt. Kein harter Absturz, kein Verlust der Analyse.

---

### PR 5: GUI-Integration (`main_window.py`)

**UI-Elemente (in einer `CollapsibleSection("Faktencheck-Verifikation")`, nahe den
API-Controls / analog zur Modellvergleich-Section):**

1. `QCheckBox` „Behauptungen verifizieren (Faktencheck Stufe 2)" → `self.verify_checkbox`.
   (Alternativ Toggle-Button — funktional identisch; Implementierer-Wahl.)
2. Ein `ProviderModelPicker` „Verifikationsmodell" → `self.verify_picker`. Letzte Auswahl
   merken (analog `get_last_model`). Nur aktiv, wenn Checkbox an.
3. Dezenter Hinweistext: „Empfohlen: web-fähiges Modell (z. B. Perplexity Sonar)."
4. Obergrenze: `QSpinBox` „Max. zu prüfende Behauptungen" (Default 10, `0 = unbegrenzt`),
   persistiert in `user_preferences.json` (Key z. B. `verification_max_claims`). Alternativ
   nur in `settings_dialog.py`, falls die Section nicht überfrachtet werden soll — PO-Wunsch:
   konfigurierbar, Platzierung Implementierer-Wahl.

**Verdrahtung in den bestehenden Einzelanalyse-Pfad (kein neuer Start-Button):**

1. **Beim Start der Analyse** (vorhandener `_start_api_call`/`_on_generate_prompt`): Wenn
   `verify_checkbox.isChecked()` → den Haupt-Prompt mit **erzwungenem Modul** bauen, d. h.
   `custom_module="FAKTENCHECK"` an `build_prompt(...)` / `build_prompt_from_transcript(...)`
   übergeben (nutzt bestehenden `_apply_custom_overrides`). So liegt die Behauptungsliste
   garantiert vor. Picker-Auswahl vorher validieren (gesetzt? sonst Hinweis, kein Start).
2. **Nach erfolgreicher Analyse** (im bestehenden `response_received`-Slot, nach Anzeige +
   `extract_module_from_result(...)`): wenn Verifikation aktiv →
   `all_claims = extract_claims_from_faktencheck(result_text)`;
   `claims, total = cap_claims(all_claims, max_claims_setting)`;
   `VerificationConfig(claims=claims, total_claims=total, …)` bauen; `VerificationWorker`
   starten; Controls sperren; Fortschritt über
   `verify_section.set_summary("Verifikation läuft … (Modell X)")` + „Abbrechen".
   Die Transparenzzeile (`claims_capped = len(claims) < total`) rendert PR 3.
3. **`finished_ok(section, result)`** → `section` an `self.result_text` **anhängen** (an die
   bestehende Analyse, nicht ersetzen). Export enthält damit Analyse **inkl.**
   Verifikationsabschnitt.
4. **`error_occurred`** → Platzhalter-Abschnitt anhängen + `QMessageBox`-Warnung; Analyse
   bleibt erhalten.
5. **Gegenseitiger Ausschluss:** Ist der Modellvergleich-Toggle aktiv, Verifikation deaktivieren
   (ausgrauen) und umgekehrt — wie der bestehende Ausschluss Einzelanalyse ↔ Modellvergleich.
   (Verifikation im Modellvergleich = Backlog, s. Nicht-Ziele.)

**Soft-Warnung Web-Fähigkeit:** Beim Start, wenn das gewählte Verifikationsmodell nicht als
web-fähig bekannt ist (Heuristik: Provider == „perplexity" ODER OpenRouter-Modell-ID mit
`:online` / bekannter Web-Plugin), eine **nicht-blockierende** `QMessageBox`-Info: „Das
gewählte Modell hat evtl. keinen Web-Zugriff; Verifikation kann ungenau sein." Start trotzdem
erlaubt (PO darf experimentieren).

---

### PR 6: Doku & Version

- Versionsbump **v0.10.0** (zentrale Versionskonstante / Titelleiste / `debug_logger.APP_VERSION`).
- `CLAUDE.md`: neue **Phase 12 „Faktencheck-Verifikation"**; Modul-Liste um
  `verification_item.py`, `verification_worker.py`, `somas_verification.txt` ergänzen;
  Template-/Modulbeschreibung (FAKTENCHECK neu) aktualisieren.
- `README.md`: Feature-Abschnitt + Changelog 0.10.0.
- `docs/` Landing Page: kurzer Abschnitt zur zweistufigen Faktenprüfung.
- Diese Spec verbleibt in `specs/`.

---

## Reihenfolge

1. **PR 1** FAKTENCHECK-Templates (Stufe-1-Format)
2. **PR 2** `prompt_builder`: Parser + Verifikations-Prompt + Cleaner (headless testbar)
3. **PR 3** `verification_item.py` + `somas_verification.txt`
4. **PR 4** `VerificationWorker`
5. **PR 5** GUI-Integration
6. **PR 6** Doku/Version

PRs 1–4 sind ohne GUI testbar (Parser-Unit-Tests + Worker-Lauf headless mit echtem Key).

---

## Verification (pro PR)

- **PR 1:** `build_prompt(..., custom_module="FAKTENCHECK")` enthält `FAKTENCHECK_FORMAT` inkl.
  aller drei Vertrags-Marker — **auch mit einem namens-only-Preset** (z. B. Standard, Minimal).
  Eine reale Analyse mit erzwungenem FAKTENCHECK liefert die drei Sub-Header in der vorgegebenen
  Form; `extract_module_from_result()` erkennt weiterhin `FAKTENCHECK`. Andere erzwungene Module
  (z. B. KRITIK) bleiben unverändert (keine Format-Injektion).
- **PR 2 (Unit-Tests, `tests/test_faktencheck_parser.py`):**
  - Standardfall: 3 Behauptungen werden korrekt extrahiert, Meinungen/Interpretationen ignoriert.
  - Robustheit: fehlender Meinungen-/Interpretationen-Block; abweichende Nummerierung (`1)` vs `1.`);
    case-insensitive Marker; kein FAKTENCHECK-Block → `[]`.
  - `cap_claims`: 14 Claims + N=10 → 10 zurück, total=14; N=0 → alle, total unverändert;
    len<=N → unverändert; Reihenfolge bleibt erhalten (Relevanz).
  - `build_verification_prompt` enthält alle Behauptungen, **keine** Meinungen, Verdikt-Skala,
    festes Format; `clean_verification_output` entfernt Fences/Vorspann.
- **PR 3:** Template rendert mit/ohne Quellenliste sauber; Sonderzeichen/Umlaute korrekt.
- **PR 4:** End-to-end Stufe 2 mit Perplexity Sonar + 3 Beispielbehauptungen; Fehlerpfade:
  fehlender Key, leerer Content (→ Platzhalter, keine Exception), leere Claim-Liste (→ skipped).
- **PR 5:** Toggle an → Hauptlauf erzwingt FAKTENCHECK, Stufe 2 läuft automatisch, Abschnitt
  wird **angehängt** (Analyse bleibt erhalten); Abbrechen funktioniert; gegenseitiger Ausschluss
  mit Modellvergleich; Export enthält beide Teile.
- **PR 6:** Version/Changelog/Docs konsistent.

**Empfohlener Verifikations-Schlussschritt (Subagent/Review):** Einen realen Lauf auf einem
Test-Video (siehe CLAUDE.md TEST_URLS) durchführen und prüfen, dass (a) Stufe 1 saubere,
einzelne Behauptungen liefert, (b) Stufe 2 für jede Behauptung Verdikt+Quelle bringt und (c)
keine Meinungen in den Stufe-2-Prompt gelangen (Debug-Log des Verifikations-Requests prüfen).

---

## Nicht-Ziele (bewusst ausgeschlossen für v0.10.0)

1. **Verifikation im Modellvergleich** und **im Batch-Modus** — zunächst nur Einzelanalyse-Pfad.
   Datenmodell/Worker sind so geschnitten, dass eine spätere Einbindung möglich ist (Backlog).
2. **Automatische DB-Persistenz der Verdikte** (eigene Tabelle, Auswertung) — MVP hängt den
   Abschnitt nur an den Ergebnistext an. Strukturierte Speicherung = Backlog.
3. **Strikt geparstes Verdikt-Datenmodell pro Behauptung** (Claim→Verdict-Objekte) — v0.10.0
   vertraut der Markdown-Ausgabe des Modells (wie bei der Einzelanalyse). Parsing in Felder ist
   Backlog (Voraussetzung für DB-Persistenz/Statistik).
4. **Erzwungener Web-Zugriff / Provider-seitige Tool-Use-Konfiguration** — wir warnen nur weich;
   echte Online-Erzwingung (z. B. OpenRouter `:online`-Auto-Suffix) ist Backlog.
5. **PDF-Export** des verifizierten Dokuments — wie gehabt nachgelagert durch den PO.
6. **App-Einstellmöglichkeit für die Preset-Zeichenlimits** (Limits pro Preset in der GUI
   regelbar) — vom PO gewünscht, aber bewusst später (~1 Monat). Backlog.
7. **Academia-Zeichenlimit entfernen/lockern** — vom PO angedacht, aber unabhängig vom
   Verifikations-Feature; nicht mitten in v0.10.0 anfassen. Separater kleiner Backlog-Punkt.
8. **Debug-Logging für zweistufige Läufe** — aktuell überschreibt im Einzelanalyse-Pfad der
   Stufe-2-Call (Verifikation) das Stufe-1-Log (Analyse), bzw. pro Lauf bleibt nur der letzte
   Request/Response erhalten (im PO-Test beobachtet). Wünschenswert: beide Schritte je Lauf
   behalten und klar nach `feature`/`step` benennen (analog ComparisonWorker-Meta), damit ein
   Verifikationslauf Analyse + Verifikation nebeneinander dokumentiert. Vom PO vorgemerkt,
   Backlog (nicht v0.10.0).

---

## Geklärte Entscheidungen (PO)

1. **Architektur:** Hybrid — Trennung fest im Hauptlauf (FAKTENCHECK), Verifikation optional. ✅
2. **Bestehendes Modul:** FAKTENCHECK erweitern/ersetzen, Identifier bleibt `FAKTENCHECK`. ✅
3. **Verifikationsmodell:** Nutzer wählt pro Lauf (ProviderModelPicker, alle 4 Provider). ✅
4. **Stufe-2-Output:** Verdikt + Quelle pro Behauptung; 4-stufige Verdikt-Skala. ✅
5. **Auslöser:** Toggle (Checkbox oder Button); aus = nur getrennte Liste, an = Auto-Stufe-2
   nach der Analyse mit Fortschritt + Abbrechen. ✅
6. **Relevanz-Priorisierung:** Stufe 1 ordnet alle drei Blöcke nach Relevanz absteigend;
   triviale Selbstverständlichkeiten ans Ende. ✅
7. **Obergrenze:** Nur **Behauptungen** werden gekappt (app-seitig, deterministisch), Default
   **N = 10**, konfigurierbar (`0 = unbegrenzt`). **Meinungen/Interpretationen**: nur ranken,
   **kein Cap** (vollständige Anzeige). ✅
8. **Sprache der Stufe-2-Ausgabe:** Default = Analysesprache (`config.language`), aktuell also
   Deutsch (alle Templates sind deutsch). Der `language`-Parameter wird durch Stufe 1 → Parser
   → Stufe 2 durchgereicht, damit die Verifikation **forward-kompatibel** ist: Sobald englische
   Templates existieren (Backlog „Englisch-Support"), zieht die Verifikationssprache automatisch
   mit. Keine separate Sprachwahl-UI in v0.10.0. ✅
9. **Zeichenlimit bei Verifikation:** Bei erzwungenem FAKTENCHECK wird das Antwort-Zeichenlimit
   **nur für diesen Lauf** aufgehoben (Klausel in der Injektion, s. PR 1.2b), damit die
   vollständige Behauptungsliste für das Top-N-Capping entsteht. Normale Analysen behalten ihr
   Preset-Limit. **Kein** neues Limit im FAKTENCHECK-Modul selbst (PO-Wunsch). ✅

---

## Offene Detailfragen für die Umsetzung (Kurt → ggf. PO)

- Derzeit keine offenen Punkte. Alle Designentscheidungen sind getroffen (s. o.).

---

## Nachbesserungen nach PO-Test (Runde 2)

> Kontext: Der PO-Test (PR 1–5) lief mechanisch korrekt, deckte aber einen **Parser-Bug**
> (inline-nummerierte Behauptungen) und Schwächen rund um No-Web-Modelle auf. Befund:
> - Lauf Claude Sonnet 4.6 (kein Web): Quellen-URLs **erfunden** (Story real, Links nicht
>   auffindbar) — bestätigt die Halluzinationsgefahr.
> - Lauf DeepSeek V4 via OpenRouter (ohne `:online` → ebenfalls kein Web): Stufe 2 meldete
>   „keine Behauptungen". Ursache war NICHT Web, sondern der Parser: DeepSeek schrieb den
>   FAKTENCHECK inline (`**Behauptungen (überprüfbar):** 1. … 2. …` in EINER Zeile);
>   `extract_claims_from_faktencheck` sucht nur in Folgezeilen → `[]`. Headless reproduziert.

**N1 — Parser-Robustheit (Pflicht, kritisch).** `extract_claims_from_faktencheck` muss
Behauptungen erkennen, egal ob (a) je Punkt auf eigener Zeile, (b) inline hinter dem
Sub-Header, (c) inline auf einer Folgezeile. Ansatz: Claim-Region = Resttext der
Sub-Header-Zeile **nach** dem Marker + Folgezeilen bis zum nächsten `**…:**`-Sub-Header /
`###` / Blockende, zusammengefügt; dann an **fortlaufenden** Nummern-Grenzen splitten (nach
Item *n* folgt Grenze *n+1*), **nicht** an beliebigen Zahlen — sonst zerreißt „am 7. Oktober
2023" einen Claim. Tests ergänzen: Inline-Block (echte DeepSeek-Fixture, s. u.),
Claim mit interner Datums-Zahl, gemischt zeilen-/inline.

**Reale Fixture (aus PO-Debug-Log, DeepSeek V4 Pro — als Test-Input verwenden):** Der
FAKTENCHECK kam komplett inline (jeder Block in EINER Zeile, Punkte mit „ N. " getrennt):

```text
### FAKTENCHECK
**Meinungen:** 1. Sanders pro-israelische Positionen sind nicht radikal. 2. Der Ausschluss aus dem Film ist eine himmelschreiende Ungerechtigkeit. 3. Die Branche war links, weil es in Mode war, nicht aus politischer Überzeugung. 4. Der moralische Kompass vieler Künstler ist verbogen. 5. Die Gesellschaft verroht zunehmend.
**Interpretationen:** 1. Sanders Ausschluss zeigt ein strukturelles Problem der Filmbranche. 2. Anti-israelische Propaganda hat breite Gesellschaftsschichten erfasst. 3. Die Dominanz anti-israelischer Erzählungen schüchtert Politiker ein. 4. Antisemitismus stammt vor allem aus arabisch-muslimischen und linken Milieus. 5. Die deutsche Erinnerungskultur ist unzureichend.
**Behauptungen (überprüfbar):** 1. Sander wurde wegen ihrer pro-israelischen Haltung aus dem Film „Die Todessehnsucht der Maria Om" ausgeschlossen. 2. Sie verfasste das Drehbuch mit einem Co-Autor. 3. Sie führt seit Ende 2024 einen Rechtsstreit gegen die Produktionsfirma. 4. Das Kammergericht Berlin entschied in der Berufung zugunsten der Produktionsfirma. 5. Auf dem Campus der Burg Giebichenstein Kunsthochschule Halle wurden Flugblätter verteilt, die die jüdische Gemeinde als rassistisch und zionistisch bezeichnen und ihre Ausladung fordern. 6. Die Hochschulleitung entfernte diese Plakate. 7. Sander gibt an, täglich hunderte Hassnachrichten mit Holocaust-Bezug zu erhalten. 8. Sie steht eigenen Angaben zufolge in Kontakt mit dem LKA. 9. Auf Berliner Free-Palestine-Demos riefen Teilnehmer arabischsprachig „Tod den Juden". 10. Auf der Sonnenallee in Berlin-Neukölln hängen Palästina-Flaggen. 11. Sander veröffentlichte im August 2025 ein kritisches Video über Teile der Schauspielbranche. 12. Die jüdische Gemeinde Halle organisierte Synagogenbesuche für Studierende.
```

Erwartung: `extract_claims_from_faktencheck(...)` liefert **genau 12** Behauptungen (1–12),
Meinungen/Interpretationen tauchen NICHT auf. Zusätzlich ein **synthetischer** Test mit interner
Datums-Zahl, z. B. inline `… 1. Sie reiste am 7. Oktober 2023 nach Israel. 2. Das Gesetz gilt
seit 2021.` → muss **2** Claims liefern (nicht an „7." zerteilen).

> **Clean-Handoff verifiziert (PO-Debug-Log):** Der reale Stufe-2-Request (Claude-Lauf) enthält
> `Faktenprüfer` + `ZU PRÜFENDE BEHAUPTUNGEN`, aber KEINE Meinungs-/Interpretations-Inhalte und
> nicht die Marker „Meinungen"/„Interpretationen". Das Design (nur Behauptungen in Stufe 2) ist
> damit am echten Lauf bestätigt.

**N2 — Format schärfen (Pflicht).** In `FAKTENCHECK_FORMAT` + den 2 beschreibenden Templates
ergänzen: „Schreibe jeden nummerierten Punkt auf eine EIGENE Zeile (Zeilenumbruch nach jedem
Punkt); keine Inline-Aufzählung." Belt-and-suspenders zum robusteren Parser (N1).

**N3 — Prompt-Riegel gegen erfundene Quellen (Pflicht).** In `build_verification_prompt`
ergänzen: „Gib nur Quellen an, die du tatsächlich abgerufen/verifiziert hast. Erfinde keine
URLs. Kannst du eine Behauptung nicht mit einer belastbaren Quelle verifizieren, nutze Verdikt
‚nicht überprüfbar' und Quelle ‚—'." Die bisherige Pflicht-Quelle-Regel entsprechend lockern
(Quelle nur verpflichtend, wenn tatsächlich verifiziert).

**N4 — Dialog mit Abbrechen / Trotzdem fortfahren.** `_verification_preflight`: bei
No-Web-Modell statt `QMessageBox.information` ein `QMessageBox.question` mit Buttons
**„Abbrechen"** (→ `return False`, Section bleibt offen zum Modellwechsel) und **„Trotzdem
fortfahren"** (→ `return True`).

**N5 — Web-Disclaimer im Output.** Wenn `_looks_web_capable(model)` False ist, `VerificationConfig`
ein Flag mitgeben (z. B. `web_unverified: bool = False`); `somas_verification.txt` rendert dann
eine sichtbare Zeile, z. B.: „⚠️ Verifikationsmodell ohne bestätigten Web-Zugriff — Quellen
ungeprüft, können unzuverlässig oder erfunden sein." Bleibt dauerhaft im Dokument (anders als
die Vorab-Warnung).

**N6 — `:online`-Schalter für OpenRouter.** Eine Checkbox „Web-Suche (:online)" am
Verifikations-Picker, die bei OpenRouter-Modellen das Suffix `:online` an die `model_id` anhängt
(falls nicht schon vorhanden). Damit ist echter Web-Zugriff aktivierbar; `_looks_web_capable`
greift dann automatisch (→ keine Warnung, kein Disclaimer). Hinweis: `ProviderModelPicker` wird
auch 3× im Modellvergleich genutzt — die Checkbox so kapseln, dass sie die bestehende
Vergleichs-Nutzung nicht stört (nur bei OpenRouter-Auswahl wirksam/sichtbar).

**Nicht in dieser Runde:** breitere Web-Erkennungs-Heuristik (PO-Entscheidung — der
`:online`-Schalter macht den Fall explizit; pauschale Modelllisten sind unzuverlässig und
wartungsintensiv). Backlog.

> **Reihenfolge:** Diese Nachbesserungen vor PR 6 (Doku/Version), damit die Doku den finalen
> Stand abbildet. Danach erneuter PO-Test (idealerweise: ein web-fähiges Modell via `:online`
> oder Perplexity → Stufe 2 liefert echte, klickbare Quellen).

---

## Nachbesserungen Runde 3 (GUI-Bugs aus PO-Test 2)

> Kontext: Erfolgreicher Web-Lauf (OpenRouter DeepSeek V4 Pro + `:online`) — Stufe 2 lieferte
> echte, klickbare Quellen und angemessen skeptische Verdikte (mehrfach „nicht überprüfbar/—",
> ein „widerlegt", ein „teilweise bestätigt"); der N3-Riegel wirkt sichtbar. Zwei GUI-Bugs:

**G1 — `:online`-Checkbox unsichtbar im checked-Zustand UND QSpinBox-Buttons defekt
(gemeinsame Ursache, Pflicht).** Beide Widgets (`verify_online_checkbox`, `verify_max_spin`)
sind schmucklos. Ursache liegt in der geteilten `CollapsibleSection`: `_body.setStyleSheet(...)`
setzt `background-color`/`border` **ohne Selektor** → kaskadiert auf alle Kind-Widgets. Geerbte
`border`-Regeln schalten bei QCheckBox/QSpinBox die Compound-Subcontrols von nativ auf QSS:
Checkbox-`::indicator` im checked-Zustand ohne Aussehen → unsichtbar; QSpinBox `::up-/down-button`
→ eine Taste tot. (Der Autor hat das für die Header-Labels bereits mit
`border:none;background:transparent` umgangen — bestätigt die Kaskade. Betrifft latent auch den
Modellvergleich.) **Zentraler Fix in `collapsible_section.py` (~3 Zeilen, behebt es überall):**

```python
self._body.setObjectName("collapsibleBody")
self._body.setStyleSheet(
    "#collapsibleBody { background-color: white; border: 1px solid #C0C0C0; "
    "border-top: none; border-bottom-left-radius: 4px; border-bottom-right-radius: 4px; }"
)
```

Der ID-Selektor begrenzt die Regel auf das Body-Widget; Kinder rendern wieder nativ (SpinBox:
vertikale Pfeile, beide funktionsfähig). Analog auch in `_update_arrow()` (dort wird der Header
neu gestylt — Body bleibt unberührt, kein Eingriff nötig). Ein horizontales −/+ am SpinBox wäre
rein optional/kosmetisch.

**Verifikation: kurzer Re-Test nach dem Fix** — Checkbox sichtbar im checked-Zustand, SpinBox
hoch/runter beide funktionsfähig, in der Verifikations- UND der Vergleichs-Section.

---

## Bugfix-Runde 4 (v0.10.1) — A1/A2 aus PO-Beobachtungen

> Zwei nach dem v0.10.0-Merge gefundene Bugs. Beide klein und klar umrissen. Quelle:
> PO-Test-Beobachtungen + externes Review. Verifiziert am Code.

**A1 — `max_tokens` fehlt im Request → HTTP 402 bei OpenRouter (HOCH, verifiziert).**
`openrouter_client.py` (Payload bei ~Z. 142) sendet nur `model` + `messages`, **kein**
`max_tokens`. Folge: OpenRouter rechnet mit dem vollen Context-Window (z. B. 65.536 Output-Token)
als Worst-Case und blockt bei moderatem Guthaben mit **HTTP 402** („requires more credits, or
fewer max_tokens"). Das war die wahre Ursache des 402 — nicht zu wenig Guthaben.
Fix:

```python
json={
    "model": model,
    "messages": [{"role": "user", "content": prompt}],
    "max_tokens": 4096,
},
```

- Wert **4096** (konsistent mit `anthropic_client.py`/`openai_client.py`, die ihn bereits setzen).
  Reicht für die kurzen Analyse- und Verifikations-Antworten locker; verhindert das Worst-Case-
  Pre-Auth. **`perplexity_client.py`** hat ebenfalls kein `max_tokens` → gleich mitziehen.
- Hinweis: Reasoning-Modelle verbrauchen zusätzlich „Denk-Token". Falls dort später Abschneiden
  auffällt, Wert erhöhen oder konfigurierbar machen (Backlog) — für jetzt genügt 4096.
- **Verify:** OpenRouter-Lauf mit knappem Guthaben kein 402 mehr; Verifikation mit vielen Claims
  wird nicht abgeschnitten.

**A2 — Prompt-Widerspruch beim Zeichenlimit bei erzwungenem FAKTENCHECK (MITTEL–HOCH, verifiziert).**
N2b stellt „Limit AUFGEHOBEN" voran, aber die Template-Zeilen zum Zeichenlimit bleiben im Prompt
→ das Modell folgt evtl. der Grenze und **kürzt die Behauptungsliste**. Das Limit steht pro
Template an bis zu **drei** Stellen (verifiziert):
1. Kopf: `⚠ ZEICHENLIMIT: Deine GESAMTE Antwort MUSS unter … Zeichen bleiben. Zähle mit.`
2. Regeln: `N. GESAMTZEICHENLIMIT: Deine GESAMTE Antwort MUSS unter … Zeichen bleiben.`
3. (Transkript/Musik) `⚠ ERINNERUNG: Maximale Ausgabelänge = … Zeichen. …`

Ein Gegen-Hinweis reicht also nicht. Fix **zentral in `_apply_custom_overrides`** (gleiche Stelle
wie die FAKTENCHECK-Injektion): wenn `custom_module == "FAKTENCHECK"`, die Zeichenlimit-Zeilen aus
dem gerenderten Prompt **entfernen**, bevor er zurückgegeben wird:

```python
if custom_module and custom_module.strip().upper() == "FAKTENCHECK":
    rendered = re.sub(
        r"(?im)^.*(?:ZEICHENLIMIT|Maximale Ausgabelänge).*\n?", "", rendered
    )
```

- Damit verschwindet der Widerspruch komplett (alle drei Varianten). `FAKTENCHECK_NO_LIMIT_HINT`
  kann dann entfallen **oder** zu einer rein positiven Zeile vereinfacht werden
  („Liste die Behauptungen vollständig; Vollständigkeit vor Kürze.") — kein „aufgehoben"-Framing
  mehr nötig, da real entfernt.
- Greift nur bei erzwungenem FAKTENCHECK (Verifikation an bzw. manuell erzwungen). **Normale
  Analysen (Verifikation aus) behalten ihr Preset-Limit unverändert** — konsistent mit
  Entscheidung #9.
- **Tests** (`tests/test_faktencheck_parser.py` o. ä.): `build_prompt(..., custom_module="FAKTENCHECK")`
  enthält **kein** `ZEICHENLIMIT`/`Maximale Ausgabelänge` mehr (für ein Limit-Preset wie Standard);
  ohne `custom_module` ist die Limit-Zeile weiterhin vorhanden.

> **Reihenfolge:** A1 zuerst (entblockt OpenRouter), dann A2. Beide vor den C-Backlog-Punkten.
> Können zusammen als v0.10.1-Hotfix laufen.

---

## Backlog / Folge-Version (v0.10.1+)

- **„Verifikation erneut versuchen"-Button (HOCH, PO-Wunsch; vom Review ausdrücklich bestätigt).**
  Nach jedem Verifikationslauf (Erfolg, „skipped", Fehler/Abbruch) im `verify_section` einen Button
  „Verifikation erneut versuchen" aktivieren. Klick:
  1. **Verifikationsmodell darf vorher gewechselt werden** — Auswahl frisch über
     `_effective_verify_choice()` lesen (Picker + `:online`). Kernnutzen (Review-Szenario):
     DeepSeek:online liefert viele „nicht überprüfbar" → Nutzer stellt auf Perplexity Sonar um und
     fährt **nur Stufe 2** neu.
  2. Claims via `extract_claims_from_faktencheck(result_text)` aus dem **vorhandenen** Ergebnis
     ziehen (Stufe 1 bleibt unberührt — kein ~80-s-Re-Run, keine Doppelkosten), `cap_claims` mit
     aktuellem SpinBox-Wert; neuen `VerificationWorker` starten (bestehendes
     `_set_verification_running`/Abbrechen wiederverwenden).
  3. **Vorhandenen Verifikationsabschnitt ERSETZEN, nicht stapeln:** vor dem Anhängen den alten
     Block ab `### FAKTENCHECK · VERIFIKATION` (inkl. vorangehendem `---`) bis Ende abschneiden,
     dann neu anhängen — sonst sammeln sich Duplikate bei mehrfachem Retry.
  Button während eines laufenden Verifikationslaufs deaktivieren.
- **`:online`-Checkbox-Tooltip präzisieren (NIEDRIG, Review-Anregung).** Tooltip ergänzen/ersetzen:
  „Das ':online'-Suffix aktiviert die modellspezifische Internetsuche; die Recherche-Qualität hängt
  stark vom Modell ab." Lernpunkt **„Webzugriff ≠ Webzugriff"**: DeepSeek:online fand real
  verifizierbare, top-aktuelle News nicht, dedizierte Such-Modelle (Perplexity Sonar) mühelos.
  Kurz auch in README/Docs als Empfehlung „für Stufe 2 ein dediziertes Such-Modell (z. B. Perplexity
  Sonar) wählen".
- **Optional: Perplexity-Modellliste ergänzen (NIEDRIG).** `api_providers.json` führt aktuell
  `sonar`, `sonar-pro`, `sonar-reasoning` — alle gültig (Stand Juni 2026, offizielle Doku). Nice-to-have:
  `sonar-reasoning-pro` (DeepSeek-R1-basiert, zeigt Reasoning) und `sonar-deep-research` aufnehmen.
  Kein Stale-ID-Problem vorhanden.
- **Debug-Logging nach Schritt/Feature benennen** (= Backlog #8, präzisiert): Logs trennen pro
  Call bereits in eigene Ordner (kein Datenverlust); sie sind nur nach Modell+Zeitstempel
  benannt. Nice-to-have: zusätzlich `feature`/`step` im Ordnernamen für leichtere Zuordnung.
- **Einzelanalyse-Export an Modellvergleich-Kopf angleichen (PO-Wunsch).** `export.get_markdown_content`
  hat aktuell nur „# Analyse · SOMAS: {Titel}" + Metazeilen. Es fehlen ggü. `somas_comparison.txt`:
  der große Videotitel als H1, der Untertitel „**{Kanal}, YT**" und der Thumbnail-Link. Umsetzung:
  in `get_markdown_content` bei YouTube-`video_info` einen Kopfblock voranstellen —
  `# {title}` / `**{channel}, YT**` / `![Thumbnail zum Video „{title}"]({maxres})` — via bestehendem
  `extract_video_id` + `build_thumbnail_urls` (YouTube-only; im Transkript-Modus kein Thumbnail/kein
  „YT"). **Design-Entscheidung (PO):** neuer Titel-Block **ersetzt** das bisherige
  „# Analyse · SOMAS: {Titel}" (Empfehlung, kein doppelter Titel bei Einzelanalyse) — Metazeilen
  (Kanal/Dauer/URL/Modell) bleiben darunter. Optional analog der Fallback-Blockquote (sd/hq) wie im
  Vergleich. Naheliegend zusammen mit dem Retry-Button als v0.10.1.
