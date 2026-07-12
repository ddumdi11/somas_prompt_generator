# Startprompt für Kurt: Leer-Inhalt in den Retry-Pfad + Abbrechen-Fix (+ optionaler Reasoning-Cap)

**Kontext:** Realtest 2026-07-12 (Anwalt-Video, DeepSeek V4 Pro, 24k-Zeichen-Prompt):
drei Fehlversuche in Folge, Debug-Artefakte liegen vor. Kleiner Robustheits-PR,
kein `APP_VERSION`-Bump nötig (fährt mit nächstem Release mit).

## Befund (aus den Debug-Logs)

| Versuch | Verlauf | App-Verhalten |
| ------- | ------- | ------------- |
| 1 (12:39, 168 s) | `finish_reason=length`, Content leer (Reasoning fraß das komplette 8192-Budget) | harter API-Fehler-Dialog, **kein** Auto-Retry |
| 2 (12:56, 217 s) | HTTP 200, `finish_reason=length`, 1284 Zeichen (FRAMING angebrochen), tokens_total 14790 | Trunkierungs-Gate griff korrekt → Auto-Retry gestartet |
| 3 (= Auto-Retry, 210 s) | wieder leer + `length` | wieder harter Fehler-Dialog |

Bekannter DeepSeek-Heavy-Reasoner-Modus (kein Bug im Modell-Handling, ehrliche
Fehler statt Müll = designtes Verhalten). Aber zwei UX-Lücken sind jetzt real belegt:

- **Asymmetrie:** trunkiert-nicht-leer bekommt seit v0.11.0 einen sichtbaren
  Ein-Retry; Leer-Inhalt (`v0.9.1`-Riegel, `api_error` „Modell lieferte leeren
  Inhalt") endet hart ohne Retry — obwohl es derselbe Fehlermodus ist
  (Reasoning verbrennt Budget).
- **Abbrechen wirkungslos:** Während „Automatischer erneuter Versuch läuft …
  (kann abgebrochen werden)" ließ sich der Lauf laut PO NICHT abbrechen.

## Aufgabe

1. **Leer-Inhalt → gleicher Eskalationspfad wie Trunkierung:** Die
   Leer-Inhalt-`APIResponse` (alle 4 Clients werfen sie einheitlich) in
   `main_window` wie eine ungültige Analyse behandeln: 1× sichtbarer Auto-Retry,
   danach offener „Modelllauf fehlgeschlagen" — statt sofortigem QMessageBox-Fehler.
   Der Fehlertext (inkl. `finish_reason`) bleibt im Fehlschlag-Hinweis erhalten.
2. **Abbrechen reparieren:** Abbrechen-Button muss auch WÄHREND des Auto-Retrys
   greifen (laufenden Retry-Call verwerfen, UI sauber zurücksetzen, keine
   Race mit spät eintreffender Response — vorhandenen `_api_worker`-Race-Guard
   aus v0.10.1 beachten/erweitern). Bitte Ursache kurz diagnostizieren
   (vermutlich wird der Cancel-Handler nur für den Erst-Call verdrahtet).
3. **Optional, wenn günstig machbar (PO-Kosten-Tradeoff beachten):** Bei
   OpenRouter-Analyse-Calls Reasoning-Budget deckeln
   (`reasoning: {"max_tokens": …, "exclude": true}`), damit fürs sichtbare
   Ergebnis garantiert Budget übrig bleibt. Konservativer Wert (z. B. 4096),
   nur OpenRouter, andere Provider unangetastet. Falls Doku/Verhalten unklar →
   weglassen und als Backlog-Notiz dokumentieren.
4. **Logging-Kosmetik (Mitnahme):** Fehler-Responses loggen `status_code=500`
   als Default, auch wenn der echte Pfad HTTP 200 + Leer-Inhalt war —
   echten Status durchreichen.

## Leitplanken

- Kein Eingriff in Prompt-Aufbau, Validator-Logik oder Verifikation.
- Fehlermodus bleibt ehrlich: nach fehlgeschlagenem Retry KEIN weiterer
  automatischer Versuch (Kostenkontrolle), Nutzer entscheidet (neu starten /
  Modell wechseln).
- Tests: Leer-Inhalt-Retry-Pfad (gemockt), Abbruch während Retry, Regression
  Trunkierungs-Retry unverändert.

## Separater Doku-/Housekeeping-Commit (NICHT in diesen PR mischen)

- `notizen/` in `.gitignore` aufnehmen (PO-Entscheidung: Notizen bleiben lokal).
- `specs/FAKTENCHECK_THEORIE.md`, `specs/SOMAS_v0.13.0_SPEC_faktencheck_plus.md`,
  `specs/STARTPROMPT_faktencheck_stufe1_sortierung_fuer_Kurt.md`,
  `specs/STATUSBERICHT_2026-07-12.md` sichten und committen (CLAUDE.md-Änderungen
  vom 2026-07-12 mit dazu).
