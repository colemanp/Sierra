"""Garmin activities CSV importer"""
import csv
from pathlib import Path
from typing import Any, Dict, Iterator, Optional

from .base import BaseImporter
from ..transforms.datetime_utils import parse_garmin_datetime, parse_garmin_duration
from ..transforms.units import pace_str_to_min_per_mile, meters_to_feet, cm_to_inches


class GarminActivitiesImporter(BaseImporter):
    """Import Garmin Connect activity exports"""

    SOURCE_NAME = "garmin_activities"

    def _parse_file(self, file_path: Path) -> Iterator[Dict[str, Any]]:
        """Parse Garmin activities CSV"""
        with open(file_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                yield row

    def _process_record(self, record: Dict[str, Any]) -> str:
        """Process a single activity record"""
        # Parse datetime
        start_time = parse_garmin_datetime(record.get("Date"))
        if not start_time:
            self.logger.warning(f"Skipping record with invalid date: {record.get('Date')}")
            return "skipped"

        # Get activity type
        garmin_type = record.get("Activity Type", "")
        activity_type_id = self.db.get_activity_type_id(garmin_type)

        # Build activity data
        activity_data = {
            "source_id": self.source_id,
            "start_time": start_time,
            "activity_type_id": activity_type_id,
            "title": record.get("Title"),
            "distance_miles": self._parse_float(record.get("Distance")),
            "calories_total": self._parse_float(record.get("Calories")),
            "duration_seconds": parse_garmin_duration(record.get("Time")),
            "moving_time_seconds": parse_garmin_duration(record.get("Moving Time")),
            "avg_hr": self._parse_int(record.get("Avg HR")),
            "max_hr": self._parse_int(record.get("Max HR")),
            "avg_pace_min_per_mile": pace_str_to_min_per_mile(record.get("Avg Pace")),
            "best_pace_min_per_mile": pace_str_to_min_per_mile(record.get("Best Pace")),
            "elevation_gain_ft": self._parse_float(record.get("Total Ascent")),
            "elevation_loss_ft": self._parse_float(record.get("Total Descent")),
            "min_elevation_ft": self._parse_float(record.get("Min Elevation")),
            "max_elevation_ft": self._parse_float(record.get("Max Elevation")),
            "is_indoor": 1 if "Treadmill" in garmin_type else 0,
        }

        # Key fields for conflict detection
        key_fields = {
            "source_id": self.source_id,
            "start_time": start_time,
            "activity_type_id": activity_type_id,
        }

        # Insert activity with conflict check
        result = self._insert_with_conflict_check(
            "activities",
            key_fields,
            activity_data
        )

        if result == "inserted":
            # Get the activity ID for related tables
            cursor = self.db.conn.execute(
                """SELECT id FROM activities
                   WHERE source_id = ? AND start_time = ? AND activity_type_id = ?""",
                (self.source_id, start_time, activity_type_id)
            )
            row = cursor.fetchone()
            if row:
                activity_id = row["id"]
                self._insert_running_dynamics(activity_id, record)
                self._insert_garmin_extras(activity_id, record)

        return result

    def _insert_running_dynamics(self, activity_id: int, record: Dict[str, Any]) -> None:
        """Insert running dynamics data"""
        # Check if any running dynamics data exists
        has_data = any([
            record.get("Avg Cadence"),
            record.get("Max Cadence"),
            record.get("Avg Stride Length"),
            record.get("Avg Vertical Ratio"),
            record.get("Avg Vertical Oscillation"),
            record.get("Avg Ground Contact Time"),
            record.get("Avg GAP"),
            record.get("Training Stress Score®"),
            record.get("Normalized Power® (NP®)"),
            record.get("Avg Power"),
            record.get("Max Power"),
        ])

        if not has_data:
            return

        data = {
            "activity_id": activity_id,
            "avg_cadence": self._parse_int(record.get("Avg Cadence")),
            "max_cadence": self._parse_int(record.get("Max Cadence")),
            "avg_stride_length_ft": self._parse_stride_length(record.get("Avg Stride Length")),
            "avg_vertical_ratio": self._parse_float(record.get("Avg Vertical Ratio")),
            "avg_vertical_oscillation_in": self._parse_vertical_oscillation(record.get("Avg Vertical Oscillation")),
            "avg_ground_contact_time_ms": self._parse_int(record.get("Avg Ground Contact Time")),
            "avg_gap_min_per_mile": pace_str_to_min_per_mile(record.get("Avg GAP")),
            "training_stress_score": self._parse_float(record.get("Training Stress Score®")),
            "normalized_power_watts": self._parse_int(record.get("Normalized Power® (NP®)")),
            "avg_power_watts": self._parse_int(record.get("Avg Power")),
            "max_power_watts": self._parse_int(record.get("Max Power")),
        }

        columns = ", ".join(data.keys())
        placeholders = ", ".join("?" for _ in data)
        self.db.conn.execute(
            f"INSERT OR IGNORE INTO activity_running_dynamics ({columns}) VALUES ({placeholders})",
            tuple(data.values())
        )

    def _insert_garmin_extras(self, activity_id: int, record: Dict[str, Any]) -> None:
        """Insert Garmin-specific extra data"""
        has_data = any([
            record.get("Aerobic TE"),
            record.get("Steps"),
            record.get("Body Battery Drain"),
            record.get("Grit"),
            record.get("Flow"),
            record.get("Number of Laps"),
            record.get("Best Lap Time"),
            record.get("Avg Resp"),
        ])

        if not has_data:
            return

        data = {
            "activity_id": activity_id,
            "aerobic_te": self._parse_float(record.get("Aerobic TE")),
            "steps": self._parse_steps(record.get("Steps")),
            "body_battery_drain": self._parse_int(record.get("Body Battery Drain")),
            "grit": self._parse_float(record.get("Grit")),
            "flow": self._parse_float(record.get("Flow")),
            "laps": self._parse_int(record.get("Number of Laps")),
            "best_lap_time_seconds": parse_garmin_duration(record.get("Best Lap Time")),
            "avg_respiration": self._parse_int(record.get("Avg Resp")),
            "min_respiration": self._parse_int(record.get("Min Resp")),
            "max_respiration": self._parse_int(record.get("Max Resp")),
        }

        columns = ", ".join(data.keys())
        placeholders = ", ".join("?" for _ in data)
        self.db.conn.execute(
            f"INSERT OR IGNORE INTO activity_garmin_extras ({columns}) VALUES ({placeholders})",
            tuple(data.values())
        )

    def _parse_float(self, value: Optional[str]) -> Optional[float]:
        """Parse float, handling '--' and empty strings"""
        if not value or value == "--" or value.strip() == "":
            return None
        try:
            # Remove commas from numbers like "7,242"
            return float(value.replace(",", ""))
        except ValueError:
            return None

    def _parse_int(self, value: Optional[str]) -> Optional[int]:
        """Parse int, handling '--' and empty strings"""
        f = self._parse_float(value)
        return int(f) if f is not None else None

    def _parse_steps(self, value: Optional[str]) -> Optional[int]:
        """Parse steps value which may have commas"""
        if not value or value == "--" or value.strip() == "":
            return None
        try:
            return int(value.replace(",", ""))
        except ValueError:
            return None

    def _parse_stride_length(self, value: Optional[str]) -> Optional[float]:
        """Parse stride length (in meters from Garmin) to feet"""
        meters = self._parse_float(value)
        return meters_to_feet(meters)

    def _parse_vertical_oscillation(self, value: Optional[str]) -> Optional[float]:
        """Parse vertical oscillation (in cm from Garmin) to inches"""
        cm = self._parse_float(value)
        return cm_to_inches(cm)

    def _log_insert(self, record: Dict[str, Any]) -> None:
        """Log insert with activity details"""
        activity_type = record.get("Activity Type", "Unknown")
        date = record.get("Date", "")
        distance = record.get("Distance", "")
        self.logger.info(f"Inserted: {activity_type} - {date} ({distance} mi)")

    def _log_skip(self, record: Dict[str, Any]) -> None:
        """Log skip with activity details"""
        activity_type = record.get("Activity Type", "Unknown")
        date = record.get("Date", "")
        self.logger.debug(f"Skipped: {activity_type} - {date} (already exists)")
