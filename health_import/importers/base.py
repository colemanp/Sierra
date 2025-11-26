"""Base importer class"""
from abc import ABC, abstractmethod
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple

from ..core.database import Database
from ..core.conflicts import ConflictDetector
from ..core.models import ImportResult
from ..core.logging_setup import get_logger


class BaseImporter(ABC):
    """Abstract base class for all importers"""

    SOURCE_NAME: str = ""  # Override in subclasses

    def __init__(self, db: Database, verbosity: int = 0):
        self.db = db
        self.verbosity = verbosity
        self.logger = get_logger()
        self.source_id: Optional[int] = None
        self.import_id: Optional[int] = None
        self.conflict_detector: Optional[ConflictDetector] = None

    def import_file(self, file_path: Path) -> ImportResult:
        """Main entry point for importing a file"""
        self.logger.info(f"Starting import: {self.SOURCE_NAME}")
        self.logger.info(f"File: {file_path}")

        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        # Get source ID
        self.source_id = self.db.get_source_id(self.SOURCE_NAME)

        # Create import log
        self.import_id = self.db.create_import_log(self.source_id, str(file_path))
        self.logger.info(f"Created import log #{self.import_id}")

        # Initialize conflict detector
        self.conflict_detector = ConflictDetector(self.db.conn, self.import_id)

        result = ImportResult()

        try:
            # Parse and process file
            for record in self._parse_file(file_path):
                result.processed += 1
                outcome = self._process_record(record)

                if outcome == "inserted":
                    result.inserted += 1
                    if self.verbosity >= 1:
                        self._log_insert(record)
                elif outcome == "skipped":
                    result.skipped += 1
                    if self.verbosity >= 1:
                        self._log_skip(record)
                elif outcome == "conflict":
                    result.conflicted += 1

            self.db.conn.commit()

            # Update import log
            self.db.update_import_log(
                self.import_id,
                result.processed,
                result.inserted,
                result.skipped,
                result.conflicted,
                status="completed"
            )

            self.logger.info("Import complete")
            self.logger.info(f"       Processed:  {result.processed}")
            self.logger.info(f"       Inserted:   {result.inserted}")
            self.logger.info(f"       Skipped:    {result.skipped} (duplicates)")
            self.logger.info(f"       Conflicts:  {result.conflicted}")

            if result.conflicted > 0:
                self.logger.info(
                    f"View conflicts: python -m health_import conflicts --import-id {self.import_id}"
                )

        except Exception as e:
            self.db.update_import_log(
                self.import_id,
                result.processed,
                result.inserted,
                result.skipped,
                result.conflicted,
                status="failed",
                error_message=str(e)
            )
            raise

        return result

    @abstractmethod
    def _parse_file(self, file_path: Path) -> Iterator[Dict[str, Any]]:
        """Parse file and yield records as dicts. Override in subclass."""
        pass

    @abstractmethod
    def _process_record(self, record: Dict[str, Any]) -> str:
        """
        Process a single record.
        Returns: "inserted", "skipped", or "conflict"
        Override in subclass.
        """
        pass

    def _insert_with_conflict_check(
        self,
        table: str,
        key_fields: Dict[str, Any],
        data: Dict[str, Any],
        compare_fields: Optional[List[str]] = None
    ) -> str:
        """
        Insert record with conflict detection.
        Returns: "inserted", "skipped", or "conflict"
        """
        exists, conflict = self.conflict_detector.detect_conflict(
            table, key_fields, data, compare_fields
        )

        if not exists:
            # Insert new record
            data["import_id"] = self.import_id
            columns = ", ".join(data.keys())
            placeholders = ", ".join("?" for _ in data)
            self.db.conn.execute(
                f"INSERT INTO {table} ({columns}) VALUES ({placeholders})",
                tuple(data.values())
            )
            return "inserted"

        if conflict:
            # Log conflict
            self.conflict_detector.log_conflict(conflict)
            return "conflict"

        # Already exists, values match
        return "skipped"

    def _log_insert(self, record: Dict[str, Any]) -> None:
        """Log insert at verbose level. Override for custom formatting."""
        self.logger.debug(f"Inserted: {record}")

    def _log_skip(self, record: Dict[str, Any]) -> None:
        """Log skip at verbose level. Override for custom formatting."""
        self.logger.debug(f"Skipped: {record} (already exists)")
