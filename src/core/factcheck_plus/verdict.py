"""Verdikt-Taxonomie und 8→4-Mapping (Faktencheck Plus, v0.13.0, PR 3).

Intern urteilt S5 auf der feinen Skala aus Theorie §6.3 (8 Werte); ausgegeben
werden die vier etablierten UI-Verdikte des Classic-Wegs
(``prompt_builder.VERDICT_VALUES``) — der **interne Grund überlebt das Mapping
in der verpflichtenden Begründungszeile** (Spec §3/S5).

Das Mapping ist bewusst verlustbehaftet: vier interne Werte landen auf
„nicht überprüfbar". Genau deshalb ist die Begründungszeile Pflicht und nicht
Kür — sie trägt die Unterscheidung, die das UI-Label allein nicht mehr hergibt
(z. B. „unbelegt" vs. „methodisch nicht herleitbar", Theorie §5.1: Retrieval-
Grenze ≠ Prüfbarkeits-Grenze).
"""
from __future__ import annotations

from .schemas import (
    INTERNAL_VERDICTS, VERDICTS_REQUIRING_SOURCE, VERDICTS_REQUIRING_SUBCLAIM,
)

# Die vier UI-Verdikte des Classic-Wegs. Bewusst hier gespiegelt statt aus
# `prompt_builder` importiert: das Package bleibt so von SOMAS entkoppelt
# (einzige Naht ist `llm_stage`, Spec §2.2). Gegen Drift schützt ein
# Konsistenztest gegen `prompt_builder.VERDICT_VALUES` — dasselbe Muster wie
# `tests/test_model_lists_consistency.py` bei den Modelllisten.
UI_VERDICTS = ("bestätigt", "teilweise bestätigt", "widerlegt", "nicht überprüfbar")

# Interner Wert → (UI-Verdikt, Klartext-Grund für die Begründungszeile).
# Die Grundtexte stammen wörtlich aus der UI-Label-Spalte von Theorie §6.3.
VERDICT_MAP: dict[str, tuple[str, str]] = {
    "supported": ("bestätigt", "alle wesentlichen Teilbedingungen gestützt"),
    "partially_supported": ("teilweise bestätigt", "belegter Teilclaim"),
    "attribution_only": ("teilweise bestätigt", "Aussage belegt, Sachverhalt offen"),
    "contradicted": ("widerlegt", "Evidenz widerspricht der Kernbehauptung"),
    "unsupported": ("nicht überprüfbar", "unbelegt — keine belastbare Evidenz gefunden"),
    "under_specified": ("nicht überprüfbar", "zu unpräzise: Akteur/Zeitraum/Metrik unbestimmt"),
    "methodologically_unfounded": ("nicht überprüfbar", "methodisch nicht herleitbar"),
    "mixed_evidence": ("nicht überprüfbar", "widersprüchliche Quellenlage"),
}

# Vollständigkeits- und Konsistenzriegel zur Importzeit: jeder interne Wert hat
# ein Ziel, und jedes Ziel ist ein echtes UI-Verdikt des Classic-Wegs. Fängt
# Drift, wenn eine der beiden Listen wächst.
assert set(VERDICT_MAP) == set(INTERNAL_VERDICTS), (
    "VERDICT_MAP deckt nicht exakt INTERNAL_VERDICTS ab: "
    f"{set(VERDICT_MAP) ^ set(INTERNAL_VERDICTS)}"
)
assert {ui for ui, _ in VERDICT_MAP.values()} <= set(UI_VERDICTS), (
    "VERDICT_MAP zielt auf ein UI-Verdikt, das der Classic-Weg nicht kennt: "
    f"{ {ui for ui, _ in VERDICT_MAP.values()} - set(UI_VERDICTS)}"
)

