"""Prompt-Verträge für die LLM-Stufen S1/S2 (Faktencheck Plus, v0.13.0, PR 2).

Die Prompts sind die **einzige** Stelle, an der die Stufen-Hygiene gegenüber dem
Modell durchgesetzt wird (Theorie §8.5): Jede Stufe hat definierte
Nicht-Zuständigkeiten, und die stehen als explizite Verbotssätze im Prompt —
nicht als Nebenbemerkung im Fließtext.

- **S1 ClaimRefiner:** zerlegt, normalisiert, typisiert. Bewertet NICHT Relevanz
  oder Wahrheit.
- **S2 ArgumentMapper:** füllt Rollen + Ratings. Wählt NICHT aus und gewichtet NICHT.

Auswahl und Gewichtung macht ausschließlich der deterministische PolicyScorer
(S3, Theorie §8.4 „Nicht dem Modell überlassen").
"""
from __future__ import annotations

from .schemas import (
    ARGUMENT_ROLES, COUNTERFACTUAL_IMPACT, IMPORTANCE_DIMS, INTERNAL_VERDICTS,
    RATING_MAX, RATING_MIN, RESEARCH_VALUE_DIMS, VERDICTS_REQUIRING_SOURCE,
    VERDICTS_REQUIRING_SUBCLAIM,
)

# Claim-Typen, die S1 vergeben DARF. Bewusst enger als `schemas.CLAIM_TYPES`:
# `opinion`/`interpretation` existieren im Vertrag nur, damit Gate 1 des Scorers
# greifen kann, falls ein Nicht-Faktum aus Stufe 1 durchrutscht — der Refiner soll
# sie aber gar nicht erst als Prüfeinheit ausgeben (Theorie §2.1).
REFINER_CLAIM_TYPES = (
    "quantitative", "causal", "hard_fact", "prognosis",
    "source_attribution", "methodological",
)

# Länge der eingebetteten Kontextfelder. Kernthese/Framing stammen aus der
# Analyse des GEPRÜFTEN Inhalts, sind also potenziell gegnerischer Text →
# Whitespace kollabieren und hart kappen (gleiches Muster wie `source_hint` in
# `prompt_builder.build_verification_prompt`).
_CONTEXT_LIMIT = 600


def sanitize_context(text: str, limit: int = _CONTEXT_LIMIT) -> str:
    """Entschärft eingebetteten Kontext gegen Prompt-Injection.

    Kollabiert Whitespace/Zeilenumbrüche und begrenzt die Länge, damit aus dem
    geprüften Inhalt kein Text die Stufenregeln aufweichen kann.

    Args:
        text: Roher Kontexttext (Kernthese, Framing, Titel …).
        limit: Maximale Zeichenzahl.

    Returns:
        Einzeiliger, gekappter Text ("" wenn nichts übrig bleibt).
    """
    return " ".join((text or "").split())[:limit]


def _context_block(
    core_thesis: str, source_hint: str, note: str, anchor_date: str = "",
) -> str:
    """Baut den optionalen Kontextblock (Kernthese + geprüfte Quelle + Datum).

    Args:
        core_thesis: SOMAS-Kernthese/Framing.
        source_hint: Titel/URL der geprüften Quelle ("" = weglassen).
        note: Stufenspezifischer Hinweis, wozu der Kontext dient — S1 ordnet nur
            ein, S2 misst die These-Nähe daran (prüfen darf sie keine der beiden).
        anchor_date: Optionales Veröffentlichungsdatum des Beitrags (v0.15.0),
            bereits als String formatiert ("" = weglassen). Injection-saniert wie
            die übrigen Felder (Werte kommen aus Code, aber gleiches Muster).

    Returns:
        Der fertige Block inkl. Leerzeile, oder "" wenn kein Kontext vorliegt.
    """
    parts: list[str] = []
    thesis = sanitize_context(core_thesis)
    hint = sanitize_context(source_hint, 300)
    published = sanitize_context(anchor_date, 60)
    if thesis:
        parts.append(f"- Kernthese/Framing der Analyse: {thesis}")
    if hint:
        parts.append(f"- Geprüfte Quelle (nur zur Einordnung): {hint}")
    if published:
        parts.append(
            f"- Veröffentlichungsdatum des geprüften Beitrags: {published}. "
            f"Relative Zeitangaben ('vor zwei Jahren' u. ä.) beziehen sich auf "
            f"dieses Datum — NICHT auf heute, NICHT auf Daten gefundener Quellen."
        )
    if not parts:
        return ""
    return f"KONTEXT ({note}):\n" + "\n".join(parts) + "\n\n"


