# Statusbericht SOMAS Prompt Generator — 2026-07-12

Faktischer Entwicklungsstand-Snapshot. Keine Empfehlungen, keine Änderungen am Code.

---

## 1. Version & Git

### Versions-Abgleich

| Quelle | Wert | Fundstelle |
| ------ | ---- | ---------- |
| Code-Konstante | `0.12.1` | `src/core/debug_logger.py:17` (`APP_VERSION`) |
| CLAUDE.md | `0.12.1` | Projektkontext-Kopf |
| README-Changelog-Tabelle | `0.12.1` | `README.md:361` |

Die drei maßgeblichen Stellen (Code, CLAUDE.md, README-Changelog) **stimmen bei 0.12.1 überein.**

**Kleine Diskrepanz:** Der README-Prosa-Abschnitt „### Aktuell (v0.12.0)" (`README.md:19`)
hängt eine Version hinterher — beschreibt noch WordPress-Veröffentlichung (0.12.0),
während der Zeitanker (0.12.1) nur in der Changelog-Tabelle darunter steht.
(Der FastAPI-`version="0.1.0"` im Submodul ist unabhängig und irrelevant.)

### Branch, Commits, Working Tree

- **Branch:** `main` (einziger lokaler Branch; nur `origin/main` remote).
- **Uncommittete Änderungen:**
  - `M docs/index.html` (modifiziert, nicht committed)
  - `?? specs/STARTPROMPT_Perplexity-Wettbewerbsfaehigkeit_fuer_Kurt.md` (untracked)
- **Offene PRs:** keine (`gh pr list` → leer).

### Letzte 15 Commits

