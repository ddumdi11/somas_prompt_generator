"""Datenmodelle für die Faktencheck-Verifikation (Stufe 2, v0.10.0).

VerificationConfig kapselt die (bereits gekappte) Behauptungsliste + das
gewählte Verifikationsmodell; VerificationResult hält den Lauf-Zustand.
Die Kappung passiert bewusst VOR dem Worker (in der GUI), damit der Worker
frei von UI-/Settings-Wissen und headless testbar bleibt.
"""

from dataclasses import dataclass, field

from .comparison_item import ModelChoice  # wiederverwenden


@dataclass
class VerificationConfig:
    """Eingabe für einen Verifikationslauf.

    Attributes:
        claims: Bereits gekappte Liste (Top-N), die geprüft wird.
        model: Das gewählte Verifikationsmodell.
        language: Sprache der Ausgabe (Default Deutsch).
        total_claims: Gesamtzahl der Behauptungen VOR der Kappung
            (für die Transparenzzeile).
        source_title: Optionaler Quellentitel (Anzeige/Debug).
        source_url: Optionale Quellen-URL (Anzeige/Debug).
    """

    claims: list[str]
    model: ModelChoice
    language: str = "Deutsch"
    total_claims: int = 0
    source_title: str = ""
    source_url: str = ""


@dataclass
class VerificationResult:
    """Laufzeit-Zustand eines Verifikationslaufs.

    Attributes:
        config: Die zugrunde liegende VerificationConfig.
        status: pending|running|done|error|skipped.
        raw_output: Bereinigte Modell-Ausgabe (Pro-Behauptung-Blöcke).
        rendered_section: Fertiger Markdown-Abschnitt inkl. Header.
        citations: Deduplizierte Quellen-URLs (falls Provider welche liefert).
        tokens_used: Token-Verbrauch.
        error_message: Fehlermeldung bei status == "error".
    """

    config: VerificationConfig
    status: str = "pending"
    raw_output: str = ""
    rendered_section: str = ""
    citations: list[str] = field(default_factory=list)
    tokens_used: int = 0
    error_message: str = ""
