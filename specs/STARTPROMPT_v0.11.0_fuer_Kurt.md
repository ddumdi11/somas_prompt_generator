# Startprompt für Kurt (Claude Code) — v0.11.0 (Reasoning-Leak-Härtung & FAKTENCHECK-Prompt-Klärung)

> Diesen Text als ersten Auftrag in Claude Code (VS Code) einfügen. Voller Kontext in
> `specs/SOMAS_v0.11.0_SPEC_reasoning_leak_haertung.md` und `CLAUDE.md`. Beweismaterial
> (echte Request/Response-Paare) liegt in
> `examples/analyse-samples_requests_and_responses_2026-07-01/`.

---

Du bist der **Programmierer** im SOMAS-Team (Architekt = Claude.ai, Programmierer = du/Claude Code,
Supervisor/PO = Thorsten). Setze **v0.11.0** um: Härtung gegen einen realen **Final-Answer-Leak**
(Modell kippt sein Reasoning in den sichtbaren Content, frisst das Token-Budget, finale Analyse
wird abgeschnitten) plus Auflösung eines **Prompt-Widerspruchs** beim erzwungenen FAKTENCHECK.
Arbeite **PR für PR in der Reihenfolge** und halte nach jedem PR kurz inne, damit der PO
testen/abnehmen kann.

## Zuerst lesen
1. `specs/SOMAS_v0.11.0_SPEC_reasoning_leak_haertung.md` — Root-Cause-Analyse, Beweislage,
   Inkremente A/B, Akzeptanzkriterien, betroffene Dateien.
2. `CLAUDE.md` — Projektkontext, Code-Stil, GUI-Konventionen.
3. Querverweise: `src/core/openrouter_client.py` (`send_prompt`, Body ~Z.143, `finish_reason`
   ~Z.157, Content-Fallback ~Z.168), `src/core/api_client.py` (`APIResponse` ~Z.28,
   `DEFAULT_MAX_TOKENS` Z.15), `src/core/prompt_builder.py` (`_apply_custom_overrides` ~Z.290,
   `strip_reasoning_preamble` ~Z.612), `src/gui/main_window.py` (`effective_module` ~Z.1203/1289,
   Antwort-Handling + `_warn_reasoning_leak` ~Z.1904–1987).

**Kernbefund vorweg (damit du die Priorität verstehst):** Zwei erzwungene FAKTENCHECK-Läufe mit
**identischem** Prompt — einer sauber (langes Transkript, Reasoning separat), einer geleakt
(kurzes Transkript, Reasoning inline im Content, dann trunkiert). Der Prompt-Widerspruch ist
**nicht** der Auslöser des Leaks, sondern die **Backend-Serialisierung** des Reasonings. Der
stärkste Hebel liegt also auf der **API-Ebene**, nicht im Prompt.

---

## PR-Reihenfolge

### Inkrement A (sofort shippbar)

#### PR 1 — OpenRouter: Reasoning aus dem Content halten (HOCH, stärkster Hebel)
`openrouter_client.py`, `send_prompt()`-Body (~Z.143–149): `"reasoning": {"exclude": true}`
mitsenden. Das Modell reasont weiter intern (Qualität bleibt), gibt das Reasoning aber nicht mehr
zurück → verunreinigt `content` nicht. **Nur der OpenRouter-Client** — Perplexity
(`sonar-reasoning-*` liefert Reasoning bewusst), OpenAI und Anthropic bleiben unangetastet.
Den `content = message.get("content") or message.get("reasoning")`-Fallback (~Z.168) mit einem
Kommentar absichern (kein rohes Reasoning als „Analyse" ausgeben; bei leerem Content greift der
bestehende Leer-Guard).

#### PR 2 — `finish_reason` durchreichen + persistieren (HOCH)
`APIResponse` (api_client.py:28) um `finish_reason: str = ""` erweitern. In `openrouter_client.py`
die bereits lokal erfasste Variable in die Response übernehmen; in Perplexity/OpenAI/Anthropic
soweit vorhanden mitziehen (Anthropic: `stop_reason`, `max_tokens` → auf `"length"` normalisieren).
`finish_reason` im Debug-Log (`debug_logger.py` / Response-Dump) **persistieren** — im Iran-Sample
fehlte genau das und hätte die Trunkierung sofort verraten.

#### PR 3 — `finish_reason` als harter Gate (HOCH)
`main_window.py`, Antwort-Handling (~Z.1904–1948): Ist `finish_reason` ∈ {`length`, `max_tokens`,
`truncated`}, gilt die Antwort **nicht** als gültige Analyse. In Inkrement A reicht ein klarer
Fehler-/Warnstatus (Retry kommt in PR 5). Eigene, klar benannte Trunkierungs-Meldung — **nicht**
mit dem bestehenden Reasoning-Leak-Dialog vermischen (zwei getrennte Symptome).