| Hash | Datum | Titel |
| ---- | ----- | ----- |
| 71a4169 | 2026-07-05 | v0.12.1: Zeitanker im Prompt (gegen Real-als-Fiktion-Fehlrahmung) (#51) |
| a348eea | 2026-07-04 | v0.12.0: WordPress-Beitragsbild (YouTube-Thumbnail als featured image) (#50) |
| 1ce172b | 2026-07-02 | Landingpage und Startprompt Anthropic-Modelle-aktualisieren |
| fdad6c9 | 2026-07-02 | v0.11.0: Reasoning-Leak-Härtung (Increment A + B) (#49) |
| 6b31c21 | 2026-07-01 | docs: Submodul-Init + optionalen Intake-Core-Install dokumentieren (#48) |
| 8053e4f | 2026-07-01 | feat: youtube-intake-service Core in-process integrieren (opt-in) (#47) |
| 8c2c887 | 2026-07-01 | Docs/intake spec revision (#46) |
| ee9bae4 | 2026-06-26 | Merge branch 'main' of github.com/ddumdi11/somas_prompt_generator |
| d6607ad | 2026-06-26 | feat: Buy-Me-a-Coffee-Button + Spec youtube-intake-service (#45) |
| 1385a13 | 2026-06-26 | fix: natuerliche Sprecher-Bezeichnung, Downloads-Default & Reasoning-… (#44) |
| e1481ca | 2026-06-26 | chore: pip-freeze Snapshot als requirements.lock.txt festhalten |
| c7196d1 | 2026-06-24 | docs: Finanzierungs-Ideen + Startprompt v0.10.1 ergänzen |
| 3b0a517 | 2026-06-22 | Feature: WordPress-Export – Analyse als Beitrag senden (Variante A) (#43) |
| 4017560 | 2026-06-17 | v0.10.1 PR 5: Verifikation erneut versuchen (Retry mit Modellwechsel) (#42) |
| 977f0ec | 2026-06-16 | v0.10.1: Faktencheck-Härtung & Fixes (PR 1-3, 6, 7) (#41) |

### Submodul `external/youtube-intake-service`

- **Gepinnt auf:** Tag `v1.0.0` (Commit `64d6973`).
- **Initialisiert:** ja (Git-Status zeigt Commit ohne `-`-Präfix; Adapter-Test `test_intake_adapter.py` läuft grün).

---

## 2. Tests

Ausgeführt mit `venv/Scripts/python.exe -m pytest tests/ -q`
(die System-`py`/Store-Python haben kein pytest; das Projekt-`venv` schon).

**Ergebnis: 50 bestanden, 0 fehlgeschlagen, 0 übersprungen** (2,97 s).

Testdateien: `test_empty_content.py`, `test_export_header.py`, `test_faktencheck_parser.py`,
`test_intake_adapter.py`, `test_reasoning_leak_validator.py`, `test_temporal_anchor.py`,
`test_wordpress_media.py`.

Keine Fehlschläge → keine Ursachenanalyse nötig.

---

## 3. Faktencheck-Modul (Schwerpunkt)

### Ist-Architektur

**Stufe 1 — Dekonstruktion (im selben Analyse-Call):**
- `FAKTENCHECK_FORMAT` (`prompt_builder.py:242`) definiert das Ausgabeformat mit den drei
  Blöcken **Meinungen / Interpretationen / Behauptungen (überprüfbar)**, relevanz-sortiert,
  ein Punkt pro Zeile, Header exakt `### FAKTENCHECK`.
- Injektion über `_apply_custom_overrides` (`prompt_builder.py:360`): erzwingt FAKTENCHECK
  als Modul, stellt `FAKTENCHECK_FORMAT` + `FAKTENCHECK_NO_LIMIT_HINT` + `FINAL_ONLY_FENCE`
  voran und entfernt die Zeichenlimit-Zeilen per Regex (`_CHARLIMIT_LINE_RE`, `:277`).
- **Parser:** `extract_claims_from_faktencheck` (`:1007`) + `_split_consecutive_claims`
  (`:962`, trennt nur an FORTLAUFENDEN Nummern-Grenzen n→n+1, damit interne Zahlen wie
  „am 7. Oktober 2023" einen Claim nicht zerreißen). `cap_claims` (`:1086`) kappt
  deterministisch auf Top-N.

**Stufe 2 — Verifikation (optional, separater Call):**
- `verification_item.py` (Config/Result), `verification_worker.py` (QThread).
- `build_verification_prompt` (`:1104`) enthält AUSSCHLIESSLICH die (bereits gekappten)
  Behauptungen — kein Transkript, keine Meinungen. Enthält den Unabhängigkeits-Riegel
  (v0.10.1): geprüftes Video zählt nicht als Beleg, `source_hint` wird als verbotene
  Eigenquelle geführt und auf 300 Zeichen gegen Prompt-Injection saniert.
- Ausführung: **ein einziger** `client.send_prompt(prompt, model_id)`
  (`verification_worker.py:162`) für alle Behauptungen zusammen.
- `somas_verification.txt` rendert das Ergebnis; `clean_verification_output` bereinigt.

### Hart kodierte Grenzen des aktuellen Ansatzes

- **Verdikt-Skala fest 4-stufig:** `VERDICT_VALUES = (bestätigt, teilweise bestätigt,
  widerlegt, nicht überprüfbar)` (`prompt_builder.py:957`) — im Prompt erzwungen.
- **Ein-Call-Verifikation:** alle Behauptungen teilen sich EIN Request-/Token-Budget
  (`verification_worker.py:162`). FAKTENCHECK-Zweiteilung (getrennte Calls) ist Backlog.
- **cap_claims-Default:** Code-Fallback in der GUI ist `10` (`main_window.py:196`),
  **aber** `user_preferences.json` überschreibt auf `verification_max_claims: 30` →
  effektiver Laufzeit-Default ist **30**. `0` = unbegrenzt.
- **source_hint** auf 300 Zeichen begrenzt (`:1130`).
- Halluzinierte Quellen werden nur **prompt-seitig** verboten („Erfinde KEINE URLs"),
  nicht technisch verhindert.

### Bekannte Schwachstellen (aus Specs/Kommentaren/Backlog)

- **Zeichenlimit vs. Vollständigkeit:** Der ursprüngliche v0.10.0-Ansatz („Gesamtzeichenlimit
  AUFGEHOBEN"-Klausel voranstellen) war fehlerhaft — die Template-Limitzeile blieb im Prompt,
  Modell kürzte trotzdem (Merkzettel A2). Behoben in v0.10.1 durch echtes Entfernen der
  Limitzeilen; als „bewusst dokumentierte Grenze" bleibt: bei **ausgeschalteter** Verifikation
  kann der FAKTENCHECK-Block durch das Preset-Limit unvollständig sein
  (SOMAS_v0.10.0_SPEC, Z. 273).
- **Reasoning-Leak** (v0.11.0): gehärtet (OpenRouter `reasoning.exclude`, `finish_reason`-Gate,
  `validate_analysis_structure`, 1× Auto-Retry statt Scheinanalyse). Zeichenlimit-Treue ist
  dabei **bewusst kein** Optimierungsziel (PO-Entscheidung #2).
- **Ein-Call-Token-Budget:** FAKTENCHECK läuft im selben Call wie die Analyse → geteiltes
  Budget kann lange Behauptungslisten abschneiden. „FAKTENCHECK-Zweiteilung" nur bei Bedarf
  (SOMAS_v0.11.0_SPEC, Z. 99; CLAUDE.md-Backlog).

---

## 4. Backlog-Abgleich

### CLAUDE.md-Backlog

| Punkt | Stand |
| ----- | ----- |
| A4: erzwungenes Modul aus `MODUL-AUSWAHL`-Liste entfernen | **offen** (FINAL_ONLY_FENCE/Format wird vorangestellt, aber die Auswahlliste selbst nicht bereinigt) |
| FAKTENCHECK-Zweiteilung (getrennte Calls, eigenes Budget) | **offen** (Verifikation weiterhin Ein-Call, `verification_worker.py:162`) |
| Docstring-Coverage ≥ 80 % (Test-Funktionen) | **offen** (CodeRabbit-Gate, niedrige Prio) |
| Wochentags-basierte Perspektive-Defaults | **offen** |
| Englisch-Support | **offen** (Prompts/UI durchgehend deutsch) |
| PDF-Export (auch Modellvergleich) | **offen** |
| Crash-Recovery-Persistenz für Modellvergleich | **offen** (nur Batch hat Persistenz) |
| N-Wege-Vergleich (> 2 Analyse-Modelle) | **offen** (`ProviderModelPicker` fest 2 Analyse + 1 Synthese) |

### Phase-15-Follow-up: `video_published` im Zeitanker

**Offen (nur vorbereitet).** `_build_temporal_anchor` und `_prepend_temporal_anchor`
akzeptieren den optionalen Parameter `video_published` (`prompt_builder.py:306/338`),
**aber** beide Aufrufer rufen ohne Wert auf: `_prepend_temporal_anchor(rendered)`
(`:483` und `:574`). Es gibt kein Upload-/Publish-Datum in `VideoInfo` (kein `upload_date`
verdrahtet), daher landet das Veröffentlichungsdatum noch nicht im Anker. Aktuell wird nur
das taggenaue **aktuelle** Datum (`datetime.now()`, locale-sicher) eingesetzt.

### WordPress Media-Dedup

**Offen.** `wordpress_client.py` hat `upload_media` (`:366`), aber keine Suche vor dem
Upload → das YouTube-Thumbnail wird bei jedem Senden neu hochgeladen (Media-Dublettenrisiko,
wie im CLAUDE.md-Backlog notiert).

---

## 5. Auffälligkeiten

- **Keine** TODO/FIXME/HACK/XXX-Kommentare im gesamten `src/`-Baum.
- **README-Prosa hängt hinterher:** „### Aktuell (v0.12.0)" (`README.md:19`) beschreibt noch
  0.12.0, obwohl Code und Changelog bei 0.12.1 sind (siehe §1).
- **cap_claims-Default-Divergenz:** Code-Fallback 10 vs. `user_preferences.json` 30 —
  dokumentierter/erwarteter Default (Spec, GUI-Tooltip) ist 10, gelebter Laufzeitwert 30 (§3).
- **`_prepend_temporal_anchor`-Parameter ungenutzt:** `video_published` existiert in der
  Signatur, wird aber nie befüllt (§4) — toter Pfad bis zum Follow-up.
- **Untracked/uncommitted:** `docs/index.html` (M) und ein neuer Startprompt-Spec sind noch
  nicht eingecheckt (§1).

---

*Erstellt: 2026-07-12 · Basis: `main` @ 71a4169 · Tests: 50/50 grün*
