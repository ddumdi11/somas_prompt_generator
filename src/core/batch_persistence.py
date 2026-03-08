"""Persistenz-Layer für Batch-Sessions (Crash-Resistenz).

Speichert Batch-Zustand als JSON in %TEMP%/somas_batch/,
damit bei App-Absturz Ergebnisse wiederhergestellt werden können.
"""

import json
import logging
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional

from .batch_item import BatchConfig, BatchItem

logger = logging.getLogger(__name__)

# Basisverzeichnis für Batch-Sessions
BATCH_BASE_DIR = Path(tempfile.gettempdir()) / "somas_batch"


def _ensure_base_dir() -> Path:
    """Stellt sicher, dass das Basisverzeichnis existiert."""
    BATCH_BASE_DIR.mkdir(parents=True, exist_ok=True)
    return BATCH_BASE_DIR


def create_batch_session(config: BatchConfig, urls: list[str]) -> Path:
    """Erstellt eine neue Batch-Session mit Konfiguration und Items.

    Args:
        config: Gemeinsame Batch-Einstellungen.
        urls: Liste der YouTube-URLs.

    Returns:
        Pfad zum Session-Verzeichnis.
    """
    base = _ensure_base_dir()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    session_dir = base / f"batch_{timestamp}"
    session_dir.mkdir(parents=True, exist_ok=True)

    # Status-Datei
    status = {
        "completed": False,
        "item_count": len(urls),
        "started_at": datetime.now().isoformat(),
        "completed_at": "",
    }
    (session_dir / "status.json").write_text(
        json.dumps(status, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # Konfiguration (ohne api_key)
    (session_dir / "config.json").write_text(
        json.dumps(config.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # Initiale Items
    for i, url in enumerate(urls):
        item = BatchItem(url=url, position=i + 1)
        save_item_state(session_dir, i, item)

    logger.info(f"Batch-Session erstellt: {session_dir} ({len(urls)} URLs)")
    return session_dir


def save_item_state(session_dir: Path, index: int, item: BatchItem) -> None:
    """Speichert den aktuellen Zustand eines BatchItems.

    Args:
        session_dir: Pfad zur Session.
        index: Item-Index (0-basiert).
        item: Das zu speichernde BatchItem.
    """
    item_path = session_dir / f"item_{index}.json"
    item_path.write_text(
        json.dumps(item.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def mark_batch_completed(session_dir: Path) -> None:
    """Markiert eine Batch-Session als abgeschlossen."""
    status_path = session_dir / "status.json"
    if status_path.exists():
        status = json.loads(status_path.read_text(encoding="utf-8"))
        status["completed"] = True
        status["completed_at"] = datetime.now().isoformat()
        status_path.write_text(
            json.dumps(status, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        logger.info(f"Batch-Session abgeschlossen: {session_dir}")


def delete_batch_session(session_dir: Path) -> None:
    """Löscht eine Batch-Session vollständig.

    Args:
        session_dir: Pfad zur Session.
    """
    import shutil

    if session_dir.exists() and session_dir.is_dir():
        shutil.rmtree(session_dir, ignore_errors=True)
        logger.info(f"Batch-Session gelöscht: {session_dir}")


def find_recoverable_sessions() -> list[dict]:
    """Sucht nach nicht abgeschlossenen Batch-Sessions.

    Returns:
        Liste von Dicts mit Session-Metadaten:
        - path: Path
        - item_count: int
        - timestamp: str
        - done_count: int (Anzahl fertiger Items)
    """
    base = BATCH_BASE_DIR
    if not base.exists():
        return []

    sessions = []
    for entry in sorted(base.iterdir()):
        if not entry.is_dir() or not entry.name.startswith("batch_"):
            continue

        status_path = entry / "status.json"
        if not status_path.exists():
            continue

        try:
            status = json.loads(status_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue

        # Nur nicht-abgeschlossene Sessions
        if status.get("completed", False):
            continue

        item_count = status.get("item_count", 0)
        done_count = 0
        for i in range(item_count):
            item_path = entry / f"item_{i}.json"
            if item_path.exists():
                try:
                    item_data = json.loads(
                        item_path.read_text(encoding="utf-8")
                    )
                    if item_data.get("status") == "done":
                        done_count += 1
                except (json.JSONDecodeError, OSError):
                    pass

        sessions.append({
            "path": entry,
            "item_count": item_count,
            "timestamp": status.get("started_at", ""),
            "done_count": done_count,
        })

    return sessions


def load_session(
    session_dir: Path,
) -> Optional[tuple[BatchConfig, list[BatchItem]]]:
    """Lädt eine Batch-Session aus dem Temp-Verzeichnis.

    Args:
        session_dir: Pfad zur Session.

    Returns:
        Tuple (BatchConfig, Liste von BatchItems) oder None bei Fehler.
        Hinweis: api_key ist in der geladenen Config leer.
    """
    config_path = session_dir / "config.json"
    status_path = session_dir / "status.json"

    if not config_path.exists() or not status_path.exists():
        logger.warning(f"Session unvollständig: {session_dir}")
        return None

    try:
        config_data = json.loads(config_path.read_text(encoding="utf-8"))
        config = BatchConfig.from_dict(config_data)

        status_data = json.loads(status_path.read_text(encoding="utf-8"))
        item_count = status_data.get("item_count", 0)

        items = []
        for i in range(item_count):
            item_path = session_dir / f"item_{i}.json"
            if item_path.exists():
                item_data = json.loads(
                    item_path.read_text(encoding="utf-8")
                )
                items.append(BatchItem.from_dict(item_data))
            else:
                logger.warning(f"Item {i} fehlt in Session {session_dir}")
                items.append(BatchItem(url="", position=i + 1, status="error",
                                       error_message="Item-Datei fehlt"))

        logger.info(
            f"Session geladen: {session_dir} "
            f"({len(items)} Items, Config: {config.preset_name})"
        )
        return config, items

    except (json.JSONDecodeError, KeyError, OSError) as e:
        logger.exception(f"Session laden fehlgeschlagen: {session_dir}")
        return None
