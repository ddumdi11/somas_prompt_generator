"""Verwaltung benutzerdefinierter Prompt-Presets.

Speichert User-Presets in user_presets.json. Jedes Preset enthält einen
angepassten system_prompt und optional ein fixiertes Modul.
"""

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

USER_PRESETS_PATH = Path(__file__).parent.parent / "config" / "user_presets.json"

VALID_MODULES = frozenset({
    "KRITIK", "ZITATE", "OFFENE_FRAGEN", "VERBINDUNGEN",
    "SUBTEXT", "FAKTENCHECK",
})


@dataclass
class UserPreset:
    """Ein benutzerdefiniertes Prompt-Preset.

    Attributes:
        id: Einzigartiger Key (usr_ + Timestamp).
        name: Anzeigename im Dropdown.
        base_preset: Preset-ID aus prompt_presets.json (z.B. "standard").
        created_at: ISO-8601 Timestamp.
        system_prompt: Der editierte System-Prompt (Role + Analysis kombiniert).
        fixed_module: Eines der 6 Module oder None für automatisch.
    """

    id: str
    name: str
    base_preset: str
    created_at: str
    system_prompt: str
    fixed_module: str | None = None


class UserPresetStore:
    """Lädt und speichert User-Presets aus/in user_presets.json."""

    def __init__(self, path: Path = USER_PRESETS_PATH) -> None:
        self._path = path
        self._presets: list[UserPreset] = []
        self._load()

    def _load(self) -> None:
        """Lädt Presets aus der JSON-Datei. Erstellt leere Datei falls nicht vorhanden."""
        if not self._path.exists():
            self._save_raw({"version": "1.0", "presets": []})
            return
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            self._presets = [
                UserPreset(**p) for p in data.get("presets", [])
            ]
        except Exception as e:
            logger.warning("user_presets.json konnte nicht geladen werden: %s", e)
            self._presets = []

    def _save_raw(self, data: dict) -> None:
        """Schreibt Roh-Dict als JSON (atomar via Temp-Datei + Replace)."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self._path.with_suffix(".json.tmp")
        tmp_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        tmp_path.replace(self._path)

    def _save(self) -> None:
        """Persistiert den aktuellen Stand."""
        self._save_raw({
            "version": "1.0",
            "presets": [
                {
                    "id": p.id,
                    "name": p.name,
                    "base_preset": p.base_preset,
                    "created_at": p.created_at,
                    "system_prompt": p.system_prompt,
                    "fixed_module": p.fixed_module,
                }
                for p in self._presets
            ],
        })

    def get_all(self) -> list[UserPreset]:
        """Gibt alle User-Presets zurück."""
        return list(self._presets)

    def get_by_id(self, preset_id: str) -> UserPreset | None:
        """Findet ein Preset anhand seiner ID."""
        for p in self._presets:
            if p.id == preset_id:
                return p
        return None

    def find_by_name(self, name: str) -> UserPreset | None:
        """Findet ein Preset anhand seines Namens (für UPSERT)."""
        for p in self._presets:
            if p.name == name:
                return p
        return None

    def save_preset(self, preset: UserPreset) -> None:
        """Speichert ein neues Preset oder überschreibt ein bestehendes (gleiche ID)."""
        self._presets = [p for p in self._presets if p.id != preset.id]
        self._presets.append(preset)
        self._save()

    def rename_preset(self, preset_id: str, new_name: str) -> bool:
        """Benennt ein Preset um. Gibt False zurück wenn ID nicht gefunden."""
        for p in self._presets:
            if p.id == preset_id:
                p.name = new_name.strip()
                self._save()
                return True
        return False

    def delete_preset(self, preset_id: str) -> bool:
        """Löscht ein Preset. Gibt False zurück wenn ID nicht gefunden."""
        before = len(self._presets)
        self._presets = [p for p in self._presets if p.id != preset_id]
        if len(self._presets) < before:
            self._save()
            return True
        return False

    @staticmethod
    def generate_id() -> str:
        """Erzeugt eine eindeutige Preset-ID."""
        return f"usr_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
