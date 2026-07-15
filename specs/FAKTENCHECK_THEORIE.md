# Faktencheck: Theorie & Methodik

**Version:** 0.3 · **Stand:** 2026-07-14 · **Status:** LEBENDES DOKUMENT

> Referenzdokument für alle Faktencheck-Entscheidungen im SOMAS Prompt Generator.
> Die Theoriepflege (Begriffsarbeit, Prüflogik, Diskursmethodik) lebt als Nebenstrang
> im Schwesterprojekt Abbild-Werkstatt; das jeweils aktuelle Destillat wird hier
> versioniert abgelegt. Implementierungs-Specs (v0.10.x, v0.13.x, …) richten sich an
> diesem Dokument aus — bei Widerspruch gilt: Theorie hier klären, DANN Spec ändern.
>
> Hauptquellen v0.1: Perplexity-Erörterung 2026-07-11
> (`notizen/Faktencheck-Eroerterung_Perplexity_2026-07-11md.md`, mit AFC-Literatur),
> Merkzettel D1–D10 (`specs/MERKZETTEL_v0.10.1_offene_punkte.md`), Realtest-Empirie
> der App (Stand v0.12.1).

---

## 1. Einordnung: Automated Fact-Checking (AFC)

Die Forschungsstandard-Pipeline des Automated Fact-Checking lautet:

```text
Claim Detection → Check-worthiness → Evidence Retrieval → Claim Verification
                                                          (Verdict + Justification)
```

SOMAS erweitert dieses Modell um eine **vorgelagerte Diskursanalyse** (Framing,
Kernthese, Elaboration, Implikation, Subtext). Das Sechs-Ebenen-Modell:

| Ebene | Aufgabe | AFC-Entsprechung |
| ----- | ------- | ---------------- |
| 1 | SOMAS-Zerlegung (Diskurs-/Framing-Analyse) | vorgelagert, kein AFC-Standard |
| 2 | Extraktion & Kategorisierung: Meinung / Interpretation / Behauptung | Claim Detection & Extraction |
| 3 | Sortierung der überprüfbaren Behauptungen nach definierter Policy | Check-worthiness Detection |
| 4 | Rechercheaufträge je Behauptung erstellen | Query Planning |
| 5 | Online-Recherche, Evidenz sammeln | Evidence Retrieval, Claim Matching |
| 6 | Verdikt anhand der Evidenz, mit Begründung | Verdict Prediction + Justification |

**Grundsatz-Invariante:** Die Diskursanalyse (Ebene 1) erklärt, *warum* ein Claim
relevant oder potenziell irreführend ist — sie darf aber **niemals das Verdikt
beeinflussen**. Aus vermutetem Framing folgt keine Unwahrheit einer Behauptung.

Realistische Selbstbeschreibung: Das System ist ein **AI-assisted Evidence
Assessment**, kein vollautomatischer Wahrheitsentscheid. Claim-Auswahl,
Evidenzgewinnung und Begründung sind getrennte, je fehleranfällige Aufgaben.

---

## 2. Claim-Lehre

### 2.1 Claim-Typen

Mindestens sechs Klassen — verhindert, dass Nicht-Prüfbares ein Tatsachenverdikt bekommt:

| Typ | Beispiel | Prüfmodus |
| --- | -------- | --------- |
| Harte Tatsachenbehauptung | „Die Inflation lag 2025 bei 3 %." | direkt verifizierbar |
| Quantitative Behauptung | „Die Kriminalität hat sich verdoppelt." | Daten, Zeitraum, Bezugsgröße |
| Kausale Behauptung | „Maßnahme X verursachte Y." | Kausalevidenz, Alternativerklärungen |
| Prognose | „Das führt nächstes Jahr zu Rezession." | nicht wahr/falsch; Plausibilität/Quellenlage |
| Interpretation | „Das ist ein politischer Erfolg." | kein Tatsachenverdikt |
| Meinung / Werturteil | „Das ist unverantwortlich." | ausweisen, nicht prüfen |