# --- S1: ClaimRefiner -----------------------------------------------------

def build_refiner_prompt(
    claims: list[str], core_thesis: str = "", source_hint: str = "",
    anchor_date: str = "",
) -> str:
    """Baut den S1-Prompt: Atomisierung, Attribution-Split, Normalisierung, Typ.

    Args:
        claims: Roh-Behauptungen aus Stufe 1 (bereits Basisfakt-bereinigt).
        core_thesis: SOMAS-Kernthese/Framing — reiner Kontext, wird nicht bewertet.
        source_hint: Identität der geprüften Quelle (Titel/URL), nur zur Einordnung.

    Returns:
        Der fertige Prompt-String; erwartet ein JSON-Array als Antwort.
    """
    numbered = "\n".join(
        f"{make_claim_id(i)}: {sanitize_context(c, 1000)}"
        for i, c in enumerate(claims, 1)
    )
    types = " | ".join(REFINER_CLAIM_TYPES)

    return (
        "Du bist ein Claim-Refiner in einer Faktencheck-Pipeline. Deine EINZIGE "
        "Aufgabe: die vorgelegten Behauptungen in atomare Prüfeinheiten zerlegen, "
        "normalisieren und typisieren. Antworte auf Deutsch.\n"
        "\n"
        # --- Nicht-Zuständigkeiten (Theorie §8.5) — harte Verbote ---
        "DEINE NICHT-ZUSTÄNDIGKEITEN (strikt einhalten):\n"
        "- Du bewertest NICHT, ob eine Behauptung WAHR oder FALSCH ist. Du "
        "recherchierst nicht und urteilst nicht.\n"
        "- Du bewertest NICHT, ob eine Behauptung WICHTIG, relevant oder "
        "prüfwürdig ist. Die Auswahl trifft eine spätere Stufe nach festen Regeln.\n"
        "- Du sortierst NICHT um, lässt NICHTS weg und fügst NICHTS hinzu, was "
        "nicht in den vorgelegten Behauptungen steht.\n"
        "\n"
        "AUFGABEN:\n"
        "1. ATOMISIERUNG: Enthält eine Behauptung mehrere unabhängig prüfbare "
        "Teile (z. B. Existenz einer Quelle, ihre Methodik, eine Zahl, eine "
        "Kausalzurechnung), zerlege sie in je EINE Prüfeinheit. Eine Prüfeinheit "
        "ist genau dann atomar, wenn sie EIN Verdikt bekommen kann, ohne dass "
        "belegte und unbelegte Teile darin verschmelzen.\n"
        "2. ATTRIBUTIONS-SPLIT (Pflicht): Bei „X behauptet/sagt/berichtet, dass Y\" "
        "IMMER zwei getrennte Prüfeinheiten ausgeben:\n"
        "   (a) den Attributions-Claim „X hat Y geäußert\" → claim_type "
        "'source_attribution';\n"
        "   (b) den Objekt-Claim „Y ist der Fall\" → claim_type nach Sachlage.\n"
        "   Auch dann, wenn dir der Objekt-Claim trivial oder offensichtlich "
        "erscheint. Beide Teile bekommen später eigene Verdikte.\n"
        "3. NORMALISIERUNG: Formuliere `normalized_claim` als eigenständig "
        "prüfbaren Satz — ohne Pronomen, ohne Verweise wie „das\" oder „dies\", "
        "verständlich ohne den Ursprungstext. Trage Entitäten, Zeitraum und "
        "Metrik in die eigenen Felder ein (unbekannt → null, nichts erfinden).\n"
        "   Enthält der Claim eine RELATIVE Zeitangabe („vor zweieinhalb Jahren\", "
        "„letztes Jahr\") UND nennt der Kontextblock unten ein "
        "Veröffentlichungsdatum, rechne sie in eine ABSOLUTE Angabe um (z. B. "
        "„vor zweieinhalb Jahren\" → „ca. Anfang 2024, bezogen auf "
        "Veröffentlichung 08/2026\") und trage diese in `timeframe` ein. Ohne "
        "Veröffentlichungsdatum: relative Angabe unverändert lassen.\n"
        f"4. TYPISIERUNG: `claim_type` ist EINES von: {types}.\n"
        "\n"
        "ID-REGELN (verbindlich):\n"
        "- Bleibt eine Behauptung ungeteilt, behalte ihre ID exakt bei "
        "(z. B. 'c01') und setze `parent_id` auf null.\n"
        "- Zerlegst du eine Behauptung, hänge Kleinbuchstaben an die "
        "Ursprungs-ID ('c01' → 'c01a', 'c01b', 'c01c', …) und setze `parent_id` "
        "auf die Ursprungs-ID ('c01').\n"
        "- Erfinde keine neuen Nummern. Jede vorgelegte ID muss in der Antwort "
        "vorkommen — entweder unverändert oder als `parent_id` ihrer Teile.\n"
        "\n"
        "AUSGABEFORMAT: NUR ein JSON-Array, kein Vorspann, kein Markdown, keine "
        "Code-Fences. Jedes Element:\n"
        "{\n"
        '  "claim_id": "c01a",\n'
        '  "parent_id": "c01",\n'
        '  "original_text": "<Wortlaut der vorgelegten Behauptung>",\n'
        '  "normalized_claim": "<eigenständig prüfbarer Satz>",\n'
        f'  "claim_type": "<{types}>",\n'
        '  "entities": ["<Personen, Organisationen, Orte>"],\n'
        '  "timeframe": "<Zeitraum oder null>",\n'
        '  "metric": "<Bezugsgröße/Einheit oder null>"\n'
        "}\n"
        "\n"
        f"{_context_block(core_thesis, source_hint, 'nur zur Einordnung, NICHT zu bewerten', anchor_date)}"
        "VORGELEGTE BEHAUPTUNGEN:\n"
        f"{numbered}\n"
    )


