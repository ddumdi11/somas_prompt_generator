"""Golden-Snapshot des Transkript-Prompts (Regressionsbasis für v0.16.0).

Bewusst ohne ``test_``-Präfix — pytest sammelt das Modul nicht ein. Die Matrix
deckt alle Presets × (freie Modulwahl | erzwungener FAKTENCHECK) × (manuelles |
automatisches Transkript) ab. Der Snapshot ``tests/fixtures/transcript_prompt_golden_v0.15.3.json``
wurde mit dem UNVERÄNDERTEN v0.15.3-Builder erzeugt; der Bündel-Modus darf ihn
bei ausgeschalteter Checkbox nicht um ein Byte verändern.

Neu erzeugen (nur bei bewusster Template-Änderung!):
    python tests/transcript_golden_helpers.py
"""
import json
import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config.defaults import SomasConfig
from src.core import prompt_builder
from src.core.prompt_builder import build_prompt_from_transcript, get_preset_names

GOLDEN_PATH = (
    Path(__file__).resolve().parent / "fixtures" / "transcript_prompt_golden_v0.15.3.json"
)

# Fester „Heute"-Wert, damit der Zeitanker deterministisch ist.
FIXED_NOW = datetime(2026, 10, 26, 9, 0)

# Transkript mit führenden Nummern, Leerzeilen und Einrückung — die Stellen, an
# denen eine Normalisierung auffallen würde.
TRANSCRIPT = (
    "1. Erster Punkt des Vortrags.\n"
    "\n"
    "2. Zweiter Punkt — mit „Zitat\" und Umlauten äöü.\n"
    "   eingerückte Folgezeile\n"
    "3.1 Unterpunkt\n"
)


class _FixedDatetime(datetime):
    """``datetime`` mit festem ``now()`` für den Zeitanker."""

    @classmethod
    def now(cls, tz=None):  # noqa: D102 — Testdoppel
        return FIXED_NOW


def render_case(preset: str, module: str | None, auto: bool, **extra) -> str:
    """Rendert einen Transkript-Prompt mit festem Datum.

    Args:
        preset: Preset-Anzeigename.
        module: Erzwungenes Modul (``None`` = freie Wahl).
        auto: ``is_auto_transcript``.
        **extra: Zusätzliche Builder-Argumente (z.B. Bündel-Flagge).

    Returns:
        Der gerenderte Prompt.
    """
    with patch.object(prompt_builder, "datetime", _FixedDatetime):
        return build_prompt_from_transcript(
            title="Testtitel", author="Testkanal", transcript=TRANSCRIPT,
            config=SomasConfig(), url=None, questions="Eine Anschlussfrage?",
            preset_name=preset, is_auto_transcript=auto,
            custom_module=module, **extra,
        )


def case_keys() -> list[tuple[str, str | None, bool]]:
    """Alle Fälle der Matrix als ``(preset, module, auto)``."""
    return [
        (preset, module, auto)
        for preset in get_preset_names()
        for module in (None, "FAKTENCHECK")
        for auto in (False, True)
    ]


def key_str(preset: str, module: str | None, auto: bool) -> str:
    """Stabiler JSON-Schlüssel eines Falls."""
    return f"{preset}|{module or '-'}|{'auto' if auto else 'manual'}"


def load_golden() -> dict:
    """Lädt den eingefrorenen v0.15.3-Snapshot."""
    return json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))


if __name__ == "__main__":
    golden = {key_str(*k): render_case(*k) for k in case_keys()}
    GOLDEN_PATH.write_text(
        json.dumps(golden, ensure_ascii=False, indent=1) + "\n", encoding="utf-8",
    )
    print(f"{len(golden)} Fälle → {GOLDEN_PATH}")
