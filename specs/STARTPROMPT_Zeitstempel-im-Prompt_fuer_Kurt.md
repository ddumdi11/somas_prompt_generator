# Startprompt für Kurt (Claude Code) — Zeitanker im Prompt (gegen „Real-als-Fiktion"-Fehlrahmung)

> Kleiner, hochwirksamer Prompt-Zuwachs. Kontext: `deepseek/deepseek-v4-pro` (Wissensstand ≈2024)
> hat ein **reales** 2026-Nachrichtenvideo (Khamenei-Begräbnis, Firstpost) in seiner FRAMING als
> „fiktives/dystopisches Szenario … alternative Zukunft (2025/2026)" abgestempelt — ein
> Framing-Totalschaden. Ursache: dem Prompt fehlt jeder Zeitbezug, also nimmt das Modell seinen
> Trainings-Zeithorizont an und deutet 2026-Ereignisse als „Zukunft = Fiktion". `claude-opus-4-8`
> (Cutoff Jan 2026) machte es beim selben Video richtig. Fix: dem Modell das aktuelle Datum + eine
> Anti-Fiktions-Leitplanke mitgeben.

---

Du bist der **Programmierer** im SOMAS-Team. Gib jedem Analyse-Prompt einen **Zeitanker** mit, damit
Modelle mit älterem Wissensstand reale aktuelle Ereignisse nicht als erfunden einstufen. Kleiner,
zentraler Eingriff — kein Template-Wildwuchs.

## Ehrliche Einordnung (wichtig fürs Design)
Der Zeitanker gibt dem Modell **kein** Wissen über Ereignisse nach seinem Cutoff. Er verhindert nur
die **Fehl-Rahmung** (real → fiktiv) und Anachronismen. Für SOMAS ist das genau ausreichend: Die
Analyse rekonstruiert, *was der Beitrag sagt*; die (web-fähige) Verifikation liefert die Fakten.

## Umsetzung

### PR 1 — Zeitanker programmatisch prepend (zentral, forget-proof)
Datei: `src/core/prompt_builder.py`.

- Neuer Helfer `_build_temporal_anchor(current_date: str, video_published: Optional[str] = None) -> str`,
  der einen kurzen Block liefert (Beispiel-Wortlaut, gern verfeinern):

  ```text
  ZEITLICHER RAHMEN:
  - Heute ist der {current_date}.
  {- Der Beitrag wurde am {video_published} veröffentlicht.   # nur wenn vorhanden}
  Behandle die im Beitrag geschilderten Ereignisse grundsätzlich als REALE, aktuelle
  Berichterstattung — auch wenn sie zeitlich nach deinem Wissensstand liegen. Stufe sie NICHT als
  fiktives, hypothetisches oder spekulatives Szenario ein, es sei denn, der Beitrag kennzeichnet
  sich SELBST ausdrücklich als Fiktion, Satire oder Spekulation.
  ```

- Den Block in **beiden** Build-Pfaden dem gerenderten Prompt **voranstellen** (analog zum
  bestehenden `_apply_custom_overrides`-Muster), damit er unabhängig vom Preset/Template immer
  greift:
  - YouTube-Pfad (Render ~Z.390, `template.render(video_title=…)`).
  - Transkript-Pfad (Render ~Z.474, `template.render(title=…, transcript=…)`).
  - Reihenfolge: Zeitanker gehört weit nach oben (rahmt die ganze Analyse). Wenn `_apply_custom_overrides`
    ohnehin einen Kopf voranstellt, den Zeitanker sinnvoll damit kombinieren (z.B. Zeitanker direkt
    unter einem etwaigen PFLICHT-MODUL-Kopf, aber vor „Analysiere …").
- `current_date` **locale-sicher** bauen (Windows hat oft keine deutsche Locale gesetzt): Tag +
  deutscher Monatsname aus einer kleinen Map + Jahr, z.B. `"4. Juli 2026"` aus `datetime.now()`.
  KEIN `locale.setlocale`/`strftime("%B")`-Verlass.

### PR 2 — Veröffentlichungsdatum (nur falls ohne Metadaten-Umbau machbar)
- Prüfen, ob `VideoInfo` (`src/config/defaults.py:50`) bereits ein Upload-/Veröffentlichungsdatum
  führt (yt-dlp liefert `upload_date`). **Wenn ja:** an `_build_temporal_anchor(video_published=…)`
  durchreichen (nur YouTube-Pfad). **Wenn nein:** für v1 **weglassen** — das aktuelle Datum allein
  behebt den Kernfehler. Kein Metadaten-Plumbing nur dafür aufbauen; als Follow-up notieren.
- Transkript-Modus: kein Video → **nur** aktuelles Datum (kein `video_published`).

## Constraints / Hinweise
- **Echte Fiktion nicht überschreiben:** die „es sei denn"-Klausel ist Pflicht — Satire/Fiktion/
  Musikanalysen sollen weiter als solche erkannt werden. Für Musik-Presets ist der Block harmlos,
  aber unschädlich.
- Kein Einfluss auf Zeichenlimit-Logik / FAKTENCHECK-Erzwingung (der Zeitanker ist zusätzlicher
  Kontext, kein Ersatz).
- Zeilenenden bewahren, keine Voll-Reformatierung (CRLF-Churn).
- Eigener kleiner PR, unabhängig von WordPress (#50) und Anthropic-Modellpflege.

## Definition of Done
- Der gerenderte Prompt (YouTube **und** Transkript, alle Presets) enthält den ZEITLICHER-RAHMEN-Block
  mit korrektem aktuellem Datum + Anti-Fiktions-Satz.
- Tests: (1) gerenderter Prompt enthält „Heute ist der {heutiges Datum}" und den Anti-Fiktions-Satz;
  (2) Transkript-Pfad enthält das aktuelle Datum, aber KEIN `video_published`; (3) locale-sicheres
  Datum (Test läuft unabhängig von der System-Locale). Bestehende Prompt-/Builder-Tests grün.
- Manuell (PO, optional): das Khamenei-Video erneut mit DeepSeek V4 Pro — die FRAMING sollte es nicht
  mehr als „fiktives Szenario" einstufen.
- Version: mit dem PO abstimmen (passt gut als Teil der laufenden 0.12.x-Reihe; nur EIN PR fasst
  APP_VERSION an — koordinieren mit WordPress/Anthropic).

## Arbeitsweise
Bei Unklarheit erst den PO (Thorsten) fragen. Nach Fertigstellung innehalten. Wortlaut des Blocks ist
Vorschlag — gern straffen, solange „reale aktuelle Berichterstattung, nicht Fiktion (außer selbst
gekennzeichnet)" erhalten bleibt.
