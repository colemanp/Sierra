"""Database connection and schema initialization"""
import sqlite3
from pathlib import Path
from typing import Optional

DEFAULT_DB_PATH = Path("data/prod/health_data.db")
TEST_DB_PATH = Path("data/test/health_data.db")
SCHEMA_PATH = Path(__file__).parent.parent.parent / "schema" / "init.sql"


class Database:
    """SQLite database manager"""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or DEFAULT_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: Optional[sqlite3.Connection] = None

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA foreign_keys = ON")
        return self._conn

    def init_schema(self) -> None:
        """Initialize database schema from init.sql"""
        if not SCHEMA_PATH.exists():
            raise FileNotFoundError(f"Schema file not found: {SCHEMA_PATH}")

        schema_sql = SCHEMA_PATH.read_text()
        self.conn.executescript(schema_sql)
        self.conn.commit()

    def get_source_id(self, source_name: str) -> int:
        """Get source ID by name"""
        cursor = self.conn.execute(
            "SELECT id FROM data_sources WHERE name = ?",
            (source_name,)
        )
        row = cursor.fetchone()
        if row is None:
            raise ValueError(f"Unknown data source: {source_name}")
        return row["id"]

    def create_import_log(self, source_id: int, file_path: str) -> int:
        """Create new import log entry, return ID"""
        cursor = self.conn.execute(
            """INSERT INTO import_log (source_id, file_path, status)
               VALUES (?, ?, 'running')""",
            (source_id, file_path)
        )
        self.conn.commit()
        return cursor.lastrowid

    def update_import_log(
        self,
        import_id: int,
        processed: int,
        inserted: int,
        skipped: int,
        conflicted: int,
        status: str = "completed",
        error_message: Optional[str] = None
    ) -> None:
        """Update import log with final counts"""
        self.conn.execute(
            """UPDATE import_log SET
                records_processed = ?,
                records_inserted = ?,
                records_skipped = ?,
                records_conflicted = ?,
                status = ?,
                error_message = ?
               WHERE id = ?""",
            (processed, inserted, skipped, conflicted, status, error_message, import_id)
        )
        self.conn.commit()

    def get_activity_type_id(self, garmin_type: str) -> Optional[int]:
        """Get activity type ID by Garmin type name"""
        cursor = self.conn.execute(
            "SELECT id FROM activity_types WHERE garmin_type = ?",
            (garmin_type,)
        )
        row = cursor.fetchone()
        return row["id"] if row else None

    def get_exercise_id(self, name: str) -> Optional[int]:
        """Get exercise ID by name or display_name (with normalization)"""
        # Normalize: lowercase, replace spaces/hyphens with underscore
        normalized = name.lower().replace(" ", "_").replace("-", "_")
        # Also try without trailing 's' for singular/plural matching
        normalized_singular = normalized.rstrip("s") if normalized.endswith("s") else normalized

        cursor = self.conn.execute(
            """SELECT id FROM strength_exercises
               WHERE name = ? OR display_name = ?
               OR name = ? OR name = ?
               OR name || 's' = ? OR ? || 's' = name""",
            (name, name, normalized, normalized_singular, normalized, normalized)
        )
        row = cursor.fetchone()
        return row["id"] if row else None

    def add_exercise(self, name: str, display_name: str, category: str, unit: str = "reps") -> int:
        """Add new exercise type"""
        cursor = self.conn.execute(
            """INSERT INTO strength_exercises (name, display_name, category, unit)
               VALUES (?, ?, ?, ?)""",
            (name.lower().replace(" ", "_").replace("-", "_"), display_name, category, unit)
        )
        self.conn.commit()
        return cursor.lastrowid

    def close(self) -> None:
        """Close database connection"""
        if self._conn:
            self._conn.close()
            self._conn = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
