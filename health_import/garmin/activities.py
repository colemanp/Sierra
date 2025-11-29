"""Garmin activities API fetcher and shared import logic"""
from datetime import date, timedelta
from pathlib import Path
from typing import Optional
import sqlite3

from garminconnect import Garmin

# Token file for session persistence
TOKEN_DIR = Path(__file__).parent.parent.parent / "data" / ".garmin"
TOKEN_FILE = TOKEN_DIR / "session.json"

# Conversion constants (also used by CSV importer via transforms)
METERS_TO_MILES = 0.000621371
METERS_TO_FEET = 3.28084
MPS_TO_MPH = 2.23694
CM_TO_FEET = 0.0328084
CM_TO_INCHES = 0.393701


class GarminActivityFetcher:
    """Fetches activity data from Garmin Connect API"""

    def __init__(self):
        self.client: Optional[Garmin] = None

    def is_logged_in(self) -> bool:
        """Check if we have a valid session"""
        if not TOKEN_FILE.exists():
            return False
        try:
            client = Garmin()
            client.login(str(TOKEN_FILE))
            client.get_full_name()
            self.client = client
            return True
        except Exception:
            return False

    def login(self, email: str, password: str) -> bool:
        """Login to Garmin Connect"""
        try:
            TOKEN_DIR.mkdir(parents=True, exist_ok=True)
            client = Garmin(email, password)
            client.login()
            client.garth.dump(str(TOKEN_FILE))
            self.client = client
            return True
        except Exception as e:
            raise Exception(f"Login failed: {e}")

    def get_user_name(self) -> str:
        """Get logged in user's name"""
        if not self.client:
            raise Exception("Not logged in")
        return self.client.get_full_name()

    def fetch_activities(
        self,
        start_date: date,
        end_date: Optional[date] = None,
    ) -> list[dict]:
        """
        Fetch activities from Garmin for a date range.
        Returns list of activity dicts with basic info.
        """
        if not self.client:
            raise Exception("Not logged in")

        end = end_date or date.today()
        activities = self.client.get_activities_by_date(
            start_date.isoformat(), end.isoformat()
        )
        return activities or []

    def fetch_activity_splits(self, activity_id: int) -> Optional[dict]:
        """Fetch lap/split data for an activity"""
        if not self.client:
            raise Exception("Not logged in")
        try:
            return self.client.get_activity_splits(activity_id)
        except Exception:
            return None