# --- S2: ArgumentMapper ---------------------------------------------------

# Die Rating-Dimensionen mit ihrer Bedeutung (Theorie §4.1). Reihenfolge und
# Schlüssel sind vertraglich (`schemas.RATING_DIMS`) — der Text erklärt sie dem
# Modell, ohne dass es die Gewichtung kennt (die ist Policy, nicht Prompt).
_IMPORTANCE_HELP: dict[str, str] = {
    "thesis_proximity": "Wie nah steht die Behauptung an der Kernthese des Beitrags?",
    "conclusion_dependency": "Wie stark hängt die Schlussfolgerung des Beitrags daran?",
    "harm_potential": "Welcher Schaden entstünde, wenn sie falsch wäre und geglaubt würde?",
    "reach_mobilization": "Wie stark ist sie auf Verbreitung/Mobilisierung angelegt?",
    "concreteness": "Wie konkret und damit überhaupt greifbar ist die Aussage?",
}
_RESEARCH_VALUE_HELP: dict[str, str] = {
    "non_triviality": "Wie wenig trivial ist sie? (Allgemeinwissen = 0, Spezialwissen = 5)",
    "recency": "Wie aktuell/zeitgebunden ist der Sachverhalt?",
    "contestedness": "Wie umstritten ist er in der öffentlichen/fachlichen Debatte?",
    "source_access": "Wie gut ist die Quellenlage erwartbar zugänglich?",
    "evidence_gap": "Wie groß ist die Lücke zwischen Behauptung und mitgeliefertem Beleg?",
    "discrepancy_potential": "Wie wahrscheinlich weicht die Faktenlage von der Behauptung ab?",
}


def _ratings_help() -> str:
    """Rendert die Rating-Dimensionen mit Erklärung als Prompt-Block."""
    lines = [f"  Wichtigkeit (importance), je {RATING_MIN}–{RATING_MAX}:"]
    lines += [f"  - {d}: {_IMPORTANCE_HELP[d]}" for d in IMPORTANCE_DIMS]
    lines.append(f"  Recherchewert (research_value), je {RATING_MIN}–{RATING_MAX}:")
    lines += [f"  - {d}: {_RESEARCH_VALUE_HELP[d]}" for d in RESEARCH_VALUE_DIMS]
    return "\n".join(lines)


