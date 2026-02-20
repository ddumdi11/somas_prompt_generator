"""SQLite-basierter Bewertungsspeicher für SOMAS-Analysen.

Changelog v0.5.2:
- Schema-Versionierung mit automatischer Migration
- Neue channels-Tabelle für Kanal-Bewertungen
- model_rating_z Spalte in analyses (Z-Skala: -2 bis +2)
"""

import logging
import sqlite3
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

DB_DIR = Path.home() / ".somas_prompt_generator"
DB_PATH = DB_DIR / "ratings.db"

# Schema Version 1: Initiales Schema (v0.5.0)
SCHEMA_V1_SQL = """
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

    -- Quellen-Dimensionen (Legacy, 1=gut, -1=schlecht, NULL=nicht bewertet)
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

# Schema Version 2: Rating-Redesign (v0.5.2)
# - channels-Tabelle für Kanal-Bewertungen
# - model_rating_z in analyses (Z-Skala: -2 bis +2)
MIGRATION_V2_SQL = """
CREATE TABLE IF NOT EXISTS channels (
    channel_name    TEXT PRIMARY KEY,
    factual_score   INTEGER DEFAULT 0,
    argument_score  INTEGER DEFAULT 0,
    bias_direction  TEXT DEFAULT '',
    bias_strength   INTEGER DEFAULT 0,
    mode_tags       TEXT DEFAULT '',
    notes           TEXT DEFAULT '',
    updated_at      TEXT DEFAULT (datetime('now'))
);
"""

CURRENT_SCHEMA_VERSION = 2


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
        """Erstellt Datenbank und führt Migrationen durch."""
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            version = self._get_schema_version(conn)
            if version < 1:
                logger.info("Erstelle initiales DB-Schema (Version 1)")
                conn.executescript(SCHEMA_V1_SQL)
                self._set_schema_version(conn, 1)
                version = 1
            if version < 2:
                self._migrate_to_v2(conn)

    def _connect(self) -> sqlite3.Connection:
        """Erstellt eine DB-Verbindung."""
        return sqlite3.connect(str(self._db_path))

    def _get_schema_version(self, conn: sqlite3.Connection) -> int:
        """Liest die aktuelle Schema-Version. 0 wenn noch keine Versionierung."""
        try:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' AND name='schema_version'"
            )
            if cursor.fetchone() is None:
                # Prüfe ob analyses-Tabelle bereits existiert (v1 ohne Versioning)
                cursor = conn.execute(
                    "SELECT name FROM sqlite_master "
                    "WHERE type='table' AND name='analyses'"
                )
                if cursor.fetchone() is not None:
                    return 1  # Existierende DB ohne Versionierung = Version 1
                return 0  # Komplett neue DB
            row = conn.execute(
                "SELECT MAX(version) FROM schema_version"
            ).fetchone()
            return row[0] if row and row[0] is not None else 0
        except sqlite3.Error:
            return 0

    def _set_schema_version(self, conn: sqlite3.Connection, version: int) -> None:
        """Setzt die Schema-Version."""
        conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_version "
            "(version INTEGER PRIMARY KEY)"
        )
        conn.execute(
            "INSERT OR REPLACE INTO schema_version (version) VALUES (?)",
            (version,),
        )

    def _migrate_to_v2(self, conn: sqlite3.Connection) -> None:
        """Migration zu Version 2: channels-Tabelle + model_rating_z."""
        logger.info("Migriere DB-Schema auf Version 2")
        try:
            # channels-Tabelle anlegen
            conn.executescript(MIGRATION_V2_SQL)

            # model_rating_z Spalte zu analyses hinzufügen
            try:
                conn.execute(
                    "ALTER TABLE analyses ADD COLUMN model_rating_z INTEGER"
                )
            except sqlite3.OperationalError as e:
                if "duplicate column" not in str(e).lower():
                    raise

            self._set_schema_version(conn, 2)
            logger.info("DB-Schema auf Version 2 migriert")
        except Exception as e:
            logger.exception(f"Migration auf Version 2 fehlgeschlagen: {e}")
            raise

    # --- Analyse-CRUD ---

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
            row_id = cursor.lastrowid
            if row_id is None:
                raise RuntimeError("INSERT hat keine lastrowid zurückgegeben")
            return row_id

    def update_model_rating_z(self, analysis_id: int, z_score: int) -> None:
        """Setzt die Modell-Bewertung auf der Z-Skala (-2 bis +2).

        Args:
            analysis_id: ID der Analyse.
            z_score: -2 (sehr schlecht) bis +2 (sehr gut).
        """
        if not -2 <= z_score <= 2:
            raise ValueError(f"Z-Score muss -2 bis +2 sein, war: {z_score}")
        with self._connect() as conn:
            conn.execute(
                "UPDATE analyses SET model_rating_z = ? WHERE id = ?",
                (z_score, analysis_id),
            )

    def update_ratings(
        self, analysis_id: int,
        quality_score: int = 0,
        channel_informative: int = 0,
        channel_balanced: int = 0,
        channel_sourced: int = 0,
        channel_entertaining: int = 0,
    ) -> None:
        """Setzt alle Bewertungen in einem Call (Legacy-Methode).

        Args:
            quality_score: 0 = nicht bewertet, 1-5 = Sterne
            channel_*: 0 = nicht bewertet, 1 = gut, -1 = schlecht
        """
        with self._connect() as conn:
            db_quality = quality_score if quality_score > 0 else None
            db_informative = channel_informative if channel_informative != 0 else None
            db_balanced = channel_balanced if channel_balanced != 0 else None
            db_sourced = channel_sourced if channel_sourced != 0 else None
            db_entertaining = channel_entertaining if channel_entertaining != 0 else None
            conn.execute(
                """UPDATE analyses SET
                    quality_score = ?,
                    channel_informative = ?,
                    channel_balanced = ?,
                    channel_sourced = ?,
                    channel_entertaining = ?
                WHERE id = ?""",
                (db_quality, db_informative, db_balanced,
                 db_sourced, db_entertaining, analysis_id),
            )

    # --- Kanal-CRUD ---

    def save_channel_rating(
        self,
        channel_name: str,
        factual_score: int = 0,
        argument_score: int = 0,
        bias_direction: str = "",
        bias_strength: int = 0,
        mode_tags: str = "",
        notes: str = "",
    ) -> None:
        """Speichert oder aktualisiert eine Kanal-Bewertung.

        Args:
            channel_name: Name des Kanals (Primary Key).
            factual_score: Faktenqualität (-2 bis +2).
            argument_score: Argumentationsqualität (-2 bis +2).
            bias_direction: Bias-Richtung (z.B. "links", "neutral", "rechts").
            bias_strength: Bias-Stärke (0-3).
            mode_tags: Komma-getrennte Tags (z.B. "Bildung,Interview").
            notes: Freitext-Notizen.
        """
        with self._connect() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO channels (
                    channel_name, factual_score, argument_score,
                    bias_direction, bias_strength, mode_tags, notes,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))""",
                (
                    channel_name, factual_score, argument_score,
                    bias_direction, bias_strength, mode_tags, notes,
                ),
            )

    def get_channel_rating(self, channel_name: str) -> dict | None:
        """Holt die Kanal-Bewertung für einen bestimmten Kanal.

        Returns:
            Dict mit allen Kanal-Feldern oder None wenn nicht bewertet.
        """
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM channels WHERE channel_name = ?",
                (channel_name,),
            ).fetchone()
            if row is None:
                return None
            return dict(row)

    def get_all_channels(self) -> list[dict]:
        """Gibt alle bewerteten Kanäle zurück.

        Returns:
            Liste von Dicts mit allen Kanal-Feldern.
        """
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM channels ORDER BY channel_name"
            ).fetchall()
            return [dict(row) for row in rows]

    # --- Abfrage-Methoden (für späteres Info-Fenster, Punkt 5) ---

    def get_model_rankings(self, min_analyses: int = 3) -> list[dict]:
        """Modell-Rankings nach Durchschnittsqualität."""
        raise NotImplementedError("Wird in Phase 5 implementiert")

    def get_channel_rankings(self, min_analyses: int = 2) -> list[dict]:
        """Kanal-Rankings nach Durchschnittsqualität."""
        raise NotImplementedError("Wird in Phase 5 implementiert")

    def get_model_stats(self, model_id: str) -> dict:
        """Detailstatistik für ein einzelnes Modell."""
        raise NotImplementedError("Wird in Phase 5 implementiert")
