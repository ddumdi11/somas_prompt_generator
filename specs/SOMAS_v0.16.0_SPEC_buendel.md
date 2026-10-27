# SOMAS v0.16.0 — Spec: Quellenbündel-Modus, Stufe 1

**Status:** Zur Abstimmung (SOMAS-Architekt, 2026-10-26) · **Grundlage:**
„Bündelformat v1" des Projekts `youtube_video_sammelextraktion_fuer_posts`
(Fassung 26.10.2026, von Thorsten freigegeben) + Architekten-Review vom selben
Tag · **Scope:** Teil-B-Stufe 1 (B1–B5). Die Paketierung dahinter:

| Paket | Inhalt |
|---|---|
| **v0.16.0 (diese Spec)** | Bündel-Template + Checkbox + Rahmung-Feld (B1, B2, B3, B5); Fragenfeld-Reset als genereller Fix (B4) |
| v0.16.x (eigene Spec) | B9 (neutrale Planner-Kernthese, generalisiert) · B6 + B7-light + Datei-Eingang im A6-YAML-Format |
| Spec-Runde 2 | Stufe 3 (B10–B14), zusammengeführt mit der internen Tuning-Liste |

---

## 1 Leitentscheidungen (PO-bestätigt)

1. **Checkbox statt Preset:** „Bündel" ist eine Eigenschaft der *Eingabe*, kein
   *Ausgabestil*. Neue **Checkbox „Quellenbündel" im Transkript-Tab** (Default
   aus). Das Varianten-Dropdown (Standard, Academia, …) bleibt frei
   kombinierbar — die Bündel-Proben liefen mit Academia, genau diese
   Kombination muss erhalten bleiben. KEIN achtes Preset.
2. **Eingabe bleibt die Textfassung** (Bündelformat Teil A2) über das
   Transkript-Feld. Der Datei-Eingang (A6-YAML) kommt erst mit dem B6-Paket —
   eine strukturierte Legende lohnt erst, wenn die Stufen sie konsumieren.
3. **Was ab v0.16.0 noch ins Textfeld gehört:** Quellenlegende (Q), ggf.
   Ursprungsdokumente (D) und die Abschnitte 1/3/4/5/6. **Nicht mehr:** die
   Lesehilfe (L — wird Template-Instruktion, Kern von B1) und die Rahmung
   (R — wandert ins neue Feld). Dieser Satz gehört sinngemäß in README und
   in die Antwortnotiz ans Nachbarprojekt.

## 2 GUI (Transkript-Tab)

- Checkbox **„Quellenbündel"**; bei Aktivierung erscheint darunter das
  mehrzeilige, optionale Feld **„Rahmung / Leitfrage"** (Platzhaltertext nach
  A5-Muster: Klammer · Leitfrage als Frage · Beobachtungsauftrag).
- Checkbox-Zustand ist Lauf-bezogen (keine Preference-Persistenz in v1).
- `video_info_source` bleibt `"transcript"`; alle bestehenden
  Ausschluss-/Race-Regeln gelten unverändert.
- **B4 als genereller Stale-State-Fix** (Fortsetzung der v0.5.0-Linie, betrifft
  ALLE Nutzer): Das Fragenfeld UND das neue Rahmung-Feld werden beim
  Quellenwechsel zurückgesetzt. **Konkrete Regel (Abstimmung 26.10.):** Reset
  beim Laden eines neuen Videos und beim **Ersetzen eines nicht-leeren
  Transkripts**; das Erst-Einfügen in ein leeres Transkript-Feld resettet
  NICHT — eine vorab geschriebene Rahmung/Frage geht dadurch nie verloren.
  Zurücksetzen statt Warnung — Beleg: Probe 7, zweimal unbemerkt gefülltes
  Fragenfeld.

## 3 Template `somas_prompt_bundle.txt`

Basis-Template-Tausch an der Build-Naht: `build_prompt_from_transcript`
erhält die Bündel-Flagge + den Rahmung-Text und rendert das Bündel- statt des
Transkript-Basis-Templates. Presets/Overrides/Zeitanker liegen unverändert
darüber (gleiche Mechanik wie heute — forget-proof bleibt forget-proof).

Inhalte des Templates:

- **Lesehilfe als Instruktion** (B1), generisch formuliert nach A4-Muster:
  Der folgende Text ist ein Quellenbündel, nicht das Transkript eines
  Beitrags; Gegenstand ist das Ereignis; Prüfgegenstand ist der Inhalt der
  Sachbehauptungen (Abschnitte 3/4/5), nicht ob eine Quelle sie genannt hat;
  Angaben über Quellen (Legende) dienen nur der Einordnung; Übereinstimmung
  bei gemeinsamem Ursprung ist Wiedergabe, keine Bestätigung. (Die
  bündelspezifischen Details — n Quellen, Anker, D-Liste — stehen weiter im
  Bündeltext selbst; das Template instruiert generisch.)
  **Bündelhinweise-Zeile** (Abstimmung 26.10.): Bündelspezifische Hinweise
  (gemeinsamer Ursprung, nur ein Lager, Dokumente nicht verwechseln) stehen
  künftig als Zeile „Bündelhinweise:" am Anfang der Quellenlegende Q; die
  Template-Instruktion verweist darauf und stellt klar, dass diese Zeile
  Lesehilfe ist — keine Behauptung, keine Interpretation.