def build_mapper_prompt(refined: list[dict], core_thesis: str = "") -> str:
    """Baut den S2-Prompt: Argumentrolle, kontrafaktischer Impact, 0–5-Ratings.

    Args:
        refined: S1-Output als Dicts (mindestens `claim_id`, `normalized_claim`,
            `claim_type`).
        core_thesis: SOMAS-Kernthese — Bezugspunkt für `thesis_proximity`.

    Returns:
        Der fertige Prompt-String; erwartet ein JSON-Array als Antwort.
    """
    listed = "\n".join(
        f"{c['claim_id']} [{c.get('claim_type', '?')}]: {c.get('normalized_claim', '')}"
        for c in refined
    )
    ids = ", ".join(f"'{c['claim_id']}'" for c in refined)
    roles = " | ".join(ARGUMENT_ROLES)
    impacts = " | ".join(COUNTERFACTUAL_IMPACT)
    dims_json = ", ".join(f'"{d}": <{RATING_MIN}-{RATING_MAX}>' for d in
                          IMPORTANCE_DIMS + RESEARCH_VALUE_DIMS)

    return (
        "Du bist ein Argument-Mapper in einer Faktencheck-Pipeline. Deine EINZIGE "
        "Aufgabe: für jede vorgelegte Prüfeinheit die Argumentrolle, den "
        "kontrafaktischen Impact und die Bewertungsdimensionen ausfüllen. "
        "Antworte auf Deutsch.\n"
        "\n"
        # --- Nicht-Zuständigkeiten (Theorie §8.5) — harte Verbote ---
        "DEINE NICHT-ZUSTÄNDIGKEITEN (strikt einhalten):\n"
        "- Du WÄHLST NICHT AUS, welche Behauptungen recherchiert werden. Du "
        "erstellst keine Rangfolge, keine Top-Liste und keine Empfehlung.\n"
        "- Du GEWICHTEST NICHT und rechnest keine Gesamtpunktzahl aus. Die "
        "Gewichte kennst du nicht; sie liegen in einer Policy außerhalb dieses "
        "Prompts. Fülle nur die Einzelfelder.\n"
        "- Du bewertest NICHT, ob eine Behauptung WAHR oder FALSCH ist. Ein "
        "hoher Recherchewert ist kein Zweifel am Wahrheitsgehalt.\n"
        "- Du änderst die Behauptungen NICHT, zerlegst sie nicht weiter und "
        "lässt keine aus.\n"
        "\n"
        "AUSZUFÜLLENDE FELDER:\n"
        f"- `argument_role`: EINES von: {roles}\n"
        "  (core_claim = trägt die Hauptthese; supporting_premise = sichert eine "
        "zentrale Schlussfolgerung; context = Hintergrund; example = Illustration; "
        "metadata = Basis-/Rahmenangabe.)\n"
        f"- `counterfactual_impact`: EINES von: {impacts}\n"
        "  (Wie stark bricht die Argumentation des Beitrags zusammen, wenn diese "
        "Prüfeinheit falsch wäre?)\n"
        f"- `ratings`: ganze Zahlen von {RATING_MIN} bis {RATING_MAX}, ALLE "
        "Dimensionen sind Pflicht:\n"
        f"{_ratings_help()}\n"
        "- `reason`: 1 Satz, warum Rolle und Impact so gewählt sind.\n"
        "\n"
        "ID-REGEL (verbindlich): Gib GENAU die vorgelegten IDs zurück — jede "
        "genau einmal, keine zusätzlichen, keine ausgelassenen. Erfinde keine IDs.\n"
        f"Erwartete IDs: {ids}\n"
        "\n"
        "AUSGABEFORMAT: NUR ein JSON-Array, kein Vorspann, kein Markdown, keine "
        "Code-Fences. Jedes Element:\n"
        "{\n"
        '  "claim_id": "c01a",\n'
        f'  "argument_role": "<{roles}>",\n'
        f'  "counterfactual_impact": "<{impacts}>",\n'
        f"  \"ratings\": {{{dims_json}}},\n"
        '  "reason": "<1 Satz>"\n'
        "}\n"
        "\n"
        f"{_context_block(core_thesis, '', 'Bezugspunkt für thesis_proximity — selbst NICHT prüfen')}"
        "PRÜFEINHEITEN:\n"
        f"{listed}\n"
    )


# --- Reparatur-Retry ------------------------------------------------------

