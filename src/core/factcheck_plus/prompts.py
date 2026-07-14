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
    ARGUMENT_ROLES, COUNTERFACTUAL_IMPACT, IMPORTANCE_DIMS, RATING_MAX,
    RATING_MIN, RESEARCH_VALUE_DIMS,
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


def _context_block(core_thesis: str, source_hint: str, note: str) -> str:
    """Baut den optionalen Kontextblock (Kernthese + geprüfte Quelle).

    Args:
        core_thesis: SOMAS-Kernthese/Framing.
        source_hint: Titel/URL der geprüften Quelle ("" = weglassen).
        note: Stufenspezifischer Hinweis, wozu der Kontext dient — S1 ordnet nur
            ein, S2 misst die These-Nähe daran (prüfen darf sie keine der beiden).

    Returns:
        Der fertige Block inkl. Leerzeile, oder "" wenn kein Kontext vorliegt.
    """
    parts: list[str] = []
    thesis = sanitize_context(core_thesis)
    hint = sanitize_context(source_hint, 300)
    if thesis:
        parts.append(f"- Kernthese/Framing der Analyse: {thesis}")
    if hint:
        parts.append(f"- Geprüfte Quelle (nur zur Einordnung): {hint}")
    if not parts:
        return ""
    return f"KONTEXT ({note}):\n" + "\n".join(parts) + "\n\n"


# --- S1: ClaimRefiner -----------------------------------------------------

def build_refiner_prompt(
    claims: list[str], core_thesis: str = "", source_hint: str = "",
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
        f"{_context_block(core_thesis, source_hint, 'nur zur Einordnung, NICHT zu bewerten')}"
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

def build_repair_prompt(original_prompt: str, raw_response: str, error: str) -> str:
    """Baut den Reparatur-Prompt für den EINEN erlaubten Retry (v0.11-Linie).

    Übergibt dem Modell die konkrete Schema-/Vertragsverletzung, statt blind
    dieselbe Anfrage zu wiederholen. Schlägt auch dieser Versuch fehl, eskaliert
    die Stufe mit offenem Fehler — keine Scheinergebnisse.

    Args:
        original_prompt: Der ursprüngliche Stufen-Prompt (Regeln bleiben gültig).
        raw_response: Die fehlerhafte Roh-Antwort des Modells.
        error: Die konkrete Fehlermeldung (Schema-Pfad, ID-Abweichung, …).

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
        "aus — als reines JSON-Array, ohne Code-Fences, ohne Vorspann, ohne "
        "Entschuldigung und ohne Kommentar. Alle ursprünglichen Regeln gelten "
        "unverändert weiter:\n"
        "\n"
        "--- URSPRÜNGLICHE AUFGABE ---\n"
        f"{original_prompt}"
    )


def make_claim_id(index: int) -> str:
    """Erzeugt die Eingangs-ID der n-ten Roh-Behauptung ('c01', 'c02', …).

    Args:
        index: 1-basierter Index der Behauptung.

    Returns:
        Nullgepolsterte Claim-ID mit 'c'-Präfix.
    """
    return f"c{index:02d}"
