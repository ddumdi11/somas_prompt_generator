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

import re

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


# --- Unabhängigkeits-Riegel, server-seitig --------------------------------

# URL und YouTube-Video-ID aus dem `source_hint` (Format: "Titel URL", s.
# `verification_worker`). Beide Teile werden getrennt geprüft: Ein Ganzstring-
# Vergleich ginge ins Leere, weil der Hint Titel UND URL enthält, eine Quelle
# aber typischerweise nur eines von beidem nennt.
_URL_RE = re.compile(r"https?://\S+", re.IGNORECASE)
_YT_ID_RE = re.compile(
    r"(?:youtu\.be/|youtube\.com/(?:watch\?v=|shorts/|embed/))([A-Za-z0-9_-]{11})",
    re.IGNORECASE,
)

# Mindestlänge, ab der ein Titelrest als Fingerabdruck taugt. Kurze Titel wie
# „ZDF" würden sonst jede seriöse Quelle mit diesem Wort fälschlich sperren.
_MIN_TITLE_FINGERPRINT = 12


def _normalize_source(text: str) -> str:
    """Normalisiert eine Quelle/einen Hint für den Vergleich (casefold + Whitespace)."""
    return " ".join((text or "").split()).casefold().strip(" .,;:/")


def is_forbidden_source(source: str, source_hint: str) -> bool:
    """Prüft, ob eine angegebene Quelle die GEPRÜFTE Quelle selbst ist.

    Der Unabhängigkeits-Riegel (seit v0.10.1, Theorie §6.3) stand bisher nur im
    Prompt — hier wird er durchgesetzt. Verglichen wird dreifach, weil
    ``source_hint`` „Titel URL" zusammenfasst, eine Quellenangabe aber meist nur
    eines davon nennt:

      1. **Video-ID** (fängt ``youtu.be/X`` vs. ``youtube.com/watch?v=X``),
      2. **volle URL** (in beide Richtungen, gegen Tracking-Suffixe),
      3. **Titelrest**, sofern lang genug für einen Fingerabdruck.

    Args:
        source: Die vom Modell angegebene Quelle.
        source_hint: Identität der geprüften Quelle ("Titel URL").

    Returns:
        True, wenn die Quelle die geprüfte Quelle selbst ist (Eigenbeleg).
    """
    src = _normalize_source(source)
    hint = _normalize_source(source_hint)
    if not src or not hint:
        return False

    # 1) Video-ID — der zuverlässigste Fingerabdruck.
    hint_ids = {m.group(1).casefold() for m in _YT_ID_RE.finditer(source_hint or "")}
    src_ids = {m.group(1).casefold() for m in _YT_ID_RE.finditer(source or "")}
    if hint_ids & src_ids:
        return True
    if hint_ids and any(vid in src for vid in hint_ids):
        return True

    # 2) URL-Teile des Hints.
    for url in _URL_RE.findall(source_hint or ""):
        url_norm = _normalize_source(url)
        if url_norm and (url_norm in src or src in url_norm):
            return True

    # 3) Titelrest (Hint ohne URLs).
    title = _normalize_source(_URL_RE.sub(" ", source_hint or ""))
    if len(title) >= _MIN_TITLE_FINGERPRINT and title in src:
        return True
    return False


def check_forbidden_sources(sources: list[str], source_hint: str) -> None:
    """Weist Eigenbelege zurück — die geprüfte Quelle zählt nie als Beleg.

    Args:
        sources: Die vom Modell angegebenen Quellen.
        source_hint: Identität der geprüften Quelle ("" = keine Prüfung möglich).

    Raises:
        VerdictError: Wenn eine Quelle die geprüfte Quelle selbst ist.
    """
    if not source_hint:
        return
    offending = [s for s in sources if is_forbidden_source(s, source_hint)]
    if offending:
        raise VerdictError(
            f"Eigenbeleg unzulässig: Diese Quelle(n) sind die GEPRÜFTE Quelle "
            f"selbst und zählen nicht als Beleg: {offending}. Nenne eine davon "
            f"UNABHÄNGIGE, EXTERNE Quelle — oder vergib 'unsupported'."
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