def build_repair_prompt(
    original_prompt: str, raw_response: str, error: str,
    json_format: str = "Array",
) -> str:
    """Baut den Reparatur-Prompt für den EINEN erlaubten Retry (v0.11-Linie).

    Übergibt dem Modell die konkrete Schema-/Vertragsverletzung, statt blind
    dieselbe Anfrage zu wiederholen. Schlägt auch dieser Versuch fehl, eskaliert
    die Stufe mit offenem Fehler — keine Scheinergebnisse.

    Args:
        original_prompt: Der ursprüngliche Stufen-Prompt (Regeln bleiben gültig).
        raw_response: Die fehlerhafte Roh-Antwort des Modells.
        error: Die konkrete Fehlermeldung (Schema-Pfad, ID-Abweichung, …).
        json_format: Das erwartete Format — ``"Array"`` (Stufen mit Listenoutput)
            oder ``"Objekt"`` (S5, ein Call pro Claim). Muss zur Extraktion der
            Stufe passen, sonst fordert die Reparatur das falsche Format an.

    Returns:
        Der fertige Reparatur-Prompt.
    """
    excerpt = (raw_response or "")[:4000]
    return (
        "Deine vorige Antwort hat den vereinbarten Vertrag VERLETZT und wurde "
        "maschinell zurückgewiesen.\n"
        "\n"
        f"KONKRETER FEHLER:\n{error}\n"
        "\n"
        "DEINE VORIGE ANTWORT (Auszug):\n"
        f"{excerpt}\n"
        "\n"
        "Korrigiere GENAU diesen Fehler und gib die VOLLSTÄNDIGE Antwort erneut "
        f"aus — als reines JSON-{json_format}, ohne Code-Fences, ohne Vorspann, "
        "ohne Entschuldigung und ohne Kommentar. Alle ursprünglichen Regeln "
        "gelten unverändert weiter:\n"
        "\n"
        "--- URSPRÜNGLICHE AUFGABE ---\n"
        f"{original_prompt}"
    )


# --- S4: ResearchPlanner --------------------------------------------------

# Quellenhierarchie (Theorie §5.2) — Policy, nicht Modellermessen.
SOURCE_HIERARCHY = (
    "1. Primärquellen (Gesetze, amtliche Statistik, Gerichtsentscheidungen, Originalstudien)",
    "2. Fachinstitutionen (Institute, Metaanalysen, internationale Organisationen)",
    "3. Qualitätsjournalismus mit transparenter Primärquellenbasis",
    "4. Vorhandene Faktenchecks als Recherchehinweis, NICHT als alleiniger Beweis",
    "5. Sekundärmaterial, Social Media, Such-Snippets nur zur Hypothesenbildung",
)

# Verbotene Abkürzungen (Theorie §5.1) — feste Policy, die der Planner in jede
# Karte übernimmt, statt sie sich je Claim neu auszudenken.
FORBIDDEN_SHORTCUTS = (
    "Ein Such-Snippet als Beleg werten, ohne die Quelle selbst zu öffnen",
    "Eine unbelegte Sekundärquelle als alleinige Evidenz nehmen",
    "Eine ähnliche Zahl mit anderem Zeitraum/Scope als Teilbeleg werten",
)


def _claim_fields(claim: dict) -> dict[str, str]:
    """Saniert ALLE Skalarfelder eines Claims für die Prompt-Einbettung.

    Die S1-Felder sind LLM-Output über gegnerisches Material und wandern in die
    S2-/S4-/S5-Prompts — eingebettete Zeilenumbrüche oder Anweisungen dürfen dort
    nicht durchschlagen. ``claim_id``/``claim_type`` sind zwar bereits regex- bzw.
    enum-validiert; sie werden aus Konsistenz mit saniert (kostet nichts).

    Args:
        claim: Das Claim-Dict aus S1.

    Returns:
        Dict mit den fertig sanierten Anzeigewerten (Fallback „—"/„?").
    """
    entities = [
        sanitize_context(str(e), 120) for e in (claim.get("entities") or [])
    ]
    return {
        "claim_id": sanitize_context(str(claim.get("claim_id", "")), 40),
        "claim_type": sanitize_context(str(claim.get("claim_type") or "?"), 40),
        "normalized_claim": sanitize_context(str(claim.get("normalized_claim") or ""), 1000),
        "entities": ", ".join(e for e in entities if e) or "—",
        "timeframe": sanitize_context(str(claim.get("timeframe") or "—"), 120),
        "metric": sanitize_context(str(claim.get("metric") or "—"), 120),
    }


