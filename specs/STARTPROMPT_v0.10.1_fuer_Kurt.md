# Startprompt für Kurt (Claude Code) — v0.10.1 (Faktencheck-Härtung & Fixes)

> Diesen Text als ersten Auftrag in Claude Code (VS Code) einfügen. Kontext steht in
> `specs/SOMAS_v0.10.0_SPEC_faktencheck_verifikation.md`, `specs/MERKZETTEL_v0.10.1_offene_punkte.md`
> und `CLAUDE.md`. v0.10.0 ist gemerged; das hier ist die Nachbesserungs-/Bugfix-Runde.

---

Du bist der **Programmierer** im SOMAS-Team (Architekt = Claude.ai, Programmierer = du/Claude Code,
Supervisor/PO = Thorsten). Setze **v0.10.1** um: gezielte Bugfixes und eine Härtung der
Faktencheck-Verifikation. Arbeite **PR für PR in der unten genannten Reihenfolge** und halte nach
jedem PR kurz inne, damit der PO testen/abnehmen kann.

## Zuerst lesen
1. `specs/MERKZETTEL_v0.10.1_offene_punkte.md` — die verfeinerten offenen Punkte (A1, A2, C1–C3).
2. `specs/SOMAS_v0.10.0_SPEC_faktencheck_verifikation.md` — Architektur/Datenmodelle/Formate.
3. `CLAUDE.md` — Projektkontext, Code-Stil, GUI-Konventionen.
4. Querverweise: `src/core/prompt_builder.py` (Verifikations-Prompt ab `build_verification_prompt`,
   ~Z. 775), `src/core/verification_worker.py`, `src/core/verification_item.py`,
   `src/core/openrouter_client.py`, `src/core/perplexity_client.py`,
   `src/config/api_providers.json`.

---

## PR-Reihenfolge

