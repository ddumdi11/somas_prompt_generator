# SOMAS Prompt Generator

[![Buy Me a Coffee](https://img.shields.io/badge/Buy%20Me%20a%20Coffee-support-FFDD00?logo=buymeacoffee&logoColor=black)](https://www.buymeacoffee.com/ddumdi11)

> **S**ource **O**verview **M**apping **A**nd extraction **S**chema – Prompt Generator
>
> Eine Desktop-App zur automatischen Generierung und KI-gestützten Ausführung von SOMAS-Analyse-Prompts für YouTube-Videos und manuelle Transkripte.

---

## 🎯 Projektziel

Diese App automatisiert den Workflow zur Erstellung strukturierter Quellenanalysen nach dem SOMAS-Schema. Sie nimmt YouTube-URLs oder manuell eingefügte Transkripte entgegen, generiert fertige Prompts und kann diese direkt über integrierte KI-Modelle analysieren lassen.

---

## ✨ Features

### Aktuell (v0.14.1) — WordPress: Sicherheits-Vorwahl „Privat"

Der Sende-Dialog „An Blog senden" öffnete den Beitragsstatus bisher auf dem in den Settings gespeicherten Default (bei mir „Veröffentlichen") – ein versehentlicher Klick hätte sofort öffentlich gepostet.

- **Beim Öffnen immer „Privat"** – Der Status ist jetzt aus Sicherheitsgründen fest auf „Privat" vorgewählt, unabhängig vom Settings-Default. So landet jeder Beitrag erst unveröffentlicht im Blog und wird dort geprüft, bevor er manuell freigeschaltet wird
- **Manuell frei wählbar** – Im Dialog lassen sich Entwurf/Veröffentlichen/Ausstehend weiterhin auswählen; der Settings-Regler „Default-Status" bleibt unangetastet (steuert nur nicht mehr die Vorwahl)

### Seit v0.14.0 — KI-Kennzeichnung in allen Output-Formen

Seit **02.08.2026** gelten die Transparenzpflichten aus **Art. 50 EU AI Act**. SOMAS-Beiträge durchlaufen menschliche Prüfung, Quellenauswahl und redaktionelle Verantwortung und fallen damit unter die **Ausnahme (Art. 50(4))** – die Kennzeichnung ist also **freiwillige Transparenz**, keine Pflichterfüllung. Sie ist trotzdem überall an, so knapp wie möglich, und **immer aktiv** (kein Toggle: Transparenz ist Standard, nicht Option).

- **Eine Quelle der Wahrheit** – `src/core/ai_disclosure.py` liefert die Kennzeichnung in drei Formen (Text / Markdown / HTML), alle mit demselben Kerntext (Drift-Schutz per Konsistenztest)
- **Fuß-Platzierung überall** – LinkedIn bekommt **nur die Textzeile** (kein Icon-Linkmüll); Markdown-Export (Einzelanalyse **und** Modellvergleich) und WordPress bekommen zusätzlich das **EU-Basiszeichen „AI"** als Icon (Hotlink, mit `alt`-Text für Barrierefreiheit)
- **Auffindbar für künftige Gesetzesänderungen** – jede Einbaustelle trägt ein grepbares Tag: `grep "Art. 50"` findet in Sekunden das zentrale Modul und alle drei Integrationspunkte

### Seit v0.13.3 — 32k-Stage-Budget für OpenRouter + Token-Split im Log

Der Reasoning-Cap aus v0.13.2 wurde nachweislich korrekt gesendet, aber der DeepSeek-Upstream-Host **respektierte ihn nicht**: S1 verbrauchte erneut das volle Budget (~11,4k Reasoning, nur ~4,6k sichtbarer Content, `finish_reason=length`). Effort-Compliance ist bei wechselnden Hosts Glückssache – also braucht der Content schlicht mehr Luft, unabhängig von Host-Kooperation.

- **OpenRouter-Stage-Budget auf 32768** – Die Plus-Stufen-Calls (S1/S2/S4/S5) bekommen bei OpenRouter das doppelte Antwort-Budget (11,4–14,7k Reasoning + ~5–6k Content ≈ 21k Worst Case → 32768 lässt ~11k Reserve). Andere Provider bleiben bei 16384; der normale Analyse-Call unverändert. Der Reasoning-Cap bleibt aktiv (schadet nie, spart Geld bei Hosts, die ihn respektieren); das Trunkierungs-Gate bleibt Sicherheitsnetz. Die Provider-Entscheidung sitzt an der Qt↔Package-Naht – das `factcheck_plus`-Package bleibt provider-agnostisch
- **Token-Split im Debug-Log** – Alle 4 Clients füllen jetzt `tokens_input`/`tokens_output` aus dem `usage`-Objekt (standen bisher immer auf 0); OpenRouter/OpenAI zusätzlich den **Reasoning-Anteil** (`tokens_reasoning`, sonst leer). Damit lässt sich der Reasoning-Verbrauch verschiedener Modelle direkt vergleichen, statt ihn per Zeichen-Arithmetik zu schätzen

### Seit v0.13.2 — Reasoning-Cap für Stage-Calls

Faktencheck Plus S1 scheiterte bei DeepSeek V4 Pro (via OpenRouter) **trotz** des 16384-Budgets aus v0.13.1: Diesmal war nicht der Output zu groß, sondern das (durch `reasoning.exclude=true` unsichtbare) Modell-Reasoning fraß ~14,7k der ~16,4k Tokens – nur ~1,6k kamen als sichtbares JSON an, mitten im Objekt gekappt (`finish_reason=length`). Budget weiter zu erhöhen wäre ein Wettrüsten.

- **Reasoning gedeckelt, wo es nicht gebraucht wird** – Die strukturierten Stage-Calls (S1/S2/S4/S5) senden an OpenRouter jetzt einen **Effort-Cap** (`reasoning: {effort: "low", exclude: true}`). Die JSON-Extraktion braucht kein ausuferndes Reasoning; der normale Analyse-Call bleibt **ungecappt** (dort ist Reasoning erwünscht, und der v0.11-Gate+Retry-Pfad fängt Trunkierung ab)
- **`effort` statt Token-Budget – bewusst** – Das reale Zielmodell DeepSeek V4 ist auf OpenRouter effort-gesteuert; `effort` wird nativ verstanden, statt über die vage `max_tokens`→effort-Rückabbildung zu laufen. Nur OpenRouter wertet den Cap aus; die anderen Provider ignorieren ihn dokumentiert (Anthropic/OpenAI haben eigene Reasoning-Semantik → separater PR)
- **Spart nebenbei Geld** – Reasoning-Tokens werden berechnet; der Cap vermeidet bei reasoning-lastigen Modellen die verschwendeten Tokens (im Fehlerfall oben: ~14,7k Tokens für einen Fehlschlag)
- **Sicherheitsnetz bleibt** – Das Trunkierungs-Gate aus v0.13.1 greift weiterhin, falls ein Modell den Cap ignoriert

### Seit v0.13.1 — Faktencheck Plus: Trunkierungs-Härtung

Faktencheck Plus scheiterte bei claim-reichen Videos (21 Roh-Behauptungen) in Stufe 1 mit einer irreführenden Meldung („kein parsebares JSON-Array"). Wahre Ursache war eine **Trunkierung**, kein Formatfehler: Der S1-Output skaliert mit der Behauptungszahl und sprengte zusammen mit dem Modell-Thinking das Antwort-Budget – das JSON brach mitten im String ab, und der Reparatur-Retry lief mit demselben Budget deterministisch erneut ins Limit.

- **Ehrlicher Abbruch statt Reparatur-Schleife** – Die Stufen-Mechanik (S1/S2/S4/S5) prüft `finish_reason` **vor** der JSON-Extraktion. Bei einer abgeschnittenen Antwort bricht sie sofort mit klarer Meldung ab („Antwort abgeschnitten (Token-Limit) — vermutlich zu viele Behauptungen für das Antwort-Budget") – ohne den zwecklosen Reparatur-Retry
- **Trunkierung wird im Stage-Log sichtbar** – Der `finish_reason` erreicht jetzt das Debug-Log; zuvor stand dort immer `""` und verschleppte genau diese Diagnose
- **Mehr Antwort-Budget für die Stufen** – Die Plus-Stufen-Calls dürfen bis zu **16384** Tokens antworten (statt der globalen 8192). Die Erhöhung gilt **nur** für die Stufen-Calls, nicht global (OpenRouter/Perplexity pre-authen gegen `max_tokens`, HTTP 402); die Trunkierungs-Bremse bleibt als Sicherheitsnetz

### Seit v0.13.0 — Faktencheck Plus

Der bisherige Faktencheck prüfte, was **prüfbar** war. Faktencheck Plus prüft, was **prüfwürdig** ist: „Das ZDF ist öffentlich-rechtlich" ist perfekt prüfbar und trotzdem wertlos, wenn dafür die tragende strittige These ungeprüft bleibt. Optional zuschaltbar – der bisherige Weg bleibt unverändert erhalten.

- **Behauptungen werden zerlegt** – Ein gebündelter Claim („Laut Analyse 54–120 Mrd. €/Jahr, genannte Schätzung ~100 Mrd.") zerfällt in vier eigene Prüfeinheiten: Existiert die Quelle? Trägt ihre Methodik? Stimmt die Zahl? Ist die Zurechnung kausal? Ohne diese Trennung verschmelzen belegte und unbelegte Teile zu einem unauflösbaren „teilweise bestätigt"
- **„X sagt Y" wird getrennt geprüft** – Attributions- und Objekt-Claim bekommen eigene Verdikte. Ein belegtes Zitat ist kein belegter Sachverhalt
- **Auswahl nach Argumentgewicht, nicht nach Bauchgefühl** – Eine versionierte Policy (`relevance_policy_v1.json`) gewichtet Wichtigkeit × Recherchewert × Prüfbarkeit und wählt klassenweise aus (Kernclaims vor Subclaims vor Kontext). Deterministisch, ohne LLM: gleicher Input → gleiche Auswahl. Basisfakten werden nur gelistet, Meinungen gar nicht erst recherchiert
- **Ein Rechercheauftrag statt „Ist das wahr?"** – Jede ausgewählte Behauptung bekommt eine Recherchekarte mit konkreten Teilfragen, **Gegenhypothesen** (Riegel gegen Bestätigungsfehler), Quellenprioritäten und – wo vorhanden – dem **direkten Prüfziel** (arXiv-ID, Repo, offizielles Dokument) statt bloßer Suchbegriffe. Bei fremdsprachigem Gegenstand zusätzlich Suchbegriffe in der Originalsprache
- **Ein Call pro Behauptung** – Jede Behauptung bekommt ihr eigenes Token-Budget und einen gezielten Such-Seed, statt als Blob in einem Request unterzugehen. Scheitert ein einzelner Call, läuft der Rest weiter
- **Der Bericht weist die Auswahl aus** – Ein Transparenz-Block zeigt, wie viele Behauptungen extrahiert, atomisiert, recherchiert, übersprungen oder als Meinung markiert wurden – samt Policy-Version und Budget. Die App hat nichts „vergessen", sie hat nach Regeln priorisiert
- **Kosten** – Der Plus-Modus macht **3 + N** API-Calls statt 1 (N = Budget, Default 8). Verfeinerung, Gewichtung und Planung laufen über das Analyse-Modell, nur die Recherche über das Verifikationsmodell

> Grundlage: `specs/FAKTENCHECK_THEORIE.md` (Claim-Lehre, Priorisierungs-Policy, Verdikt-Taxonomie) und `specs/SOMAS_v0.13.0_SPEC_faktencheck_plus.md`.

### Seit v0.12.3

- **Perplexity-Verifikation mit mehr Belegtiefe** – Inhaltliche Perplexity-Anfragen nutzen jetzt die höchste Such-Tiefe (`search_context_size: "high"`, Default wäre „low"); dazu eine Verdikt-Leitplanke „Kern belegt, Detail offen → *teilweise bestätigt*", damit vorsichtige Modelle nicht pauschal auf „nicht überprüfbar" ausweichen (Caveat: mehr Quellen = höhere Request-Gebühr, nur Verifikationsstufe)
- **Faktencheck-Sortierung nach Argumentgewicht** – Überprüfbare Behauptungen werden nach argumentativem Gewicht und Recherchewert priorisiert (nicht nach bloßer Prüfbarkeit); leicht prüfbare Basisfakten landen mit `[Basisfakt]` am Listenende und blockieren keine Prüf-Slots mehr (Grundlage: `specs/FAKTENCHECK_THEORIE.md` §3, „prüfbar ≠ prüfwürdig")
- **Leer-Inhalt-Robustheit** – Eine leere Modellantwort (HTTP 200, aber Reasoning frisst das Token-Budget) läuft jetzt in denselben sichtbaren Auto-Retry wie eine Trunkierung statt in einen harten Fehlerdialog; der Abbrechen-Button greift auch **während** des Auto-Retrys
- **Anthropic-Direktmodelle aktualisiert** – Auswahl auf **Fable 5 / Opus 4.8 / Sonnet 5** gehoben (die beiden 4.6er bleiben als Kontinuität), Default weiterhin **Sonnet 4.6**; ein Konsistenztest hält Client- und Provider-Liste synchron
- **Zeitanker im Prompt (v0.12.1)** – Jeder Analyse-Prompt bekommt einen ZEITLICHER-RAHMEN-Block mit aktuellem Datum + Anti-Fiktions-Leitplanke, damit Modelle mit älterem Wissensstand reale aktuelle Ereignisse nicht als fiktiv einstufen

### Seit v0.12.0 — WordPress-Veröffentlichung

Sendet eine fertige SOMAS-Analyse direkt als Beitrag an eine selbstgehostete WordPress-Seite (REST-API). Da SOMAS eine Desktop-App ist, genügt HTTP Basic Auth mit einem **Application Password** – kein CORS, kein Plugin nötig.

- **Sende-Dialog** – Getrennte Felder für Intro / Analyse / Outro (Markdown), einstellbarer Status (Entwurf/Privat/Veröffentlichen/Ausstehend), Kategorie und Tags, plus HTML-Vorschau. Der Default-Status („Entwurf") kommt aus den Einstellungen
- **YouTube-Thumbnail als Beitragsbild** – Das Thumbnail des analysierten Videos wird in die Mediathek hochgeladen und als **echtes Beitragsbild** (featured image) gesetzt – nicht inline. Checkbox „YouTube-Thumbnail als Beitragsbild verwenden" (aktiv bei Video, ausgeblendet im Transkript-Modus). **Nicht fatal:** Schlägt der Bild-Upload fehl (z. B. fehlende Rechte), wird der Beitrag trotzdem gepostet – der Text ist wichtiger als das Bild
- **Sicher & lokal** – URL/Benutzer/Defaults in den Einstellungen, das Application Password im OS-Credential-Manager (wie die API-Keys)
- **Voraussetzungen** – WP-Benutzer mit Veröffentlichungsrecht (fürs Beitragsbild zusätzlich `upload_files`, also Autor/Admin) und ein Application Password. Security-Plugins wie **Wordfence** ggf. für REST-/Application-Password-Requests freischalten

### Seit v0.11.0 — Reasoning-Leak-Härtung

Behebt einen realen **Final-Answer-Leak**: Ein Modell kippte statt der Analyse seinen Denkprozess in die Antwort, verbrauchte damit das Token-Budget und wurde mitten im Satz abgeschnitten – heraus kam Notizen-Müll statt einer Analyse.

- **Reasoning bleibt draußen** – OpenRouter-Analysen senden `reasoning.exclude=true`: Das Modell denkt intern weiter (Qualität bleibt), gibt den Denkprozess aber nicht mehr zurück und verunreinigt den Analysetext nicht
- **Trunkierung wird sichtbar** – `finish_reason` wird durch alle Provider gereicht und protokolliert; eine bei der Token-Grenze abgeschnittene Antwort gilt **nicht** als gültige Analyse (statt eine halbe, „halb-plausible" Behauptungsliste anzuzeigen)
- **Struktur-Validator** – Prüft die Analyse positiv (Start mit `### FRAMING`, erwartete Abschnitte in Reihenfolge, bei Faktencheck die drei Sub-Header, keine abgeschnittene Nummerierung) – **ohne** legitime Analysen zu verwerfen, die zufällig Wörter wie „Prompt" im Text haben
- **Ein sichtbarer Auto-Retry** – Bei Leak/Trunkierung/fehlender Struktur wird **einmal** automatisch neu angefordert (abbrechbar). Bleibt es fehlerhaft, erscheint ein offener **„Modelllauf fehlgeschlagen"** – bewusst **keine** kosmetisch reparierte Scheinanalyse
- **Sauberer Faktencheck-Prompt** – Der erzwungene FAKTENCHECK-Modus enthält keinen Widerspruch mehr (volle Analyse **+** FAKTENCHECK als 5. Abschnitt); ein Final-Only-Zaun hält Arbeitsnotizen aus dem Output. Die Web-Verifikation (Stufe 2) startet **nur** auf einer gültigen, nicht-trunkierten Analyse

### Seit v0.10.1 — Faktencheck-Verifikation (gehärtet)

- **Zweistufige Faktenprüfung** – Das FAKTENCHECK-Modul trennt jetzt strikt **Meinungen**, **Interpretationen** und **überprüfbare Behauptungen** (relevanz-sortiert). Optional prüft danach ein web-fähiges Modell **nur die nackten Behauptungen** und liefert pro Behauptung **Verdikt + Quelle**
- **Halluzinations-Schutz** – In der Verifikation stehen **keine Meinungen** im Prompt – das Modell kann nicht durch rhetorische Sprache „verführt" werden. Zusätzlicher Riegel gegen erfundene Quellen (kann nicht belegt werden → Verdikt „nicht überprüfbar", Quelle „—")
- **4-stufige Verdikt-Skala** – bestätigt · teilweise bestätigt · widerlegt · nicht überprüfbar
- **Frei wählbares Verifikationsmodell** – ProviderModelPicker über alle 4 Provider; `:online`-Schalter für echten Web-Zugriff (OpenRouter); Web-Disclaimer, wenn kein bestätigter Web-Zugriff
- **Konfigurierbare Obergrenze** – Default 10 zu prüfende Behauptungen (app-seitig, deterministisch gekappt; `0 = unbegrenzt`); Meinungen/Interpretationen werden vollständig angezeigt
- **Sauberer Anhang** – Der Verifikationsabschnitt wird an die Analyse angehängt (Export enthält beide Teile); Stufe-2-Fehler ist nicht fatal (Analyse bleibt erhalten)
- **Unabhängigkeits-Riegel (v0.10.1)** – Das geprüfte Video selbst zählt nicht als Beleg; nur unabhängige externe Quellen bestätigen/widerlegen. „Verifikation erneut versuchen"-Button wiederholt **nur Stufe 2** (z. B. nach Modellwechsel auf ein stärkeres Web-Modell)

### Seit v0.9.0 — Modellvergleich

- **Zwei Analysen, ein Video** – Dasselbe YouTube-Video (oder Transkript) von zwei frei wählbaren Modellen nach dem SOMAS-Schema analysieren lassen. Gleiches Preset, gleiche Perspektive, gleiche Tiefe für beide – nur das Modell variiert (fairer Vergleich)
- **Automatische Synthese** – Ein drittes Modell erzeugt aus beiden Analysen eine neutrale Kurzbeschreibung (ein Absatz). Eingabe sind die vollständigen Analysetexte, nicht das Transkript
- **Provider-übergreifend** – Analyse-Modelle A/B und Synthese-Modell frei aus allen 4 Providern wählbar (Perplexity, OpenRouter, Anthropic, OpenAI)
- **Deterministisches Layout** – Die App baut das fertige Markdown-Dokument selbst (Jinja2): Titel + YouTube-Thumbnail, verwendete Modelle, Kurzbeschreibung, beide Analysen untereinander. Kein Format-Glücksspiel
- **Robuster Ablauf** – Sequenziell (Metadaten → Analyse A → Analyse B → Synthese → Render) mit Fortschrittsanzeige und Abbrechen. Synthese-Fehler ist nicht fatal (Platzhalter)
- **Export ohne Doppel-Header** – Das fertige Dokument wird direkt nach `exports/…_Modellvergleich.md` gespeichert (UTF-8-BOM, Pandoc-kompatibel) – ideal für die anschließende PDF-Erzeugung

### Seit v0.8.0 — Custom Prompt Editor

- **Prompt-Anpassung** – System-Prompt und Modul vor der Generierung anpassen ("Anpassen…"-Button). Benutzerdefinierte Anweisungen werden dem Template vorangestellt
- **Modul-Fixierung** – Eines der 6 Module fest wählen (PFLICHT-MODUL), Anti-Monotonie wird automatisch unterdrückt
- **Benutzerdefinierte Presets** – Auto-Save nach API-Analyse, JSON-Persistenz, Umbenennen/Löschen per Rechtsklick
- **Export-Branding** – Titel in LinkedIn- und Markdown-Export: "Analyse · SOMAS"

### Seit v0.7.0

- **Batch-Verarbeitung** – 2-5 YouTube-URLs in einem Durchlauf analysieren. Non-modaler Dialog mit Fortschrittsanzeige, Tab-basierte Ergebnisansicht, integrierte Bewertung pro Video, Crash-resistente Persistenz (JSON in %TEMP%)
- **Anthropic API (direkt)** – Claude-Modelle ohne Umweg über OpenRouter: Opus 4.6, Sonnet 4.6, Haiku 4.5
- **OpenAI API (direkt)** – GPT-4o, GPT-4o mini, o3, o4-mini über die Chat Completions API
- **4 API-Provider** – Perplexity (Web-Search), OpenRouter (200+ Modelle), Anthropic (direkt), OpenAI (direkt)

### Seit v0.6.0

- **Perspektive-Parameter** – Drei Analysehaltungen: Neutral-Deskriptiv, Kritisch-Analytisch, Empathisch-Rekonstruktiv. Jedes Preset hat einen Default, jederzeit manuell überschreibbar via UI-Dropdown
- **6 Analyse-Module** – Modulpool von 4 auf 6 erweitert: SUBTEXT (implizite Botschaften dekodieren) und FAKTENCHECK (überprüfungsbedürftige Aussagen priorisieren)
- **Modul-Statistik** – Gewähltes Modul wird pro Analyse in SQLite gespeichert (Schema v3, automatische Migration)
- **Anti-Monotonie** – Erkennt wenn 3x hintereinander dasselbe Modul gewählt wurde und gibt dem Modell einen Variationshinweis

### Seit v0.5.2

- **Bewertungs-Redesign** – Z-Skala (-2 bis +2) statt 1-5 Sterne, separater Kanal-Bewertungsdialog mit Fakten-/Argumentationsqualität, Bias-Spektrum (10 Richtungen), Modus-Tags (11 Kategorien), Freitext-Notizen
- **Kanal-Datenbank** – Eigene `channels`-Tabelle mit Schema-Versionierung und automatischer Migration
- **CSV Export/Import** – Kanal-Bewertungen als CSV exportieren/importieren (UTF-8-sig für Excel)
- **Kanal-Meta-Anzeige** – Bekannte Kanäle zeigen ihr Profil in den Metadaten (Toggle in Einstellungen)
- **Songstruktur-Preset** – Neues Preset für musikalische Formanalyse (Songform, Arrangements, Dynamik)

### Seit v0.5.0

- **Musik-Preset** – Eigenes 4-Teil-Schema für Songtext-Analysen (KONTEXT → SONGTEXT-ANALYSE → EINORDNUNG → BEWERTUNG)
- **Zeichenlimit-Kontrolle** – Traffic-Light-Counter, Sandwich-Technik im Prompt, Rework-Button zum Kürzen
- **Transkript-Disclaimer** – Automatischer STT-Hinweis für maschinelle Transkripte, geschlechtsneutrale Sprache, SOMAS-Selbstreferenz-Unterdrückung

### Seit v0.4.1

- **Kompaktes UI** – Einklappbare Sektionen (Metadaten, Zeitbereich) mit kompakter Zusammenfassung
- **Transkript-Brücke** – YouTube-Transkripte automatisch im Transkript-Tab verfügbar, editierbar
- **Smarte Prompt-Einbettung** – Verfügbare Transkripte werden direkt in den Prompt eingebettet (Modelle ohne Web-Zugriff analysieren tatsächlichen Inhalt)
- **Dual-Input-Modus** – YouTube-URL oder manuelles Transkript (Tab-basiert)
- **YouTube-Integration** – URL einfügen, Metadaten automatisch abrufen
- **Zeitbereich-Analyse** – Nur einen bestimmten Abschnitt des Videos analysieren (MM:SS oder HH:MM:SS)
- **Manuelles Transkript** – Podcasts, Vorträge, Interviews – jede Textquelle analysierbar
- **Integrierte KI-Analyse** – Ein-Klick-Analyse über API:
  - **Perplexity AI** – Sonar, Sonar Pro, Sonar Reasoning (Web-Search)
  - **OpenRouter** – 200+ Modelle (Claude, Gemini, GPT, Llama, DeepSeek...)
  - **Anthropic** – Claude direkt (Opus 4.6, Sonnet 4.6, Haiku 4.5)
  - **OpenAI** – GPT-4o, GPT-4o mini, o3, o4-mini direkt
  - Suchbare Modell-Liste mit dynamischer Preisanzeige
- **7 Prompt-Presets:**
  - **Standard** – Ausgewogene Analyse (2.800 Zeichen, ~2 Min Lesezeit)
  - **LinkedIn** – Social-Media-optimiert (2.200 Zeichen, ~90 Sek)
  - **Minimal** – Blitz-Überblick (800 Zeichen, ~30 Sek)
  - **Academia** – Wissenschaftlich (3.000 Zeichen, ~2,5 Min)
  - **Research** – Umfassende Tiefenrecherche (unbegrenzt)
  - **Musik** – Songtext-Analyse (2.400 Zeichen, ~75 Sek)
  - **Songstruktur** – Musikalische Formanalyse (Web-Search erforderlich)
- **Export-Formate:**
  - LinkedIn-optimiert (Unicode-Bold, Post-Header, Aufzählungen)
  - Markdown (.md)
- **Debug-Logging** – Session-Tracking mit Versionsinformation

### Nächste Schritte

- „Verifikation erneut versuchen"-Button (nur Stufe 2 wiederholen) — v0.10.1
- Einheitlicher Export-Kopf (Einzelanalyse mit Titel-Block + Thumbnail) — v0.10.1
- Wochentags-basierte Perspektive-Defaults (nach Recherche)
- Englisch-Support
- PDF-Export

---

## 🏗️ Architektur

```text
somas_prompt_generator/
├── main.py                 # Entry point
├── requirements.txt        # Dependencies
├── README.md              # Diese Datei
├── CLAUDE.md              # Instruktionen für Claude Code
│
├── src/
│   ├── gui/
│   │   ├── main_window.py      # Hauptfenster mit Tabs, Presets, API-Controls
│   │   ├── collapsible_section.py # Einklappbare UI-Sektionen
│   │   ├── model_selector.py   # FilterableModelSelector (OpenRouter)
│   │   ├── rating_widget.py    # Z-Skala Modell-Bewertung (-2 bis +2)
│   │   ├── channel_dialog.py   # Kanal-Bewertungsdialog (Fakten, Bias, Tags)
│   │   ├── settings_dialog.py  # Einstellungsdialog (API-Keys, CSV-Export)
│   │   ├── transcript_widget.py # Transkript-Eingabewidget
│   │   ├── batch_dialog.py     # Batch-Verarbeitung (2-5 URLs, non-modaler Dialog)
│   │   ├── prompt_edit_dialog.py # Prompt-Anpassungsdialog (System-Prompt + Modul)
│   │   └── provider_model_picker.py # Provider+Modell-Auswahl (3× im Modellvergleich)
│   │
│   ├── core/
│   │   ├── youtube_client.py   # YouTube-Metadaten via yt-dlp
│   │   ├── prompt_builder.py   # SOMAS-Prompt + Preset-Handling
│   │   ├── linkedin_formatter.py # Unicode-Bold, Post-Formatierung
│   │   ├── export.py           # Markdown-Export
│   │   ├── api_client.py       # API-Abstraktion (Provider-Routing)
│   │   ├── api_worker.py       # QThread-Worker für async API-Calls
│   │   ├── perplexity_client.py # Perplexity Sonar/Deep Research
│   │   ├── openrouter_client.py # OpenRouter (200+ Modelle)
│   │   ├── anthropic_client.py # Anthropic API (Claude direkt)
│   │   ├── openai_client.py    # OpenAI API (GPT/o-Series direkt)
│   │   ├── batch_item.py       # BatchItem/BatchConfig Datenmodelle
│   │   ├── batch_worker.py     # QThread-Worker für Batch-Verarbeitung
│   │   ├── batch_persistence.py # Crash-resistente Batch-Persistenz (JSON)
│   │   ├── rating_store.py     # SQLite-Bewertungsspeicher (Schema-Versionierung, Kanal-DB)
│   │   ├── user_preset_store.py # Benutzerdefinierte Presets (JSON-Persistenz)
│   │   ├── comparison_item.py  # ModelChoice/ComparisonConfig/ComparisonResult
│   │   ├── comparison_worker.py # QThread: 2 Analysen + Synthese + Layout-Render
│   │   ├── verification_item.py # VerificationConfig/VerificationResult (Faktencheck Stufe 2)
│   │   ├── verification_worker.py # QThread: Behauptungen verifizieren (Verdikt + Quelle)
│   │   └── debug_logger.py     # Debug-Logging
│   │
│   └── config/
│       ├── defaults.py         # VideoInfo, SomasConfig, TimeRange
│       ├── api_config.py       # API-Provider-Konfiguration
│       ├── prompt_presets.json  # 7 Preset-Konfigurationen
│       ├── api_providers.json   # Provider-Definitionen
│       ├── user_presets.json    # Benutzerdefinierte Presets
│       └── user_preferences.json # Benutzereinstellungen
│
├── templates/
│   ├── somas_prompt.txt        # Basis-Prompt-Template (Jinja2)
│   ├── somas_prompt_transcript.txt # Transkript-Template (mit STT-Disclaimer)
│   ├── somas_standard.txt      # Standard-Preset
│   ├── somas_linkedin.txt      # LinkedIn-Preset
│   ├── somas_minimal.txt       # Minimal-Preset
│   ├── somas_academia.txt      # Academia-Preset
│   ├── somas_research.txt      # Research-Preset
│   ├── somas_music.txt         # Musik-Preset (Songtext-Analyse)
│   ├── somas_songstruktur.txt  # Songstruktur-Preset (Formanalyse)
│   ├── somas_comparison.txt    # Modellvergleich-Dokumentlayout (Jinja2)
│   └── somas_verification.txt  # Faktencheck-Verifikation-Abschnitt (Stufe 2)
│
├── docs/                   # GitHub Pages Landing Page
│   ├── index.html
│   ├── style.css
│   └── assets/
│
└── tests/                  # Test-Analyse-Beispiele
```

---

## 🛠️ Tech Stack

| Komponente | Technologie | Begründung |
| ------------ | ------------- | ------------ |
| **GUI** | PyQt6 | Konsistent mit anderen Projekten (VidScaler, DocReducter) |
| **YouTube** | `youtube-transcript-api` | Leichtgewichtig, direkter Transkript-Zugriff |
| **YouTube Metadaten** | `yt-dlp` | Robuste Metadaten-Extraktion (Titel, Dauer, Thumbnail) |
| **Templates** | `Jinja2` | Flexible Prompt-Generierung mit Conditionals |
| **API-Calls** | `requests`, `anthropic`, `openai` | HTTP-Kommunikation mit Perplexity/OpenRouter + native SDKs für Anthropic/OpenAI |
| **Key-Storage** | `keyring` | Sichere API-Key-Verwaltung (Windows Credential Manager) |
| **Markdown** | Built-in | Keine externe Abhängigkeit |

---

## 📋 Abhängigkeiten

```txt
PyQt6>=6.4.0
youtube-transcript-api>=1.0.0
yt-dlp>=2024.1.0
Jinja2>=3.1.0
requests>=2.31.0
keyring>=24.0.0
anthropic>=0.40.0
openai>=1.50.0
```

---

## 🚀 Installation & Start

```bash
# Repository klonen (inkl. Submodul)
git clone --recurse-submodules https://github.com/ddumdi11/somas_prompt_generator.git
cd somas_prompt_generator
# Falls ohne --recurse-submodules geklont wurde:
# git submodule update --init --recursive

# Virtual Environment erstellen
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # macOS/Linux

# Dependencies installieren
pip install -r requirements.txt

# App starten
python main.py
```

### Optional: YouTube-Intake-Core

Für den (opt-in) YouTube-Intake-Service-Modus wird der Core aus dem Submodul
`external/youtube-intake-service` installiert — **nur der Core, ohne `[server]`-Extra**:

```bash
pip install ./external/youtube-intake-service
```

Danach in den Einstellungen „YouTube-Intake-Service (Core) verwenden" aktivieren.
Ohne diese Installation (oder bei deaktiviertem Toggle) nutzt SOMAS unverändert den
bisherigen direkten Weg (yt-dlp / youtube-transcript-api) — es ist also **optional**.
Nach einem Pin-Wechsel des Submoduls den Core neu installieren.

---

## 📖 Nutzung

### YouTube-Modus

1. **YouTube-URL eingeben** und "Get Meta" klicken
2. **Optional: Zeitbereich** aktivieren (Start/Ende im Format MM:SS oder HH:MM:SS)
3. **Preset wählen** (Standard, LinkedIn, Minimal, Academia, Research)
4. **"Generate Prompt" klicken** → SOMAS-Prompt wird generiert
5. **API-Automatik** → KI analysiert direkt (oder manuell kopieren)
6. **Export** → LinkedIn / Markdown

### Transkript-Modus

1. Auf **Tab "Transkript"** wechseln
2. **Titel, Autor** und **Transkript-Text** eingeben
3. **"Generate Prompt" klicken** → Analyse aus dem Transkript

### Batch-Modus

1. **"Batch" klicken** im Hauptfenster
2. **2-5 YouTube-URLs** einfügen (eine pro Zeile)
3. **Preset und Provider** wählen → Alle Videos werden sequenziell analysiert
4. **Ergebnisse** in Tabs anzeigen, einzeln bewerten und exportieren

### Modellvergleich-Modus

1. Im API-Bereich **"Zwei Modell-Analysen vergleichen"** aktivieren → Bereich "Modellvergleich" klappt auf
2. Für **Modell A, Modell B** und **Modell C (Zusammenfassung)** je Provider + Modell wählen
3. **YouTube-URL** eingeben (oder Tab "Transkript" nutzen), Preset/Perspektive wie gewohnt setzen
4. **"Modellvergleich starten"** → beide Analysen + Synthese laufen sequenziell, Fortschritt im Bereichs-Header
5. Das fertige Markdown erscheint im Ergebnisfeld → **"Export: Markdown"** speichert nach `exports/…_Modellvergleich.md`

### Faktencheck-Verifikation-Modus

1. Im API-Bereich **"Behauptungen verifizieren (Faktencheck Stufe 2)"** aktivieren → Bereich "Faktencheck-Verifikation" klappt auf
2. **Verifikationsmodell** wählen (web-fähig empfohlen, z. B. Perplexity Sonar; für OpenRouter das **`:online`-Häkchen** setzen)
3. Optional **Max. zu prüfende Behauptungen** anpassen (Default 10, `0 = unbegrenzt`)
4. **"Generate Prompt"** → die Analyse erzwingt das FAKTENCHECK-Modul; danach läuft **automatisch** die Verifikation
5. Der Abschnitt `### FAKTENCHECK · VERIFIKATION` (Verdikt + Quelle pro Behauptung) wird an die Analyse angehängt und mitexportiert

### API-Integration

- API-Keys werden sicher im System-Keyring gespeichert
- 4 Provider wählbar: Perplexity, OpenRouter, Anthropic, OpenAI
- Modellauswahl mit Suchfeld und Preisanzeige (OpenRouter)

---

## 📝 LinkedIn-Formatierung

LinkedIn unterstützt nur eingeschränkte Formatierung:

| Element | LinkedIn-Syntax | Beispiel |
| --------- | ----------------- | ---------- |
| **Fett** | Unicode-Zeichen | 𝗙𝗿𝗮𝗺𝗶𝗻𝗴 |
| *Kursiv* | Unicode-Zeichen | 𝘒𝘦𝘳𝘯𝘵𝘩𝘦𝘴𝘦 |
| Aufzählung | Bullet | - Punkt 1 |
| Zeilenumbruch | Doppelter Enter | |
| Emojis | Direkt | 📌 |

**Nicht unterstützt:** Markdown-Headers, Links mit Text, Code-Blöcke

---

## 📊 SOMAS-Schema

Die App implementiert das SOMAS-Framework mit Content-Type-spezifischen Analyse-Schemata:

### Standard-Schema (Vorträge, Interviews, Nachrichten)

1. **FRAMING** – Wer spricht, Format, Kontext
2. **KERNTHESE** – Zentrale Aussage/Position
3. **ELABORATION** – Vertiefung, Belege, Details
4. **IMPLIKATION** – Fazit, Empfehlung, Bedeutung
5. **[MODUL]** – Automatisch gewählt: Kritik · Zitate · Offene Fragen · Verbindungen · Subtext · Faktencheck
   - **FAKTENCHECK** trennt seit v0.10.0 Meinungen / Interpretationen / überprüfbare Behauptungen; die Behauptungen können optional in einer zweiten Stufe web-verifiziert werden (Verdikt + Quelle)

### Musik-Schema (Songtexte, Musikvideos)

1. **KONTEXT** – Künstler, Genre, Einordnung
2. **SONGTEXT-ANALYSE** – Thema, Erzählperspektive, sprachliche Mittel
3. **EINORDNUNG** – Genre-Vergleich, kulturelle Bezüge
4. **BEWERTUNG** – Stärken, Schwächen, Gesamteindruck

---

## 📜 Changelog

| Version | Datum | Änderungen |
| --------- | ------- | ------------ |
| 0.13.0 | 2026-07-15 | **Faktencheck Plus (argumentgewichtete Recherche)** – neue, optional zuschaltbare Strategie neben dem bisherigen Faktencheck (der unverändert bleibt). Fünfstufige Pipeline mit JSON-Verträgen zwischen den Stufen: **S1 ClaimRefiner** (Atomisierung in einzeln prüfbare Einheiten, verpflichtender Attributions-Split „X sagt Y" → Aussage + Sachverhalt, Normalisierung, Typisierung) → **S2 ArgumentMapper** (Argumentrolle, kontrafaktischer Impact, 11 Bewertungsdimensionen) → **S3 PolicyScorer** (deterministisch, **kein LLM**: Gates vor Scores, `Wichtigkeit × Recherchewert × Prüfbarkeit`, klassenweise Quoten statt Top-N; gleicher Input → gleiche Auswahl) → **S4 ResearchPlanner** (Recherchekarte je Claim: Teilfragen, **Gegenhypothesen**, Quellenprioritäten, kanonische Prüfziele wie arXiv-ID/Repo statt Suchbegriffen, Suchbegriffe in Originalsprache) → **S5 Recherche+Verdikt** (ein Call **pro** Claim = eigenes Token-Budget + gezielter Such-Seed; Einzelfehler nicht fatal). Gewichte/Gates/Quoten liegen versioniert in `src/config/relevance_policy_v1.json` – Policy als Konfiguration, nicht als Code. **Durchgesetzte Leitplanken** (nicht nur im Prompt erbeten): kein positives Teilverdikt ohne benannten belegten Teilclaim samt Quelle; das geprüfte Video zählt nie als Beleg (server-seitiger Eigenbeleg-Riegel über Video-ID/URL/Titel). Intern 8-stufige Verdikt-Taxonomie, im Bericht auf die 4 bekannten UI-Verdikte gemappt **plus** verpflichtende Begründungszeile mit dem internen Grund. Abschließender **Transparenz-Block** (extrahiert → atomisiert → recherchiert/übersprungen/dokumentiert, Policy-Version, Budget). GUI: Checkbox in der Verifikations-Sektion, die vorhandene SpinBox steuert im Plus-Modus das **Deep-Research-Budget** (Default 8), Fortschrittsanzeige je Stufe und je Claim, Abbruch zwischen den Claims mit gültigem Teilergebnis. *Caveat:* Plus macht **3 + N** API-Calls statt 1. Grundlagen: `specs/FAKTENCHECK_THEORIE.md`, `specs/SOMAS_v0.13.0_SPEC_faktencheck_plus.md` |
| 0.12.3 | 2026-07-12 | **Perplexity in der Verifikation konkurrenzfähiger:** Inhaltliche Perplexity-Calls setzen jetzt `web_search_options.search_context_size: "high"` (Default wäre „low", die oberflächlichste Such-Stufe) → deutlich mehr Quellen/Belegtiefe pro Anfrage; der reine Verbindungstest bleibt schlank. Zusätzlich eine Verdikt-Leitplanke im Verifikations-Prompt: **Kern belegt, Detail offen → „teilweise bestätigt"** (mit Benennung von Kern & offenem Detail) statt pauschal „nicht überprüfbar" – hebt vorsichtige Modelle (Sonar) näher an die Codex-Granularität. Bestehende Riegel und die 4 Verdikt-Werte unverändert. *Caveat:* höhere Such-Tiefe = mehr Quellen = höhere Perplexity-Request-Gebühr (nur die optionale Verifikationsstufe) |
| 0.12.2 | 2026-07-12 | **Faktencheck Stufe 1 – Basisfakt-Markierung & argumentgewichtete Sortierung:** Behauptungen werden nach argumentativem Gewicht/Recherchewert geordnet (nicht nach Prüfbarkeit), leicht prüfbare Basisfakten (biografisch/lexikalisch/institutionell) landen mit Suffix `[Basisfakt]` am Listenende und werden von der Verifikation ausgeschlossen (auch bei „unbegrenzt"), zählen nicht gegen die Cap; reine Zusatzheuristik (ohne Suffix unverändert). Grundlage: `specs/FAKTENCHECK_THEORIE.md` §3 (prüfbar ≠ prüfwürdig). — **Leer-Inhalt-Robustheit:** Ein Leer-Inhalt (HTTP 200, aber Content leer, weil Reasoning das Token-Budget verbrennt) durchläuft jetzt denselben Eskalationspfad wie eine Trunkierung – 1× sichtbarer Auto-Retry, dann offener „Modelllauf fehlgeschlagen" (Fehlertext inkl. `finish_reason` bleibt erhalten) statt sofortigem harten Fehlerdialog; der Abbrechen-Button greift auch während des Auto-Retrys; Debug-Log führt bei Leer-Inhalt den echten HTTP-Status (200) statt Default-500. — **Anthropic-Direktmodelle aktualisiert:** Fable 5 / Opus 4.8 / Sonnet 5 ergänzt (Opus 4.6 & Sonnet 4.6 bleiben als Kontinuität), Default weiterhin `claude-sonnet-4-6`; Client-Liste (`anthropic_client.MODELS`) und `api_providers.json` per Konsistenztest synchron gehalten |
| 0.12.1 | 2026-07-04 | Zeitanker im Prompt: jeder Analyse-Prompt (YouTube + Transkript, alle Presets) bekommt einen ZEITLICHER-RAHMEN-Block mit aktuellem (locale-sicherem) Datum + Anti-Fiktions-Leitplanke – Modelle mit älterem Wissensstand stufen reale aktuelle Ereignisse nicht mehr fälschlich als fiktiv/dystopisch ein (echte Fiktion/Satire/Musik bleibt unberührt) |
| 0.12.0 | 2026-07-04 | WordPress-Veröffentlichung: Analyse als Beitrag senden (Intro/Analyse/Outro, Status/Kategorie/Tags, HTML-Vorschau) + YouTube-Thumbnail als **Beitragsbild** (featured image, Media-Upload mit Fallback-Kette maxres→hq→sd, nicht-fatal). App-Password im OS-Keyring; Voraussetzung `upload_files` + ggf. Wordfence-Freigabe |
| 0.11.0 | 2026-07-02 | Reasoning-Leak-Härtung: OpenRouter `reasoning.exclude=true` (Denkprozess bleibt intern), `finish_reason` durchgereicht + geloggt + als harter Trunkierungs-Gate, preamble-scoped Struktur-/Trunkierungs-Validator, ein sichtbarer + abbrechbarer Auto-Retry statt Scheinanalyse („Modelllauf fehlgeschlagen"), FAKTENCHECK-Prompt-Widerspruch aufgelöst + Final-Only-Zaun, Iran-Leak als Test-Fixture |
| 0.10.1 | 2026-06-16 | Faktencheck-Härtung: Unabhängigkeits-Riegel (kein Eigenbeleg durchs Video, `source_hint` injection-sicher), „Verifikation erneut versuchen"-Button (nur Stufe 2, Modellwechsel), Perplexity-Modelle aktualisiert (`sonar-reasoning-pro`/`sonar-deep-research`), `DEFAULT_MAX_TOKENS=8192` (HTTP-402-Fix), einheitlicher Export-Kopf (Titel + Thumbnail), Zeichenlimit-Fix bei FAKTENCHECK |
| 0.10.0 | 2026-06-14 | Faktencheck-Verifikation (Hybrid): Stufe 1 trennt Meinungen/Interpretationen/Behauptungen; optionale Stufe 2 verifiziert Behauptungen per web-fähigem Modell (Verdikt + Quelle, 4-stufige Skala), Halluzinations-Schutz + Riegel gegen erfundene Quellen, `:online`-Schalter, Top-N-Kappung, Auto-Anhang |
| 0.9.1 | 2026-05-30 | Fix: leeren/None-Content der Provider (z.B. OpenRouter `tencent/hy3-preview`) sauber als Fehler behandeln statt Crash; `reasoning`-Fallback + `finish_reason`-Diagnose; alle 4 Clients abgesichert; Regressionstest |
| 0.9.0 | 2026-05-29 | Modellvergleich: zwei SOMAS-Analysen eines Videos + automatische Synthese-Kurzbeschreibung, deterministisches Markdown-Layout (Thumbnail), ProviderModelPicker, Export nach exports/ |
| 0.8.0 | 2026-03-30 | Custom Prompt Editor (System-Prompt + Modul anpassen), Benutzerdefinierte Presets (Auto-Save, Rename, Delete), Export-Branding "Analyse · SOMAS" |
| 0.7.0 | 2026-03-08 | Batch-Verarbeitung (2-5 URLs), Anthropic API direkt, OpenAI API direkt, 4 Provider |
| 0.6.0 | 2026-03-01 | Schema-Erweiterung: Perspektive-Parameter (3 Haltungen), Modulpool 4→6 (SUBTEXT, FAKTENCHECK), Modul-Statistik, Anti-Monotonie |
| 0.5.2 | 2026-02-20 | Bewertungs-Redesign (Z-Skala, Kanal-Dialog, CSV Export/Import, Meta-Toggle), Songstruktur-Preset |
| 0.5.0 | 2026-02-14 | Musik-Preset, Bewertungssystem (Sterne+Daumen), Zeichenlimit-Kontrolle (Counter, Sandwich, Rework), Transkript-Disclaimer, Stale-State-Fix |
| 0.4.1 | 2026-02-07 | UI-Redesign (Collapsible Sections), Transkript-Brücke, Transkript-Einbettung in Prompts |
| 0.4.0 | 2026-02-03 | Zeitbereich-Analyse, Manuelles Transkript, Tab-basierte Eingabe, Landing Page v0.4.0 |
| 0.3.1 | 2026-01-31 | FilterableModelSelector, OpenRouter-Suchfeld mit Filtern |
| 0.3.0 | 2026-01-29 | API-Integration (Perplexity + OpenRouter), Debug-Logger, Research-Preset |
| 0.2.0 | 2025-01-28 | Prompt-Presets (4 Varianten), LinkedIn-Export mit Post-Header |
| 0.1.0 | 2025-01-26 | Initial MVP – URL-Eingabe, Metadaten, Prompt-Generierung |

---

## 🔗 Verwandte Projekte

- **VidScalerSubtitleAdder** – PyQt6-basiertes Video-Tool
- **DocReducter** – PDF-Verarbeitungstool

---

## 📄 Lizenz

MIT - Open Source – Thorsten Diederichs
