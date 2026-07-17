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
from typing import Callable, Protocol

from ..api_client import (
    APIResponse, APIStatus, is_truncated_finish_reason,
)
from .prompts import build_repair_prompt

logger = logging.getLogger(__name__)


class PromptClient(Protocol):
    """Minimalvertrag, den die Stufen vom LLM-Client brauchen.

    Bewusst ein Protocol statt ``LLMClient``: die Stufenklassen (``ClaimRefiner``,
    ``ArgumentMapper``) typisieren damit präzise, ohne selbst von ``api_client``
    abzuhängen — dieses Modul bleibt die einzige Kopplungsnaht des Packages
    (Spec §2.2). Jeder Client mit passender ``send_prompt``-Signatur erfüllt ihn,
    auch die Test-Doppelgänger.
    """

    def send_prompt(
        self, prompt: str, model: str, max_tokens: int | None = None,
        cap_reasoning: bool = False,
    ) -> APIResponse:
        """Sendet einen Prompt und liefert die Antwort."""
        ...

# Anzahl der Reparaturversuche nach einem Vertragsbruch. Bewusst 1 (v0.11-Linie):
# ein gezielter Nachschlag, dann offener Fehler — keine Retry-Schleifen, die
# Token verbrennen und Fehler verschleiern.
MAX_REPAIR_ATTEMPTS = 1

# Antwort-Budget der Plus-Stufen-Calls. Bewusst höher als DEFAULT_MAX_TOKENS (8192):
# Der S1-Output skaliert mit der Claim-Zahl — jede Prüfeinheit echot ``original_text``
# + ``normalized_claim`` — und bei Anthropic zählt zusätzlich das Modell-Thinking
# gegen ``max_tokens``. Bei ~40 Prüfeinheiten (21 Roh-Claims) sprengte 8192 den
# Deckel: valides, aber mitten im String abgeschnittenes JSON (Realtest 2026-07-16,
# v0.13.1). 16384 deckt ~40 Einheiten + Thinking. Gilt NUR für Stufen-Calls, nicht
# global — OpenRouter/Perplexity pre-authen gegen ``max_tokens`` (HTTP 402, v0.10.1);
# provoziert 16384 dort ein 402, greift der Trunkierungs-Gate unten als Sicherheitsnetz.
STAGE_MAX_TOKENS = 16384

_FENCE_RE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$", re.IGNORECASE)


class StageError(RuntimeError):
    """Eine LLM-Stufe lieferte auch nach dem Reparatur-Retry kein gültiges Ergebnis."""


def strip_code_fences(text: str) -> str:
    """Entfernt umschließende Markdown-Code-Fences (```json … ```).

    Args:
        text: Roh-Antwort des Modells; darf ``None``/leer sein.

    Returns:
        Der Text ohne umschließende Code-Fences und ohne Randwhitespace
        ("" wenn nichts übrig bleibt).
    """
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


def extract_json_object(text: str) -> dict:
    """Liest ein JSON-Objekt aus einer Modellantwort — tolerant gegen Beiwerk.

    Pendant zu :func:`extract_json_array` für die Stufen, die genau ein Objekt
    liefern (S5: ein Call pro Claim).

    Args:
        text: Roh-Antwort des Modells.

    Returns:
        Das geparste Dict.

    Raises:
        ValueError: Wenn kein JSON-Objekt gefunden bzw. geparst werden kann.
    """
    cleaned = strip_code_fences(text)
    if not cleaned:
        raise ValueError("Antwort ist leer — erwartet wurde ein JSON-Objekt.")

    candidates = [cleaned]
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start != -1 and end > start:
        candidates.append(cleaned[start:end + 1])

    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
        raise ValueError(
            f"Erwartet wurde ein JSON-Objekt, geliefert wurde "
            f"{type(parsed).__name__}."
        )

    raise ValueError(
        "Antwort enthält kein parsebares JSON-Objekt (kein gültiges JSON gefunden)."
    )


