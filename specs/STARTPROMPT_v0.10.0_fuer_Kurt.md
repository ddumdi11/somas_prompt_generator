# Startprompt für Kurt (Claude Code) — v0.10.0 Faktencheck-Verifikation

> Diesen Text als ersten Auftrag in Claude Code (VS Code) einfügen. Die vollständige
> Architektur steht in `specs/SOMAS_v0.10.0_SPEC_faktencheck_verifikation.md`.

---

Du bist der **Programmierer** im SOMAS-Team (Rollen: Architekt = Claude.ai, Programmierer =
du/Claude Code, Supervisor/PO = Thorsten). Setze das Feature **v0.10.0 — Faktencheck-
Verifikation (Hybrid)** um.

## Zuerst lesen
1. `specs/SOMAS_v0.10.0_SPEC_faktencheck_verifikation.md` — **vollständig**. Sie ist die
   verbindliche Vorgabe (Architektur, PRs, Datenmodelle, Output-Formate, Tests, Nicht-Ziele).
2. `CLAUDE.md` — Projektkontext, Code-Stil, GUI-Konventionen.
3. Querverweise zur Orientierung: `src/core/comparison_worker.py`, `comparison_item.py`,
   `src/core/prompt_builder.py`, `src/gui/provider_model_picker.py`, `src/core/rating_store.py`.

## Auftrag
Implementiere die PRs **in der in der Spec genannten Reihenfolge** (PR 1 → PR 6). PRs 1–4 sind
ohne GUI testbar — baue und teste sie zuerst headless, GUI (PR 5) zuletzt gegen den fertigen
Worker. Halte dich an die in der Spec definierten Funktionssignaturen und Datei-/Modulnamen.

## Harte Constraints (nicht brechen)
- **Modul-Header bleibt exakt `### FAKTENCHECK`** — sonst bricht die Modul-Statistik
  (`rating_store.VALID_MODULES`, Regex `^###\s*FAKTENCHECK\b`, DB-Schema v3).
- **Modul erzwingen** über den **bestehenden** `custom_module`-Mechanismus
  (`_apply_custom_overrides`), keine neue Forcing-Logik.
- `ALL_MODULES` / `VALID_MODULES` bleiben **6 Module** mit denselben Namen.
- **Kappung app-seitig & deterministisch** (`cap_claims`), Default **N = 10**, konfigurierbar
  (`0 = unbegrenzt`). Cap **nur auf Behauptungen**; Meinungen/Interpretationen ranken, **kein Cap**.
- **Stufe-2-Prompt enthält ausschließlich die nackten Behauptungen** — keine Meinungen, kein
  Transkript (der zentrale Qualitätspunkt).
- **API-Keys** zur Laufzeit aus dem Keyring (`get_api_key`), niemals serialisieren.
- **Sprache der Stufe-2-Ausgabe = `config.language`** (Default Deutsch); Parameter durchreichen,
  nicht hartkodieren.
- Stufe-2-Fehler ist **nicht fatal**: Analyse bleibt erhalten, Platzhalter-Abschnitt + Warnung.

## Code-Konventionen (aus CLAUDE.md)
- PEP 8, Type Hints, Google-Style-Docstrings. Deutsche Kommentare OK, Code/Variablen englisch.
- `try/except` um alle externen API-Calls; Nutzerfehler über `QMessageBox`; Logging über
  `debug_logger`.
- Neue Tests anlegen (`tests/test_faktencheck_parser.py` lt. Spec) und **bestehende Tests grün
  halten**.

## Zeilenenden / Diffs (wichtig)
Das Repo hat **CRLF-Churn und kein `.gitattributes`**. Bewahre die vorhandenen Zeilenenden der
bearbeiteten Dateien; **keine Voll-Reformatierung** ganzer Dateien (z. B. kein globales
Umstellen von Quotes/Einrückung), damit die Diffs klein und reviewbar bleiben. Ändere nur, was
das Feature braucht.

## Nicht-Ziele (NICHT umsetzen)
Keine Verifikation in Batch/Modellvergleich, keine DB-Persistenz der Verdikte, kein
strukturiertes Claim→Verdict-Datenmodell, keine erzwungene Web-Konfiguration, kein PDF-Export,
**kein Englisch-/i18n-Umbau** (eigenes späteres Vorhaben).

## Definition of Done
- Alle PRs umgesetzt, Funktionssignaturen wie spezifiziert.
- Versionsbump **v0.10.0** (zentrale Konstante / `debug_logger.APP_VERSION` / Titelleiste).
- `CLAUDE.md` (neue Phase 12 + Modul-/Templateliste), `README.md` (Changelog), `docs/` aktualisiert.
- Tests grün (neu + bestehend).
- **Ein realer End-to-End-Lauf** auf einem Test-Video (siehe `CLAUDE.md` TEST_URLS): prüfen,
  dass Stufe 1 saubere, einzelne, relevanz-sortierte Behauptungen liefert und Stufe 2 pro
  Behauptung Verdikt + Quelle bringt. Im **Debug-Log des Stufe-2-Requests verifizieren, dass
  keine Meinungen in den Prompt gelangt sind.**

## Arbeitsweise
Wenn etwas in der Spec unklar oder widersprüchlich ist, oder eine Annahme nötig wäre: **frag den
PO (Thorsten), bevor du sie triffst.** Lieber einmal zu viel fragen als eine falsche Annahme
einbauen. Arbeite PR für PR und halte nach jedem PR kurz inne, damit der PO testen/abnehmen kann.