- **Kein STT-Disclaimer**; „Sprecher/Wer spricht"-Formulierungen durch
  Bündel-Formulierungen ersetzt (B1).
- **Absatzvorgaben gelten nicht für den FAKTENCHECK-Abschnitt** (B1).
- **B5-Anweisung mit Vorrangregel** (Abstimmung 26.10., geschärft):
  Quellenkürzel (`[Q1]`) und Kanalnamen aus der Legende nicht in
  Sachbehauptungen übernehmen — im Bündelmodus hat das **Vorrang vor dem
  Attributions-Hinweis des FAKTENCHECK-Formats** (der erzeugte in den Proben
  „laut Q2"/„Kulinski behauptet"). **Scope-Schärfung:** Der Vorrang gilt NUR
  für die bündel-eigenen Quellen (Q1…Qn, Kanalnamen). Attributionsaussagen
  über Akteure IM Ereignis („Musk sagte X") und Zuschreibungen an
  Ursprungsdokumente (A3.3, zweistufige Prüfung) bleiben unverändert
  attributions-pflichtig.
- **Rahmung-Block** (nur wenn Feld gefüllt), nach A5-Semantik gekennzeichnet:
  „Deutung des Kurators — nicht prüfbar, keine Quelle, nicht als Behauptung
  oder Interpretation extrahieren; dient der Fokussierung der Analyse."
  Beleg Probe 7: Bündel-Rahmung leckt nicht in Interpretationen,
  Fragenfeld-Rahmung schon — deshalb das eigene Feld (B3).
- **B2 — keine Normalisierung:** Zeilenumbrüche und führende Nummern des
  Bündeltexts bleiben erhalten (Verweise wie „Abschnitt 4" müssen tragen).
  Gegen den bestehenden Transkript-Builder prüfen; als Testfall fixieren.
- Zeitanker (Phase 15/30) bleibt aktiv (`video_published=None` im
  Transkript-Modus — die Bündel-Regel A3.4 „absolute Daten" kompensiert).

## 4 Verträglichkeit

- FAKTENCHECK-Erzwingung, Verifikation (Classic + Plus), Chunking,
  KI-Kennzeichnung: unverändert — der Bündel-Modus ändert nur den Basis-Prompt.
- Modellvergleich mit Transkript-Eingabe erbt den Bündel-Modus über denselben
  Builder (erwünschter Nebeneffekt, als Testfall dokumentieren). Batch ist
  URL-basiert und nicht betroffen.
- **Regression (wichtigste):** Transkript-Lauf OHNE Checkbox bleibt
  byte-identisch zu heute.

## 5 Tests (offline)

1. Checkbox aus → Prompt byte-identisch zu v0.15.3 (Regression).
2. Checkbox an → Bündel-Template: Lesehilfe-Instruktion präsent, kein
   STT-Disclaimer, B5-Anweisung präsent, FAKTENCHECK-Absatzvorgaben-Ausnahme.
3. Rahmung gefüllt → gekennzeichneter Block; leer → kein Block, kein „None".
4. Preset-Kombination: Academia-Overlay (Limit, Perspektive) über
   Bündel-Template; erzwungener FAKTENCHECK koexistiert; Zeitanker präsent.
5. B2: Bündeltext mit Nummerierung/Umbrüchen übersteht den Build unverändert.
6. B4: Fragen- und Rahmung-Feld werden bei Quellenwechsel geleert (Video UND
   Transkript-Ersetzung); **Erst-Einfügen in leeres Feld resettet NICHT**
   (Rahmung-zuerst-Workflow); Regression: Felder bleiben bei bloßem
   Preset-Wechsel.
7. GUI: Rahmung-Feld nur sichtbar bei aktiver Checkbox.
8. B5-Vorrang: Bündel-Fixture mit `[Q1]`-Kürzeln → FAKTENCHECK-Anweisungen
   enthalten die Vorrangregel (keine Q-/Kanal-Attribution), während die
   Attributions-Pflicht für Ereignis-Akteure und Ursprungsdokumente im Prompt
   erhalten bleibt.
9. Lesehilfe-Instruktion verweist auf die „Bündelhinweise:"-Zeile der Legende
   (als Lesehilfe gekennzeichnet, nicht als Behauptung/Interpretation).

## 6 Nicht in v0.16.0

B6–B9 (Stufen-Kontext, Planner-Neutralität), A6-YAML-Parser/Datei-Eingang,
B10–B14 (Vertragsänderungen), Lesehilfe-Parametrisierung ({n}, Anker aus
strukturierter Eingabe — kommt mit A6). Umsetzungsreihenfolge siehe Kopf.

## 7 Definition of Done

- `APP_VERSION` → 0.16.0, README (Feature-Absatz + Changelog), CLAUDE.md
  (Architekt, nach Merge).
- PO-Realtest: ein Bündel aus den Proben (Textfassung OHNE L/R, Rahmung im
  Feld) mit Academia + Faktencheck Plus — **zweimal: einmal MIT, einmal OHNE
  Rahmung** (Wunsch Nachbarprojekt: Vergleichsbasis für das B9-Paket, da die
  Rahmung bis B9 über die Kernthese weiter auf den Planner wirkt, Probe 7).
  Erwartung gegenüber den Proben: keine „Compiler deutet …"-Interpretationen,
  keine Attributions-Recherchen zu `[Q1]`-Kürzeln, Rahmung erscheint nicht als
  Behauptung/Interpretation.
