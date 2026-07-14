"""Aggregation: Verdikte + Auswahl → Render-Kontext für den Plus-Abschnitt.

Baut **nur Daten** — das Jinja2-Rendering bleibt beim Worker (PR 4), genau wie
beim Classic-Weg (`verification_worker._render`). So bleibt das Package frei von
Template-/Pfad-Abhängigkeiten und offline vollständig testbar (Spec §2.2).

Der Transparenz-Block ist die Antwort auf „die App hat etwas vergessen": Sie hat
nach Regeln priorisiert, und diese Regeln werden ausgewiesen (Theorie §8.7).
"""
from __future__ import annotations

from .models import STATUS_BASISFAKT_SKIPPED, STATUS_EXCLUDED_OPINION
from .models import STATUS_NOT_SELECTED_BUDGET, STATUS_SELECTED
from .models import STATUS_UNDER_SPECIFIED, ClaimVerdict, RefinedClaim, SelectionResult
from .verdict import FAILED_UI_VERDICT, format_reason_line, map_verdict


def build_verdict_rows(
    claims: list[RefinedClaim], verdicts: list[ClaimVerdict],
) -> list[dict]:
    """Baut die Renderzeilen je geprüftem Claim (UI-Verdikt + Begründungszeile).

    Das 8→4-Mapping passiert genau hier — der interne Grund wandert in die
    verpflichtende Begründungszeile, statt verloren zu gehen (Spec §3/S5).

    **Gescheiterte Claim-Calls sind ein Sonderfall:** Sie bekommen zwar intern
    ``unsupported`` als Platzhalter, dürfen aber NICHT dessen Grundtext
    („unbelegt — keine belastbare Evidenz gefunden") tragen. Der wäre schlicht
    falsch: Es wurde keine Evidenz gesucht, der Call ist gescheitert. Genau die
    Verwechslung von Retrieval- und Prüfbarkeits-Grenze, vor der Theorie §5.1
    warnt — hier über den Bericht statt über das Modell.

    Args:
        claims: Die :class:`models.RefinedClaim`-Objekte (für den Claim-Text).
        verdicts: Die :class:`models.ClaimVerdict`-Objekte aus S5.

    Returns:
        Liste von Dicts mit `claim`, `verdict` (UI), `reason_line`, `sources`,
        `open_questions`, `failed` — in Verdikt-Reihenfolge.

    Raises:
        ValueError: Wenn zu einem Verdikt der Claim fehlt.
    """
    by_id = {c.claim_id: c for c in claims}
    rows: list[dict] = []
    for verdict in verdicts:
        claim = by_id.get(verdict.claim_id)
        if claim is None:
            raise ValueError(f"Kein Claim zu Verdikt '{verdict.claim_id}'")
        if verdict.failed:
            ui_verdict = FAILED_UI_VERDICT
            reason_line = verdict.reason
        else:
            ui_verdict, _ground = map_verdict(verdict.verdict)
            reason_line = format_reason_line(
                verdict.verdict, verdict.reason, verdict.supported_subclaim,
            )
        rows.append({
            "claim_id": verdict.claim_id,
            "claim": claim.normalized_claim,
            "verdict": ui_verdict,
            "reason_line": reason_line,
            "sources": [s for s in verdict.sources if s and s.strip()],
            "open_questions": (verdict.open_questions or "").strip() or None,
            "failed": verdict.failed,
        })
    return rows


def build_skipped_rows(
    claims: list[RefinedClaim], selection: SelectionResult,
) -> list[dict]:
    """Baut die Titelzeilen der übersprungenen Basisfakten.

    PO-Entscheidung (Spec §8.2): übersprungene Basisfakten erscheinen im Bericht
    **nur mit Titelzeile** — keine Recherche, kein Verdikt.

    Args:
        claims: Alle atomisierten Claims.
        selection: Das Auswahlergebnis des PolicyScorers.

    Returns:
        Liste von Dicts mit `claim_id` und `claim`.
    """
    by_id = {c.claim_id: c for c in claims}
    skipped = [a.claim_id for a in selection.audits if a.status == STATUS_BASISFAKT_SKIPPED]
    return [
        {"claim_id": cid, "claim": by_id[cid].normalized_claim}
        for cid in skipped if cid in by_id
    ]


def build_transparency(selection: SelectionResult, raw_claim_count: int) -> dict:
    """Baut den Transparenz-Block (Theorie §8.7, Spec §3/Aggregation).

    Args:
        selection: Das Auswahlergebnis des PolicyScorers.
        raw_claim_count: Zahl der Roh-Behauptungen aus Stufe 1 (vor Atomisierung).

    Returns:
        Dict mit `extracted`, `atomised`, `researched`, `skipped_basisfakt`,
        `documented_context`, `excluded_opinion`, `under_specified`,
        `policy_version`, `budget`.
    """
    counts = selection.counts
    return {
        "extracted": raw_claim_count,
        "atomised": counts.get("extracted", 0),
        "researched": counts.get(STATUS_SELECTED, 0),
        "skipped_basisfakt": counts.get(STATUS_BASISFAKT_SKIPPED, 0),
        # „Als Kontext dokumentiert, nicht recherchiert": eligible, aber vom
        # Budget/der Quote nicht erreicht.
        "documented_context": counts.get(STATUS_NOT_SELECTED_BUDGET, 0),
        "excluded_opinion": counts.get(STATUS_EXCLUDED_OPINION, 0),
        "under_specified": counts.get(STATUS_UNDER_SPECIFIED, 0),
        "policy_version": selection.policy_version,
        "budget": selection.budget,
    }


def build_render_context(
    claims: list[RefinedClaim],
    selection: SelectionResult,
    verdicts: list[ClaimVerdict],
    raw_claim_count: int,
    model_name: str = "",
    provider_name: str = "",
    date: str = "",
    web_unverified: bool = False,
) -> dict:
    """Baut den vollständigen Render-Kontext für `somas_verification_plus.txt`.

    Args:
        claims: Alle atomisierten Claims (S1).
        selection: Auswahlergebnis (S3).
        verdicts: Verdikte der geprüften Claims (S5).
        raw_claim_count: Zahl der Roh-Behauptungen aus Stufe 1.
        model_name: Anzeigename des Verifikationsmodells.
        provider_name: Anzeigename des Providers.
        date: Vorformatiertes Datum (der Aufrufer bestimmt das Format).
        web_unverified: True, wenn der Web-Zugriff des Modells unbestätigt ist.

    Returns:
        Das Kontext-Dict für die Jinja2-Vorlage.
    """
    verdict_rows = build_verdict_rows(claims, verdicts)
    return {
        "model_name": model_name,
        "provider_name": provider_name,
        "date": date,
        "web_unverified": web_unverified,
        "verdicts": verdict_rows,
        "skipped": build_skipped_rows(claims, selection),
        "transparency": build_transparency(selection, raw_claim_count),
        # Bei Abbruch zwischen Claims wurden weniger geprüft als selektiert —
        # das muss sichtbar sein, sonst liest sich der Bericht als vollständig.
        "cancelled_early": len(verdict_rows) < len(selection.selected_ids),
        "selected_count": len(selection.selected_ids),
        "failed_count": sum(1 for r in verdict_rows if r["failed"]),
    }
