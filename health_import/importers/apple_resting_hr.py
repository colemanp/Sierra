"""Apple HealthKit resting heart rate XML importer"""
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, Iterator, Optional
from datetime import datetime

from .base import BaseImporter


class AppleRestingHRImporter(BaseImporter):
    """Import resting heart rate from Apple Health export.xml

    Uses streaming XML parsing (iterparse) for memory efficiency
    with large export files (often 500MB+).

    Extracts records with type: HKQuantityTypeIdentifierRestingHeartRate
    """

    SOURCE_NAME = "apple_healthkit"

    # HealthKit type for resting heart rate
    RESTING_HR_TYPE = "HKQuantityTypeIdentifierRestingHeartRate"

    def _parse_file(self, file_path: Path) -> Iterator[Dict[str, Any]]:
        """Parse Apple Health export XML using streaming"""
        self.logger.info("Parsing Apple Health export (this may take a while for large files)...")

        context = ET.iterparse(str(file_path), events=("end",))
        count = 0

        for event, elem in context:
            if elem.tag == "Record":
                record_type = elem.get("type", "")

                # Only process resting heart rate records
                if record_type == self.RESTING_HR_TYPE:
                    yield {
                        "type": record_type,
                        "value": elem.get("value"),
                        "unit": elem.get("unit"),
                        "startDate": elem.get("startDate"),
                        "endDate": elem.get("endDate"),
                        "sourceName": elem.get("sourceName"),
                        "sourceVersion": elem.get("sourceVersion"),
                        "device": elem.get("device"),
                    }
                    count += 1

                    # Progress logging
                    if count % 100 == 0:
                        self.logger.debug(f"Processed {count} resting HR records...")

                # Clear element to free memory
                elem.clear()

        self.logger.info(f"Found {count} resting heart rate records")

    def _process_record(self, record: Dict[str, Any]) -> str:
        """Process a single resting heart rate record"""
        # Parse date from startDate (format: 2025-11-24 08:00:00 -0800)
        start_date_str = record.get("startDate", "")
        date_iso = self._parse_healthkit_date(start_date_str)

        if not date_iso:
            self.logger.warning(f"Skipping record with invalid date: {start_date_str}")
            return "skipped"

        # Parse heart rate value
        hr_value = self._parse_int(record.get("value"))
        if hr_value is None:
            self.logger.warning(f"Skipping record with invalid HR value: {record.get('value')}")
            return "skipped"

        source_name = record.get("sourceName")

        # Build data
        data = {
            "source_id": self.source_id,
            "measurement_date": date_iso,
            "resting_hr": hr_value,
            "source_name": source_name,
        }

        # Key fields - one reading per day per source
        key_fields = {
            "source_id": self.source_id,
            "measurement_date": date_iso,
        }

        return self._insert_with_conflict_check(
            "resting_heart_rate",
            key_fields,
            data
        )

    def _parse_healthkit_date(self, date_str: Optional[str]) -> Optional[str]:
        """
        Parse HealthKit date format to YYYY-MM-DD.

        Input: "2025-11-24 08:00:00 -0800"
        Output: "2025-11-24"
        """
        if not date_str:
            return None

        try:
            # Split off timezone if present
            parts = date_str.split(" ")
            if len(parts) >= 2:
                date_part = parts[0]
                # Validate it's a proper date
                datetime.strptime(date_part, "%Y-%m-%d")
                return date_part
        except ValueError:
            pass

        return None

    def _parse_int(self, value: Optional[str]) -> Optional[int]:
        """Parse int value"""
        if not value:
            return None
        try:
            return int(float(value))
        except (ValueError, TypeError):
            return None

    def _log_insert(self, record: Dict[str, Any]) -> None:
        """Log insert"""
        date = record.get("startDate", "")[:10]
        hr = record.get("value", "")
        source = record.get("sourceName", "")
        self.logger.info(f"Inserted: {date} - Resting HR: {hr} bpm ({source})")

    def _log_skip(self, record: Dict[str, Any]) -> None:
        """Log skip"""
        date = record.get("startDate", "")[:10]
        self.logger.debug(f"Skipped: {date} (already exists)")
