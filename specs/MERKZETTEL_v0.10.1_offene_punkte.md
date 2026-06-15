# Merkzettel — offene Punkte nach v0.10.0

> Stand: Abend 14.06.2026 (nach v0.10.0-Merge). Für die nächste Sitzung / v0.10.1.
> Quelle: Abend-Beobachtungen Thorsten + Perplexity-Review. Noch nicht in die Haupt-Spec eingearbeitet.

## A — Code-Bugs (für Kurt)

**A1 · `max_tokens` fehlt im OpenRouter-Request (HOCH, verifiziert).**
`openrouter_client.py` (Payload ~Z. 142) sendet kein `max_tokens`. Folge: OpenRouter reserviert
das volle Context-Window (z. B. 65.536 Token) als Worst-Case und blockt mit **HTTP 402** bei
moderatem Guthaben („requires more credits, or fewer max_tokens"). Das war die wahre Ursache des
402 — nicht zu wenig Guthaben.
→ Fix: expliziten `max_tokens` mitsenden. Wert groß genug, dass lange Verifikations-/
Analyse-Antworten **nicht abgeschnitten** werden (Vorschlag 4096–8192), aber nicht das ganze
Window. Perplexity-Client (`perplexity_client.py`) hat ebenfalls kein `max_tokens` → gleich
mitziehen. Anthropic/OpenAI setzen es bereits (4096).

**A2 · Prompt-Widerspruch beim Zeichenlimit bei aktiver Verifikation (MITTEL–HOCH).**
Bei erzwungenem FAKTENCHECK stellt N2b den Hinweis „Gesamtzeichenlimit AUFGEHOBEN" voran —
**aber** die Template-Zeile „⚠ ZEICHENLIMIT: … unter 2800 Zeichen" bleibt im Prompt (im echten
Request nachgewiesen). Das Modell folgt dann evtl. der 2800-Grenze und **kürzt die
Behauptungsliste** → genau das, was wir bei Verifikation NICHT wollen.
→ Robuster Fix: bei erzwungenem FAKTENCHECK die `GESAMTZEICHENLIMIT`-Zeile im Template wirklich
**unterdrücken** (Jinja-Conditional bzw. per Variable steuerbar), statt nur einen
widersprechenden Hinweis voranzustellen. Revidiert PR 1.2b.

## B — Konto-Sache (für Thorsten, kein Code)

**B1 · Perplexity-API nicht erreichbar = Account, nicht Code.**
Perplexity hat das monatliche 5-$-Gratis-API-Guthaben (~Feb 2026) abgeschafft → reines Prepaid.
Account stand auf 0 $ → 401/402. 500 Credits (5 $) sind jetzt geladen und reichen für **hunderte**
Läufe (ein 7-Claim-Lauf kostet < 0,05 $). Falls weiter Fehler:
1. 10–15 Min Aktivierungsverzögerung nach erster Aufladung abwarten.
2. Model-ID prüfen (aktuell: `sonar`, `sonar-pro`, `sonar-reasoning-pro`). Im fehlgeschlagenen
   Request lief `sonar-reasoning` → **api_providers.json auf aktuelle Perplexity-IDs prüfen.**
3. API-Key korrekt im Keyring (`get_api_key`)?
Die gelbe „Guthaben wird knapp"-Warnung ist nur ein Default-Hinweis bei ≤ 5 $ — ignorierbar.

## C — Backlog v0.10.1 (verfeinert durch Perplexity-Review)

**C1 · „Verifikation erneut versuchen"-Button (HOCH) — mit Modellwechsel.**
Wie geplant, aber Verfeinerung: vor dem Retry das **Verifikationsmodell wechseln** können
(Picker + `:online` neu lesen) und nur Stufe 2 auf den bereits isolierten Claims neu fahren.
Kernszenario: DeepSeek:online liefert 5/7 „nicht überprüfbar" → auf Perplexity Sonar umstellen
und nur Stufe 2 wiederholen (kein 80-s-Stufe-1 erneut, keine Doppelkosten).

**C2 · `:online`-Checkbox-Tooltip präzisieren (NIEDRIG).**
Ergänzen: „Das ':online'-Suffix aktiviert die modellspezifische Internetsuche; die
Recherche-Qualität hängt stark vom Modell ab." Lernpunkt aus dem Test: **Webzugriff ≠ Webzugriff**
— DeepSeek:online fand top-aktuelle, real verifizierbare News nicht; dedizierte Such-Modelle
(Perplexity Sonar) finden sie mühelos. Ggf. als Empfehlung auch in README/Docs.

**C3 · Einheitlicher Export-Kopf** (Titel + „Kanal, YT" + Thumbnail) — bereits in der Spec geparkt.

## Notiz
Perplexity (Ideengeber) hat v0.10.0 begutachtet und ausdrücklich gelobt/abgesegnet: saubere
Claim-Trennung, ehrliches „nicht überprüfbar" statt Halluzination. Architektur bestätigt.

---
Nächster Schritt morgen: A1 + A2 zu Kurt (kleine, klar umrissene Fixes), B1 selbst prüfen,
C1–C3 in die Spec-Backlog-Sektion übernehmen.
