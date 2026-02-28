# Feature: SOMAS Schema-Erweiterung v0.6.0

> Branch: `feature/schema-extension-v060`
> Priorität: Hoch — nächster Meilenstein nach Bewertungs-Redesign
> Aufwand: Mittel — Prompt-Logik, Template-Erweiterung, DB-Ergänzung, UI-Dropdown
> Abhängigkeit: v0.5.2 (Bewertungs-Redesign abgeschlossen)
> Ursprung: Brainstorming mit Gemini 3 (Thinking Mode), architektonisch
> eingeordnet durch Claude.ai, freigegeben durch Thorsten (PO)

---

## Hintergrund

Ein Modellvergleich (Gemini Web, Claude Sonnet 4.6, Gemini 3.1 Preview)
bei der Analyse desselben YouTube-Transkripts offenbarte drei Probleme:

1. **Modul-Monotonie:** 2 von 3 Modellen wählten KRITIK als Modul — selbst
   wenn es nicht zur Auswahl stand. KRITIK ist der "Default-Impuls" der
   meisten Modelle.

2. **Fehlende Haltungssteuerung:** Presets steuern *Was* analysiert wird,
   Module den *Zusatzaspekt* — aber die *Haltung* des Modells zur Quelle
   (sachlich vs. kritisch vs. empathisch) war bisher ungesteuert und
   vom Modell-Temperament abhängig.

3. **Begrenzter Modulpool:** Vier Module decken nicht alle analytischen
   Perspektiven ab. Insbesondere fehlten: implizite Botschaften dekodieren
   (SUBTEXT) und überprüfungsbedürftige Aussagen priorisieren (FAKTENCHECK).

---

## Übersicht der Änderungen

### A. Perspektive-Parameter (neue Analyse-Achse)

Drei orthogonale Steuerungsachsen für jede Analyse:
- **Preset** → *Wie* wird analysiert (Format, Länge, Tonalität)
- **Modul** → *Welcher Zusatzaspekt* wird beleuchtet (5. Abschnitt)
- **Perspektive** → *Mit welcher Haltung* wird analysiert (NEU)

| Wert       | Kurzname                 | Fokus                                        |
|------------|--------------------------|----------------------------------------------|
| `neutral`  | Neutral-Deskriptiv       | Was wird gesagt? (Spiegel)                   |
| `critical` | Kritisch-Analytisch      | Welche Techniken, was fehlt? (Mikroskop)     |
| `empathic` | Empathisch-Rekonstruktiv | Warum überzeugt das? (Verstärker-Antenne)    |

Defaults pro Preset:
- Standard → `neutral`
- LinkedIn → `neutral`
- Minimal → `neutral`
- Academia → `critical`
- Musik → `empathic`
- Songstruktur → `neutral`

### B. Modulpool-Erweiterung (4 → 6 Module)

| Modul         | Status | Fokus                                          |
|---------------|--------|------------------------------------------------|
| KRITIK        | ✅ alt  | Bias, Werbung, problematische Aussagen         |
| ZITATE        | ✅ alt  | O-Töne, markante Aussagen                      |
| OFFENE_FRAGEN | ✅ alt  | Was bleibt ungeklärt                           |
| VERBINDUNGEN  | ✅ alt  | Historischer/gesellschaftlicher Kontext         |
| SUBTEXT       | 🆕 neu | Implizite Botschaften dekodieren (nicht bewerten) |
| FAKTENCHECK   | 🆕 neu | Überprüfungsbedürftige Aussagen priorisieren   |

### C. Modul-Statistik (Tracking + Anti-Monotonie)

- Gewähltes Modul pro Analyse in SQLite mitloggen
- Bei K-maliger Wiederholung desselben Moduls: Prompt-Nudge zur Abwechslung
- Perspektive-Defaults optional wochentagsgesteuert (nach Recherche)

---

## Implementierung

### PR 1: Perspektive-Parameter

**Dateien:**

| Datei | Aktion |
|-------|--------|
| `src/config/prompt_presets.json` | MODIFY — `perspective` Feld pro Preset |
| `src/core/prompt_builder.py` | MODIFY — Perspektive-Block in Prompt einfügen |
| `templates/somas_*.txt` | MODIFY — Perspektive-Platzhalter integrieren |
| `src/gui/main_window.py` | MODIFY — Perspektive-Dropdown in UI |

