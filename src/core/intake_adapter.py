"""In-Process-Adapter für den `youtube-intake-service` (Core).

Ruft den **Core** direkt in-process auf (`youtube_intake_core.process`) — NIEMALS
den Server. Der Core ist reine Logik ohne Port/`service.info`; ein versehentlicher
Import der Server-/FastAPI-Schicht würde einen Port binden und mit dem laufenden
Webclip-Daemon kollidieren (siehe Spec §1, „nie den Server"-Regel). Strukturell ist
das ohnehin abgesichert: SOMAS installiert den Core ohne `[server]`-Extra, FastAPI
ist im Venv gar nicht vorhanden.

Kontrakt (Service v1.0.0, eingefroren):
- Erfolg/Teilerfolg → dict mit 12 Feldern (u. a. `status`, `transcript_available`,
  `title`, `channel`, `duration` [int-Sek.], `url`, `transcript`, `warnings`).
- Harte Fehler (ungültige URL, Video weg) → typisierte Exception `IntakeError`
  (mit `.error_code`) aus `youtube_intake_core`.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from src.config.defaults import VideoInfo

logger = logging.getLogger(__name__)


class IntakeUnavailable(RuntimeError):
    """Der Core ist nicht importierbar/installiert.

    Signalisiert dem Router, dass er auf den bestehenden In-Process-YouTube-Pfad
    (`get_video_info`) zurückfallen soll — KEIN inhaltlicher Fehler.
    """


class IntakeFailed(RuntimeError):
    """Harter, inhaltlicher Fehler aus dem Core (ungültige URL, Video nicht verfügbar).

    Trägt den `error_code` des Core für spätere differenzierte Fehleranzeigen.
    """

    def __init__(self, error_code: str, message: str) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.message = message


@dataclass
class IntakeResult:
    """Ergebnis eines Core-Aufrufs, gemappt auf SOMAS-Datenmodelle.

    Attributes:
        video_info: Auf `VideoInfo` gemappte Metadaten (+ Transkript).
        status: `"complete"` | `"metadata_only"` (nie `"error"` — das wird geraised).
        transcript_available: Verlässliches „hat Transkript?"-Signal
            (NICHT über `transcript == ""` prüfen).
        warnings: Nicht-fatale Hinweise des Core (u. a. Sprach-Fallback, s. O5).
    """

    video_info: VideoInfo
    status: str
    transcript_available: bool
    warnings: list[str] = field(default_factory=list)


def fetch(url: str, language: str = "de") -> IntakeResult:
    """Ruft den Core in-process auf und mappt das Ergebnis auf `IntakeResult`.

    Args:
        url: YouTube-URL.
        language: Bevorzugte Transkript-Sprache (Fallback-Kette liegt im Core, O5).

    Returns:
        IntakeResult mit `VideoInfo` + Status/Transkript-Verfügbarkeit/Warnungen.

    Raises:
        IntakeUnavailable: Core nicht installiert/importierbar → Aufrufer soll auf
            den Alt-Pfad zurückfallen.
        IntakeFailed: Harter, inhaltlicher Fehler des Core (mit `error_code`).
    """
    # Lazy import: nur den CORE, niemals den Server. Fehlt das Paket, ist das kein
    # inhaltlicher Fehler, sondern „nicht verfügbar" → Fallback.
    try:
        from youtube_intake_core import process, IntakeError  # type: ignore
    except ImportError as e:
        raise IntakeUnavailable(
            f"youtube_intake_core ist nicht installiert/importierbar: {e}"
        ) from e

    try:
        data = process(url, language=language)
    except IntakeError as e:
        # Deckt InvalidURLError / VideoUnavailableError / processing_failed ab.
        error_code = getattr(e, "error_code", "processing_failed")
        message = getattr(e, "message", None) or str(e)
        raise IntakeFailed(error_code, message) from e
    except Exception as e:
        # Unerwartete Fehler aus dem Core (NICHT IntakeError) dürfen nicht roh
        # entkommen — sonst bricht der ValueError-Kontrakt der Aufrufer
        # (resolve_video_info fängt nur IntakeUnavailable/IntakeFailed). Als
        # harter Fehler mit generischem error_code weiterreichen.
        raise IntakeFailed("processing_failed", f"Unerwarteter Core-Fehler: {e}") from e

    try:
        raw_warnings = data.get("warnings", [])
        if not isinstance(raw_warnings, list):
            # Fail-fast wie bei den übrigen Kontrakt-Feldern statt still zu
            # coercen (z.B. würde list("text") die Zeichen zerlegen).
            raise TypeError(
                f"'warnings' muss eine Liste sein, war {type(raw_warnings).__name__}"
            )
        video_info = VideoInfo(
            title=data["title"],
            channel=data["channel"],
            duration=data["duration"],
            url=data["url"],
            transcript=data.get("transcript") or "",
        )
        return IntakeResult(
            video_info=video_info,
            status=data.get("status", ""),
            transcript_available=bool(data.get("transcript_available", False)),
            warnings=list(raw_warnings),
        )
    except (KeyError, TypeError) as e:
        # Wire-Form ist eingefroren; ein Mapping-Fehler heißt Kontraktbruch → laut
        # als harter Fehler melden statt still Falsches zu liefern.
        raise IntakeFailed(
            "mapping_error",
            f"Unerwartete Core-Antwortstruktur: {e}",
        ) from e
