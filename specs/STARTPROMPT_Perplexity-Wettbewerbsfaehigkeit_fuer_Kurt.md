# Startprompt für Kurt (Claude Code) — Perplexity in der Verifikation konkurrenzfähig machen

> Kleiner, gebündelter Zwei-Teil-Fix. Kontext: Beim Faktencheck (Stufe 2) lieferte GPT-5.3-Codex
> spürbar bessere Verdikte als Perplexity Sonar Pro — Codex fand Belege und differenzierte
> („teilweise bestätigt"), Sonar griff öfter zur konservativen Schublade „nicht überprüfbar". Zwei
> Ursachen, beide klein behebbar: (A) Perplexity sucht zu **oberflächlich**, weil der API-Parameter
> `search_context_size` nie gesetzt wird (Default „low"); (B) dem Verifikations-Prompt fehlt eine
> **Verdikt-Leitplanke** für „Kern belegt, Details nicht".

---

Du bist der **Programmierer** im SOMAS-Team. Setze zwei unabhängige, kleine Verbesserungen um, die
zusammen Perplexity als Verifikationsmodell näher an Codex heben. Beide dürfen in einem PR laufen.

## Ausgangslage (verifiziert)
- `src/core/perplexity_client.py`, `send_prompt()` (~Z.67): Request-Body (~Z.83) setzt nur
  `model`, `messages`, `max_tokens` — **kein** `web_search_options`. Perplexitys Default für
  `search_context_size` ist **„low"** = die oberflächlichste Such-Stufe (docs.perplexity.ai →
  „Search Context Size Guide"). Alle Perplexity-Modelle in SOMAS sind Sonar-Web-Modelle (sonar,
  sonar-pro, sonar-reasoning-pro, sonar-deep-research), der Parameter ist also immer anwendbar.
- Verifikation ruft generisch `create_client(...).send_prompt(prompt, model)` auf
  (`verification_worker.py` Z.94/162; `api_client.py` Z.113).
- `build_verification_prompt` in `prompt_builder.py` (~Z.1104); Verdikt-Skala-Konstante ~Z.958
  (`bestätigt` · `teilweise bestätigt` · `widerlegt` · `nicht überprüfbar`).

## Teil A — Such-Tiefe: `search_context_size` setzen

`src/core/perplexity_client.py`:
- Dem Request-Body (`send_prompt`, ~Z.83) ergänzen:
  ```json
  "web_search_options": { "search_context_size": <wert> }
  ```
- **Default `"high"`** (gezielt für die Verifikation, wo Belegtiefe zählt). „low" ist zu wenig,
  „high" zieht deutlich mehr Quellen pro Anfrage.
- Sauberste Anbindung (Implementierer-Wahl, aber empfohlen): ein **PerplexityClient-Attribut**
  `self._search_context_size = "high"` (Default), das immer in den Payload geht. Optional per
  Benutzereinstellung überschreibbar (`perplexity_search_context`, low/medium/high) — wenn ohne
  großen Aufwand machbar; sonst Default „high" fest und Einstellung als Follow-up notieren.
- Falls es im Client eine **zweite** Chat-Request-Stelle gibt (~Z.174, evtl. Verbindungstest/
  Fallback): prüfen, ob sie denselben Parameter braucht — für einen reinen Verbindungstest ist
  „low" ok, also nur die inhaltlichen Calls auf „high".
- **Nur** den Perplexity-Client anfassen (der Parameter ist Sonar-spezifisch).

**Caveat (dokumentieren):** höhere Such-Tiefe = mehr Quellen = **höhere Request-Gebühr** pro
Perplexity-Aufruf. Betrifft nur die (optionale) Verifikationsstufe, ist also gut vertretbar; falls
als Einstellung umgesetzt, dort kurz erwähnen.

## Teil B — Verdikt-Leitplanke „Kern belegt, Details nicht"

`src/core/prompt_builder.py`, `build_verification_prompt` (~Z.1104):
- Eine Regel ergänzen (Wortlaut Vorschlag, gern straffen):

  > Wenn der **Kern** einer Behauptung durch eine unabhängige externe Quelle belegt ist, einzelne
  > **Detailangaben** (Datum, Zahl, Zusatz) aber nicht, dann vergib **„teilweise bestätigt"** und
  > benenne konkret den belegten Kern sowie das offene Detail — **nicht** pauschal „nicht
  > überprüfbar".

- Bestehende Riegel unangetastet lassen: Unabhängigkeit (das geprüfte Video zählt NICHT als Beleg),
  keine erfundenen Quellen, exakt die 4 Verdikt-Werte.
- Ziel: schwächere/vorsichtigere Modelle (Sonar) an Codex-Granularität heranführen — Codex machte
  das bereits unaufgefordert (Katar-747-Behauptung: „teilweise bestätigt" statt „nicht überprüfbar").

## Definition of Done
- Perplexity-Request enthält `web_search_options.search_context_size` (Default „high") — per
  gemocktem Test verifiziert.
- `build_verification_prompt` enthält die „teilweise bestätigt"-Leitplanke — Prompt-Test.
- Manueller Gegentest (PO, optional): dieselbe Behauptung (z.B. Katar-747) mit **Sonar Pro** erneut
  verifizieren — erwartet: findet jetzt die externe Quelle und liefert „teilweise bestätigt" statt
  „nicht überprüfbar".
- Bestehende Faktencheck-/Parser-/Client-Tests grün.
- Version: mit PO abstimmen (Patch, passt in 0.12.x; nur EIN PR fasst APP_VERSION an — mit
  Anthropic-Modellpflege koordinieren).

## Nicht in diesem PR (Backlog)
- Claim-Atomisierung in Stufe 1 (gebündelte Behauptungen splitten) — der tiefere Umbau; separat.
- `search_context_size` als vollwertige UI-Einstellung, falls in Teil A nur als Default umgesetzt.

## Arbeitsweise
Bei Unklarheit erst den PO (Thorsten) fragen. Eigener kleiner PR, unabhängig von Anthropic-Modellpflege.
Wortlaut der Leitplanke ist Vorschlag — Kernaussage („Kern belegt → teilweise bestätigt, nicht
pauschal nicht-überprüfbar") muss erhalten bleiben.
