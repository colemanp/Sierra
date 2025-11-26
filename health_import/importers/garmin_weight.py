"""Garmin weight/body composition CSV importer"""
import csv
from pathlib import Path
from typing import Any, Dict, Iterator, Optional

from .base import BaseImporter
from ..transforms.datetime_utils import parse_garmin_date, parse_time_12h


class GarminWeightImporter(BaseImporter):
    """Import Garmin Connect weight/body composition exports

    Garmin exports weight data in a non-standard multiline CSV format:
    - Odd rows contain the date (e.g., " Nov 25, 2025")
    - Even rows contain the measurement data
    """

    SOURCE_NAME = "garmin_weight"

    def _parse_file(self, file_path: Path) -> Iterator[Dict[str, Any]]:
        """Parse Garmin weight CSV (multiline format)"""
        with open(file_path, "r", encoding="utf-8-sig") as f:
            lines = f.readlines()

        if not lines:
            return

        # Skip header row
        lines = lines[1:]

        # Process pairs of lines (date row + data row)
        current_date = None
        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Date lines start with a quote and contain month name
            # Format: '" Nov 25, 2025",'
            if line.startswith('"'):
                # Extract the date from quotes
                # Find content between first pair of quotes
                end_quote = line.find('"', 1)
                if end_quote > 0:
                    current_date = line[1:end_quote].strip()
                continue

            # Data line: time,weight,change,bmi,body_fat,muscle,bone,water
            parts = line.rstrip(",").split(",")

            # This is a data line (starts with time like "9:25 AM")
            if current_date and len(parts) >= 8:
                yield {
                    "date": current_date,
                    "time": parts[0].strip() if parts[0].strip() else None,
                    "weight": parts[1].strip() if len(parts) > 1 else None,
                    "change": parts[2].strip() if len(parts) > 2 else None,
                    "bmi": parts[3].strip() if len(parts) > 3 else None,
                    "body_fat": parts[4].strip() if len(parts) > 4 else None,
                    "muscle_mass": parts[5].strip() if len(parts) > 5 else None,
                    "bone_mass": parts[6].strip() if len(parts) > 6 else None,
                    "body_water": parts[7].strip() if len(parts) > 7 else None,
                }

    def _process_record(self, record: Dict[str, Any]) -> str:
        """Process a single weight record"""
        # Parse date
        date_iso = parse_garmin_date(record.get("date"))
        if not date_iso:
            self.logger.warning(f"Skipping record with invalid date: {record.get('date')}")
            return "skipped"

        # Parse time
        time_24h = parse_time_12h(record.get("time"))

        # Build measurement data
        data = {
            "source_id": self.source_id,
            "measurement_date": date_iso,
            "measurement_time": time_24h,
            "weight_lbs": self._parse_weight(record.get("weight")),
            "weight_change_lbs": self._parse_weight(record.get("change")),
            "bmi": self._parse_float(record.get("bmi")),
            "body_fat_pct": self._parse_percent(record.get("body_fat")),
            "muscle_mass_lbs": self._parse_weight(record.get("muscle_mass")),
            "bone_mass_lbs": self._parse_weight(record.get("bone_mass")),
            "body_water_pct": self._parse_percent(record.get("body_water")),
        }

        # Key fields for conflict detection
        key_fields = {
            "source_id": self.source_id,
            "measurement_date": date_iso,
            "measurement_time": time_24h,
        }

        return self._insert_with_conflict_check(
            "body_measurements",
            key_fields,
            data
        )

    def _parse_float(self, value: Optional[str]) -> Optional[float]:
        """Parse float, handling empty strings"""
        if not value or value.strip() == "":
            return None
        try:
            return float(value.strip())
        except ValueError:
            return None

    def _parse_weight(self, value: Optional[str]) -> Optional[float]:
        """Parse weight value like '157.4 lbs'"""
        if not value or value.strip() == "":
            return None
        try:
            # Remove 'lbs' suffix and parse
            clean = value.replace("lbs", "").strip()
            return float(clean)
        except ValueError:
            return None

    def _parse_percent(self, value: Optional[str]) -> Optional[float]:
        """Parse percentage value like '22.4 %'"""
        if not value or value.strip() == "":
            return None
        try:
            # Remove '%' suffix and parse
            clean = value.replace("%", "").strip()
            return float(clean)
        except ValueError:
            return None

    def _log_insert(self, record: Dict[str, Any]) -> None:
        """Log insert with weight details"""
        date = record.get("date", "")
        weight = record.get("weight", "")
        self.logger.info(f"Inserted: {date} - {weight}")

    def _log_skip(self, record: Dict[str, Any]) -> None:
        """Log skip with date"""
        date = record.get("date", "")
        self.logger.debug(f"Skipped: {date} (already exists)")