### PR 1 — Unabhängigkeits-Riegel im Verifikations-Prompt (HOCH, neu verifiziert) ⚠️
**Problem (real beobachtet, 15.06.2026, Sonar-Pro):** Das Verifikationsmodell hat **8 von 12**
Behauptungen mit „**bestätigt**" markiert und als **Quelle das analysierte YouTube-Video selbst**
angegeben (z. B. Quelle: „YouTube-Video ‚Ich habe SIE konfrontiert…'"). Begründungstenor: „Im
Video wird X gesagt, also ist X gestützt." Das ist **zirkulär** — die Quelle, die geprüft werden
soll, wird zu ihrem eigenen Beleg. Das untergräbt den Kernzweck der Verifikation.

Beispiel-Verdikte aus dem Fehllauf:
- „Die tatsächliche Teilnehmendenzahl lag … bei ca. 3.000 bis 4.000" → **bestätigt**, Quelle = Video
  („Diese Angabe ist damit im Video selbst belegt"). Faktisch ist das **nicht** verifiziert.
- „Beim Holocaust seien nur 284.000 Menschen gestorben" (als Aussage eines Teilnehmers) →
  **bestätigt**, Quelle = Video. Gefährlich missverständlich: bestätigt wird hier nur, *dass es im
  Video gesagt wurde*, nicht der Wahrheitsgehalt.
- Demgegenüber **korrekt**: die KPD/SPD-Verbots- und die Gauland-„Vogelschiss"-Behauptung wurden mit
  **echten externen Quellen** (Bundestag, LeMO, dokumentierte Parteitagsrede) belegt.

**Fix in `build_verification_prompt` (`prompt_builder.py`):** Regelblock ergänzen, der
Eigenbeleg ausschließt. Inhaltlich:
- Das **analysierte Video/Transkript zählt NICHT als Beleg**. Eine Behauptung gilt nur dann als
  *bestätigt / teilweise bestätigt / widerlegt*, wenn eine **vom geprüften Inhalt unabhängige,
  externe Quelle** sie stützt bzw. widerlegt.
- „Im Video wird X gesagt" ist **kein** Verifikationsgrund. Lässt sich X nur aus dem Video selbst
  ableiten → Verdikt **„nicht überprüfbar"**, Quelle **„—"**.
- Sauber trennen: die Frage ist **„Stimmt die Behauptung?"**, nicht **„Wurde sie im Video
  gesagt?"**. (Zweiteres ist durch Stufe 1 ohnehin schon gegeben.)
- Die Quellen-URL/der Quellentitel darf **nicht** die Quellen-URL/der Titel des geprüften Videos
  sein. (Quelltitel/URL stehen in `VerificationConfig.source_title` / `source_url` — diese als
  „verbotene Eigenquelle" explizit in den Prompt aufnehmen bzw. als Negativ-Hinweis durchreichen.)

Bestehende Riegel beibehalten (keine erfundenen URLs; Quelle nur bei echter Verifikation Pflicht;
nur die vier Verdikt-Werte). Test: realer Lauf auf einem Test-Video — im Ergebnis darf **keine**
Behauptung „bestätigt" + Video-als-Quelle sein; rein videointerne Behauptungen müssen „nicht
überprüfbar" werden.

### PR 2 — Perplexity-Modellliste aktualisieren (PFLICHT)
Der Fehllauf nutzte `sonar-reasoning`; aktueller Perplexity-Stand (Doku, Juni 2026):
`sonar`, `sonar-pro`, `sonar-reasoning`, **`sonar-reasoning-pro`**, **`sonar-deep-research`**.
- In **`src/config/api_providers.json`** und **`src/core/perplexity_client.py`** (Modellliste
  ~Z. 25–37) das veraltete/abgestufte `sonar-reasoning` durch **`sonar-reasoning-pro`** ersetzen und
  **`sonar-deep-research`** ergänzen. `sonar` und `sonar-pro` bleiben.
- Beide Stellen **konsistent** halten (Config + Client-Default/Liste). Default-Modell prüfen
  (`sonar-pro` bleibt sinnvoll).
- **Vor dem Commit gegen die offizielle Doku gegenprüfen** (`https://docs.perplexity.ai/docs/sonar/models`),
  da sich IDs ändern können. Bei Abweichung: PO kurz fragen.

### PR 3 — `max_tokens` mitsenden (HOCH, verifiziert — war die echte 402-Ursache)
`openrouter_client.py` (Payload ~Z. 142) sendet **kein** `max_tokens` → OpenRouter reserviert das
volle Context-Window als Worst-Case und blockt mit **HTTP 402** trotz Guthaben.
- Expliziten `max_tokens` mitsenden (Vorschlag **4096–8192** — groß genug, dass lange Verifikations-/
  Analyse-Antworten **nicht abgeschnitten** werden, aber nicht das ganze Window).
- **`perplexity_client.py`** hat ebenfalls keins → gleich mitziehen. Anthropic/OpenAI setzen
  bereits 4096.
- Wert idealerweise als benannte Konstante, nicht magisch inline.

### PR 4 — Zeichenlimit-Widerspruch bei aktiver Verifikation (MITTEL–HOCH)
Bei erzwungenem FAKTENCHECK stellt N2b „Gesamtzeichenlimit AUFGEHOBEN" voran, **aber** die
Template-Zeile „⚠ ZEICHENLIMIT: … unter 2800 Zeichen" bleibt im Prompt → das Modell kürzt evtl. die
Behauptungsliste (genau unerwünscht).
- **Robuster Fix:** bei erzwungenem FAKTENCHECK die `GESAMTZEICHENLIMIT`-Zeile im Template wirklich
  **unterdrücken** (Jinja-Conditional / steuernde Variable), statt nur einen widersprechenden
  Hinweis voranzustellen. Revidiert PR 1.2b aus v0.10.0.

### PR 5 — „Verifikation erneut versuchen"-Button mit Modellwechsel (HOCH)
- Button, der **nur Stufe 2** auf den **bereits isolierten Claims** neu fährt (kein erneuter
  ~80-s-Stufe-1-Lauf, keine Doppelkosten).
- Vor dem Retry **Verifikationsmodell wechselbar** (Picker + `:online` neu lesen).
- Kernszenario: DeepSeek:online liefert 5/7 „nicht überprüfbar" → auf Perplexity `sonar-pro`/
  `sonar-reasoning-pro` umstellen und nur Stufe 2 wiederholen.
- Race-Beachtung wie in v0.10.0: Quelle/Controls während des Laufs sperren.

### PR 6 — `:online`-Tooltip präzisieren (NIEDRIG)
Ergänzen: „Das ‚:online'-Suffix aktiviert die modellspezifische Internetsuche; die Recherche-
Qualität hängt stark vom Modell ab." Lernpunkt: **Webzugriff ≠ Webzugriff** — DeepSeek:online fand
aktuell verifizierbare News nicht, dedizierte Such-Modelle (Perplexity Sonar) mühelos. Optional als
Empfehlung in README/Docs.

### PR 7 — Einheitlicher Export-Kopf (C3, PO bestätigt: JA, in diese Runde)
Die **Einzelanalyse** soll denselben Kopf bekommen wie der Modellvergleich: Titel-Block + „Kanal,
YT" + Thumbnail, dann der SOMAS-Block. Heute baut der PO sich das manuell zusammen — das soll
automatisch passieren.

**Zielformat (vom PO vorgegeben, exakt so):**
```markdown
# {video_title}
**{channel}, YT**

![Thumbnail zum Video]({thumbnail_url})

# Analyse · SOMAS
**Kanal:** {channel}
**Dauer:** {duration_formatted}
**URL:** {url}
**Modell:** {model_name} ({provider_name})

---

### FRAMING
...
```

**Umsetzung (`src/core/export.py`, `get_markdown_content`, ~Z. 204–216):**
- Vor den SOMAS-Block einen **Titel-Block** voranstellen: `# {video_title}` + Zeile
  `**{channel}, YT**` + Leerzeile + Thumbnail-Bild.
- Thumbnail-URL über den **bestehenden Helfer `build_thumbnail_urls`** (in `prompt_builder.py`,
  schon für den Modellvergleich genutzt) bauen — **nicht** neu zusammenbauen. Bei Transkript-Quelle
  (kein YouTube / keine Video-ID) **kein** Thumbnail und **kein** „, YT"-Suffix (analog
  `is_youtube`-Logik im `somas_comparison.txt`-Template).
- Den SOMAS-Block-Header von `# Analyse · SOMAS: {title}` auf **nur `# Analyse · SOMAS`** ändern
  (der Titel steht jetzt oben im Titel-Block, keine Dopplung).
- Metadaten-Zeilen (`**Kanal:** / **Dauer:** / **URL:** / **Modell:**`) wie bisher, nur ohne
  vorangestellten Titel.
- Konsistenz mit dem Modellvergleich-Kopf (`templates/somas_comparison.txt`, Z. 1–35) wahren; wo
  sinnvoll, dieselbe Fallback-Logik für Thumbnail-Varianten (sd/hq) übernehmen.
- **LinkedIn-Export nicht** mit Titelblock/Thumbnail aufblähen (LinkedIn kann kein Markdown-Bild);
  nur der Markdown-Export bekommt den neuen Kopf.

Test: ein YouTube-Export zeigt Titelblock + Thumbnail + `# Analyse · SOMAS`; ein Transkript-Export
zeigt Titelblock **ohne** Thumbnail/„, YT".

---

## Version & Doku (Definition of Done)
- **`debug_logger.APP_VERSION` 0.10.0 → 0.10.1** (+ Titelleiste, falls dort referenziert).
- **README-Changelog** (Phase 12b / v0.10.1) und ggf. `CLAUDE.md` Backlog-Sektion aktualisieren
  (erledigte Punkte abhaken).
- Tests: bestehende grün halten; für PR 1 einen Regressions-/Prompt-Test ergänzen, der prüft, dass
  der Unabhängigkeits-Riegel-Text im generierten Prompt steht und die Quell-URL des Videos als
  Negativhinweis durchgereicht wird.
- **Ein realer End-to-End-Lauf** auf einem Test-Video (siehe `CLAUDE.md` TEST_URLS): bestätigen,
  dass keine Behauptung mehr „bestätigt + Video-als-Quelle" ist.

## Harte Constraints (nicht brechen)
- Modul-Header bleibt exakt `### FAKTENCHECK` (Modul-Statistik/Regex/DB-Schema v3).
- Stufe-2-Prompt enthält **ausschließlich die nackten Behauptungen** — keine Meinungen, kein
  Transkript.
- API-Keys zur Laufzeit aus dem Keyring (`get_api_key`), niemals serialisieren.
- Sprache der Ausgabe = `config.language` durchreichen, nicht hartkodieren.
- Stufe-2-Fehler bleibt **nicht fatal** (Analyse erhalten, Platzhalter + Warnung).

## Zeilenenden / Diffs (wichtig)
Repo hat **CRLF-Churn und kein `.gitattributes`**. Vorhandene Zeilenenden bewahren, **keine
Voll-Reformatierung** ganzer Dateien (keine globalen Quote-/Einrückungs-Umstellungen), damit Diffs
klein und reviewbar bleiben. Nur ändern, was der Fix braucht.

## Repo-Hygiene (kurz)
- Zwei alte Branches `ddumdi11-patch-*` sind obsolet und sollen **gelöscht** werden (nach
  PO-Bestätigung). Bitte vor dem Löschen kurz auflisten, was sie enthalten, falls noch nicht
  gemerged.

## Nicht-Ziele (NICHT umsetzen)
Keine Verifikation in Batch/Modellvergleich; keine DB-Persistenz der Verdikte; kein strukturiertes
Claim→Verdict-Datenmodell; kein PDF-Export; **kein Englisch-/i18n-Umbau** (eigenes späteres
Vorhaben).

## Arbeitsweise
Bei Unklarheit/Widerspruch in der Spec oder nötigen Annahmen: **erst den PO (Thorsten) fragen.**
Lieber einmal zu viel fragen als eine falsche Annahme einbauen. PR für PR, nach jedem PR kurz
innehalten zur Abnahme.
