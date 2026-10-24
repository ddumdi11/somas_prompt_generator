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


# Kontext-Radius des Fehlerzitats in der Vertragsbruch-Meldung (v0.15.2). Der
# Reparatur-Prompt zitiert die vorige Antwort nur auszugsweise (erste 4000
# Zeichen) — lag der Fehler dahinter, sah das Modell die kaputte Stelle nie
# (Realtest 2026-10-24: Fehler bei Zeichen 4995, der Retry wiederholte ihn
# wortgleich). Das Zitat holt genau diese Stelle in die Fehlermeldung.
DIAGNOSIS_CONTEXT_CHARS = 100

# Markiert die Fehlerposition im Zitat — bewusst ein Zeichen, das in JSON-Output
# praktisch nie vorkommt, damit es nicht mit dem zitierten Text verwechselt wird.
_ERROR_MARK = "⟦HIER⟧"

# Zeichen, die nach einem SCHLIESSENDEN String-Quote legitim folgen
# (Key → ``:``, Wert → ``,``/``}``/``]``). Steht nach einem ``"`` etwas anderes,
# war es ein inneres, unescaptes Anführungszeichen.
_AFTER_STRING_END = frozenset(",}]:")

# JSONDecodeError-Meldungen, die selbst einen Fehler INNERHALB eines Strings melden.
_STRING_ERROR_PREFIXES = (
    "Unterminated string", "Invalid control character", "Invalid \\escape",
    "Invalid \\uXXXX",
)


class JSONSyntaxError(ValueError):
    """Die Antwort enthält JSON-artigen Text, der syntaktisch nicht parsebar ist.

    Trägt neben der diagnostischen Meldung den geprüften Kandidaten-Text — den
    braucht :func:`run_json_stage` für die Quote-Heilung (v0.15.2).

    Attributes:
        candidate: Der Text, an dem ``json.loads`` scheiterte.
        decode_error: Der ursprüngliche ``json.JSONDecodeError``.
    """

    def __init__(
        self, message: str, candidate: str, decode_error: json.JSONDecodeError,
    ) -> None:
        super().__init__(message)
        self.candidate = candidate
        self.decode_error = decode_error


def _next_significant_char(text: str, index: int) -> str:
    """Liefert das nächste Nicht-Whitespace-Zeichen ab ``index`` ("" am Textende)."""
    return text[index:].lstrip()[:1]


def _error_inside_string(text: str, error: json.JSONDecodeError) -> bool:
    """Schätzt, ob ein Parse-Fehler in einem String-Wert entstanden ist.

    Zwei Fälle: Der Parser meldet selbst einen String-Fehler (unterminiert,
    Steuerzeichen, kaputtes Escape) — oder er stolpert direkt hinter einem
    ``"`` über ein Zeichen, das nach einem String-Ende nicht stehen darf. Das ist
    die Signatur eines unescapten inneren Anführungszeichens: Der String endete
    für den Parser zu früh (Realtest 2026-10-24: ``„Message received." dient``).

    Args:
        text: Der geparste Text.
        error: Der Parse-Fehler.

    Returns:
        ``True``, wenn der Fehler vermutlich in einem String liegt.
    """
    if error.msg.startswith(_STRING_ERROR_PREFIXES):
        return True
    # Folgt direkt ein weiteres ``"``, fehlt eher ein Trennzeichen zwischen zwei
    # Strings — dann kein Anführungszeichen-Hinweis (er führte das Modell in die Irre).
    nxt = _next_significant_char(text, error.pos)
    return (
        text[:error.pos].rstrip().endswith('"')
        and nxt not in ("", '"') and nxt not in _AFTER_STRING_END
    )