def _convert_activity(activity: dict) -> dict:
    """Convert Garmin activity to DB format (imperial units)"""
    # Distance in meters -> miles
    distance = activity.get('distance', 0) or 0
    distance_miles = distance * METERS_TO_MILES

    # Duration in seconds
    duration = activity.get('duration', 0) or 0
    moving_duration = activity.get('movingDuration', 0) or 0

    # Speed m/s -> mph
    avg_speed = activity.get('averageSpeed', 0) or 0
    max_speed = activity.get('maxSpeed', 0) or 0
    avg_speed_mph = avg_speed * MPS_TO_MPH
    max_speed_mph = max_speed * MPS_TO_MPH

    # Pace (min/mile)
    avg_pace = None
    if avg_speed and avg_speed > 0:
        avg_pace = 26.8224 / avg_speed  # min/mile

    # Elevation in meters -> feet
    elev_gain = activity.get('elevationGain', 0) or 0
    elev_loss = activity.get('elevationLoss', 0) or 0
    min_elev = activity.get('minElevation')
    max_elev = activity.get('maxElevation')

    # Running dynamics - stride length cm -> ft, vertical osc mm -> in
    stride_cm = activity.get('avgStrideLength', 0) or 0
    vert_osc_mm = activity.get('avgVerticalOscillation', 0) or 0

    return {
        'garmin_activity_id': activity.get('activityId'),
        'title': activity.get('activityName'),
        'activity_type': activity.get('activityType', {}).get('typeKey'),
        'event_type': activity.get('eventType', {}).get('typeKey'),
        'start_time': activity.get('startTimeLocal'),
        'duration_seconds': duration,
        'moving_time_seconds': moving_duration,
        'distance_miles': distance_miles,
        'calories_total': activity.get('calories'),
        'avg_speed_mph': avg_speed_mph if avg_speed else None,
        'max_speed_mph': max_speed_mph if max_speed else None,
        'avg_pace_min_per_mile': avg_pace,
        'avg_hr': activity.get('averageHR'),
        'max_hr': activity.get('maxHR'),
        'elevation_gain_ft': elev_gain * METERS_TO_FEET if elev_gain else None,
        'elevation_loss_ft': elev_loss * METERS_TO_FEET if elev_loss else None,
        'min_elevation_ft': min_elev * METERS_TO_FEET if min_elev else None,
        'max_elevation_ft': max_elev * METERS_TO_FEET if max_elev else None,
        'location_name': activity.get('locationName'),
        # Running dynamics
        'avg_cadence': int(activity.get('averageRunningCadenceInStepsPerMinute') or 0) or None,
        'max_cadence': int(activity.get('maxRunningCadenceInStepsPerMinute') or 0) or None,
        'avg_power_watts': activity.get('avgPower'),
        'max_power_watts': activity.get('maxPower'),
        'normalized_power_watts': activity.get('normPower'),
        'avg_stride_length_ft': stride_cm * CM_TO_FEET if stride_cm else None,
        'avg_vertical_oscillation_in': vert_osc_mm * CM_TO_INCHES / 10 if vert_osc_mm else None,  # mm to cm to in
        'avg_ground_contact_time_ms': int(activity.get('avgGroundContactTime') or 0) or None,
        'avg_vertical_ratio': activity.get('avgVerticalRatio'),
        # Garmin extras
        'aerobic_te': activity.get('aerobicTrainingEffect'),
        'anaerobic_te': activity.get('anaerobicTrainingEffect'),
        'training_load': activity.get('activityTrainingLoad'),
        'vo2max_value': activity.get('vO2MaxValue'),
        'steps': activity.get('steps'),
    }


def _convert_lap(lap: dict, lap_index: int) -> dict:
    """Convert Garmin lap to DB format (imperial units)"""
    # Distance in meters -> miles
    distance = lap.get('distance', 0) or 0
    distance_miles = distance * METERS_TO_MILES

    # Duration in seconds
    duration = lap.get('duration', 0) or 0
    moving_duration = lap.get('movingDuration', 0) or 0

    # Speed m/s -> mph
    avg_speed = lap.get('averageSpeed', 0) or 0
    max_speed = lap.get('maxSpeed', 0) or 0
    avg_speed_mph = avg_speed * MPS_TO_MPH if avg_speed else None
    max_speed_mph = max_speed * MPS_TO_MPH if max_speed else None

    # Pace (min/mile)
    avg_pace = None
    if avg_speed and avg_speed > 0:
        avg_pace = 26.8224 / avg_speed

    # Elevation in meters -> feet
    elev_gain = lap.get('elevationGain', 0) or 0
    elev_loss = lap.get('elevationLoss', 0) or 0

    # Running dynamics - stride length cm -> ft, vertical osc cm -> in
    stride_cm = lap.get('strideLength', 0) or 0
    vert_osc_cm = lap.get('verticalOscillation', 0) or 0

    return {
        'lap_index': lap_index,
        'start_time': lap.get('startTimeGMT'),
        'distance_miles': distance_miles,
        'duration_seconds': duration,
        'moving_duration_seconds': moving_duration,
        'avg_speed_mph': avg_speed_mph,
        'max_speed_mph': max_speed_mph,
        'avg_pace_min_per_mile': avg_pace,
        'avg_hr': lap.get('averageHR'),
        'max_hr': lap.get('maxHR'),
        'avg_cadence': int(lap.get('averageRunCadence') or 0) or None,
        'max_cadence': int(lap.get('maxRunCadence') or 0) or None,
        'avg_power_watts': lap.get('averagePower'),
        'max_power_watts': lap.get('maxPower'),
        'normalized_power_watts': lap.get('normalizedPower'),
        'calories': lap.get('calories'),
        'elevation_gain_ft': elev_gain * METERS_TO_FEET if elev_gain else None,
        'elevation_loss_ft': elev_loss * METERS_TO_FEET if elev_loss else None,
        'avg_stride_length_ft': stride_cm * CM_TO_FEET if stride_cm else None,
        'avg_vertical_oscillation_in': vert_osc_cm * CM_TO_INCHES if vert_osc_cm else None,
        'avg_ground_contact_time_ms': int(lap.get('groundContactTime') or 0) or None,
        'avg_vertical_ratio': lap.get('verticalRatio'),
    }


