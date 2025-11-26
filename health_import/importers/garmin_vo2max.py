"""Garmin VO2 Max CSV importer"""
import csv
from pathlib import Path
from typing import Any, Dict, Iterator, Optional

from .base import BaseImporter
from ..transforms.datetime_utils import parse_garmin_date


class GarminVO2MaxImporter(BaseImporter):
    """Import Garmin VO2 Max CSV exports

    Format:
    - Header rows (skip first 2 lines)
    - Data: date, activity_type, vo2max_value
    """

    SOURCE_NAME = "garmin_vo2max"

    def _parse_file(self, file_path: Path) -> Iterator[Dict[str, Any]]:
        """Parse Garmin VO2 Max CSV"""
        with open(file_path, "r", encoding="utf-8-sig") as f:
            lines = f.readlines()

        # Skip header rows (first 2 lines)
        for line in lines[2:]:
            line = line.strip()
            if not line:
                continue

            parts = line.split(",")
            if len(parts) >= 3:
                yield {
                    "date": parts[0].strip(),
                    "activity_type": parts[1].strip(),
                    "vo2max": parts[2].strip(),
                }

    def _process_record(self, record: Dict[str, Any]) -> str:
        """Process a single VO2 Max record"""
        # Parse date
        date_iso = parse_garmin_date(record.get("date"))
        if not date_iso:
            self.logger.warning(f"Skipping record with invalid date: {record.get('date')}")
            return "skipped"

        # Parse VO2 Max value
        vo2max = self._parse_float(record.get("vo2max"))
        if vo2max is None:
            self.logger.warning(f"Skipping record with invalid VO2 Max: {record.get('vo2max')}")
            return "skipped"

        activity_type = record.get("activity_type", "").strip() or None

        # Build data
        data = {
            "source_id": self.source_id,
            "measurement_date": date_iso,
            "activity_type": activity_type,
            "vo2max_value": vo2max,
        }

        # Key fields for conflict detection
        key_fields = {
            "source_id": self.source_id,
            "measurement_date": date_iso,
            "activity_type": activity_type,
        }

        return self._insert_with_conflict_check(
            "garmin_vo2max",
            key_fields,
            data
        )

    def _parse_float(self, value: Optional[str]) -> Optional[float]:
        """Parse float value"""
        if not value or value.strip() == "":
            return None
        try:
            return float(value.strip())
        except ValueError:
            return None

    def _log_insert(self, record: Dict[str, Any]) -> None:
        """Log insert with VO2 Max details"""
        date = record.get("date", "")
        vo2max = record.get("vo2max", "")
        activity = record.get("activity_type", "")
        self.logger.info(f"Inserted: {date} - {activity} VO2 Max: {vo2max}")

    def _log_skip(self, record: Dict[str, Any]) -> None:
        """Log skip with date"""
        date = record.get("date", "")
        self.logger.debug(f"Skipped: {date} (already exists)")