def describe_json_error(text: str, error: json.JSONDecodeError) -> str:
    """Formuliert einen JSON-Parse-Fehler als präzise Reparatur-Diagnose (v0.15.2).

    Enthält Fehlerart (``error.msg``), Zeile/Spalte/Position und ein klar als
    Zitat markiertes Fenster (±:data:`DIAGNOSIS_CONTEXT_CHARS` Zeichen) des
    eigenen Outputs mit Marke an der Fehlerstelle. Liegt der Fehler in einem
    String, folgt die gezielte Anweisung zu unescapten Anführungszeichen.

    Args:
        text: Der Text, an dem ``json.loads`` scheiterte.
        error: Der Parse-Fehler.

    Returns:
        Die mehrzeilige Diagnose.
    """
    pos = error.pos
    lo = max(0, pos - DIAGNOSIS_CONTEXT_CHARS)
    hi = min(len(text), pos + DIAGNOSIS_CONTEXT_CHARS)
    excerpt = (
        ("…" if lo > 0 else "")
        + text[lo:pos] + _ERROR_MARK + text[pos:hi]
        + ("…" if hi < len(text) else "")
    )
    lines = [
        f"JSON-Syntaxfehler: {error.msg} (Zeile {error.lineno}, Spalte "
        f"{error.colno}, Zeichen {pos}).",
        f"Fundstelle in DEINER vorigen Antwort (Zitat, ±{DIAGNOSIS_CONTEXT_CHARS} "
        f"Zeichen; {_ERROR_MARK} markiert die Fehlerposition):",
        "--- ZITAT ANFANG ---",
        excerpt,
        "--- ZITAT ENDE ---",
    ]
    if _error_inside_string(text, error):
        lines.append(
            'Der Fehler liegt in einem String-Wert. Prüfe unescapte '
            'Anführungszeichen in String-Werten an dieser Stelle: Ein " '
            'INNERHALB eines Strings muss als \\" escapt werden.'
        )
    return "\n".join(lines)


def heal_unescaped_quotes(text: str) -> tuple[str, int]:
    """Escapt unescapte innere ``"`` in JSON-Strings — rein additiv (v0.15.2).

    Konservative Heuristik über einen String-Zustandsautomaten: Ein ``"``
    innerhalb eines Strings gilt als **schließend**, wenn das nächste
    Nicht-Whitespace-Zeichen ``,`` ``}`` ``]`` ``:`` ist oder der Text endet —
    sonst als **inneres** Anführungszeichen, vor das ein Backslash gesetzt wird.
    Vorhandene Escapes bleiben unangetastet. Es werden ausschließlich Backslashes
    ergänzt, nie Zeichen geändert oder entfernt. Ob das Ergebnis gilt, entscheidet
    der Aufrufer (parsebar UND schema-valide), nicht diese Funktion.

    Args:
        text: Der unparsebare JSON-Kandidat.

    Returns:
        ``(geheilter_text, anzahl_ergänzter_escapes)`` — bei 0 ist der Text
        unverändert.
    """
    out: list[str] = []
    in_string = False
    healed = 0
    i, n = 0, len(text)
    while i < n:
        ch = text[i]
        if in_string:
            if ch == "\\":
                out.append(text[i:i + 2])  # vorhandenes Escape unverändert
                i += 2
                continue
            if ch == '"':
                nxt = _next_significant_char(text, i + 1)
                if nxt != "" and nxt not in _AFTER_STRING_END:
                    out.append('\\"')
                    healed += 1
                    i += 1
                    continue
                in_string = False
        elif ch == '"':
            in_string = True
        out.append(ch)
        i += 1
    return "".join(out), healed