# Verdikt, das ein fehlgeschlagener Claim-Call bekommt. Ein Einzelfehler ist
# NICHT fatal (Spec §3/S5) — der Claim wird sichtbar als ungeprüft ausgewiesen,
# statt den ganzen Lauf zu kippen oder still zu verschwinden.
FAILED_UI_VERDICT = "nicht überprüfbar"
FAILED_REASON_PREFIX = "Prüfung fehlgeschlagen"


class VerdictError(ValueError):
    """Ein Verdikt verletzt eine Leitplanke der Taxonomie (Theorie §6.3)."""


def map_verdict(internal: str) -> tuple[str, str]:
    """Bildet ein internes Verdikt auf UI-Verdikt + Grundtext ab.

    Args:
        internal: Einer der acht Werte aus :data:`schemas.INTERNAL_VERDICTS`.

    Returns:
        Tupel ``(ui_verdikt, grund)`` — ``ui_verdikt`` ist eines der vier
        ``VERDICT_VALUES``.

    Raises:
        VerdictError: Bei unbekanntem internen Verdikt.
    """
    if internal not in VERDICT_MAP:
        raise VerdictError(
            f"Unbekanntes internes Verdikt '{internal}'. Erlaubt: "
            f"{sorted(VERDICT_MAP)}."
        )
    return VERDICT_MAP[internal]


def check_verdict_guardrails(
    internal: str, supported_subclaim: str | None, sources: list[str],
) -> None:
    """Prüft die harten Leitplanken der Verdikt-Taxonomie (Theorie §6.3).

    Zwei Regeln, beide nicht verhandelbar:
      1. **Kein positives Teilverdikt ohne benannten belegten Teilclaim samt
         Quelle** — sonst entstehen genau die unauflösbaren „teilweise
         bestätigt"-Verdikte, gegen die das ganze Modul gebaut ist.
      2. Verdikte, die einen Rechercheerfolg behaupten, brauchen eine Quelle.

    Args:
        internal: Das interne Verdikt.
        supported_subclaim: Der explizit benannte belegte Teilclaim (oder None).
        sources: Die angegebenen Quellen.

    Raises:
        VerdictError: Bei Verletzung einer der beiden Regeln.
    """
    subclaim = (supported_subclaim or "").strip()
    clean_sources = [s for s in sources if s and s.strip() and s.strip() != "—"]

    if internal in VERDICTS_REQUIRING_SUBCLAIM and not subclaim:
        raise VerdictError(
            f"Verdikt '{internal}' ohne benannten belegten Teilclaim: Bei einem "
            f"positiven Teilverdikt MUSS 'supported_subclaim' konkret benennen, "
            f"welcher Teil belegt ist (Theorie §6.3)."
        )
    if internal in VERDICTS_REQUIRING_SOURCE and not clean_sources:
        raise VerdictError(
            f"Verdikt '{internal}' ohne Quelle: Ein Verdikt, das einen "
            f"Rechercheerfolg behauptet, braucht mindestens eine belastbare "
            f"Quelle. Ohne Beleg ist 'unsupported' das richtige Verdikt."
        )


def format_reason_line(internal: str, reason: str, supported_subclaim: str | None = None) -> str:
    """Baut die verpflichtende Begründungszeile mit dem internen Grund.

    Beispiele: ``"Teilweise bestätigt — belegter Teilclaim: …"`` bzw.
    ``"Nicht überprüfbar — methodisch nicht herleitbar. …"`` (Spec §3/S5).

    Args:
        internal: Das interne Verdikt.
        reason: Die Modellbegründung (1–2 Sätze).
        supported_subclaim: Der belegte Teilclaim bei positiven Teilverdikten.

    Returns:
        Die fertige Begründungszeile (ohne Markdown-Rahmen).
    """
    _ui, ground = map_verdict(internal)
    subclaim = (supported_subclaim or "").strip()
    if internal in VERDICTS_REQUIRING_SUBCLAIM and subclaim:
        head = f"{ground}: {subclaim}"
    else:
        head = ground
    text = (reason or "").strip()
    return f"{head}. {text}" if text else f"{head}."
