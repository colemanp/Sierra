"""Garmin weight/body composition CSV importer"""
from pathlib import Path
from typing import Any, Dict, Iterator, Optional

from .base import BaseImporter
from ..transforms.datetime_utils import parse_garmin_date, parse_time_12h
from ..garmin.weight import import_weight_to_db


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

    def import_file(self, file_path: Path) -> Dict[str, int]:
        """Import file using shared import logic"""
        self.logger.info(f"Importing {file_path}")

        # Parse CSV to normalized records
        records = []
        for raw_record in self._parse_file(file_path):
            date_iso = parse_garmin_date(raw_record.get("date"))
            if not date_iso:
                continue

            weight_lbs = self._parse_weight(raw_record.get("weight"))
            if not weight_lbs:
                continue

            records.append({
                "measurement_date": date_iso,
                "measurement_time": parse_time_12h(raw_record.get("time")),
                "weight_lbs": weight_lbs,
                "weight_change_lbs": self._parse_weight(raw_record.get("change")),
                "bmi": self._parse_float(raw_record.get("bmi")),
                "body_fat_pct": self._parse_percent(raw_record.get("body_fat")),
                "muscle_mass_lbs": self._parse_weight(raw_record.get("muscle_mass")),
                "bone_mass_lbs": self._parse_weight(raw_record.get("bone_mass")),
                "body_water_pct": self._parse_percent(raw_record.get("body_water")),
            })

        # Use shared import function
        result = import_weight_to_db(self.db.conn, records, self.source_id)

        self.logger.info(
            f"Completed: {result['processed']} processed, "
            f"{result['inserted']} inserted, {result['skipped']} skipped"
        )
        return result

    def _process_record(self, record: Dict[str, Any]) -> str:
        """Not used - import_file overrides base class"""
        raise NotImplementedError("Use import_file instead")

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