**1a. Neues Feld in prompt_presets.json:**

```json
{
  "standard": {
    "perspective": "neutral",
    ...
  },
  "academia": {
    "perspective": "critical",
    ...
  },
  "music": {
    "perspective": "empathic",
    ...
  }
}
```

**1b. Perspektive-Bausteine (Prompt Builder fügt einen davon ein):**

`neutral`:
```
PERSPEKTIVE: Neutral-Deskriptiv.
Beschreibe in nüchterner Sprache, was gesagt wird, ohne eigene Wertung.
Ordne Positionen und Argumente ein, ohne sie zu bewerten. Gib die Logik
des Sprechers wieder, auch wenn sie fehlerhaft ist — die Einordnung
übernimmt der Leser. Bei mehreren Sprechern: Stelle die verschiedenen
Standpunkte gleichwertig dar.
```

`critical`:
```
PERSPEKTIVE: Kritisch-Analytisch.
Hinterfrage in analytischer Sprache rhetorische Techniken, identifiziere
Auslassungen und bewerte die Schlüssigkeit der Argumentation. Benenne,
was gesagt wird, aber auch, was bewusst nicht gesagt wird. Bei mehreren
Sprechern: Analysiere, wer den Diskurs dominiert und mit welchen Mitteln.
```

`empathic`:
```
PERSPEKTIVE: Empathisch-Rekonstruktiv.
Versetze dich in die Position der Zielgruppe und erkläre in einfühlsamer
Sprache, warum der Inhalt sie überzeugt. Rekonstruiere die innere Logik
und emotionale Wirkung, ohne sie dir zu eigen zu machen oder zu bewerten.
Ziel ist Verständnis, nicht Zustimmung. Bei mehreren Sprechern: Beschreibe
die emotionalen Dynamiken zwischen den Teilnehmern.
```

**1c. UI: Perspektive-Dropdown**

- Platzierung: Neben dem Preset-Selector
- Vorbelegt mit dem Preset-Default
- User kann überschreiben
- Tipp: Zunächst manuell über Zusatzanweisungsfeld testen, bevor
  UI-Dropdown finalisiert wird

**Commit:** `feat: add perspective parameter (neutral/critical/empathic)`

---

### PR 2: Neue Module + Modulpool-Erweiterung

**Dateien:**

| Datei | Aktion |
|-------|--------|
| `templates/somas_standard.txt` | MODIFY — SUBTEXT + FAKTENCHECK in Modulauswahl |
| `templates/somas_linkedin.txt` | MODIFY — dito |
| `templates/somas_minimal.txt` | MODIFY — dito |
| `templates/somas_academia.txt` | MODIFY — dito |
| `templates/somas_research.txt` | MODIFY — dito |
| `src/config/prompt_presets.json` | MODIFY — module_logic aktualisieren |

**2a. Neue Modulbeschreibungen im Prompt:**

```
- SUBTEXT: Dekodiere die impliziten Botschaften. Was wird zwischen den
  Zeilen gesagt? Welche Annahmen setzt der Sprecher als
  selbstverständlich voraus, ohne sie zu begründen? Welche
  Weltanschauung liegt unter der Argumentation? Nicht bewerten —
  nur sichtbar machen. Verzichte auf wertende Adjektive.
- FAKTENCHECK: Identifiziere die 3–4 Aussagen im Transkript, die
  am dringendsten einer unabhängigen Überprüfung bedürfen. Nenne
  pro Aussage: Was wurde behauptet, warum ist es überprüfungs-
  bedürftig, und wonach sollte der Leser suchen. Stelle keine
  eigenen Faktenbehauptungen auf und urteile nicht über Wahr oder
  Falsch — deine Aufgabe ist ausschließlich die Priorisierung.
```

**2b. module_logic in prompt_presets.json:**

```json
"module_logic": "Select one module based on content: KRITIK (bias/ads),
  OFFENE_FRAGEN (complexity), ZITATE (interviews), VERBINDUNGEN
  (history/context), SUBTEXT (implicit messages), or FAKTENCHECK
  (claims needing verification)."
```