def run_json_stage(
    client: PromptClient,
    model: str,
    prompt: str,
    parse: Callable,
    stage_name: str,
    extract: Callable[[str], object] = extract_json_array,
):
    """Führt eine LLM-Stufe mit Vertragsprüfung und einem Reparatur-Retry aus.

    Ablauf: Prompt senden → JSON via ``extract`` lesen → ``parse`` validiert
    Schema und Stufen-Invarianten (IDs, Bijektion, Leitplanken …). Bricht der
    Vertrag, geht **ein** Reparaturversuch mit der konkreten Fehlermeldung raus.
    Danach: ``StageError``.

    Transport-/API-Fehler (inkl. Leer-Inhalt) lösen KEINEN Reparatur-Retry aus —
    ein Reparaturprompt, der eine leere Antwort zitiert, wäre sinnlos. Sie
    eskalieren sofort; über einen fachlichen Wiederholungslauf entscheidet der
    aufrufende Worker (PR 4).

    **Trunkierung** (``finish_reason`` ∈ ``length``/``max_tokens``/``truncated``)
    ist ebenfalls kein Vertragsbruch, sondern ein abgeschnittenes — womöglich für
    sich valides — JSON. Ein Reparatur-Retry liefe mit demselben Budget
    deterministisch erneut ins Limit; deshalb eskaliert die Stufe sofort mit
    ehrlicher Meldung, statt einen sinnlosen Nachschlag zu verbrennen (v0.13.1).

    Args:
        client: LLM-Client mit ``send_prompt(prompt, model) -> APIResponse``.
        model: Modell-ID (Analyse-Modell; kein eigener Picker, PO-Entscheidung §8.3).
        prompt: Der Stufen-Prompt.
        parse: Callback, das die Rohdaten validiert und Domänenobjekte liefert;
            wirft ``ValueError``/``SchemaError`` mit sprechender Meldung.
        stage_name: Stufenname für Logging/Fehlertexte (z.B. "ClaimRefiner").
        extract: Wie das JSON aus der Antwort gelesen wird —
            :func:`extract_json_array` (Default, Stufen mit Listenoutput) oder
            :func:`extract_json_object` (S5: ein Call pro Claim).

    Returns:
        Das Ergebnis von ``parse``.

    Raises:
        StageError: Bei API-Fehler, Trunkierung oder nach erschöpften
            Reparaturversuchen.
    """
    current_prompt = prompt
    last_error = ""
    # Der Reparatur-Prompt muss dasselbe Format fordern, das die Stufe auch
    # extrahiert — sonst verlangt er bei S5 ein Array statt eines Objekts.
    json_format = "Objekt" if extract is extract_json_object else "Array"

    for attempt in range(MAX_REPAIR_ATTEMPTS + 1):
        # cap_reasoning=True: Stage-Calls sind strukturierte JSON-Extraktion, kein
        # Freitext — ausuferndes Reasoning fraß bei DeepSeek V4 Pro das Antwort-
        # Budget auf (v0.13.2). Nur OpenRouter wertet das Flag aus; die anderen
        # Clients ignorieren es. Das Trunkierungs-Gate unten bleibt Sicherheitsnetz.
        response = client.send_prompt(
            current_prompt, model, max_tokens=STAGE_MAX_TOKENS, cap_reasoning=True,
        )

        if response.status != APIStatus.RECEIVED:
            # Transport-/Leer-Inhalt-Fehler: kein Vertragsbruch → keine Reparatur.
            raise StageError(
                f"{stage_name}: API-Fehler — {response.error_message}"
            )

        # Trunkierung VOR der JSON-Extraktion abfangen: ein bei der Token-Grenze
        # abgeschnittenes (evtl. für sich valides) JSON ist kein Formatfehler. Ein
        # Reparatur-Retry liefe mit demselben Budget erneut ins Limit → sofort
        # offen eskalieren, ohne Nachschlag (v0.13.1).
        if is_truncated_finish_reason(response.finish_reason):
            raise StageError(
                f"{stage_name}: Antwort abgeschnitten (Token-Limit, "
                f"finish_reason={response.finish_reason}) — vermutlich zu viele "
                f"Behauptungen für das Antwort-Budget."
            )

        try:
            raw = extract(response.content)
            result = parse(raw)
        except (ValueError, KeyError, TypeError) as exc:
            last_error = str(exc)
            if attempt >= MAX_REPAIR_ATTEMPTS:
                break
            logger.warning(
                "%s: Vertragsbruch (Versuch %d/%d) → Reparatur-Retry: %s",
                stage_name, attempt + 1, MAX_REPAIR_ATTEMPTS + 1, last_error,
            )
            current_prompt = build_repair_prompt(
                prompt, response.content, last_error, json_format,
            )
            continue

        if attempt > 0:
            logger.info("%s: Reparatur-Retry erfolgreich.", stage_name)
        return result

    raise StageError(
        f"{stage_name}: Ungültige Antwort auch nach Reparatur-Retry — {last_error}"
    )
