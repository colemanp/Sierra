"""Just 6 Weeks strength training CSV importer"""
import csv
from pathlib import Path
from typing import Any, Dict, Iterator, Optional

from .base import BaseImporter
from ..transforms.datetime_utils import parse_six_week_datetime, parse_garmin_duration


class SixWeekImporter(BaseImporter):
    """Import Just 6 Weeks app CSV exports

    Format: semicolon-delimited CSV with columns:
    Date;Workout;Goal;Period;Week;Day;Time;Set 1;Set 2;Set 3;Set 4;Set 5;Sum of Sets;Kcal
    """

    SOURCE_NAME = "six_week"

    def _parse_file(self, file_path: Path) -> Iterator[Dict[str, Any]]:
        """Parse 6-week challenge CSV (semicolon delimiter)"""
        with open(file_path, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f, delimiter=";")
            for row in reader:
                yield row

    def _process_record(self, record: Dict[str, Any]) -> str:
        """Process a single workout record"""
        # Parse datetime
        date_str = record.get("Date", "")
        date_iso, time_24h = parse_six_week_datetime(date_str)

        if not date_iso:
            self.logger.warning(f"Skipping record with invalid date: {date_str}")
            return "skipped"

        # Get or create exercise
        workout_name = record.get("Workout", "").strip()
        exercise_id = self.db.get_exercise_id(workout_name)

        if exercise_id is None:
            # Determine unit based on workout type
            unit = "seconds" if workout_name.lower() == "plank" else "reps"
            category = "core" if workout_name.lower() == "plank" else "upper_body"
            exercise_id = self.db.add_exercise(
                workout_name,
                workout_name,
                category,
                unit
            )
            self.logger.info(f"Added new exercise: {workout_name}")

        # Parse sets - for plank these might be times (MM:SS)
        is_plank = workout_name.lower() == "plank"
        set1 = self._parse_set_value(record.get("Set 1"), is_plank)
        set2 = self._parse_set_value(record.get("Set 2"), is_plank)
        set3 = self._parse_set_value(record.get("Set 3"), is_plank)
        set4 = self._parse_set_value(record.get("Set 4"), is_plank)
        set5 = self._parse_set_value(record.get("Set 5"), is_plank)
        total = self._parse_set_value(record.get("Sum of Sets"), is_plank)

        # Parse other fields
        week = self._parse_int(record.get("Week"))
        day = self._parse_int(record.get("Day"))
        goal = self._parse_float(record.get("Goal"))
        duration = parse_garmin_duration(record.get("Time"))
        calories = self._parse_int(record.get("Kcal"))

        # Build data
        data = {
            "source_id": self.source_id,
            "exercise_id": exercise_id,
            "workout_date": date_iso,
            "workout_time": time_24h,
            "goal_value": goal,
            "program_name": record.get("Period", "").strip() or None,
            "week_number": week,
            "day_number": day,
            "set1": set1,
            "set2": set2,
            "set3": set3,
            "set4": set4,
            "set5": set5,
            "total_value": total,
            "duration_seconds": int(duration) if duration else None,
            "calories": calories,
        }

        # Key fields for conflict detection
        key_fields = {
            "source_id": self.source_id,
            "workout_date": date_iso,
            "exercise_id": exercise_id,
            "workout_time": time_24h,
        }

        return self._insert_with_conflict_check(
            "strength_workouts",
            key_fields,
            data
        )

    def _parse_set_value(self, value: Optional[str], is_time: bool = False) -> Optional[float]:
        """
        Parse set value - either reps (int) or time (MM:SS -> seconds)
        """
        if not value or value.strip() == "":
            return None

        value = value.strip()

        # Check if it's a time format (contains :)
        if ":" in value or is_time:
            seconds = parse_garmin_duration(value)
            return seconds

        # Otherwise treat as reps
        try:
            return float(value)
        except ValueError:
            return None

    def _parse_int(self, value: Optional[str]) -> Optional[int]:
        """Parse int value"""
        if not value or value.strip() == "":
            return None
        try:
            return int(value.strip())
        except ValueError:
            return None

    def _parse_float(self, value: Optional[str]) -> Optional[float]:
        """Parse float value"""
        if not value or value.strip() == "":
            return None
        try:
            return float(value.strip())
        except ValueError:
            return None

    def _log_insert(self, record: Dict[str, Any]) -> None:
        """Log insert with workout details"""
        date = record.get("Date", "")
        workout = record.get("Workout", "")
        total = record.get("Sum of Sets", "")
        self.logger.info(f"Inserted: {workout} - {date} (total: {total})")

    def _log_skip(self, record: Dict[str, Any]) -> None:
        """Log skip"""
        date = record.get("Date", "")
        workout = record.get("Workout", "")
        self.logger.debug(f"Skipped: {workout} - {date} (already exists)")