### 2.2 Atomisierung

Jeder Claim mit mehreren Teilbehauptungen wird in **atomare Prüfeinheiten** zerlegt.
Referenzbeispiel (IRGC-Realtest): „Kosten laut zitierter Analyse 54–120 Mrd. €/Jahr,
genannte Schätzung ~100 Mrd." enthält mindestens vier Prüfeinheiten:

1. *Quellenexistenz* — es gibt eine identifizierbare Analyse mit dieser Schätzung.
2. *Methodik* — die Methode trägt eine jährliche Gesamtschätzung für Europa.
3. *Quantität* — die Analyse nennt ~100 Mrd. €/Jahr.
4. *Kausalzurechnung* — die Kosten sind der IRGC ursächlich zurechenbar.

Ohne Atomisierung entstehen unauflösbare „teilweise bestätigt"-Verdikte, weil
belegte und unbelegte Teile im selben Claim verschmelzen.

### 2.3 Attribution vs. Objekt-Claim

Strikt trennen:

- **Attributions-Claim:** „Organisation A erklärte, X sei geschehen." → prüfbar über
  Existenz des Originalstatements.
- **Objekt-Claim:** „X ist geschehen." → braucht unabhängige Belege.

Ein bestätigter Attributions-Claim darf beim Leser nie wie eine Bestätigung des
Sachverhalts wirken (eigenes Verdikt: „Aussage belegt, Sachverhalt offen").

### 2.4 Claim-Klassen (Arbeitsklassen für die Priorisierung)

| Klasse | Bedeutung | Behandlung |
| ------ | --------- | ---------- |
| A: Kernclaim | trägt die Hauptthese | immer Deep Research, Primärquellen + Gegenrecherche |
| B: Tragender Subclaim | sichert zentrale Schlussfolgerung | Deep Research |
| C: Kontextclaim | Hintergrund/Einordnung | nur bei freier Kapazität |
| D: Basis-/Metadatenclaim | Allgemeinwissen, Biografie, Lexikonfakt | kein Deep Research; allenfalls Schnellprüfung |

Klassifizierung erfolgt **vor** jeder numerischen Priorisierung — sonst überholt ein
leicht prüfbarer D-Claim einen A-Claim.

### 2.5 Argumentgewicht

Leitfrage pro Claim (kontrafaktischer Test):

> Welche Schlussfolgerung des Ausgangstexts würde geschwächt, verändert oder
> unhaltbar, wenn dieser Claim falsch wäre?

Ergebnis ist ein kleiner Argument-Abhängigkeitsgraph (Kernthese ← tragende
Subclaims ← Kontext/Beispiele). Ein wahres, aber nicht tragendes Beispiel (z. B.
Einzelbeschlagnahmung) belegt keine quantitative Kernthese — das Verdikt muss die
geringe Tragweite ausweisen können.

---

## 3. Kernprinzip: prüfbar ≠ prüfwürdig

**Die zentrale Fehlerquelle beobachteter Fehlallokation:** Ein Priorisierer, der
faktische *Prüfbarkeit* mit *Recherchewürdigkeit* verwechselt, verschwendet
Recherchebudget auf Selbstverständliches, während erkenntnisträchtige Claims
unten aus der Liste fallen.

Drei empirisch belegte Fehlmodi (Realtests der App, 07/2026):

1. **Prüfbar ist nicht prüfwürdig:** „Das ZDF ist öffentlich-rechtlich" ist perfekt
   prüfbar, aber ohne Erkenntnisgewinn.
2. **Hintergrund verdrängt die tragende These:** korrekte historische Basissätze
   fressen die Recherche-Slots des eigentlichen Prüfgegenstands (z. B. Wortlaut und
   Rechtsstatus eines behaupteten aktuellen Abkommens).
3. **Attribution wird mit Tatsachenbehauptung verwechselt** (siehe 2.3).

---

## 4. Priorisierung: Policy statt Bauchgefühl

### 4.1 Zwei getrennte Scores

Relevanz wird nicht als ein diffuser Wert, sondern als Produkt getrennter
Dimensionen bestimmt:

```text
ResearchPriority = ClaimImportance × ResearchValue × Checkability
```

**ClaimImportance** („Würde sich die Kernaussage ändern, wenn der Claim falsch
wäre?"): These-Nähe, Schlussfolgerungsabhängigkeit, Schadenspotenzial,
Reichweite/Mobilisierung, Konkretheit.

**ResearchValue** („Lohnt knappe KI-Recherchekapazität genau hierfür?"):
Nicht-Trivialität, Neuheit/Aktualität, Streitigkeit, Quellenzugang, Evidenzlücke,
Diskrepanzpotenzial (überraschend präzise/große Zahlen sind besonders fehleranfällig).

Ein Claim kommt nur in die Deep-Research-Auswahl, wenn er in **beiden** Dimensionen
ausreichend hoch liegt.

### 4.2 Harte Gates (vor jedem Scoring)

```text
Gate 1: Externe Tatsachen-/Zahlen-/Kausal-/Dokumentbehauptung?
        Nein → Meinung/Deutung markieren, nicht recherchieren
Gate 2: Relevant für Kernthese, tragende Argumentation oder Schadenspotenzial?
        Nein → Kontextclaim, nur dokumentieren
Gate 3: Trivial bzw. mit einer kanonischen Quelle auflösbar?
        Ja → Basisfakt/Schnellprüfung, kein Deep-Research-Slot
Gate 4: Attributionsbehauptung?
        Ja → Attributions- und Objekt-Claim getrennt ausgeben
Gate 5: Zu vage?
        Ja → operationalisieren oder als „nicht ausreichend präzise" ausweisen
```

### 4.3 Quoten statt reiner Top-X

Eine reine Top-X-Liste kann von 30 leichten Randdetails geflutet werden.
Budgetrichtwerte:

- 50–60 % Kernclaims der Hauptthese
- 20–30 % tragende Subclaims und Kausalbrücken
- 10–20 % Gegenhypothesen, relevante Auslassungen, Kontext
- ≤ 10 % Basis-/Plausibilitätschecks
- 0 % Off-Topic-Claims (separate Nachrichtensegmente ggf. als eigener Abschnitt
  mit eigenem Budget)

### 4.4 Policy als Code

Gewichte, Quoten, Ausschlüsse und Schwellen wählt **nicht das Modell**, sondern eine
versionierte, deterministische Konfiguration (z. B. `relevance_policy_v1.json`).
Jede Auswahl ist auditierbar: Score-Komponenten + Policy-Version + Begründung werden
mit ausgegeben. So lässt sich die Auswahlpolitik ändern, ohne die Pipeline umzubauen.

---

## 5. Recherche

### 5.1 Rechercheauftrag pro Claim (nicht „Ist das wahr?")

Offene Wahrheitsfragen erzeugen Bestätigungsfehler; ein Claim-Blob als Such-Seed
findet bei Nischenthemen nichts Relevantes (empirisch: Sonar-Totalausfall beim
„OpenRouter Fusion"-Test). Stattdessen bekommt jeder ausgewählte Claim eine
**Recherchekarte**: normalisierte Entitäten, Zeitraum, Claim-Typ, konkrete
Recherchefragen, **Gegenhypothesen**, bevorzugte Quellenklassen, verbotene
Abkürzungen (Snippet als Beleg, unbelegte Sekundärquelle als alleinige Evidenz),
geforderte Evidenzarten (Methode, Abgrenzung, Zurechnung, unabhängige Bestätigung).

**Sprachdimension:** Liegt der Claim-Gegenstand außerhalb des deutsch-/englisch-
sprachigen Raums, muss die Recherchekarte Suchbegriffe in der Originalsprache
samt Transliterationen vorgeben (empirisch: „Amu Lindsey"-Fall 07/2026 — persische
Quellen für eine englischzentrierte Suche unsichtbar). Analog gilt für wörtliche
Zitate aus Videos: kanonische Quelle ist der Originalclip; wird er nicht gefunden,
lautet das Verdikt „unbelegt", nicht „nicht überprüfbar" (Retrieval-Grenze ≠
Prüfbarkeits-Grenze).

**Kanonische Prüfziele:** Verweist ein Claim auf ein benennbares Artefakt
(Forschungsarbeit, Code-Repository, offizielles Dokument, Gesetzestext, Datenbank),
muss die Recherchekarte das **direkte Prüfziel** benennen (arXiv-ID, GitHub-Repo,
Doku-/Registers-URL) statt nur Suchbegriffe — generische Such-Checks verfehlen
solche Belege systematisch. Empirischer Beleg (Querprojekt KI-Modellanatomie,
14.07.2026): 10 von 17 Sonar-Verdikten „nicht überprüfbar", davon ≥ 7 per
Primärquelle sofort belegbar (arXiv-Papers, GitHub-Systemprompt-Repo, offizielle
Charakterdokumente, NPR-Berichterstattung). Arbeitsregel: **„Nicht überprüfbar"
heißt bei generischen Such-Checks oft nur „mit dieser Suchstrategie nicht
gefunden"** — die Schwäche liegt in der Werkzeugschicht des Prüfsystems, nicht im
Analysemodell. Konsequenz für die Pipeline: Verdikte „unbelegt/nicht überprüfbar"
bei Claims MIT kanonischem Prüfziel qualifizieren für einen gezielten Zweitversuch
(Eskalationsroute), bevor das Verdikt final wird.

### 5.2 Quellenhierarchie

1. Primärquellen (Gesetze, amtliche Statistik, Gerichtsentscheidungen, Originalstudien)
2. Fachinstitutionen (Institute, Metaanalysen, internationale Organisationen)
3. Qualitätsjournalismus mit transparenter Primärquellenbasis
4. Vorhandene Faktenchecks als Recherchehinweis, nicht als alleiniger Beweis
5. Sekundärmaterial, Social Media, Such-Snippets nur zur Hypothesenbildung

Optionaler vorgelagerter Schritt: Claim-Matching gegen bereits publizierte
Faktenchecks (Google Fact Check Tools API / ClaimReview).

### 5.3 Zeit- und Scope-Logik

Eine Quelle kann korrekt sein und trotzdem nicht passen: Akteur, Metrik, Geografie
und Zeitraum müssen einzeln abgeglichen werden (`scope_match`). Eine zufällig
ähnliche Zahl mit anderem Zeitraum/anderer Messgröße ist **kein** Teilbeleg.

---

## 6. Evidenz und Verdikt

### 6.1 Evidenzobjekte statt Quellenliste

Jede Quelle wird in eine explizite Claim-Evidenz-Beziehung übersetzt: URL, Publisher,
Datum, Abrufzeitpunkt, Quellen-Tier, relevanter Auszug, Haltung
(`supports | refutes | contextualizes | insufficient`), `scope_match`, Limitationen.
Keine Zitate ohne Fundstelle.

### 6.2 Trennung von Evidenz und Urteil (Zielbild)

> Der Verdikt-Schritt erhält keinen offenen Webzugang. Er urteilt ausschließlich
> über Claim + gespeichertes Evidenzpaket.

Das verhindert, dass der finale Prüfer unprotokollierte Behauptungen oder
Modellwissen in den Bericht zieht. (SOMAS-Ist v0.12.1: Recherche und Verdikt noch
in einem Call — bewusste Übergangslösung.)

### 6.3 Verdikt-Taxonomie

Intern differenziert, im UI auf kompakte Hauptverdikte gemappt (mit Begründungszeile):

| Intern | UI-Label | Wann |
| ------ | -------- | ---- |
| `supported` | Bestätigt | alle wesentlichen Teilbedingungen gestützt |
| `partially_supported` | Teilweise bestätigt | **genau benannter** Teilclaim gestützt |
| `unsupported` | Unbelegt | keine ausreichende belastbare Evidenz |
| `contradicted` | Widerlegt | Evidenz widerspricht der Kernbehauptung |
| `under_specified` | Zu unpräzise prüfbar | Akteur/Zeitraum/Metrik/Begriff unbestimmt |
| `attribution_only` | Aussage belegt, Sachverhalt offen | nur das Statement ist nachweisbar |
| `methodologically_unfounded` | Methodisch nicht herleitbar | präzise Zahl/Kausalität ohne tragfähige Methode |
| `mixed_evidence` | Widersprüchliche Quellenlage | relevante Quellen widersprechen einander |

**Leitplanken:**

- Kein positives Teilverdikt ohne explizit ausgewiesenen, belegten Teilclaim samt Quelle.
- „Nicht überprüfbar" ist eine technische Ausnahme (Quelle unzugänglich, Akteur nicht
  identifizierbar, nicht operationalisierbar) — kein Sammelbecken.
- Unabhängigkeits-Riegel: das geprüfte Material selbst zählt nie als Beleg
  (in SOMAS seit v0.10.1, real bewährt).
- Jede Behauptung wird unabhängig geprüft; kein Verdikt wird aus einem anderen abgeleitet.

### 6.4 Ausgabe-Anatomie

Vollständiges Verdikt enthält: Originalclaim + Fundstelle, normalisierte Fassung,
Verdikt + Konfidenz + Begründung, Pro-/Kontra-/Kontext-Evidenz, offene
Unsicherheiten, Policy-Version.

---

## 7. Empirische Befunde SOMAS (Stand 07/2026)

- **Such-Seed ist der größte Hebel (D6a):** Behauptungs-Blob als ein Request führt zu
  thematisch fremden Quellen und pauschalem „nicht überprüfbar"; Recherche pro Claim
  mit gezieltem Auftrag behebt das strukturell.
- **Modellwahl ist themenabhängig:** gut indexierte Allgemeinfakten → Perplexity
  Sonar Pro; frische/Nischen-Themen → agentischer Web-Searcher (z. B. Opus via
  OpenRouter). `sonar-reasoning-pro` fürs Belegen schwach.
- **Perplexity-Tiefe konfigurieren:** ohne `web_search_options.search_context_size:
  "high"` sucht Sonar auf Default „low" — wesentliche Ursache oberflächlicher Läufe.
- **confident ≠ correct:** auch beste agentische Modelle irren selbstbewusst bei
  Zahlen-/Vergleichsclaims → menschlicher Spot-Check gegen Primärquellen bleibt Teil
  der Methodik (Human-in-the-Loop).
- **Token-Budget ist Prüfqualität:** geteilte Budgets (Analyse+Faktencheck bzw. alle
  Claims in einem Call) schneiden lange Listen ab; Reasoning-Modelle können das
  Budget vollständig intern verbrauchen (`finish_reason`-Gate nötig).
- **Websuche ≠ Research:** Single-Pass-Retrieval (`sonar`, `:online`) vs. iterativer
  agentischer Loop (`sonar-deep-research`); Research ⊃ Websuche.

---

## 8. Umsetzungsleitplanken für SOMAS

1. **Parallel statt Umbau:** Der bestehende zweistufige Faktencheck (v0.10.x) bleibt
   als Basis-Strategie erhalten. Neue Wege docken als zusätzliche, per UI wählbare
   Strategie an (Strategie-Abstraktion). Alte Wege werden erst nach bewährtem
   Parallelbetrieb zurückgebaut.
2. **Kern als eigenständiges Modul** (Arbeitstitel `factcheck_core`), von SOMAS
   in-process importiert — nach dem bewährten Muster `youtube-intake-service`.
   Keine Server-/n8n-Infrastruktur als Voraussetzung; n8n-Tauglichkeit bleibt als
   Option erhalten, weil die Stufen über JSON-Verträge kommunizieren.
3. **State Machine, kein Agentenschwarm:** deterministische Stufenfolge mit
   validierten JSON-Übergaben (Schema-Validierung außerhalb des LLM, Retry mit
   Reparaturprompt, dann Eskalation). Agentische Freiheit nur eng begrenzt im
   Recherche-Schritt.
4. **Nicht dem Modell überlassen:** Relevanzgewichtung, zulässige Quellenklassen,
   Verdikt-Taxonomie, Auswahl-Quoten — alles Policy/Code.
5. **Stufen (Zielbild):** Claim Refiner → Argument Mapper → Triage (deterministisch)
   → Research Planner → Research Worker → Evidence Critic → Verifier; jede Stufe hat
   definierte Nicht-Zuständigkeiten (z. B. Refiner entscheidet nicht über Relevanz
   oder Wahrheit).
6. **MVP-Reihenfolge:** Refiner + Mapper + PolicyScorer + Planner zuerst; der
   vorhandene Verifikations-Call wird zunächst weiterverwendet — nur für die
   selektierten, verfeinerten Claims (je Claim eigener Call = eigenes Token-Budget).
   Evidenzobjekte, Critic und getrennter Verdict-Writer folgen danach.
7. **Transparenz im UI:** Nach dem Lauf ausweisen, wie viele Claims extrahiert,
   deep-recherchiert, schnellgeprüft, dokumentiert oder als Meinung markiert wurden —
   samt Policy-Version. Die App hat nichts „vergessen", sie hat nach Regeln priorisiert.
8. **Regressionstest-Korpus:** manuell geprüfte Texte mit erwarteten Claim-/
   Verdict-Strukturen als Dauertest gegen Qualitätsdrift.

---

## 9. Quellen

- Perplexity-Erörterung 2026-07-11 (GPT-5.6 Terra Thinking), inkl. Analyse von vier
  realen SOMAS-Faktenchecks: `notizen/Faktencheck-Eroerterung_Perplexity_2026-07-11md.md`
- Guo et al.: *A Survey on Automated Fact-Checking* (TACL 2022) · AFC-Survey arxiv 2108.11896
- ClaimBuster (Hassan et al., KDD 2017) — Check-worthiness als eigenes Problem
- Full Fact AI — Praxis: Automatisierung von Auffinden/Priorisieren, nicht des Wahrheitsentscheids
- IFCN Code of Principles — Transparenz von Methode, Quellen, Korrekturen
- Google Fact Check Tools API / ClaimReview — Claim-Matching gegen publizierte Checks
- SOMAS-Specs: `SOMAS_v0.10.0_SPEC_faktencheck_verifikation.md`,
  `MERKZETTEL_v0.10.1_offene_punkte.md` (D1–D10), `SOMAS_v0.11.0_SPEC_reasoning_leak_haertung.md`

---

## Änderungshistorie

| Version | Datum | Änderung |
| ------- | ----- | -------- |
| 0.1 | 2026-07-12 | Erstfassung aus Perplexity-Erörterung 2026-07-11 + D-Merkzettel + App-Empirie (Hauptchat) |
| 0.2 | 2026-07-12 | §5.1 Sprachdimension der Recherchekarte + Zitat-Retrieval („unbelegt" ≠ „nicht überprüfbar"); Anlass: Graham-Testfall (Kasparian-Zitat, „Amu Lindsey") |
| 0.3 | 2026-07-14 | §5.1 Kanonische Prüfziele + Eskalationsroute für Verdikte ohne Fund; Anlass: Querprojekt KI-Modellanatomie (7/10 „nicht überprüfbar" per Primärquelle belegbar) |
