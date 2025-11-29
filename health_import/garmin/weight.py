"""Garmin weight data fetcher and importer"""
from datetime import date
from pathlib import Path
from typing import Optional
import sqlite3

from garminconnect import Garmin

# Token file for session persistence
TOKEN_DIR = Path(__file__).parent.parent.parent / "data" / ".garmin"
TOKEN_FILE = TOKEN_DIR / "session.json"

# Conversion constants
GRAMS_TO_LBS = 0.00220462
KG_TO_LBS = 2.20462


class GarminWeightFetcher:
    """Fetches weight data from Garmin Connect API"""

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

    def fetch_weight(
        self,
        start_date: date,
        end_date: Optional[date] = None,
    ) -> list[dict]:
        """
        Fetch weight data from Garmin for a date range.
        Returns list of weight entries.
        """
        if not self.client:
            raise Exception("Not logged in")

        end = end_date or date.today()
        response = self.client.get_weigh_ins(
            start_date.isoformat(), end.isoformat()
        )

        if not response:
            return []

        # Extract entries from daily summaries
        entries = []
        summaries = response.get('dailyWeightSummaries', [])
        for summary in summaries:
            # Weight data is in latestWeight, not in the summary root
            latest = summary.get('latestWeight', {})
            if not latest:
                continue

            entry = {
                'date': summary.get('summaryDate'),
                'weight_grams': latest.get('weight'),  # in grams
                'bmi': latest.get('bmi'),
                'body_fat_pct': latest.get('bodyFat'),
                'muscle_mass_grams': latest.get('muscleMass'),
                'bone_mass_grams': latest.get('boneMass'),
                'body_water_pct': latest.get('bodyWater'),
                'visceral_fat': latest.get('visceralFat'),
            }
            entries.append(entry)

        return entries


def import_weight_to_db(
    conn: sqlite3.Connection,
    entries: list[dict],
    source_id: int,
) -> dict:
    """
    Import weight entries to database.

    Shared by both CSV and API importers.

    Expected record format (all fields optional except measurement_date, weight_lbs):
        {
            measurement_date: str,
            measurement_time: str | None,
            weight_lbs: float,
            weight_change_lbs: float | None,
            bmi: float | None,
            body_fat_pct: float | None,
            muscle_mass_lbs: float | None,
            bone_mass_lbs: float | None,
            body_water_pct: float | None,
            visceral_fat_level: int | None,
        }

    For API data, call convert_api_weight() first.

    Returns:
        {processed: int, inserted: int, skipped: int}
    """
    processed = 0
    inserted = 0
    skipped = 0

    for entry in entries:
        processed += 1

        measurement_date = entry.get('measurement_date')
        weight_lbs = entry.get('weight_lbs')

        if not measurement_date or not weight_lbs:
            skipped += 1
            continue

        try:
            conn.execute(
                """INSERT INTO body_measurements (
                    source_id, measurement_date, measurement_time, weight_lbs,
                    weight_change_lbs, bmi, body_fat_pct, muscle_mass_lbs, bone_mass_lbs,
                    body_water_pct, visceral_fat_level
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    source_id,
                    measurement_date,
                    entry.get('measurement_time'),
                    weight_lbs,
                    entry.get('weight_change_lbs'),
                    entry.get('bmi'),
                    entry.get('body_fat_pct'),
                    entry.get('muscle_mass_lbs'),
                    entry.get('bone_mass_lbs'),
                    entry.get('body_water_pct'),
                    entry.get('visceral_fat_level'),
                )
            )
            inserted += 1
        except sqlite3.IntegrityError:
            # Already exists
            skipped += 1

    conn.commit()
    return {'processed': processed, 'inserted': inserted, 'skipped': skipped}


def convert_api_weight(entry: dict) -> dict:
    """Convert Garmin API weight entry to standard format (imperial units)"""
    weight_grams = entry.get('weight_grams') or 0
    muscle_grams = entry.get('muscle_mass_grams') or 0
    bone_grams = entry.get('bone_mass_grams') or 0

    return {
        'measurement_date': entry.get('date'),
        'measurement_time': None,  # Garmin API gives daily summaries, no time
        'weight_lbs': weight_grams * GRAMS_TO_LBS if weight_grams else None,
        'bmi': entry.get('bmi'),
        'body_fat_pct': entry.get('body_fat_pct'),
        'muscle_mass_lbs': muscle_grams * GRAMS_TO_LBS if muscle_grams else None,
        'bone_mass_lbs': bone_grams * GRAMS_TO_LBS if bone_grams else None,
        'body_water_pct': entry.get('body_water_pct'),
        'visceral_fat_level': entry.get('visceral_fat'),
    }
