"""Conflict detection and resolution for imports"""
import json
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional, Tuple
import sqlite3

from .logging_setup import get_logger


@dataclass
class ConflictInfo:
    """Information about a detected conflict"""
    table_name: str
    record_key: Dict[str, Any]
    existing_value: Dict[str, Any]
    new_value: Dict[str, Any]
    conflict_fields: List[str]


# Tolerance values for comparing numeric fields
TOLERANCES = {
    "weight_lbs": 0.1,
    "distance_miles": 0.01,
    "duration_seconds": 1.0,
    "calories_total": 1.0,
    "avg_hr": 1,
    "max_hr": 1,
    "body_fat_pct": 0.1,
    "muscle_mass_lbs": 0.1,
    "vo2max_value": 0.1,
}


def values_match(field: str, existing: Any, new: Any) -> bool:
    """Check if two values match, accounting for tolerances"""
    if existing is None and new is None:
        return True
    if existing is None or new is None:
        return False

    # Check if field has a tolerance
    tolerance = TOLERANCES.get(field)
    if tolerance is not None:
        try:
            return abs(float(existing) - float(new)) <= tolerance
        except (ValueError, TypeError):
            pass

    return existing == new


class ConflictDetector:
    """Detects and logs conflicts during imports"""

    def __init__(self, conn: sqlite3.Connection, import_id: int):
        self.conn = conn
        self.import_id = import_id
        self.logger = get_logger()

    def check_exists(
        self,
        table: str,
        key_fields: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Check if record exists by natural key.
        Returns existing record as dict or None.
        """
        where_clause = " AND ".join(f"{k} = ?" for k in key_fields.keys())
        query = f"SELECT * FROM {table} WHERE {where_clause}"

        cursor = self.conn.execute(query, tuple(key_fields.values()))
        row = cursor.fetchone()

        if row:
            return dict(row)
        return None

    def detect_conflict(
        self,
        table: str,
        key_fields: Dict[str, Any],
        new_data: Dict[str, Any],
        compare_fields: Optional[List[str]] = None
    ) -> Tuple[bool, Optional[ConflictInfo]]:
        """
        Check for conflicts between existing and new data.

        Returns:
            (exists, conflict_info)
            - (False, None) if record doesn't exist
            - (True, None) if exists and values match
            - (True, ConflictInfo) if exists and values differ
        """
        existing = self.check_exists(table, key_fields)

        if existing is None:
            return (False, None)

        # Determine fields to compare
        if compare_fields is None:
            # Compare all fields except metadata
            skip_fields = {"id", "import_id", "created_at", "source_id"}
            compare_fields = [
                k for k in new_data.keys()
                if k not in skip_fields and k not in key_fields
            ]

        # Find differing fields
        conflict_fields = []
        for field in compare_fields:
            if field in existing and field in new_data:
                if not values_match(field, existing[field], new_data[field]):
                    conflict_fields.append(field)

        if not conflict_fields:
            return (True, None)  # Exists, values match

        # Build conflict info
        conflict = ConflictInfo(
            table_name=table,
            record_key=key_fields,
            existing_value={f: existing.get(f) for f in conflict_fields},
            new_value={f: new_data.get(f) for f in conflict_fields},
            conflict_fields=conflict_fields
        )

        return (True, conflict)

    def log_conflict(self, conflict: ConflictInfo) -> None:
        """Log conflict to database and console"""
        # Log to console
        key_str = ", ".join(f"{k}={v}" for k, v in conflict.record_key.items())
        self.logger.warning(f"Conflict: {conflict.table_name} - {key_str}")
        for field in conflict.conflict_fields:
            existing = conflict.existing_value[field]
            new = conflict.new_value[field]
            self.logger.warning(f"       {field}: {existing} -> {new}")
        self.logger.warning("       Keeping existing record")

        # Log to database
        self.conn.execute(
            """INSERT INTO import_conflicts
               (import_id, table_name, record_key, existing_value, new_value, conflict_fields)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                self.import_id,
                conflict.table_name,
                json.dumps(conflict.record_key),
                json.dumps(conflict.existing_value),
                json.dumps(conflict.new_value),
                json.dumps(conflict.conflict_fields)
            )
        )
