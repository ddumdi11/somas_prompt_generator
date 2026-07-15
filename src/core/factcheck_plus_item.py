"""Datenmodelle für Faktencheck Plus (Stufe 2 Plus, v0.13.0, PR 4).

Analog zu :mod:`verification_item` (Classic-Weg): ``FactcheckPlusConfig`` kapselt
die Eingabe eines Plus-Laufs, ``FactcheckPlusResult`` den Lauf-Zustand.

Unterschied zum Classic-Weg: Es gibt **zwei** Modelle. Refiner/Mapper/Planner
laufen über das **Analyse-Modell** (PO-Entscheidung, Spec §8.3 — kein eigener
Picker), nur die Recherche (S5) braucht das web-fähige Verifikationsmodell.
Die Behauptungen kommen hier **ungekappt** herein: Im Plus-Modus ersetzt das
Deep-Research-Budget die Max-Behauptungen-Kappung (Spec §4), und die Auswahl
trifft der PolicyScorer.
"""
from dataclasses import dataclass, field

from .comparison_item import ModelChoice  # wiederverwenden


@dataclass
class FactcheckPlusConfig:
    """Eingabe für einen Faktencheck-Plus-Lauf (S1–S5).

    Attributes:
        claims: Die Roh-Behauptungen aus Stufe 1 — **ungekappt**, aber bereits
            Basisfakt-bereinigt (`cap_claims` mit `max_claims=0`). Die Auswahl
            trifft der PolicyScorer, nicht die GUI.
        analysis_model: Modell für S1/S2/S4 (Refiner/Mapper/Planner).
        research_model: Web-fähiges Modell für S5 (Recherche + Verdikt).
        budget: Deep-Research-Budget — wie viele Claims maximal recherchiert
            werden (PO-Default 8, Spec §8.1).
        language: Sprache der Ausgabe.
        core_thesis: SOMAS-Kernthese/Framing als Kontext für S1/S2/S4.
            Wird nie bewertet, nur zur Einordnung (Theorie §8.5).
        source_title: Titel der geprüften Quelle.
        source_url: URL der geprüften Quelle.
        web_unverified: True, wenn das Recherchemodell keinen bestätigten
            Web-Zugriff hat (rendert einen Disclaimer).
    """

    claims: list[str]
    analysis_model: ModelChoice
    research_model: ModelChoice
    budget: int = 8
    language: str = "Deutsch"
    core_thesis: str = ""
    source_title: str = ""
    source_url: str = ""
    web_unverified: bool = False

    @property
    def source_hint(self) -> str:
        """Identität der geprüften Quelle für den Unabhängigkeits-Riegel.

        Gleiches Format wie im Classic-Weg (`verification_worker`): Titel und
        URL zusammengefügt. Der server-seitige Eigenbeleg-Riegel
        (`factcheck_plus.verdict.check_forbidden_sources`) zerlegt ihn wieder.
        """
        return " ".join(p for p in (self.source_title, self.source_url) if p)


@dataclass
class FactcheckPlusResult:
    """Laufzeit-Zustand eines Faktencheck-Plus-Laufs.

    Attributes:
        config: Die zugrunde liegende Konfiguration.
        status: pending|running|done|error|skipped|cancelled.
        rendered_section: Fertiger Markdown-Abschnitt inkl. Header.
        refined_count: Zahl der atomisierten Prüfeinheiten (S1).
        selected_count: Zahl der vom PolicyScorer selektierten Claims (S3).
        verified_count: Zahl der tatsächlich geprüften Claims (S5) — kleiner bei
            Abbruch.
        failed_count: Zahl der Claims, deren Einzel-Call scheiterte.
        tokens_used: Summierter Token-Verbrauch über alle Stufen.
        error_message: Fehlermeldung bei status == "error".
    """

    config: FactcheckPlusConfig
    status: str = "pending"
    rendered_section: str = ""
    refined_count: int = 0
    selected_count: int = 0
    verified_count: int = 0
    failed_count: int = 0
    tokens_used: int = 0
    error_message: str = ""
    citations: list[str] = field(default_factory=list)
