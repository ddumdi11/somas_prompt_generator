"""SQLite-basierter Bewertungsspeicher für SOMAS-Analysen."""

import logging
import sqlite3
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

DB_DIR = Path.home() / ".somas_prompt_generator"
DB_PATH = DB_DIR / "ratings.db"

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS analyses (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp       TEXT NOT NULL DEFAULT (datetime('now')),

    -- Modell-Info
    provider_id     TEXT NOT NULL,
    model_id        TEXT NOT NULL,
    model_name      TEXT NOT NULL,

    -- Video/Kanal-Info
    video_url       TEXT,
    video_title     TEXT,
    channel_name    TEXT,
    video_duration  INTEGER DEFAULT 0,

    -- Preset-Info
    preset_name     TEXT NOT NULL,
    preset_max_chars INTEGER DEFAULT 0,

    -- Automatische Metriken
    result_chars    INTEGER NOT NULL,
    response_time   REAL NOT NULL,
    tokens_used     INTEGER DEFAULT 0,
    price_input     REAL DEFAULT 0,
    price_output    REAL DEFAULT 0,

    -- Berechnete Metriken
    limit_ratio     REAL,
    is_over_limit   BOOLEAN DEFAULT 0,

    -- Manuelle Bewertung (optional)
    quality_score   INTEGER,

    -- Quellen-Dimensionen (1=gut, -1=schlecht, NULL=nicht bewertet)
    channel_informative   INTEGER,
    channel_balanced      INTEGER,
    channel_sourced       INTEGER,
    channel_entertaining  INTEGER,

    -- Kontext
    input_mode      TEXT DEFAULT 'youtube',
    had_transcript  BOOLEAN DEFAULT 0,
    had_time_range  BOOLEAN DEFAULT 0,
    had_questions   BOOLEAN DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_model ON analyses(model_id);
CREATE INDEX IF NOT EXISTS idx_channel ON analyses(channel_name);
CREATE INDEX IF NOT EXISTS idx_preset ON analyses(preset_name);
CREATE INDEX IF NOT EXISTS idx_timestamp ON analyses(timestamp);
"""


@dataclass
class AnalysisRecord:
    """Datensatz für eine einzelne Analyse."""

    # Modell
    provider_id: str
    model_id: str
    model_name: str
    # Video
    video_url: str = ""
    video_title: str = ""
    channel_name: str = ""
    video_duration: int = 0
    # Preset
    preset_name: str = ""
    preset_max_chars: int = 0
    # Automatische Metriken
    result_chars: int = 0
    response_time: float = 0.0
    tokens_used: int = 0
    price_input: float = 0.0
    price_output: float = 0.0
    # Kontext
    input_mode: str = "youtube"
    had_transcript: bool = False
    had_time_range: bool = False
    had_questions: bool = False


class RatingStore:
    """Verwaltet die SQLite-Datenbank für Analyse-Bewertungen."""

    def __init__(self, db_path: Path = DB_PATH):
        self._db_path = db_path
        self._ensure_db()

    def _ensure_db(self) -> None:
        """Erstellt Datenbank und Tabelle falls nicht vorhanden."""
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(SCHEMA_SQL)

    def _connect(self) -> sqlite3.Connection:
        """Erstellt eine DB-Verbindung."""
        return sqlite3.connect(str(self._db_path))

    def save_analysis(self, record: AnalysisRecord) -> int:
        """Speichert eine Analyse und gibt die ID zurück."""
        limit_ratio = None
        is_over_limit = False
        if record.preset_max_chars > 0:
            limit_ratio = record.result_chars / record.preset_max_chars
            is_over_limit = record.result_chars > record.preset_max_chars

        with self._connect() as conn:
            cursor = conn.execute(
                """INSERT INTO analyses (
                    provider_id, model_id, model_name,
                    video_url, video_title, channel_name, video_duration,
                    preset_name, preset_max_chars,
                    result_chars, response_time, tokens_used,
                    price_input, price_output,
                    limit_ratio, is_over_limit,
                    input_mode, had_transcript, had_time_range, had_questions
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    record.provider_id, record.model_id, record.model_name,
                    record.video_url, record.video_title, record.channel_name,
                    record.video_duration,
                    record.preset_name, record.preset_max_chars,
                    record.result_chars, record.response_time, record.tokens_used,
                    record.price_input, record.price_output,
                    limit_ratio, is_over_limit,
                    record.input_mode, record.had_transcript,
                    record.had_time_range, record.had_questions,
                ),
            )
            return cursor.lastrowid

    def update_quality_score(self, analysis_id: int, score: int) -> None:
        """Setzt die manuelle Qualitätsbewertung (1-5)."""
        if not 1 <= score <= 5:
            raise ValueError(f"Score muss 1-5 sein, war: {score}")
        with self._connect() as conn:
            conn.execute(
                "UPDATE analyses SET quality_score = ? WHERE id = ?",
                (score, analysis_id),
            )

    def update_ratings(
        self, analysis_id: int,
        quality_score: int = 0,
        channel_informative: int = 0,
        channel_balanced: int = 0,
        channel_sourced: int = 0,
        channel_entertaining: int = 0,
    ) -> None:
        """Setzt alle Bewertungen in einem Call.

        Args:
            quality_score: 0 = nicht bewertet, 1-5 = Sterne
            channel_*: 0 = nicht bewertet, 1 = gut, -1 = schlecht
        """
        with self._connect() as conn:
            # quality_score: >0 setzen, 0 → NULL (Abwahl)
            db_quality = quality_score if quality_score > 0 else None
            conn.execute(
                "UPDATE analyses SET quality_score = ? WHERE id = ?",
                (db_quality, analysis_id),
            )
            for field, value in [
                ("channel_informative", channel_informative),
                ("channel_balanced", channel_balanced),
                ("channel_sourced", channel_sourced),
                ("channel_entertaining", channel_entertaining),
            ]:
                # value != 0 → setzen, value == 0 → auf NULL zurücksetzen
                # (damit Abwahl einer vorherigen Bewertung wirkt)
                db_value = value if value != 0 else None
                conn.execute(
                    f"UPDATE analyses SET {field} = ? WHERE id = ?",
                    (db_value, analysis_id),
                )

    # --- Abfrage-Methoden (für späteres Info-Fenster, Punkt 5) ---

    def get_model_rankings(self, min_analyses: int = 3) -> list[dict]:
        """Modell-Rankings nach Durchschnittsqualität."""
        ...

    def get_channel_rankings(self, min_analyses: int = 2) -> list[dict]:
        """Kanal-Rankings nach Durchschnittsqualität."""
        ...

    def get_model_stats(self, model_id: str) -> dict:
        """Detailstatistik für ein einzelnes Modell."""
        ...
