"""Apply Garmin schema changes to existing database"""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "health.db"


def migrate():
    """Apply schema migrations"""
    if not DB_PATH.exists():
        print(f"Database not found: {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)

    # Create activity_garmin_extras table if not exists
    conn.execute("""
        CREATE TABLE IF NOT EXISTS activity_garmin_extras (
            activity_id INTEGER PRIMARY KEY REFERENCES activities(id),
            garmin_activity_id BIGINT UNIQUE,
            event_type TEXT,
            location_name TEXT,
            aerobic_te REAL,
            anaerobic_te REAL,
            training_load REAL,
            vo2max_value REAL,
            steps INTEGER,
            body_battery_drain INTEGER,
            grit REAL,
            flow REAL,
            laps INTEGER,
            best_lap_time_seconds REAL,
            avg_respiration INTEGER,
            min_respiration INTEGER,
            max_respiration INTEGER
        )
    """)
    print("Created/verified table: activity_garmin_extras")

    # Add new columns to activity_garmin_extras (if table existed without them)
    new_columns = [
        ("garmin_activity_id", "BIGINT UNIQUE"),
        ("event_type", "TEXT"),
        ("location_name", "TEXT"),
        ("anaerobic_te", "REAL"),
        ("training_load", "REAL"),
        ("vo2max_value", "REAL"),
    ]

    for col_name, col_type in new_columns:
        try:
            conn.execute(f"ALTER TABLE activity_garmin_extras ADD COLUMN {col_name} {col_type}")
            print(f"Added column: activity_garmin_extras.{col_name}")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e).lower():
                print(f"Column already exists: activity_garmin_extras.{col_name}")
            else:
                print(f"Error adding {col_name}: {e}")

    # Create activity_laps table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS activity_laps (
            id INTEGER PRIMARY KEY,
            activity_id INTEGER NOT NULL REFERENCES activities(id) ON DELETE CASCADE,
            lap_index INTEGER NOT NULL,
            start_time TEXT,
            distance_miles REAL,
            duration_seconds REAL,
            moving_duration_seconds REAL,
            avg_speed_mph REAL,
            max_speed_mph REAL,
            avg_pace_min_per_mile REAL,
            avg_hr INTEGER,
            max_hr INTEGER,
            avg_cadence INTEGER,
            max_cadence INTEGER,
            avg_power_watts INTEGER,
            max_power_watts INTEGER,
            normalized_power_watts INTEGER,
            calories INTEGER,
            elevation_gain_ft REAL,
            elevation_loss_ft REAL,
            avg_stride_length_ft REAL,
            avg_vertical_oscillation_in REAL,
            avg_ground_contact_time_ms INTEGER,
            avg_vertical_ratio REAL,
            UNIQUE(activity_id, lap_index)
        )
    """)
    print("Created table: activity_laps")

    # Create indexes
    try:
        conn.execute("CREATE INDEX IF NOT EXISTS idx_activity_laps_activity ON activity_laps(activity_id)")
        print("Created index: idx_activity_laps_activity")
    except:
        pass

    try:
        conn.execute("CREATE INDEX IF NOT EXISTS idx_activity_garmin_extras_garmin_id ON activity_garmin_extras(garmin_activity_id)")
        print("Created index: idx_activity_garmin_extras_garmin_id")
    except:
        pass

    # Add garmin_api data source
    try:
        conn.execute(
            "INSERT OR IGNORE INTO data_sources (name, description) VALUES (?, ?)",
            ("garmin_api", "Garmin Connect API imports")
        )
        print("Added data source: garmin_api")
    except:
        pass

    conn.commit()
    conn.close()
    print("Migration complete!")


if __name__ == "__main__":
    migrate()