#### PR 4 — Prompt-Widerspruch auflösen (MITTEL)
`prompt_builder.py`, `_apply_custom_overrides()` (~Z.290–307): den Prepend
*„Verwende ausschließlich das Modul '{MODUL}'. Keine andere Wahl ist erlaubt."* ersetzen durch
sinngemäß: **„Erzwinge {MODUL} als 5. Abschnitt. Behalte FRAMING, KERNTHESE, ELABORATION und
IMPLIKATION unverändert bei. Wähle kein anderes Erweiterungsmodul."** (generisch, für jedes
erzwungene Modul). Zusätzlich ein knapper **Final-Only-Zaun**: „Gib ausschließlich die fertige
Analyse aus — keine Arbeitsnotizen, keine Selbstanweisungen, keine Sätze über den Prompt/die
Aufgabe (z. B. ‚Ich muss …', ‚Wir müssen …', ‚Der Nutzer fordert …')." Die bestehende
FAKTENCHECK-Injektion (`FAKTENCHECK_FORMAT`, `FAKTENCHECK_NO_LIMIT_HINT`, Zeichenlimit-Entfernung)
**bleibt unverändert**. Optional-Feinschliff (nur wenn ohne Template-Umbau sauber machbar): das
erzwungene Modul aus der gerenderten `MODUL-AUSWAHL`-Liste nehmen (`templates/somas_prompt.txt`
Z.15–21, `somas_prompt_transcript.txt` Z.18–24) — sonst Backlog.

### Inkrement B (setzt auf A auf)

#### PR 5 — Struktur-/Trunkierungs-Validator + Retry-Eskalation (HOCH)
Neuer, headless-testbarer Validator (in `prompt_builder.py`), der die **bereits
preamble-bereinigte** Analyse **positiv** prüft: startet mit `### FRAMING`; erwartete Header in
Reihenfolge; bei FAKTENCHECK `### FAKTENCHECK` **nach** `### IMPLIKATION` mit den drei Sub-Headern
(`**Meinungen:**` / `**Interpretationen:**` / `**Behauptungen (überprüfbar):**`); Trunkierungs-
Heuristik (endet mitten in Nummerierung/Satz). **Scope strikt auf den Text vor dem ersten
`### FRAMING`** — **kein** globaler Substring-Scan (Trigger wie „Prompt"/„ich werde"/„fordert"
würden legitime Analysen verwerfen). Der Validator gibt nur `{ok, reason}` zurück, entscheidet
**nicht** selbst über Retry.
Eskalation in `main_window.py`: (1) Normalcall (mit `exclude=true`). (2) Bei Leak/Trunkierung/
fehlender Struktur **einmal** sichtbar + abbrechbar neu anfordern. (3) Bei erneutem Fehler als
**„Modelllauf fehlgeschlagen"** anzeigen — **nicht** die kosmetisch von `strip_reasoning_preamble`
reparierte Scheinanalyse. Die Faktencheck-Verifikation (Stufe 2) startet **nur** auf einer
gültigen, nicht-trunkierten Analyse.

---

## Version & Doku (Definition of Done)
- `debug_logger.APP_VERSION` 0.10.1 → **0.11.0** (+ Titelleiste, falls referenziert).
- README-Changelog (neue Phase 13 / v0.11.0) und `CLAUDE.md`-Backlog aktualisieren.
- Tests: Iran-Fall als **Fixture** einchecken (`tests/fixtures/reasoning_leak_iran.txt` aus
  `examples/…/2026-07-01_15-27-06_…/response.json`); neuer `tests/test_reasoning_leak_validator.py`
  mit: Iran = ungültig (Leak **und** Trunkierung), Literaturcafé (`…08-27-27…`) = gültig, und
  **False-Positive-Guards** (legitime Analyse mit „Prompt"/„ich werde"/„fordert … auf" im
  Fließtext, aber sauberem `### FRAMING`-Start → gültig). Bestehende Tests grün halten.
- Ein realer End-to-End-Lauf auf dem Iran-Video mit aktiver Verifikation: kein Notizen-Müll mehr —
  entweder saubere volle Analyse oder Auto-Retry und, falls weiter fehlerhaft, offener Fehlschlag.

## Harte Constraints (nicht brechen)
- Modul-Header bleibt exakt `### FAKTENCHECK` (Modul-Statistik/Regex/DB-Schema v3).
- `reasoning.exclude` **nur** im OpenRouter-Client; andere Provider nicht anfassen.
- Leak-Erkennung bleibt **preamble-scoped** (bestehende `strip_reasoning_preamble`-Logik).
- API-Keys zur Laufzeit aus dem Keyring; Ausgabesprache = `config.language` durchreichen.
- Stufe-2-Fehler bleibt nicht fatal (Analyse erhalten, Platzhalter + Warnung).

## Ausdrücklich NICHT umsetzen
- **Keine** Arbeit für Zeichenlimit-Treue (PO-Entscheidung: Qualität vor Zeichentreue; zu lange
  Beiträge kürzt der PO manuell / verschiebt sie in LinkedIn-Kommentare).
- **Kein** separater „nur-FAKTENCHECK"-Prompt-Zweig (verworfen).
- **Keine** FAKTENCHECK-Zweiteilung (getrennte Calls) — bleibt Backlog, nur bei Bedarf.
- Kein `DEFAULT_MAX_TOKENS`-Hochsetzen als Einzelmaßnahme (Spannungsfeld mit dem 402-Fix).
- Kein PDF-Export, kein Englisch-/i18n-Umbau.

## Zeilenenden / Diffs
Repo hat CRLF-Churn und kein `.gitattributes`. Vorhandene Zeilenenden bewahren, **keine**
Voll-Reformatierung; nur ändern, was der Fix braucht, damit Diffs klein/reviewbar bleiben.

## Arbeitsweise
Bei Unklarheit/Widerspruch in der Spec oder nötigen Annahmen: **erst den PO (Thorsten) fragen.**
Lieber einmal zu viel fragen als eine falsche Annahme einbauen. PR für PR, nach jedem PR kurz
innehalten zur Abnahme. Inkrement A kann eigenständig gemerged werden, bevor B beginnt.