def _format_claim_line(claim: dict) -> str:
    """Rendert einen Claim samt Ankern als zweizeiligen Prompt-Eintrag."""
    f = _claim_fields(claim)
    return (
        f"{f['claim_id']} [{f['claim_type']}]: {f['normalized_claim']}\n"
        f"    Entitäten: {f['entities']} · Zeitraum: {f['timeframe']} · "
        f"Metrik: {f['metric']}"
    )


def build_planner_prompt(
    cards_input: list[dict], core_thesis: str = "", anchor_date: str = "",
) -> str:
    """Baut den S4-Prompt: je selektiertem Claim eine Recherchekarte.

    Args:
        cards_input: Selektierte Claims als Dicts (`claim_id`, `normalized_claim`,
            `claim_type`, `entities`, `timeframe`, `metric`).
        core_thesis: SOMAS-Kernthese — nur Kontext.

    Returns:
        Der fertige Prompt-String; erwartet ein JSON-Array als Antwort.
    """
    listed = "\n".join(_format_claim_line(c) for c in cards_input)
    ids = ", ".join(f"'{sanitize_context(str(c['claim_id']), 40)}'" for c in cards_input)
    hierarchy = "\n".join(f"  {line}" for line in SOURCE_HIERARCHY)

    return (
        "Du bist ein Research-Planner in einer Faktencheck-Pipeline. Deine "
        "EINZIGE Aufgabe: für jede vorgelegte Behauptung einen konkreten "
        "RECHERCHEAUFTRAG schreiben. Antworte auf Deutsch.\n"
        "\n"
        # --- Nicht-Zuständigkeiten (Theorie §8.5) — harte Verbote ---
        "DEINE NICHT-ZUSTÄNDIGKEITEN (strikt einhalten):\n"
        "- Du RECHERCHIERST NICHT und beantwortest die Fragen NICHT. Du planst "
        "nur, wie geprüft werden muss.\n"
        "- Du bewertest NICHT, ob eine Behauptung wahr oder falsch ist, und "
        "nimmst kein Verdikt vorweg — auch nicht andeutungsweise.\n"
        "- Du erfindest KEINE Quellen, URLs, Studien oder IDs. Nenne ein "
        "konkretes Prüfziel nur, wenn du dir seiner Existenz sicher bist.\n"
        "\n"
        "GRUNDREGEL (Theorie §5.1): Ein Rechercheauftrag ist NICHT die Frage "
        "„Ist das wahr?\" — offene Wahrheitsfragen erzeugen Bestätigungsfehler. "
        "Formuliere gezielte Teilfragen, die eine Quelle beantworten KANN.\n"
        "\n"
        "PFLICHTFELDER JE KARTE:\n"
        "- `research_questions`: 2–4 konkrete, einzeln beantwortbare Teilfragen.\n"
        "- `counter_hypotheses`: 1–3 Gegenhypothesen — was müsste zutreffen, "
        "damit die Behauptung NICHT stimmt? (Riegel gegen Bestätigungsfehler; "
        "niemals leer.)\n"
        "- `source_priorities`: bevorzugte Quellenklassen für DIESEN Claim, "
        "abgeleitet aus dieser Hierarchie:\n"
        f"{hierarchy}\n"
        "- `required_evidence`: welche Evidenzarten den Claim tragen würden "
        "(z. B. Methode, Abgrenzung, Zurechnung, unabhängige Bestätigung).\n"
        "- `canonical_targets`: Zeigt der Claim auf ein benennbares Artefakt "
        "(Forschungsarbeit, Code-Repository, offizielles Dokument, Gesetzestext, "
        "Register, Originalclip)? Dann nenne das DIREKTE Prüfziel (arXiv-ID, "
        "GitHub-Repo, Doku-/Register-URL, Fundstelle) statt bloßer Suchbegriffe — "
        "generische Suchen verfehlen solche Belege systematisch. Existiert kein "
        "solches Artefakt: leere Liste `[]`.\n"
        "- `language_hints`: Liegt der Gegenstand außerhalb des deutsch-/"
        "englischsprachigen Raums, gib Suchbegriffe in der ORIGINALSPRACHE samt "
        "Transliteration an (sonst bleiben die einschlägigen Quellen unsichtbar). "
        "Andernfalls: leere Liste `[]`.\n"
        "\n"
        "ID-REGEL (verbindlich): Gib GENAU die vorgelegten IDs zurück — jede "
        "genau einmal, keine zusätzlichen, keine ausgelassenen.\n"
        f"Erwartete IDs: {ids}\n"
        "\n"
        "AUSGABEFORMAT: NUR ein JSON-Array, kein Vorspann, kein Markdown, keine "
        "Code-Fences. Jedes Element:\n"
        "{\n"
        '  "claim_id": "c01a",\n'
        '  "research_questions": ["…"],\n'
        '  "counter_hypotheses": ["…"],\n'
        '  "source_priorities": ["…"],\n'
        '  "required_evidence": ["…"],\n'
        '  "canonical_targets": [],\n'
        '  "language_hints": []\n'
        "}\n"
        "\n"
        f"{_context_block(core_thesis, '', 'nur zur Einordnung, NICHT zu bewerten', anchor_date)}"
        "ZU PLANENDE BEHAUPTUNGEN:\n"
        f"{listed}\n"
    )


