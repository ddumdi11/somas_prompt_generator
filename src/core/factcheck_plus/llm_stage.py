"""Gemeinsame Mechanik der LLM-Stufen S1/S2 (Faktencheck Plus, v0.13.0, PR 2).

Setzt die Leitplanke „State Machine, kein Agentenschwarm" um (Theorie §8.3):
Schema-Validierung passiert **außerhalb** des LLM, ein Vertragsbruch führt zu
genau EINEM Reparatur-Retry mit konkreter Fehlermeldung — danach eskaliert die
Stufe mit offenem Fehler statt ein Scheinergebnis durchzureichen (v0.11-Linie,
vgl. `main_window._escalate_failed_analysis`).

Dieses Modul ist die **einzige** Stelle des Packages, die den SOMAS-Client kennt.
Bei einer späteren Extraktion als eigenständiges ``factcheck_core`` (Spec §2.2)
ist genau hier der Adapter anzusetzen; die übrigen Module bleiben abhängigkeitsfrei.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Callable

from ..api_client import APIStatus
from .prompts import build_repair_prompt

logger = logging.getLogger(__name__)

# Anzahl der Reparaturversuche nach einem Vertragsbruch. Bewusst 1 (v0.11-Linie):
# ein gezielter Nachschlag, dann offener Fehler — keine Retry-Schleifen, die
# Token verbrennen und Fehler verschleiern.
MAX_REPAIR_ATTEMPTS = 1

_FENCE_RE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$", re.IGNORECASE)


class StageError(RuntimeError):
    """Eine LLM-Stufe lieferte auch nach dem Reparatur-Retry kein gültiges Ergebnis."""


def strip_code_fences(text: str) -> str:
    """Entfernt umschließende Markdown-Code-Fences (```json … ```)."""
    return _FENCE_RE.sub("", (text or "").strip()).strip()


def extract_json_array(text: str) -> list:
    """Liest ein JSON-Array aus einer Modellantwort — tolerant gegen Beiwerk.

    Modelle rahmen JSON gern mit Code-Fences oder einem Einleitungssatz ein.
    Erst wird die bereinigte Antwort direkt geparst; scheitert das, wird der
    Bereich vom ersten ``[`` bis zum letzten ``]`` versucht.

    Args:
        text: Roh-Antwort des Modells.

    Returns:
        Die geparste Liste.

    Raises:
        ValueError: Wenn kein JSON-Array gefunden bzw. geparst werden kann.
    """
    cleaned = strip_code_fences(text)
    if not cleaned:
        raise ValueError("Antwort ist leer — erwartet wurde ein JSON-Array.")

    candidates = [cleaned]
    start, end = cleaned.find("["), cleaned.rfind("]")
    if start != -1 and end > start:
        candidates.append(cleaned[start:end + 1])

    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, list):
            return parsed
        raise ValueError(
            f"Erwartet wurde ein JSON-Array, geliefert wurde "
            f"{type(parsed).__name__}."
        )

    raise ValueError(
        "Antwort enthält kein parsebares JSON-Array (kein gültiges JSON gefunden)."
    )


def run_json_stage(
    client,
    model: str,
    prompt: str,
    parse: Callable[[list], list],
    stage_name: str,
) -> list:
    """Führt eine LLM-Stufe mit Vertragsprüfung und einem Reparatur-Retry aus.

    Ablauf: Prompt senden → JSON-Array extrahieren → ``parse`` validiert Schema
    und Stufen-Invarianten (IDs, Bijektion …). Bricht der Vertrag, geht **ein**
    Reparaturversuch mit der konkreten Fehlermeldung raus. Danach: ``StageError``.

    Transport-/API-Fehler (inkl. Leer-Inhalt) lösen KEINEN Reparatur-Retry aus —
    ein Reparaturprompt, der eine leere Antwort zitiert, wäre sinnlos. Sie
    eskalieren sofort; über einen fachlichen Wiederholungslauf entscheidet der
    aufrufende Worker (PR 4).

    Args:
        client: LLM-Client mit ``send_prompt(prompt, model) -> APIResponse``.
        model: Modell-ID (Analyse-Modell; kein eigener Picker, PO-Entscheidung §8.3).
        prompt: Der Stufen-Prompt.
        parse: Callback, das die Rohliste validiert und Domänenobjekte liefert;
            wirft ``ValueError``/``SchemaError`` mit sprechender Meldung.
        stage_name: Stufenname für Logging/Fehlertexte (z.B. "ClaimRefiner").

    Returns:
        Das Ergebnis von ``parse`` (Liste von Domänenobjekten).

    Raises:
        StageError: Bei API-Fehler oder nach erschöpften Reparaturversuchen.
    """
    current_prompt = prompt
    last_error = ""

    for attempt in range(MAX_REPAIR_ATTEMPTS + 1):
        response = client.send_prompt(current_prompt, model)

        if response.status != APIStatus.RECEIVED:
            # Transport-/Leer-Inhalt-Fehler: kein Vertragsbruch → keine Reparatur.
            raise StageError(
                f"{stage_name}: API-Fehler — {response.error_message}"
            )

        try:
            raw = extract_json_array(response.content)
            result = parse(raw)
        except (ValueError, KeyError, TypeError) as exc:
            last_error = str(exc)
            if attempt >= MAX_REPAIR_ATTEMPTS:
                break
            logger.warning(
                "%s: Vertragsbruch (Versuch %d/%d) → Reparatur-Retry: %s",
                stage_name, attempt + 1, MAX_REPAIR_ATTEMPTS + 1, last_error,
            )
            current_prompt = build_repair_prompt(prompt, response.content, last_error)
            continue

        if attempt > 0:
            logger.info("%s: Reparatur-Retry erfolgreich.", stage_name)
        return result

    raise StageError(
        f"{stage_name}: Ungültige Antwort auch nach Reparatur-Retry — {last_error}"
    )
