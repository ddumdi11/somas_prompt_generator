# Feature: Reasoning-Leak-Härtung & FAKTENCHECK-Prompt-Klärung (v0.11.0)

> Branch: `feature/reasoning-leak-haertung-v0110`
> Priorität: Hoch — behebt einen realen Final-Answer-Leak mit Datenverlust (kein kosmetisches Problem)
> Aufwand: Klein–Mittel — 1 API-Parameter, 1 neues APIResponse-Feld, Prompt-Umformulierung, ein Validator + Retry-Kette, Tests
> Abhängigkeit: v0.10.1 (FAKTENCHECK-Verifikation, `strip_reasoning_preamble`, `_warn_reasoning_leak`) abgeschlossen; Intake-Service-Update eingespielt
> Ursprung: Real aufgetretener DeepSeek-V4-Pro-Ausrutscher (2026-07-01), Sample-Analyse durch Claude.ai (Cowork), Zweitmeinung ChatGPT, Entscheidungen freigegeben durch Thorsten (PO)

---

## Hintergrund

Am 2026-07-01 lieferte `deepseek/deepseek-v4-pro` (über OpenRouter) bei einem erzwungenen
FAKTENCHECK-Lauf (Video „Iran Military END BEGINS!", The Daily Jagran) **keine finale
Analyse**, sondern 31.526 Zeichen sichtbares Arbeitsdenken („Wir müssen den Anforderungstext
parsen …"), das mitten im Satz abbrach (`… Sortieren: 1 zentral, dann`). Der bestehende
Reasoning-Leak-Schutz (`strip_reasoning_preamble`, v0.11-Vorstufe) hat den Vorspann korrekt
entfernt und den Warndialog gezeigt — aber übrig blieb Müll (leere Header + abgeschnittene
Notizen), keine brauchbare Analyse.

### Was die Beweislage wirklich zeigt (Sample-Vergleich)

Referenz-Samples: `examples/analyse-samples_requests_and_responses_2026-07-01/`.

Zwei erzwungene FAKTENCHECK-Läufe mit **identischem Prompt-Wortlaut**, gegensätzliches Ergebnis:

| | CLEAN (08:27, Literaturcafé) | LEAK (15:27, Iran) |
| --- | --- | --- |
| Prompt-Wortlaut | FAKTENCHECK erzwungen (identisch) | identisch |
| Transkript | ~50.000 Zeichen | ~5.500 Zeichen |
| Content | 11.087 Zeichen, Start `### FRAMING` | 31.526 Zeichen, Start „Wir müssen …" |
| `tokens_total` | 24.809 | 10.682 |
| Reasoning | **separat** (~21k Tokens NICHT im Content) | **inline im Content**, danach hart trunkiert |
| Ergebnis | vollständige, saubere Analyse | keine finale Antwort |

Alle fünf **nicht-erzwungenen** DeepSeek-Läufe des Tages waren sauber (`### FRAMING` am Start).

**Schlussfolgerung (root cause):** Der Fehler ist **kein** Prompt-Formatkonflikt und **keine**
„Modell-plaudert"-Entscheidung. Ursache ist die **Serialisierung des Reasonings durch den
OpenRouter-Upstream-Backend**: mal getrennt (eigenes `reasoning`-Feld → Content bleibt sauber),
mal inline im `content` (→ frisst das `max_tokens`-Budget = `DEFAULT_MAX_TOKENS` 8192 → finale
Antwort wird abgeschnitten). OpenRouter routet dasselbe Modell teils auf unterschiedliche
Upstream-Provider; die App sendet aktuell **keinen** `reasoning`-Steuerparameter und liest
stumpf `message.content or message.reasoning` (`openrouter_client.py`).

Der lange als „Haupthebel" gehandelte **Prompt-Widerspruch** (siehe unten) ist damit nachweislich
**nicht** der Auslöser des Leaks — er **vergrößert** den Dump nur, weil das Modell Tokens für die
Auflösung des Widerspruchs verbrennt, was auf knappem Budget die Trunkierung wahrscheinlicher
macht.

### Der Prompt-Widerspruch (sekundär, aber real)

Bei erzwungenem FAKTENCHECK stellt `_apply_custom_overrides` (`prompt_builder.py`) dem Prompt
voran: *„Verwende **ausschließlich** das Modul 'FAKTENCHECK'. **Keine andere Wahl** ist
erlaubt."* — während das dahinter unverändert gerenderte Basis-Template weiterhin „Erstelle
genau 5 Absätze: FRAMING, KERNTHESE, ELABORATION, IMPLIKATION + gewähltes Modul" plus die
vollständige 6-Modul-Liste (inkl. FAKTENCHECK) enthält. „Ausschließlich" liest sich wie „gib nur
den FAKTENCHECK-Block aus", ist aber **nie** das gewünschte Verhalten.

### Vom PO freigegebene Designentscheidungen

1. **Zielverhalten ist die volle Analyse + FAKTENCHECK** — FRAMING, KERNTHESE, ELABORATION,
   IMPLIKATION **und** `### FAKTENCHECK` als 5. Abschnitt. Das gilt **normal** (Modell wählt
   FAKTENCHECK selbst) **und** bei **erzwungenem** FAKTENCHECK (Verifikation aktiv). Das
   Literaturcafé-Beispiel ist somit **korrektes Zielverhalten**, kein Fehler.
2. **Zeichenlimit-Überschreitung ist akzeptiert und ausdrücklich KEIN Optimierungsziel.**
   Output-Qualität geht vor Zeichentreue. Der FAKTENCHECK-Teil darf länger werden.
   (Die Zeichenlimit-Zeilen werden bei erzwungenem FAKTENCHECK bereits entfernt — bleibt so.)
3. **Kein „nur FAKTENCHECK"-Umbau.** Es wird **kein** separater Faktencheck-Prompt-Zweig
   gebaut (verworfene ChatGPT-Erst-Empfehlung). Der Fix ist eine Umformulierung, keine
   Architekturänderung.
4. **Leak-Erkennung bleibt scoped.** Detektion nur im Text **vor** dem ersten `### FRAMING`
   (bestehende `strip_reasoning_preamble`-Logik). **Kein** globaler Substring-Scan über die
   ganze Antwort — Trigger wie „Prompt", „ich werde", „Der Nutzer fordert" würden legitime
   Analysen (z. B. ein Video *über* Prompting, ein FRAMING-Satz „Der Kanal fordert seine
   Zuschauer auf …") fälschlich verwerfen.

---

## Begriffe & Benennung

| Begriff | Bedeutung |
| --- | --- |
| **Reasoning-Leak** | Modell-Denkprozess erscheint im sichtbaren `content` statt im separaten `reasoning`-Feld. |
| **Trunkierung** | Antwort wird bei `max_tokens` abgeschnitten (`finish_reason = length`); finale Analyse unvollständig. |
| **Final-Answer-Leak** | Kombination beider: Reasoning frisst das Budget, es kommt nie eine vollständige Antwort. |
| **Modell-Reasoning (erwünscht)** | Internes Nachdenken, das die Qualität steigert, aber **nicht** ausgegeben werden soll. |

---

## Umfang: zwei Inkremente (einzeln shippbar)

**Inkrement A** (klein, sofort wertstiftend): Prompt-Klärung + API-Absicherung + `finish_reason`
als harter Gate. Behebt die Ursache und macht Trunkierung sichtbar/blockierbar.

**Inkrement B** (setzt auf A auf): Retry-Eskalationskette + Struktur-/Trunkierungs-Validator
statt „strip-and-show".

**Backlog** (nur bei Bedarf): FAKTENCHECK-Zweiteilung (getrennte Calls) für garantiert eigenes
Token-Budget.

---

## Inkrement A — Prompt-Klärung + API-Absicherung

### A1 · OpenRouter: Reasoning aus dem Content heraushalten (stärkster Hebel)

Datei: `src/core/openrouter_client.py`, `send_prompt()` (Request-Body ~Z.143–149).

- Im JSON-Body ergänzen: `"reasoning": {"exclude": true}`. Bedeutung laut OpenRouter: das
  Modell **reasont weiterhin intern** (Qualität bleibt), die Reasoning-Tokens werden aber
  **nicht zurückgegeben** und verunreinigen den `content` nicht. Das ist genau der Unterschied
  CLEAN↔LEAK aus der Beweislage.
- **Empirischer Prüfpunkt (Implementierer):** Ob `exclude:true` bei einem Backend, der Reasoning
  *als Content* serialisiert, auch die Trunkierung verhindert, ist modell-/backend-abhängig.
  Deshalb ist A1 **notwendig, aber nicht allein hinreichend** — der `finish_reason`-Gate (A3)
  bleibt Pflicht. Optional zusätzlich `"reasoning": {"exclude": true, "max_tokens": …}` oder ein
  `provider`-Routing-Preference (Backend, der Reasoning trennt) evaluieren; nur übernehmen, wenn
  am Iran-Sample verifiziert.
- `content = message.get("content") or message.get("reasoning")` (~Z.168): Der `reasoning`-
  Fallback darf **nicht** dazu führen, dass rohes Reasoning als „Analyse" ausgegeben wird. Bei
  gesetztem `exclude:true` sollte `reasoning` ohnehin leer sein; bleibt `content` leer, ist das
  ein sauberer Fehler (bestehender Leer-Guard greift). Fallback-Verhalten in einem Kommentar
  festhalten.
- **Scope:** Diese Änderung betrifft **nur** den OpenRouter-Client. Perplexity
  (`sonar-reasoning-*` liefert Reasoning bewusst), OpenAI und Anthropic haben eigene Semantik
  und bleiben in A unangetastet.

### A2 · `finish_reason` durch die Abstraktion reichen

Dateien: `src/core/api_client.py`, alle vier Clients.

- `APIResponse` (api_client.py:28) um Feld erweitern: `finish_reason: str = ""`.
- `openrouter_client.py`: die bereits lokal erfasste Variable `finish_reason`
  (choice.get("finish_reason")) in die `APIResponse` übernehmen. Analog, soweit vom Provider
  geliefert, in `perplexity_client.py`, `openai_client.py`, `anthropic_client.py`
  (Anthropic: `stop_reason`; `max_tokens` → auf `"length"` normalisieren).
- `debug_logger.py` / Response-Dump: `finish_reason` **persistieren**. (Im Iran-Sample fehlte
  genau dieses Feld — es hätte die Trunkierung sofort verraten.)

### A3 · `finish_reason` als harter Qualitäts-Gate

Datei: `src/gui/main_window.py`, im Antwort-Handling nach dem API-Call (rund um
`strip_reasoning_preamble`/`_warn_reasoning_leak`, ~Z.1904–1948).

- Ist `finish_reason` ∈ {`length`, `max_tokens`, `truncated`}, gilt die Antwort **nicht als
  gültige Analyse**. In Inkrement A: klarer Fehler-/Warnstatus statt stiller Anzeige (in
  Inkrement B: Retry). Begründung: eine abgeschnittene Behauptungsliste sieht „halb plausibel"
  aus und ist für einen Faktencheck gefährlicher als ein offener Fehler.
- Der bestehende `_warn_reasoning_leak`-Dialog bleibt; Trunkierung bekommt eine **eigene,
  klar benannte** Meldung (nicht mit dem Reasoning-Leak vermischen — es sind zwei Symptome).

### A4 · Prompt-Widerspruch auflösen

Datei: `src/core/prompt_builder.py`, `_apply_custom_overrides()` (~Z.290–307).

- Den Prepend-Text bei erzwungenem Modul ersetzen. Statt
  *„Verwende ausschließlich das Modul 'FAKTENCHECK'. Keine andere Wahl ist erlaubt."* künftig
  semantisch korrekt, sinngemäß:

  > PFLICHT-MODUL: Erzwinge **{MODUL}** als 5. Abschnitt. Behalte die vier Standardabschnitte
  > FRAMING, KERNTHESE, ELABORATION und IMPLIKATION unverändert bei. Wähle **kein anderes**
  > Erweiterungsmodul.

  (Generisch halten — der Mechanismus gilt für jedes erzwungene Modul, nicht nur FAKTENCHECK.)
- Ergänzend ein knapper **Final-Only-Zaun** (kostet wenig, hilft am Rand):

  > Gib ausschließlich die fertige Analyse aus — keine Arbeitsnotizen, keine Selbstanweisungen,
  > keine Sätze über den Prompt oder die Aufgabe (z. B. „Ich muss …", „Wir müssen …",
  > „Der Nutzer fordert …").

- Bei erzwungenem Modul FAKTENCHECK zusätzlich `FAKTENCHECK_NO_LIMIT_HINT` + `FAKTENCHECK_FORMAT`
  wie bisher voranstellen (unverändert) und die Zeichenlimit-Zeilen entfernen (unverändert).
- **Optional-Feinschliff:** Wenn ein Modul erzwungen ist, dieses Modul aus der im Template
  gerenderten `MODUL-AUSWAHL`-Liste entfernen (steht sonst doppelt drin —
  `templates/somas_prompt.txt:15–21`, `templates/somas_prompt_transcript.txt:18–24`). Nur
  umsetzen, wenn ohne Template-Umbau sauber per Regex/Builder möglich; sonst Backlog.

---

## Inkrement B — Retry-Eskalation statt „strip-and-show"

### B1 · Struktur-/Trunkierungs-Validator (preamble-scoped)

Neuer Helfer in `prompt_builder.py` (oder `verification_item`-Umfeld), rein funktional & headless
testbar. Er ergänzt `strip_reasoning_preamble` um eine **Positiv-Strukturprüfung** der bereits
preamble-bereinigten Analyse:

- Beginnt der Text mit `### FRAMING`? (Preamble-Scope — kein globaler Scan.)
- Sind die erwarteten Header vorhanden und in Reihenfolge (`### FRAMING` … `### IMPLIKATION`,
  dann das erzwungene Modul, bei FAKTENCHECK `### FAKTENCHECK` **nach** `### IMPLIKATION`)?
- Enthält der FAKTENCHECK-Block die drei Sub-Header
  (`**Meinungen:**` / `**Interpretationen:**` / `**Behauptungen (überprüfbar):**`)?
- **Trunkierungs-Heuristik:** endet die Antwort mitten in Nummerierung/Satz (kein
  Satzendezeichen, offene Aufzählung)? (Der Iran-Fall endete auf `Sortieren: 1 zentral, dann`.)
- Rückgabe strukturiert (z. B. `ValidationResult{ok, reason}`), damit die GUI gezielt reagieren
  kann. Der Validator **entscheidet nicht** selbst über Retry — das tut die GUI (B2).

### B2 · Eskalationskette

Datei: `src/gui/main_window.py` (bzw. der zuständige Worker).

```text
1. Normalcall (OpenRouter mit reasoning.exclude=true).
2. Wenn finish_reason=length ODER Leak/fehlende Struktur (B1):
   → EINMAL automatisch neu anfordern (gleicher Prompt, exclude=true,
     optional gepinnter/anderer Provider). Fortschritt anzeigen.
3. Wenn erneut fehlerhaft:
   → NICHT als Analyse anzeigen, sondern als „Modelllauf fehlgeschlagen"
     (mit Hinweis: anderes Modell wählen).
```

- Grundsatz: **Lieber ein offener Fehlschlag als eine nur kosmetisch von
  `strip_reasoning_preamble` reparierte Scheinanalyse.**
- Kosten/UX: genau **ein** Auto-Retry (der Iran-Call dauerte ~143 s — nicht mehrfach blind
  wiederholen). Retry für den Nutzer sichtbar + abbrechbar.
- Interaktion mit der Faktencheck-Verifikation (Stufe 2): Stufe 2 startet erst, wenn die
  Analyse **gültig** ist (Struktur ok, nicht trunkiert). Eine trunkierte Behauptungsliste darf
  **nie** in die Web-Verifikation gehen.

---

## Backlog / optional (nicht in v0.11.0)

- **FAKTENCHECK-Zweiteilung:** Call 1 = FRAMING…IMPLIKATION, Call 2 = FAKTENCHECK. Garantiert
  dem FAKTENCHECK-Teil ein **eigenes** Token-Budget (adressiert Budget-Erschöpfung unabhängig
  von der Backend-Serialisierung). Teurer, zwei Calls, Parser bleibt (liest `### FAKTENCHECK`).
  Nur ziehen, wenn A+B den Fall nicht ausreichend stabilisieren.
- **`DEFAULT_MAX_TOKENS` erhöhen:** schwacher Einzelhebel (Reasoning-Leak kann auch ein größeres
  Budget fressen) und Spannungsfeld mit dem HTTP-402-Fix aus v0.10.1. Nur in Kombination mit
  A1/A3 erwägen, nicht isoliert.

---

## Ausdrücklich außerhalb des Scopes

- **Zeichenlimit-Treue** (PO-Entscheidung #2). Kein Validator, keine Nacharbeit deswegen.
- **Separater „nur-FAKTENCHECK"-Prompt-Zweig** (verworfen, #3).
- **Änderungen an Perplexity/OpenAI/Anthropic-Reasoning-Verhalten** (A betrifft nur OpenRouter).

---

## Testplan

Der Iran-Fall wird zum **Crash-Dummy für Reasoning-Leaks** — als Fixture einchecken.

- `tests/fixtures/reasoning_leak_iran.txt` (o. ä.): der geleakte Roh-Content aus dem Sample
  (`2026-07-01_15-27-06_…/response.json`).
- `tests/test_reasoning_leak_validator.py`:
  - `strip_reasoning_preamble` + B1 erkennen den Iran-Content als ungültig (Leak **und**
    Trunkierung).
  - Der CLEAN-Literaturcafé-Content (`2026-07-01_08-27-27_…`) validiert als **gültig**
    (volle Struktur, FAKTENCHECK nach IMPLIKATION, drei Sub-Header).
  - **False-Positive-Guards:** eine legitime Analyse, die im Fließtext „Prompt", „ich werde"
    oder „fordert … auf" enthält (aber sauber mit `### FRAMING` startet), validiert als gültig.
  - Trunkierungs-Heuristik: Text, der mitten in einer Nummerierung endet → ungültig.
- `test_export_header.py` / `test_faktencheck_parser.py`: unverändert grün (kein Regress am
  Vertragsformat).
- **Manuell (PO):** Iran-Video mit aktivierter Verifikation erneut über OpenRouter/DeepSeek —
  erwartet: entweder saubere volle Analyse (A1 greift) oder Auto-Retry und, falls weiter
  fehlerhaft, klarer „Modelllauf fehlgeschlagen"-Status (B2) — **kein** Notizen-Müll mehr.

---

## Akzeptanzkriterien

- [ ] OpenRouter-Analysecalls senden `reasoning.exclude=true`; `finish_reason` ist in
      `APIResponse` verfügbar und wird im Debug-Log persistiert.
- [ ] Eine bei `max_tokens` trunkierte Antwort wird **nie** als gültige Analyse angezeigt.
- [ ] Der erzwungene FAKTENCHECK-Prompt enthält **keinen** Widerspruch mehr; das Zielverhalten
      (volle Analyse + FAKTENCHECK) ist eindeutig instruiert.
- [ ] Leak-/Struktur-Erkennung bleibt **preamble-scoped**; legitime Analysen werden nicht
      fälschlich verworfen (False-Positive-Tests grün).
- [ ] (Inkrement B) Bei Leak/Trunkierung erfolgt genau ein sichtbarer Auto-Retry; bei erneutem
      Fehler ein offener Fehlschlag statt kosmetisch reparierter Scheinanalyse.
- [ ] Verifikation (Stufe 2) startet nur auf einer gültigen, nicht-trunkierten Analyse.
- [ ] Iran-Fixture-Tests + bestehende Parser/Export-Tests grün.

---

## Betroffene Dateien (Anhaltspunkte)

| Datei | Änderung |
| --- | --- |
| `src/core/openrouter_client.py` | `reasoning.exclude=true` im Body; `finish_reason` durchreichen; Reasoning-Fallback-Kommentar (A1/A2) |
| `src/core/api_client.py` | `APIResponse.finish_reason` (A2) |
| `src/core/perplexity_client.py`, `openai_client.py`, `anthropic_client.py` | `finish_reason`/`stop_reason` durchreichen (A2) |
| `src/core/prompt_builder.py` | Prepend-Wortlaut (A4), Final-Only-Zaun; neuer Struktur-/Trunkierungs-Validator (B1) |
| `src/gui/main_window.py` | `finish_reason`-Gate (A3); Eskalationskette + getrennte Trunkierungsmeldung (B2) |
| `src/core/debug_logger.py` | `finish_reason` persistieren (A2) |
| `templates/somas_prompt.txt`, `somas_prompt_transcript.txt` | optional: erzwungenes Modul aus `MODUL-AUSWAHL` entfernen (A4-Feinschliff) |
| `tests/…` | Iran-Fixture + Validator-Tests, False-Positive-Guards |

---

> Erstellt: 2026-07-01 · Architektur/Spec: Claude.ai (Cowork) · Zweitmeinung: ChatGPT ·
> Freigabe: Thorsten (PO) · Umsetzung: Claude Code (VS Code)