def _extract_json(text: str, expected: type, label: str):
    """Gemeinsamer Kern von :func:`extract_json_array`/:func:`extract_json_object`.

    Erst wird die bereinigte Antwort direkt geparst; scheitert das, der Bereich
    von der ersten öffnenden bis zur letzten schließenden Klammer.

    Args:
        text: Roh-Antwort des Modells.
        expected: ``list`` oder ``dict``.
        label: "Array" bzw. "Objekt" (für Meldungen).

    Returns:
        Das geparste Ergebnis vom Typ ``expected``.

    Raises:
        JSONSyntaxError: Wenn kein Kandidat parsebar ist — Diagnose zum zuletzt
            geprüften (dem engsten) Kandidaten.
        ValueError: Wenn die Antwort leer ist oder einen falschen JSON-Typ liefert.
    """
    cleaned = strip_code_fences(text)
    if not cleaned:
        raise ValueError(f"Antwort ist leer — erwartet wurde ein JSON-{label}.")

    opener, closer = ("[", "]") if expected is list else ("{", "}")
    candidates = [cleaned]
    start, end = cleaned.find(opener), cleaned.rfind(closer)
    if start != -1 and end > start:
        candidates.append(cleaned[start:end + 1])

    last_error: json.JSONDecodeError | None = None
    last_candidate = cleaned
    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError as exc:
            last_error, last_candidate = exc, candidate
            continue
        if isinstance(parsed, expected):
            return parsed
        raise ValueError(
            f"Erwartet wurde ein JSON-{label}, geliefert wurde "
            f"{type(parsed).__name__}."
        )

    assert last_error is not None  # jeder Kandidat ist gescheitert
    raise JSONSyntaxError(
        f"Antwort enthält kein parsebares JSON-{label}.\n"
        + describe_json_error(last_candidate, last_error),
        last_candidate, last_error,
    )


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
        JSONSyntaxError: Bei Syntaxfehler — Meldung mit präziser Diagnose
            (Fehlerart, Position, Kontext-Zitat; v0.15.2).
        ValueError: Wenn die Antwort leer ist oder kein Array liefert.
    """
    return _extract_json(text, list, "Array")


def extract_json_object(text: str) -> dict:
    """Liest ein JSON-Objekt aus einer Modellantwort — tolerant gegen Beiwerk.

    Pendant zu :func:`extract_json_array` für die Stufen, die genau ein Objekt
    liefern (S5: ein Call pro Claim).

    Args:
        text: Roh-Antwort des Modells.

    Returns:
        Das geparste Dict.

    Raises:
        JSONSyntaxError: Bei Syntaxfehler — Meldung mit präziser Diagnose.
        ValueError: Wenn die Antwort leer ist oder kein Objekt liefert.
    """
    return _extract_json(text, dict, "Objekt")


def _extract_and_parse(
    content: str, extract: Callable[[str], object], parse: Callable,
    stage_name: str,
):
    """Extrahiert + validiert eine Antwort, mit Quote-Heilung als stillem Vorversuch.

    Scheitert ``extract`` an einem Syntaxfehler, wird EINMAL
    :func:`heal_unescaped_quotes` auf den Kandidaten angewendet. Das Ergebnis
    gilt nur, wenn es danach parsebar ist UND ``parse`` (Schema + Invarianten)
    besteht — sonst wird der URSPRÜNGLICHE Syntaxfehler samt Diagnose
    weitergeworfen (→ Reparatur-Retry). Bei Erfolg spart das einen LLM-Call.

    Args:
        content: Roh-Antwort des Modells.
        extract: Extraktionsfunktion der Stufe.
        parse: Validierungs-Callback der Stufe.
        stage_name: Stufenname fürs Logging.

    Returns:
        Das Ergebnis von ``parse``.

    Raises:
        ValueError/KeyError/TypeError: Vertragsbruch (→ Reparatur-Retry).
    """
    try:
        raw = extract(content)
    except JSONSyntaxError as exc:
        healed_text, count = heal_unescaped_quotes(exc.candidate)
        if count == 0:
            raise
        try:
            result = parse(extract(healed_text))
        except (ValueError, KeyError, TypeError) as heal_exc:
            logger.info(
                "%s: Quote-Heilung verworfen (%d Stellen, danach weiterhin "
                "ungültig: %s).", stage_name, count,
                (str(heal_exc).splitlines() or [""])[0],
            )
            raise exc from None
        logger.info("%s: Quote-Heilung angewendet: %d Stellen.", stage_name, count)
        return result
    return parse(raw)


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

    Reihenfolge je Antwort: API-/Leer-Fehler → Trunkierung → Extraktion (bei
    Syntaxfehler: stille Quote-Heilung, v0.15.2) → Schema → Reparatur-Retry. Ein
    Syntaxfehler geht mit präziser Diagnose (Fehlerart, Position, Kontext-Zitat)
    in den Reparatur-Prompt — der generische Fehler ohne Position wurde vom
    Modell nachweislich wortgleich wiederholt (Realtest 2026-10-24).

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
            result = _extract_and_parse(
                response.content, extract, parse, stage_name,
            )
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
