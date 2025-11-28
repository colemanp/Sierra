"""MacroFactor nutrition CSV importer"""
import csv
from pathlib import Path
from typing import Any, Dict, Iterator, Optional
from datetime import datetime

from .base import BaseImporter


class MacroFactorImporter(BaseImporter):
    """Import MacroFactor nutrition CSV exports

    MacroFactor CSV exports contain individual food entries with:
    - Date, Time, Food Name, Serving info
    - Calories, macros, micros per food item
    """

    SOURCE_NAME = "macrofactor"

    def _parse_file(self, file_path: Path) -> Iterator[Dict[str, Any]]:
        """Parse MacroFactor CSV file"""
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Normalize headers to lowercase
                record = {k.lower(): v for k, v in row.items()}
                yield record

    def _process_record(self, record: Dict[str, Any]) -> str:
        """Process a single food entry record"""
        date_value = record.get("date")
        if not date_value:
            return "skipped"

        date_iso = self._parse_date(date_value)
        if not date_iso:
            self.logger.warning(f"Skipping record with invalid date: {date_value}")
            return "skipped"

        return self._process_food_entry(date_iso, record)

    def _process_food_entry(self, date_iso: str, record: Dict[str, Any]) -> str:
        """Process individual food entry"""
        food_name = self._get_string(record, ["food name", "food", "name", "item", "description"])
        if not food_name:
            return "skipped"

        time_value = self._get_string(record, ["time", "logged time", "meal time"])
        time_24h = self._parse_time(time_value) if time_value else None

        data = {
            "source_id": self.source_id,
            "date": date_iso,
            "time": time_24h,
            "food_name": food_name,
            "serving_size": self._get_string(record, ["serving size", "serving", "portion"]),
            "serving_qty": self._get_float(record, ["serving qty", "quantity", "servings", "amount"]),
            "serving_weight_g": self._get_float(record, ["serving weight (g)", "weight (g)", "weight", "grams"]),
            "calories_kcal": self._get_float(record, ["calories (kcal)", "calories", "energy", "kcal"]),
            "protein_g": self._get_float(record, ["protein (g)", "protein"]),
            "fat_g": self._get_float(record, ["fat (g)", "fat"]),
            "carbs_g": self._get_float(record, ["carbs (g)", "carbs", "carbohydrates"]),
            "fiber_g": self._get_float(record, ["fiber (g)", "fiber", "fibre"]),
        }

        key_fields = {
            "source_id": self.source_id,
            "date": date_iso,
            "time": time_24h,
            "food_name": food_name,
        }

        return self._insert_with_conflict_check(
            "nutrition_entries",
            key_fields,
            data
        )

    def _get_float(self, record: Dict, keys: list) -> Optional[float]:
        """Get float value from record, trying multiple possible keys"""
        for key in keys:
            if key in record and record[key] is not None:
                try:
                    return float(record[key])
                except (ValueError, TypeError):
                    continue
        return None

    def _get_string(self, record: Dict, keys: list) -> Optional[str]:
        """Get string value from record"""
        for key in keys:
            if key in record and record[key]:
                return str(record[key]).strip()
        return None

    def _parse_date(self, value: Any) -> Optional[str]:
        """Parse date value to ISO format"""
        if isinstance(value, datetime):
            return value.strftime("%Y-%m-%d")
        if isinstance(value, str):
            # Try common formats
            for fmt in ["%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%Y/%m/%d"]:
                try:
                    dt = datetime.strptime(value, fmt)
                    return dt.strftime("%Y-%m-%d")
                except ValueError:
                    continue
        return None

    def _parse_time(self, value: Any) -> Optional[str]:
        """Parse time value to HH:MM:SS format"""
        if isinstance(value, datetime):
            return value.strftime("%H:%M:%S")
        if isinstance(value, str):
            for fmt in ["%H:%M:%S", "%H:%M", "%I:%M %p", "%I:%M:%S %p"]:
                try:
                    dt = datetime.strptime(value.upper(), fmt)
                    return dt.strftime("%H:%M:%S")
                except ValueError:
                    continue
        return None

    def _log_insert(self, record: Dict[str, Any]) -> None:
        """Log insert"""
        date = record.get("date", "")
        self.logger.info(f"Inserted: nutrition {date}")

    def _log_skip(self, record: Dict[str, Any]) -> None:
        """Log skip"""
        date = record.get("date", "")
        self.logger.debug(f"Skipped: nutrition {date} (already exists)")