# --- S5: Recherche + Verdikt (ein Call PRO Claim) -------------------------

def _card_block(card: dict) -> str:
    """Rendert die Recherchekarte als Auftragsblock für den S5-Prompt."""
    def _lines(key: str, label: str) -> str:
        items = card.get(key) or []
        if not items:
            return ""
        body = "\n".join(f"  - {sanitize_context(str(i), 400)}" for i in items)
        return f"{label}:\n{body}\n"

    parts = [
        _lines("research_questions", "ZU BEANTWORTENDE TEILFRAGEN"),
        _lines("counter_hypotheses", "GEGENHYPOTHESEN (aktiv mitprüfen)"),
        _lines("canonical_targets", "DIREKTE PRÜFZIELE (zuerst hier nachsehen)"),
        _lines("language_hints", "SUCHBEGRIFFE IN ORIGINALSPRACHE (mitverwenden)"),
        _lines("source_priorities", "BEVORZUGTE QUELLENKLASSEN"),
        _lines("required_evidence", "GEFORDERTE EVIDENZARTEN"),
        _lines("forbidden_shortcuts", "VERBOTENE ABKÜRZUNGEN"),
    ]
    return "".join(p for p in parts if p)


def build_claim_verification_prompt(
    claim: dict, card: dict, language: str = "Deutsch", source_hint: str = "",
    anchor_date: str = "",
) -> str:
    """Baut den S5-Prompt für EINEN Claim (eigener Call, eigenes Token-Budget).

    Übernimmt die bewährten Riegel des Classic-Wegs unverändert: Unabhängigkeits-
    Riegel (das geprüfte Video zählt nie als Beleg), Verbot erfundener URLs,
    ``source_hint``-Sanitisierung. Neu sind der Rechercheauftrag aus S4, der
    Scope-Check (Theorie §5.3) und die interne 8-stufige Verdikt-Skala.

    Args:
        claim: Der Claim als Dict (`claim_id`, `normalized_claim`, `claim_type`,
            `entities`, `timeframe`, `metric`, `original_text`).
        card: Die Recherchekarte aus S4 (Dict).
        language: Ausgabesprache.
        source_hint: Identität der GEPRÜFTEN Quelle — verbotene Eigenquelle.

    Returns:
        Der fertige Prompt-String; erwartet EIN JSON-Objekt als Antwort.
    """
    verdicts = " | ".join(INTERNAL_VERDICTS)
    # Aus dem Vertrag abgeleitet, nicht handgepflegt: so können Prompt und
    # Laufzeit-Validator (`verdict.check_verdict_guardrails`) nicht auseinanderdriften.
    source_verdicts = ", ".join(f"'{v}'" for v in VERDICTS_REQUIRING_SOURCE)
    subclaim_verdicts = ", ".join(f"'{v}'" for v in VERDICTS_REQUIRING_SUBCLAIM)
    safe_hint = sanitize_context(source_hint, 300)
    forbidden = (
        f"- Die GEPRÜFTE Quelle selbst darf NICHT als Beleg dienen (weder in der "
        f"Begründung noch als Quelle): {safe_hint}\n"
        if safe_hint else ""
    )
    # Zeitanker (v0.15.0): 'veröffentlicht', NICHT 'aufgenommen' — hilft dem
    # Scope-Check, relative Zeitangaben korrekt einzuordnen (Referenz-Drift).
    safe_anchor = sanitize_context(anchor_date, 60)
    anchor_block = (
        f"- Das geprüfte Video wurde am {safe_anchor} VERÖFFENTLICHT. Relative "
        f"Zeitangaben im Claim ('vor zwei Jahren' u. ä.) beziehen sich auf diesen "
        f"Anker, NICHT auf heute und NICHT auf Daten gefundener Quellen; das "
        f"Aufnahmedatum ist unbekannt (Differenz offen).\n"
        if safe_anchor else ""
    )
    f = _claim_fields(claim)

    return (
        f"Du bist ein sorgfältiger Faktenprüfer. Führe den folgenden "
        f"RECHERCHEAUFTRAG aus und beurteile GENAU EINE Behauptung gegen "
        f"UNABHÄNGIGE, EXTERNE Quellen (Websuche). Antworte in {language}.\n"
        "\n"
        "ZU PRÜFENDE BEHAUPTUNG:\n"
        f"{f['normalized_claim']}\n"
        f"  Typ: {f['claim_type']} · Entitäten: {f['entities']} · "
        f"Zeitraum: {f['timeframe']} · Metrik: {f['metric']}\n"
        "\n"
        f"{_card_block(card)}"
        "\n"
        "REGELN:\n"
        # --- Unabhängigkeits-Riegel (unverändert aus v0.10.1) ---
        "- Das analysierte Video/Transkript zählt NICHT als Beleg. Die Behauptung "
        "gilt nur dann als gestützt oder widerlegt, wenn eine davon UNABHÄNGIGE, "
        "EXTERNE Quelle sie stützt bzw. widerlegt.\n"
        "- Maßgeblich ist 'Stimmt die Behauptung?', NICHT 'Wurde sie im Video "
        "gesagt?' (Letzteres ist bereits bekannt).\n"
        f"{forbidden}"
        "- Gib NUR Quellen an, die du tatsächlich abgerufen hast. Erfinde KEINE "
        "URLs.\n"
        # --- Scope-Check (Theorie §5.3) ---
        "- SCOPE-CHECK: Gleiche Akteur, Metrik, Geografie und Zeitraum EINZELN "
        "gegen die Quelle ab. Eine Quelle kann korrekt sein und trotzdem nicht "
        "passen — eine zufällig ähnliche Zahl mit anderem Zeitraum oder anderer "
        "Messgröße ist KEIN Teilbeleg.\n"
        f"{anchor_block}"
        # --- Retrieval-Grenze ≠ Prüfbarkeits-Grenze (Theorie §5.1) ---
        "- Findest du trotz Auftrag nichts: Verdikt 'unsupported' (unbelegt). "
        "'under_specified' ist NUR richtig, wenn die Behauptung selbst zu vage "
        "ist, um überhaupt geprüft zu werden. Verwechsle 'nicht gefunden' nicht "
        "mit 'nicht prüfbar'.\n"
        "- Ist NUR belegt, dass jemand etwas geäußert hat, der Sachverhalt selbst "
        "aber offen: Verdikt 'attribution_only'.\n"
        # --- Leitplanken §6.3 (Werte aus dem Vertrag, nicht handgepflegt) ---
        f"- Ein positives Teilverdikt ({subclaim_verdicts}) ist NUR zulässig mit "
        f"konkret benanntem belegtem Teilclaim in 'supported_subclaim'.\n"
        f"- Diese Verdikte behaupten einen Rechercheerfolg und brauchen daher "
        f"ZWINGEND mindestens eine Quelle: {source_verdicts}. Kannst du keine "
        f"belastbare Quelle nennen, ist 'unsupported' das richtige Verdikt.\n"
        "\n"
        f"VERDIKT — EXAKT einer dieser Werte:\n{verdicts}\n"
        "\n"
        "AUSGABEFORMAT: NUR ein JSON-Objekt, kein Vorspann, keine Code-Fences:\n"
        "{\n"
        f'  "claim_id": "{f["claim_id"]}",\n'
        f'  "verdict": "<{verdicts}>",\n'
        '  "reason": "<1–2 Sätze, inhaltlich begründet>",\n'
        '  "supported_subclaim": "<welcher Teil ist belegt — oder null>",\n'
        '  "sources": ["<URL oder Titel>"],\n'
        '  "open_questions": "<was bleibt offen — oder null>"\n'
        "}\n"
    )


def make_claim_id(index: int) -> str:
    """Erzeugt die Eingangs-ID der n-ten Roh-Behauptung ('c01', 'c02', …).

    Args:
        index: 1-basierter Index der Behauptung.

    Returns:
        Nullgepolsterte Claim-ID mit 'c'-Präfix.
    """
    return f"c{index:02d}"