**Commit:** `feat: add SUBTEXT and FAKTENCHECK modules to pool (4→6)`

---

### PR 3: Modul-Statistik + Anti-Monotonie

**Dateien:**

| Datei | Aktion |
|-------|--------|
| `src/core/rating_store.py` | MODIFY — Schema-Migration v2→v3, chosen_module Feld |
| `src/core/prompt_builder.py` | MODIFY — Anti-Monotonie-Logik |
| `src/gui/main_window.py` | MODIFY — Modul-Parsing nach Analyse |

**3a. Schema-Migration (v2 → v3):**

```sql
ALTER TABLE analyses ADD COLUMN chosen_module TEXT DEFAULT NULL;
```

**3b. Modul-Parsing (nach Analyse-Ergebnis):**

Regex-Pattern:
```python
MODULE_PATTERN = r'###\s*(KRITIK|ZITATE|OFFENE_FRAGEN|VERBINDUNGEN|SUBTEXT|FAKTENCHECK)'
```

Nach erfolgreicher Analyse: Modul aus Ergebnis parsen, in
`chosen_module` speichern. Bei Parse-Fehler: NULL belassen.

**3c. Anti-Monotonie im Prompt Builder:**

```python
# Lookback: Letzte N Analysen abfragen
recent_modules = rating_store.get_recent_modules(n=3)

# Wenn alle gleich: Nudge einfügen
if len(set(recent_modules)) == 1 and len(recent_modules) == 3:
    excluded = recent_modules[0]
    nudge = f"Wähle bevorzugt ein anderes Modul als {excluded}."
```

**Parameter (konfigurierbar, in defaults.py oder prompt_presets.json):**
- `rotation_lookback`: 3 (Default)
- `rotation_threshold`: 3 (Default)

**3d. Neue Methoden in rating_store.py:**

```python
def save_chosen_module(self, analysis_id: int, module: str) -> None:
    """Speichert das gewählte Modul für eine Analyse."""

def get_recent_modules(self, n: int = 3) -> list[str]:
    """Gibt die letzten N gewählten Module zurück."""
```

**Commit:** `feat: add module statistics and anti-monotony nudge`

---

### PR 4: Wochentags-basierte Perspektive-Defaults (nach Recherche)

**Abhängigkeit:** Thorstens ZEIT-Online-Stimmungsrecherche

**Dateien:**

| Datei | Aktion |
|-------|--------|
| `src/core/prompt_builder.py` | MODIFY — Wochentag → Default-Perspektive |

**4a. Statische Mapping-Logik (kein API-Call):**

```python
from datetime import datetime

WEEKDAY_PERSPECTIVE = {
    0: "critical",   # Montag
    1: "critical",   # Dienstag
    2: "critical",   # Mittwoch
    3: "empathic",   # Donnerstag
    4: "empathic",   # Freitag
    5: "empathic",   # Samstag
    6: "empathic",   # Sonntag
}
```

Cluster-Einteilung wird nach Thorstens Recherche finalisiert.
Die Defaults greifen nur, wenn der User keine manuelle Perspektive
gewählt hat.

**Commit:** `feat: add weekday-based perspective defaults`

---

## Reihenfolge

```
PR 1 (Perspektive-Parameter)
  └──→ PR 2 (Neue Module)
         └──→ PR 3 (Modul-Statistik + Anti-Monotonie)
                └──→ PR 4 (Wochentags-Defaults — nach Recherche)
```

## Verification (pro PR)

- **PR 1:** Perspektive-Dropdown sichtbar, Prompt enthält Perspektive-Block,
  Default wechselt bei Preset-Änderung
- **PR 2:** Modulauswahl im Prompt zeigt 6 Module, Modelle wählen
  gelegentlich SUBTEXT oder FAKTENCHECK
- **PR 3:** `chosen_module` in DB gefüllt, nach 3× gleichem Modul
  erscheint Nudge im Prompt
- **PR 4:** Default-Perspektive ändert sich je nach Wochentag

## Nicht-Ziele (bewusst ausgeschlossen)

- Automatische Content-Format-Erkennung vor der Analyse
- Dynamische Stimmungs-API (ZEIT Online o.ä.)
- "RESONANZ"-Modul (Social-Media-Analyse, nicht Quellenanalyse)
