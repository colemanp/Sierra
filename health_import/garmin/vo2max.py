"""Garmin VO2 Max data fetcher"""
from datetime import date, timedelta
from pathlib import Path
from typing import Optional
import sqlite3

from garminconnect import Garmin

# Token file for session persistence
TOKEN_DIR = Path(__file__).parent.parent.parent / "data" / ".garmin"
TOKEN_FILE = TOKEN_DIR / "session.json"


class GarminVO2MaxFetcher:
    """Fetches VO2 Max data from Garmin Connect API"""

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

    def fetch_vo2max(
        self,
        days_back: Optional[int] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> list[dict]:
        """
        Fetch VO2 Max readings from Garmin.

        Args:
            days_back: Number of days to go back from today
            start_date: Start date for range
            end_date: End date for range (defaults to today)

        Returns:
            List of {date: str, vo2max: float, activity_type: str}
        """
        if not self.client:
            raise Exception("Not logged in")

        # Determine date range
        if days_back:
            end = date.today()
            start = end - timedelta(days=days_back)
        elif start_date:
            start = start_date
            end = end_date or date.today()
        else:
            raise ValueError("Must specify days_back or start_date")

        # Fetch readings for each day
        vo2_readings = []
        seen_dates = set()

        current = end
        while current >= start:
            try:
                data = self.client.get_training_status(current.isoformat())
                if data and 'mostRecentVO2Max' in data:
                    vo2_data = data['mostRecentVO2Max']

                    # Running VO2 Max
                    if vo2_data.get('generic'):
                        g = vo2_data['generic']
                        cal_date = g.get('calendarDate')
                        vo2 = g.get('vo2MaxPreciseValue')
                        if cal_date and vo2 and cal_date not in seen_dates:
                            # Only include if within our date range
                            if start.isoformat() <= cal_date <= end.isoformat():
                                seen_dates.add(cal_date)
                                vo2_readings.append({
                                    'date': cal_date,
                                    'vo2max': vo2,
                                    'activity_type': 'running'
                                })

                    # Cycling VO2 Max
                    if vo2_data.get('cycling'):
                        c = vo2_data['cycling']
                        cal_date = c.get('calendarDate')
                        vo2 = c.get('vo2MaxPreciseValue')
                        cycle_key = f"{cal_date}_cycling"
                        if cal_date and vo2 and cycle_key not in seen_dates:
                            if start.isoformat() <= cal_date <= end.isoformat():
                                seen_dates.add(cycle_key)
                                vo2_readings.append({
                                    'date': cal_date,
                                    'vo2max': vo2,
                                    'activity_type': 'cycling'
                                })
            except Exception:
                pass  # Skip errors for individual days

            current -= timedelta(days=1)

        # Sort by date descending
        vo2_readings.sort(key=lambda x: x['date'], reverse=True)
        return vo2_readings


def import_vo2max_to_db(
    conn: sqlite3.Connection,
    readings: list[dict],
    source_id: int,
) -> dict:
    """
    Import VO2 Max readings to database.

    Returns:
        {processed: int, inserted: int, skipped: int}
    """
    processed = 0
    inserted = 0
    skipped = 0

    for reading in readings:
        processed += 1
        try:
            conn.execute(
                """INSERT INTO garmin_vo2max (source_id, measurement_date, activity_type, vo2max_value)
                   VALUES (?, ?, ?, ?)""",
                (source_id, reading['date'], reading['activity_type'], reading['vo2max'])
            )
            inserted += 1
        except sqlite3.IntegrityError:
            # Already exists
            skipped += 1

    conn.commit()
    return {'processed': processed, 'inserted': inserted, 'skipped': skipped}


def get_existing_vo2max(conn: sqlite3.Connection) -> list[dict]:
    """Get existing VO2 Max records from database"""
    cursor = conn.execute(
        """SELECT measurement_date, vo2max_value, activity_type
           FROM garmin_vo2max
           ORDER BY measurement_date DESC"""
    )
    return [
        {'date': row[0], 'vo2max': row[1], 'activity_type': row[2]}
        for row in cursor.fetchall()
    ]
