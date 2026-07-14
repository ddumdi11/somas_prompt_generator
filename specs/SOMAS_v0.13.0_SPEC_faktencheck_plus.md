# SOMAS v0.13.0 — Faktencheck Plus (argumentgewichtete Recherche)

**Status:** ENTWURF · PO-Fragen entschieden (§8) · **Stand:** 2026-07-12
**Grundlage:** `specs/FAKTENCHECK_THEORIE.md` v0.1 (maßgeblich, insb. §4, §6, §8)
**Rollen:** Architekt = Claude.ai (dieser Chat) · Umsetzung = Kurt (Claude Code) · PO = Thorsten

---

## 1. Ziel

Ein zweiter, per Checkbox wählbarer Faktencheck-Weg, der die empirisch belegten
Fehlallokationen des bestehenden Wegs behebt (prüfbar ≠ prüfwürdig; Claim-Blob als
Such-Seed; unauflösbare „teilweise bestätigt"-Verdikte). Der bestehende zweistufige
Faktencheck (v0.10.x) bleibt **unverändert** als Basis-Strategie erhalten —
Parallel-Präzedenzfall gemäß Theorie §8.1.

**Nicht-Ziele (v0.13.0):** Evidenzobjekte, Evidence Critic, getrennter
Verdict-Writer ohne Webzugang, ClaimReview-Matching, Policy-Profile-Auswahl im UI,
n8n-Anbindung, Auslagerung als Submodul. Alles spätere Ausbaustufen.

## 2. Architektur-Entscheidungen

1. **Strategie-Abstraktion:** Neues Interface (z. B. `VerificationStrategy`) mit
   zwei Implementierungen: `ClassicVerification` (bestehender Ein-Call-Weg,
   Verhalten bitgenau unverändert) und `PlusVerification` (neu). Auswahl über
   GUI-Checkbox; Persistenz in `user_preferences.json` (`use_factcheck_plus`,
   Default AUS — analog `use_intake_core`).
2. **Paketstruktur:** Neues Subpackage `src/core/factcheck_plus/` — **ohne
   Qt-Imports**, Kommunikation zwischen Stufen ausschließlich über validierte
   JSON-/Dataclass-Verträge. Damit später als eigenständiges `factcheck_core`
   extrahierbar (Intake-Muster), aber v0.13.0 bewusst in-repo (kein
   Submodul-Overhead).
3. **State Machine, kein Agent:** Feste Stufenfolge, jede Stufe hat definierte
   Nicht-Zuständigkeiten (Theorie §8.5). LLM-Stufen liefern JSON; Validierung in
   Python (nicht im LLM); bei Schema-Fehler 1× Retry mit Reparaturprompt, dann
   offener Fehler (kein Schein-Ergebnis — Linie von v0.11.0 fortgesetzt).
4. **Modelle:** MVP nutzt den vorhandenen Verifikationsmodell-Picker für die
   Recherche-Calls. Refiner/Mapper/Planner laufen über das Analyse-Modell
   (vorhandene Client-Factory `create_client()`); separate Modellwahl pro Stufe ist
   spätere Ausbaustufe (wartet u. a. auf Model-Finder-Resultate).

## 3. Pipeline (MVP)

```text
Bestehende SOMAS-Analyse mit erzwungenem FAKTENCHECK (unverändert)
  └─ extract_claims_from_faktencheck (vorhanden)
       │  [Checkbox AUS] → ClassicVerification (wie bisher)
       │  [Checkbox AN]  → PlusVerification:
       ├─ S1 ClaimRefiner        (LLM, 1 Call)
       ├─ S2 ArgumentMapper      (LLM, 1 Call)
       ├─ S3 PolicyScorer        (reiner Python-Code, deterministisch)
       ├─ S4 ResearchPlanner     (LLM, 1 Call für alle selektierten Claims)
       └─ S5 Recherche+Verdikt   (LLM, 1 Call PRO selektiertem Claim, Web-Modell)
            └─ Aggregation → Markdown-Abschnitt + Transparenz-Block
```

### S1 — ClaimRefiner (LLM → JSON)

Input: extrahierte Behauptungen + SOMAS-Kernthese/Framing (nur als Kontext) +
Video-Metadaten. Aufgabe: Atomisierung (ein Claim = eine Prüfeinheit), Trennung
Attribution/Objekt-Claim (Theorie §2.2/§2.3), Normalisierung (Entitäten, Zeitraum,
Metrik), Claim-Typ (Theorie §2.1). **Darf nicht:** Relevanz oder Wahrheit bewerten.

Output je Claim (Dataclass `RefinedClaim`):
```json
{
  "claim_id": "c01a", "parent_id": "c01",
  "original_text": "…", "normalized_claim": "…",
  "claim_type": "quantitative | causal | hard_fact | prognosis | source_attribution | methodological",
  "entities": ["…"], "timeframe": "… | null", "metric": "… | null"
}
```

### S2 — ArgumentMapper (LLM → JSON)

Input: RefinedClaims + SOMAS-Kernthese. Aufgabe: Argumentrolle + kontrafaktischer
Impact + Komponenten-Ratings (0–5) für die Policy-Dimensionen aus Theorie §4.1
(These-Nähe, Schlussfolgerungsabhängigkeit, Schadenspotenzial, Konkretheit;
Nicht-Trivialität, Aktualität, Streitigkeit, Quellenzugang, Evidenzlücke,
Diskrepanzpotenzial). **Darf nicht:** auswählen oder gewichten — nur Felder füllen.

Output je Claim (`ArgumentMapping`): `argument_role`
(`core_claim | supporting_premise | context | example | metadata`),
`counterfactual_impact` (`high|medium|low`), `ratings: {…}`, `reason`.

### S3 — PolicyScorer (Python, deterministisch — KEIN LLM)

Neue Konfigurationsdatei `src/config/relevance_policy_v1.json`: Gewichte, Gates,
Quoten, Budget. Der Scorer implementiert:

- **Gates 1–5** (Theorie §4.2): Meinung/Deutung raus, Kontext markieren, Trivial →
  `skip_or_fast_verify`, Attribution splitten (kommt gesplittet aus S1), Vage →
  `under_specified`.
- **Scores:** `ClaimImportance × ResearchValue × Checkability` aus den
  S2-Ratings und Policy-Gewichten.
- **Quotenauswahl** (Theorie §4.3) statt reiner Top-N: erst `core_claims`, dann
  tragende Subclaims, max. 1–2 Kontextclaims; Budget aus GUI
  (Default 8, SpinBox, ersetzt im Plus-Modus das bisherige Max-Behauptungen-Limit).
- **Audit-Output:** je Claim Score-Komponenten + Policy-Version + Auswahlgrund
  (wird im Transparenz-Block ausgegeben).

→ Vollständig offline testbar; Kern der Regressionstests.

**Policy-Schema (festgezurrt für PR 1; Zahlwerte = Startwerte, Tuning nach
Realtests):**

```json
{
  "policy_version": "relevance-de-v1",
  "rating_scale": [0, 5],
  "weights": {
    "importance": {
      "thesis_proximity": 1.0,
      "conclusion_dependency": 1.0,
      "harm_potential": 1.0,
      "reach_mobilization": 0.75,
      "concreteness": 0.5
    },
    "research_value": {
      "non_triviality": 1.0,
      "recency": 1.0,
      "contestedness": 1.0,
      "source_access": 1.0,
      "evidence_gap": 1.0,
      "discrepancy_potential": 1.0
    }
  },
  "gates": {
    "exclude_claim_types": ["opinion", "interpretation"],
    "basisfakt_route": "skip_listed_only",
    "triviality_skip_at": 4,
    "under_specified_route": "flag_not_research"
  },
  "quotas": {
    "core_claims_share": 0.6,
    "supporting_share": 0.3,
    "context_max_claims": 2
  },
  "budget": {
    "deep_research_default": 8
  }
}
```

Rechenweg: `importance` und `research_value` = gewichtete Summe der 0–5-Ratings
aus S2, jeweils auf 0–1 normiert; `priority = importance × research_value ×
checkability` (checkability 0–1 aus S1-Feldern: Entität/Zeitraum/Metrik
vorhanden?). Auswahl klassenweise nach Quoten (A vor B vor C), innerhalb der
Klasse absteigend nach `priority`. Feldnamen sind verbindlich (JSON-Schema);
Gewichte/Schwellen sind Konfiguration, kein Code.

**Bekannte Tuning-Kandidaten (Stand PR 2, 2026-07-14 — beide „Ist-Zustand per
Test dokumentiert", Entscheidung nach Realtests zusammen mit Gewichte-Tuning):**

1. `checkability = Anker/3` benachteiligt nicht-quantitative Claims systematisch
   (hard_fact ohne Metrik ≤ 2/3). Jetzt quantifiziert (IRGC-Fixture): die
   Kausalzurechnung `c01d` verliert ⅓ (Kausalaussagen haben keine Metrik), die
   Quellenexistenz `c01a` ⅔. Fix-Richtung: claim-typ-abhängige Anker-Erwartung
   (Metrik nur bei `quantitative`/`methodological` einfordern).
2. Klassen-Quoten wirken bei kleinem Budget als **Obergrenze** statt Richtwert:
   bei Budget 2 bekommt Klasse A nur `round(2 × 0.6) = 1` Slot — ein B-Claim
   (priority 0.433) verdrängt dann einen A-Claim (0.489). Bei Default-Budget 8
   ohne Wirkung. Fix-Richtung: Shares als garantierte **Minima** interpretieren,
   Restbudget klassenübergreifend (nur A/B) nach globaler priority füllen;
   `context_max_claims` bleibt harter Cap.

### S4 — ResearchPlanner (LLM → JSON)

Für die ≤ Budget selektierten Claims **eine** Recherchekarte je Claim
(Theorie §5.1): konkrete Recherchefragen, **Gegenhypothesen**, Quellenprioritäten
(Hierarchie §5.2), geforderte Evidenzarten, verbotene Abkürzungen. Ein Call für
alle selektierten Claims (JSON-Array).

Zwei Pflichtfelder aus Theorie §5.1 (Stand v0.3): **`canonical_targets`** —
verweist der Claim auf ein benennbares Artefakt (Paper, Repo, offizielles
Dokument, Register), nennt die Karte das direkte Prüfziel (arXiv-ID, GitHub-Repo,
Doku-URL) statt nur Suchbegriffe (empirisch: generische Such-Checks verfehlen
solche Belege — 7/10-Befund Querprojekt 14.07.2026); leer, wenn keins existiert.
**`language_hints`** — bei fremdsprachigem Claim-Gegenstand Suchbegriffe in
Originalsprache + Transliteration.

*Spätere Ausbaustufe (nicht v0.13.0):* Eskalationsroute — „unbelegt/nicht
überprüfbar"-Verdikte bei Claims mit nicht-leerem `canonical_targets` bekommen
einen gezielten Zweitversuch, bevor das Verdikt final wird.

### S5 — Recherche + Verdikt (pro Claim ein Call)

Erweiterung des bestehenden Verifikationswegs — **das ist D6a**:

- Ein `send_prompt` **pro Claim** mit dessen Recherchekarte (eigenes Token-Budget
  je Claim; absorbiert die Backlog-„Zweiteilung").
- Prompt übernimmt die bestehenden Riegel unverändert: Unabhängigkeits-Riegel,
  keine erfundenen URLs, `source_hint`-Sanitisierung.
- **Verdikt:** intern 8-stufig (Theorie §6.3), im Output auf die bestehenden
  4 UI-Verdikte gemappt + verpflichtende Begründungszeile mit dem internen Grund
  (z. B. „Teilweise bestätigt — belegter Teilclaim: …" / „Nicht überprüfbar —
  methodisch nicht herleitbar"). Leitplanke: kein positives Teilverdikt ohne
  benannten belegten Teilclaim samt Quelle.
- Scope-Check im Prompt: Akteur/Metrik/Geografie/Zeitraum müssen zur Quelle passen;
  „ähnliche Zahl, anderer Scope" ist kein Teilbeleg.
- Fehler eines einzelnen Claim-Calls sind **nicht fatal** (Claim erhält
  „Prüfung fehlgeschlagen"-Vermerk, Rest läuft weiter); Abbrechen-Button bricht
  zwischen Claims ab.

### Aggregation & Transparenz-Block

Neues Template `templates/somas_verification_plus.txt` (Jinja2, deterministisch):
Verdikt-Abschnitt je geprüftem Claim + abschließender Transparenz-Block
(Theorie §8.7):

```text
N Behauptungen extrahiert → M atomisiert
- X deep-recherchiert · Y Schnellprüfung übersprungen (Basisfakten)
- Z als Kontext dokumentiert, nicht recherchiert
Policy: relevance_policy_v1 · Budget: 8
```

## 4. GUI

- Checkbox in der Faktencheck-Sektion: **„Faktencheck Plus (argumentgewichtete
  Recherche)"**, Tooltip: „Prüft vorrangig zentrale, strittige und folgenreiche
  Behauptungen. Überspringt Basisfakten und dokumentiert die Auswahlkriterien."
- Sichtbar/aktiv nur bei aktivierter Verifikation; im Plus-Modus steuert die
  vorhandene SpinBox das Deep-Research-Budget (Label wechselt entsprechend).
- Fortschrittsanzeige je Stufe („Verfeinere Behauptungen …", „Recherchiere
  Claim 3/8 …"); Ausschluss mit Modellvergleich wie beim Classic-Weg.
- Kostenhinweis im Tooltip: Plus-Modus macht 3 + N Calls statt 1.

## 5. Worker & Persistenz

Neuer `FactcheckPlusWorker` (QThread) orchestriert S1–S5 (Signale: Stufe,
Claim-Fortschritt, Fehler, Ergebnis). Race-Schutz analog bestehendem
Verifikations-Worker (Quelle während Lauf gesperrt). Debug-Logger persistiert je
Stufe Request/Response + `finish_reason` (bestehende Infrastruktur).

## 6. Tests

- **Fixtures:** IRGC-Fall als Referenz (aus `notizen/Faktencheck-Eroerterung…`):
  Roh-Claims → erwartete Atomisierung (4 Prüfeinheiten), erwartete Klassen.
- `tests/test_claim_refiner_contract.py`: Schema-Validierung, Attribution-Split,
  Reparatur-Retry-Pfad (gemockt).
- `tests/test_policy_scorer.py`: Gates, Quoten, Determinismus (gleicher Input =
  gleiche Auswahl), Basisfakt-Verdrängungs-Regression („ZDF ist
  öffentlich-rechtlich" darf nie einen core_claim verdrängen).
- `tests/test_verdict_mapping.py`: 8→4-Mapping vollständig + Begründungszeile Pflicht.
- Bestehende Tests bleiben grün (Classic-Weg unverändert).

## 7. PR-Schnitt (Vorschlag)

| PR | Inhalt | Merge-Kriterium |
| -- | ------ | --------------- |
| 1 | `factcheck_plus`-Package: Datenmodelle, JSON-Schemas, PolicyScorer + Policy-Datei + Tests | offline grün |
| 2 | ClaimRefiner + ArgumentMapper (Prompts, Contracts, Retry) + Tests | offline grün (gemockt) |
| 3 | ResearchPlanner + Pro-Claim-Verifikation (S4/S5) + Verdikt-Mapping + Template | E2E an 1 Realfall |
| 4 | GUI (Checkbox, Budget, Fortschritt), Worker, Preference, Doku (CLAUDE.md Phase 16, README) | PO-Realtest |

Nur PR 4 fasst `APP_VERSION` an (→ 0.13.0). Reihenfolge nach den bereits
liegenden Specs (Anthropic-Modellpflege → 0.12.2, Perplexity-Wettbewerbsfähigkeit);
S5 soll `search_context_size: "high"` aus der Perplexity-Spec bereits voraussetzen.

## 8. PO-Entscheidungen (Thorsten, 2026-07-12)

1. Budget-Default im Plus-Modus: **8**.
2. Übersprungene Basisfakten erscheinen im Bericht **nur mit Titelzeile**
   (keine Recherche, keine Verdikte).
3. Refiner/Mapper laufen über das Analyse-Modell — **kein eigener Picker**.

---

*Änderungen an Prüflogik/Taxonomie zuerst in `FAKTENCHECK_THEORIE.md` klären,
dann hier nachziehen.*
