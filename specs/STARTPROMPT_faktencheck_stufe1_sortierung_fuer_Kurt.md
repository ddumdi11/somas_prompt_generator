# Startprompt für Kurt: Stufe-1-Sortierung — Basisfakt-Markierung & argumentgewichtete Reihenfolge

**Kontext:** Sofort-PR (Quick Win) vor v0.13.0 „Faktencheck Plus".
**Grundlage:** `specs/FAKTENCHECK_THEORIE.md` §3 (prüfbar ≠ prüfwürdig) + §2.4.
**Umfang:** 1 PR, klein. Kein `APP_VERSION`-Bump (fährt mit dem nächsten Release mit);
README-Changelog-Eintrag unter „Unreleased" o. ä. nach Bestandspraxis.

---

## Problem

Empirisch belegt (4 Realfälle, dokumentiert in
`notizen/Faktencheck-Eroerterung_Perplexity_2026-07-11md.md`): Die Stufe-1-Sortierung
verwechselt Prüfbarkeit mit Prüfwürdigkeit. Leicht prüfbare Basisfakten („Das ZDF ist
öffentlich-rechtlich") landen oben, tragende strittige Claims (z. B. quantitative
Kernthesen) rutschen unter die Cap-Grenze und werden nie verifiziert. Verstärkt wird
das durch eine Spannung zwischen zwei Prompt-Bausteinen in
`src/core/prompt_builder.py`:

- `FAKTENCHECK_FORMAT` (ab :242): ordnet nach „zentral … strittig … folgenreich",
  Triviales ans Ende.
- `FAKTENCHECK_NO_LIMIT_HINT` (:259): „Vollständigkeit hat Vorrang vor Kürze" —
  fördert lange Listen gleichrangiger Neben-Claims ohne Prioritätssignal.

## Aufgabe (3 Teile)

### 1. `FAKTENCHECK_FORMAT` präzisieren

Den Sortierabsatz (Zeilen „Ordne JEDEN Block … ans Ende stellen.") ersetzen durch
sinngemäß (Formulierung darf geglättet werden, Semantik bindend):

> Ordne die Behauptungen nach argumentativem Gewicht und Recherchewert, NICHT nach
> Prüfbarkeit: Eine Behauptung steht umso höher, je stärker ihre Widerlegung oder
> fehlende Belegbarkeit die Kernthese des Beitrags materiell schwächen würde und je
> mehr eine externe Recherche dazu echten Erkenntnisgewinn verspricht.
> Biografische, lexikalische, institutionelle und allgemein bekannte Basisfakten:
> am Listenende einordnen und mit dem Suffix „ [Basisfakt]" kennzeichnen — niemals
> unter den obersten Prüfkandidaten.
> Attributionsaussagen („X behauptet/erklärt, dass …") als solche formulieren und
> nicht mit der Sachaussage selbst verschmelzen.

Meinungen/Interpretationen-Blöcke: Sortierregel unverändert lassen.

### 2. `FAKTENCHECK_NO_LIMIT_HINT` entschärfen

Ersetzen durch sinngemäß:

> Erfasse alle überprüfbaren Behauptungen — Vollständigkeit geht nicht zulasten der
> Priorisierung: Die Reihenfolge bildet argumentatives Gewicht und Recherchewert ab.

### 3. Parser & Cap: Basisfakten nicht in die Top-N

In `prompt_builder.py`:

- `extract_claims_from_faktencheck` (bzw. nachgelagert): Suffix „[Basisfakt]"
  (case-insensitiv, mit/ohne eckige Klammern tolerant) erkennen und als Flag am
  Claim führen; Suffix aus dem Claim-Text entfernen.
- `cap_claims`: als Basisfakt geflaggte Claims bei der Top-N-Auswahl überspringen
  (sie zählen nicht gegen das Budget und gehen nicht in die Verifikation).
  Verhalten bei `0 = unbegrenzt`: Basisfakten trotzdem ausschließen.
- Anzeige der Stufe-1-Analyse bleibt unverändert (Markierung darf dort sichtbar sein).

## Leitplanken

- **Kein** Eingriff in Stufe 2 (`build_verification_prompt`, Worker, Verdikte).
- Header bleibt exakt `### FAKTENCHECK`; bestehende Vertrags-Marker und
  `FINAL_ONLY_FENCE` unangetastet.
- Robustheit: Wenn ein Modell das Suffix NICHT setzt, muss alles exakt wie bisher
  funktionieren (reine Zusatzheuristik, kein Pflichtfeld).

## Tests (erweitern: `tests/test_faktencheck_parser.py`)

1. Claim mit Suffix „ [Basisfakt]" → Flag gesetzt, Suffix entfernt.
2. Schreibweisen-Toleranz: „[basisfakt]", „(Basisfakt)" → ebenfalls erkannt
   (Umfang nach Ermessen, mindestens eckige Klammern beide Kasus).
3. `cap_claims(top_n=3)` bei 2 Basisfakten unter den ersten 5 → die 3 Slots gehen
   an Nicht-Basisfakten.
4. `cap_claims(0)` → Basisfakten ausgeschlossen, Rest unbegrenzt.
5. Bestandsfixtures ohne Suffix → Verhalten unverändert (Regression).
6. Interne Zahlen in Claims („am 7. Oktober 2023") weiterhin kein Split (Regression).

## Definition of Done

- Alle Tests grün (Bestand + neu).
- README-Changelog-Eintrag; CLAUDE.md-Backlog-/Phasenpflege minimal.
- Kurzer PR-Text mit Verweis auf `FAKTENCHECK_THEORIE.md` §3.
