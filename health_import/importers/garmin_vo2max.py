"""Garmin VO2 Max CSV importer"""
from pathlib import Path
from typing import Any, Dict, Iterator, Optional

from .base import BaseImporter
from ..transforms.datetime_utils import parse_garmin_date
from ..garmin.vo2max import import_vo2max_to_db


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

    def import_file(self, file_path: Path) -> Dict[str, int]:
        """Import file using shared import logic"""
        self.logger.info(f"Importing {file_path}")

        # Parse CSV to normalized records
        records = []
        for raw_record in self._parse_file(file_path):
            date_iso = parse_garmin_date(raw_record.get("date"))
            vo2max = self._parse_float(raw_record.get("vo2max"))

            if not date_iso or vo2max is None:
                continue

            records.append({
                "date": date_iso,
                "activity_type": raw_record.get("activity_type", "").strip() or None,
                "vo2max": vo2max,
            })

        # Use shared import function
        result = import_vo2max_to_db(self.db.conn, records, self.source_id)

        self.logger.info(
            f"Completed: {result['processed']} processed, "
            f"{result['inserted']} inserted, {result['skipped']} skipped"
        )
        return result

    def _process_record(self, record: Dict[str, Any]) -> str:
        """Not used - import_file overrides base class"""
        raise NotImplementedError("Use import_file instead")

    def _parse_float(self, value: Optional[str]) -> Optional[float]:
        """Parse float value"""
        if not value or value.strip() == "":
            return None
        try:
            return float(value.strip())
        except ValueError:
            return None