def _get_or_create_activity_type(conn: sqlite3.Connection, garmin_type: str) -> int:
    """Get or create activity type, return ID"""
    # Try to find by garmin_type
    row = conn.execute(
        "SELECT id FROM activity_types WHERE garmin_type = ?", (garmin_type,)
    ).fetchone()
    if row:
        return row[0]

    # Try exact name match
    row = conn.execute(
        "SELECT id FROM activity_types WHERE name = ?", (garmin_type.lower().replace(' ', '_'),)
    ).fetchone()
    if row:
        return row[0]

    # Create new
    cursor = conn.execute(
        "INSERT INTO activity_types (name, garmin_type) VALUES (?, ?)",
        (garmin_type.lower().replace(' ', '_'), garmin_type)
    )
    return cursor.lastrowid


def import_activities_to_db(
    conn: sqlite3.Connection,
    fetcher: GarminActivityFetcher,
    activities: list[dict],
    source_id: int,
    status=None,
) -> dict:
    """
    Import activities and their laps to database.

    - If garmin_activity_id already exists: skip entirely
    - If activity with same start_time exists: link laps/extras to it (enrichment)
    - Otherwise: create new activity with laps/extras

    Returns:
        {processed: int, inserted: int, enriched: int, skipped: int, laps_inserted: int}
    """
    processed = 0
    inserted = 0
    enriched = 0
    skipped = 0
    laps_inserted = 0
    total = len(activities)

    for activity in activities:
        processed += 1
        garmin_id = activity.get('activityId')

        # Check if garmin_activity_id already imported
        existing_garmin = conn.execute(
            "SELECT activity_id FROM activity_garmin_extras WHERE garmin_activity_id = ?",
            (garmin_id,)
        ).fetchone()
        if existing_garmin:
            skipped += 1
            continue

        # Convert activity data
        data = _convert_activity(activity)
        start_time = data['start_time']

        # Get activity type ID
        activity_type = data.pop('activity_type', None)
        type_id = None
        if activity_type:
            type_id = _get_or_create_activity_type(conn, activity_type)

        # Extract garmin extras
        garmin_activity_id = data.pop('garmin_activity_id')
        event_type = data.pop('event_type', None)
        location_name = data.pop('location_name', None)
        aerobic_te = data.pop('aerobic_te', None)
        anaerobic_te = data.pop('anaerobic_te', None)
        training_load = data.pop('training_load', None)
        vo2max_value = data.pop('vo2max_value', None)
        steps = data.pop('steps', None)

        # Extract running dynamics
        avg_cadence = data.pop('avg_cadence', None)
        max_cadence = data.pop('max_cadence', None)
        avg_power_watts = data.pop('avg_power_watts', None)
        max_power_watts = data.pop('max_power_watts', None)
        normalized_power_watts = data.pop('normalized_power_watts', None)
        avg_stride_length_ft = data.pop('avg_stride_length_ft', None)
        avg_vertical_oscillation_in = data.pop('avg_vertical_oscillation_in', None)
        avg_ground_contact_time_ms = data.pop('avg_ground_contact_time_ms', None)
        avg_vertical_ratio = data.pop('avg_vertical_ratio', None)

        # Check if activity with same start_time exists (from CSV import)
        existing_activity = conn.execute(
            "SELECT id FROM activities WHERE start_time = ?",
            (start_time,)
        ).fetchone()

        if existing_activity:
            # Enrich existing activity with garmin extras and laps
            activity_id = existing_activity[0]
            enriched += 1
        else:
            # Insert new activity
            cursor = conn.execute(
                """INSERT INTO activities (
                    source_id, activity_type_id, start_time, duration_seconds, moving_time_seconds,
                    title, distance_miles, calories_total, avg_speed_mph, max_speed_mph,
                    avg_pace_min_per_mile, avg_hr, max_hr,
                    elevation_gain_ft, elevation_loss_ft, min_elevation_ft, max_elevation_ft
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    source_id,
                    type_id,
                    data['start_time'],
                    data['duration_seconds'],
                    data['moving_time_seconds'],
                    data['title'],
                    data['distance_miles'],
                    data['calories_total'],
                    data['avg_speed_mph'],
                    data['max_speed_mph'],
                    data['avg_pace_min_per_mile'],
                    data['avg_hr'],
                    data['max_hr'],
                    data['elevation_gain_ft'],
                    data['elevation_loss_ft'],
                    data['min_elevation_ft'],
                    data['max_elevation_ft'],
                )
            )
            activity_id = cursor.lastrowid
            inserted += 1

        # Insert garmin extras (or update if exists)
        conn.execute(
            """INSERT OR REPLACE INTO activity_garmin_extras (
                activity_id, garmin_activity_id, event_type, location_name,
                aerobic_te, anaerobic_te, training_load, vo2max_value, steps
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                activity_id,
                garmin_activity_id,
                event_type,
                location_name,
                aerobic_te,
                anaerobic_te,
                training_load,
                vo2max_value,
                steps,
            )
        )

        # Insert or update running dynamics if present
        if any([avg_cadence, avg_power_watts, avg_stride_length_ft, avg_vertical_oscillation_in]):
            conn.execute(
                """INSERT OR REPLACE INTO activity_running_dynamics (
                    activity_id, avg_cadence, max_cadence, avg_power_watts, max_power_watts,
                    normalized_power_watts, avg_stride_length_ft, avg_vertical_oscillation_in,
                    avg_ground_contact_time_ms, avg_vertical_ratio
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    activity_id,
                    avg_cadence,
                    max_cadence,
                    avg_power_watts,
                    max_power_watts,
                    normalized_power_watts,
                    avg_stride_length_ft,
                    avg_vertical_oscillation_in,
                    avg_ground_contact_time_ms,
                    avg_vertical_ratio,
                )
            )

        # Fetch and insert laps
        if status:
            activity_name = data.get('title') or f"Activity {garmin_id}"
            status.write(f"[{processed}/{total}] {activity_name} - fetching laps...")
        splits = fetcher.fetch_activity_splits(garmin_id)
        if splits and 'lapDTOs' in splits:
            for lap in splits['lapDTOs']:
                lap_index = lap.get('lapIndex', 0)
                lap_data = _convert_lap(lap, lap_index)

                conn.execute(
                    """INSERT OR REPLACE INTO activity_laps (
                        activity_id, lap_index, start_time, distance_miles, duration_seconds,
                        moving_duration_seconds, avg_speed_mph, max_speed_mph, avg_pace_min_per_mile,
                        avg_hr, max_hr, avg_cadence, max_cadence, avg_power_watts, max_power_watts,
                        normalized_power_watts, calories, elevation_gain_ft, elevation_loss_ft,
                        avg_stride_length_ft, avg_vertical_oscillation_in, avg_ground_contact_time_ms,
                        avg_vertical_ratio
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        activity_id,
                        lap_data['lap_index'],
                        lap_data['start_time'],
                        lap_data['distance_miles'],
                        lap_data['duration_seconds'],
                        lap_data['moving_duration_seconds'],
                        lap_data['avg_speed_mph'],
                        lap_data['max_speed_mph'],
                        lap_data['avg_pace_min_per_mile'],
                        lap_data['avg_hr'],
                        lap_data['max_hr'],
                        lap_data['avg_cadence'],
                        lap_data['max_cadence'],
                        lap_data['avg_power_watts'],
                        lap_data['max_power_watts'],
                        lap_data['normalized_power_watts'],
                        lap_data['calories'],
                        lap_data['elevation_gain_ft'],
                        lap_data['elevation_loss_ft'],
                        lap_data['avg_stride_length_ft'],
                        lap_data['avg_vertical_oscillation_in'],
                        lap_data['avg_ground_contact_time_ms'],
                        lap_data['avg_vertical_ratio'],
                    )
                )
                laps_inserted += 1

    conn.commit()
    return {
        'processed': processed,
        'inserted': inserted,
        'enriched': enriched,
        'skipped': skipped,
        'laps_inserted': laps_inserted,
    }
