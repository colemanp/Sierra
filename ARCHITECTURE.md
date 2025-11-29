# Health Data Import System - Architecture

## Overview
Python system to import health/fitness data from multiple sources into normalized SQLite database.

## Data Sources
| Source | Format | Delimiter | Key Data |
|--------|--------|-----------|----------|
| Garmin Activities | CSV | comma | workouts, HR, pace, running dynamics, power |
| Garmin Weight | CSV | comma (multiline) | weight, BMI, body fat, muscle/bone mass |
| Garmin VO2 Max | CSV | comma | date, activity type, vo2max value |
| 6-Week Challenge | CSV | semicolon | strength sets/reps (push-ups, pull-ups, plank) |
| MacroFactor | CSV | comma | nutrition, macros, micros, individual food entries |
| Apple HealthKit | XML | n/a | 872MB - design reference only for now |

## Storage
- **Database**: `./data/prod/health_data.db` (production), `./data/test/health_data.db` (test)
- **Units**: Imperial (lbs, miles, mph, min/mile)

## Project Structure
```
Sierra/
├── pyproject.toml
├── data/
│   ├── prod/
│   │   └── health_data.db
│   └── test/
│       └── health_data.db
├── health_import/
│   ├── __init__.py
│   ├── __main__.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── database.py         # DB connection, schema init
│   │   ├── models.py           # Dataclasses for records
│   │   ├── logging_setup.py    # Audit logging config
│   │   └── conflicts.py        # Conflict detection/warnings
│   ├── importers/
│   │   ├── __init__.py
│   │   ├── base.py             # Abstract base importer
│   │   ├── garmin_activities.py
│   │   ├── garmin_weight.py
│   │   ├── garmin_vo2max.py
│   │   ├── six_week.py
│   │   ├── macrofactor.py
│   │   └── apple_resting_hr.py
│   ├── garmin/                 # Garmin API fetchers & shared import
│   │   ├── __init__.py
│   │   ├── activities.py       # GarminActivityFetcher, import_activities_to_db
│   │   ├── weight.py           # GarminWeightFetcher, import_weight_to_db
│   │   └── vo2max.py           # GarminVO2MaxFetcher, import_vo2max_to_db
│   ├── mcp/                    # MCP server for LLM access
│   │   ├── __init__.py
│   │   ├── __main__.py
│   │   ├── config.py           # Centralized DB_PATH config
│   │   ├── server.py           # FastMCP server, tool registration
│   │   ├── weight.py           # Weight query/hide tools
│   │   ├── nutrition.py
│   │   ├── activity.py
│   │   ├── resting_hr.py       # RHR query/hide tools
│   │   ├── vo2max.py
│   │   └── strength.py
│   ├── transforms/
│   │   ├── __init__.py
│   │   ├── units.py            # kg->lbs, km->mi, pace conversions
│   │   └── datetime_utils.py   # Date/time parsing
│   └── cli/
│       ├── __init__.py
│       └── main.py             # CLI entry point
├── scripts/
│   ├── test_import.py          # Test import runner
│   ├── test_garmin.py          # Garmin API test script
│   ├── inspect_db.py           # Query and display tables
│   ├── show_conflicts.py       # Review import conflicts
│   └── compare_sources.py      # Cross-source data comparison
├── schema/
│   └── init.sql                # Full DDL
└── dashboard/                  # Streamlit dashboard
    ├── app.py
    ├── components/
    │   ├── weight.py           # Weight tab with hide feature
    │   ├── resting_hr.py       # RHR tab with hide feature
    │   ├── vo2max.py
    │   ├── garmin_import.py    # Garmin API import tab
    │   ├── mcp.py              # MCP request monitoring
    │   └── ...
    └── utils/
```

## Conflict Handling
Import files are **not deterministic** - can contain different date ranges each time.
Duplicate detection happens at the **individual record level**, not file level.

1. For each row, check if record exists by natural key (source + date/time + type)
2. If exists, compare values (with tolerances, e.g. weight within 0.1 lbs)
3. If values differ:
   - Log WARNING to CLI
   - Store conflict details in `import_conflicts` table
   - Keep existing record, skip new one
4. If values match → skip silently (already imported)
5. If not exists → insert
6. Review conflicts via `scripts/show_conflicts.py`

## Import Flow
```
File → Parse → For Each Row:
                  ↓
            Query by natural key
                  ↓
        ┌─── Exists? ───┐
        No              Yes
        ↓                ↓
      Insert      Compare values
                        ↓
                ┌── Match? ──┐
                Yes          No
                ↓            ↓
              Skip      Log conflict
                        Keep existing
```

1. Create `import_log` entry (status: running)
2. Parse file (CSV/XLSX)
3. Transform each row: unit conversions, date parsing, type mapping
4. For each record: duplicate check at row level
5. Update `import_log` with final counts

## Garmin Import Architecture

Garmin data can be imported from two sources: **CSV files** (manual export) or **Garmin Connect API** (dashboard).
Both share the same database insert logic to ensure consistent deduplication.

### Layer Design
```
┌─────────────────────────────────────────────────────────────────┐
│                         UI LAYER                                │
│  CLI (click)                    Dashboard (Streamlit)           │
│  health_import/cli/main.py      dashboard/components/           │
└─────────────────┬───────────────────────────┬───────────────────┘
                  │                           │
┌─────────────────▼───────────────────────────▼───────────────────┐
│                       PARSER LAYER                              │
│  CSV Parsers                    API Fetchers                    │
│  health_import/importers/       health_import/garmin/           │
│  - garmin_activities.py         - GarminActivityFetcher         │
│  - garmin_weight.py             - GarminWeightFetcher           │
│  - garmin_vo2max.py             - GarminVO2MaxFetcher           │
└─────────────────┬───────────────────────────┬───────────────────┘
                  │                           │
                  │   Normalized Records      │
                  │   (same format)           │
                  │                           │
┌─────────────────▼───────────────────────────▼───────────────────┐
│                    SHARED IMPORT LAYER                          │
│  health_import/garmin/                                          │
│  - import_vo2max_to_db()      Dedup: (source_id, date, type)   │
│  - import_weight_to_db()      Dedup: (source_id, date, time)   │
│  - import_activities_to_db()  Dedup: garmin_activity_id         │
│                               + start_time match for enrichment │
└─────────────────────────────────────────────────────────────────┘
                  │
┌─────────────────▼───────────────────────────────────────────────┐
│                      DATABASE LAYER                             │
│  SQLite: activities, body_measurements, garmin_vo2max,          │
│          activity_laps, activity_garmin_extras                  │
└─────────────────────────────────────────────────────────────────┘
```

### Shared Import Functions

| Data Type | Function | Location | Dedup Key |
|-----------|----------|----------|-----------|
| VO2 Max | `import_vo2max_to_db()` | `garmin/vo2max.py` | `(source_id, measurement_date, activity_type)` |
| Weight | `import_weight_to_db()` | `garmin/weight.py` | `(source_id, measurement_date, measurement_time)` |
| Activities | `import_activities_to_db()` | `garmin/activities.py` | `garmin_activity_id` or `start_time` |

### Deduplication Behavior

All imports skip existing records:

1. **VO2 Max / Weight**: Uses `sqlite3.IntegrityError` on UNIQUE constraint
2. **Activities**:
   - If `garmin_activity_id` exists → skip entirely
   - If `start_time` matches existing activity → enrich with laps/extras (no duplicate)
   - Otherwise → insert new activity

### Activity Enrichment

API imports can enrich CSV-imported activities:
```
CSV Import: Creates activity record (no garmin_activity_id, no laps)
     ↓
API Import: Finds matching start_time
     ↓
     Links garmin_activity_id, adds laps, adds garmin_extras
     (no duplicate activity created)
```

### Data Flow Examples

**CSV Import (CLI)**:
```
CSV File → GarminWeightImporter._parse_file()
        → Normalize to {measurement_date, weight_lbs, ...}
        → import_weight_to_db()
        → INSERT with IntegrityError catch
```

**API Import (Dashboard)**:
```
Garmin API → GarminWeightFetcher.fetch_weight()
          → convert_api_weight() (grams→lbs)
          → import_weight_to_db()  ← same function!
          → INSERT with IntegrityError catch
```

## MCP Server

Model Context Protocol server exposes health data to LLMs with token-efficient queries.

### Configuration
Database selection in `health_import/mcp/config.py`:
```python
DB_PATH = DB_PATHS["prod"]  # or "test"
```

### Running
```bash
python -m health_import.mcp
```

### Claude Desktop Config
```json
{
  "mcpServers": {
    "sierra-health": {
      "command": "python",
      "args": ["-m", "health_import.mcp"],
      "cwd": "C:/dev/python/Sierra"
    }
  }
}
```

### Available Tools

| Category | Tools |
|----------|-------|
| Weight | `weight_summary`, `weight_trend`, `weight_records`, `weight_stats`, `weight_compare`, `weight_hide`, `weight_hide_above`, `weight_hide_below`, `weight_unhide_all` |
| Nutrition | `nutrition_summary`, `nutrition_trend`, `nutrition_day`, `nutrition_stats`, `nutrition_compare` |
| Activity | `activity_summary`, `activity_trend`, `activity_records`, `activity_stats`, `activity_compare` |
| Resting HR | `rhr_summary`, `rhr_trend`, `rhr_records`, `rhr_stats`, `rhr_compare`, `rhr_hide`, `rhr_hide_above`, `rhr_hide_below` |
| VO2 Max | `vo2max_summary`, `vo2max_trend`, `vo2max_records`, `vo2max_stats`, `vo2max_compare` |
| Strength | `strength_summary`, `strength_trend`, `strength_records`, `strength_stats`, `strength_exercises`, `strength_compare` |

### Token-Efficient Keys
Responses use abbreviated keys to minimize tokens:
- `d`=date, `t`=time, `wt`=weight, `fat`=body_fat, `m`=muscle
- `cur`=current/latest, `rng`=range, `s`=start, `e`=end, `n`=count
- `avg`=mean, `med`=median, `chg`=change
- `r`=records, `pg`=page, `pgs`=pages

### Hidden Records
Weight and RHR support hiding outliers via `*_hide`, `*_hide_above`, `*_hide_below` tools. Hidden records excluded from all queries.

---

## Dependencies
```toml
[project]
dependencies = ["openpyxl>=3.1.0", "garminconnect>=0.2.0", "mcp>=1.0.0"]
```
All else stdlib: sqlite3, csv, logging, argparse, dataclasses, hashlib

## CLI Usage
```bash
# Import files
python -m health_import import garmin-activities ExampleExportFiles/GarminExportExample.csv
python -m health_import import garmin-weight ExampleExportFiles/GarminWeightExample.csv
python -m health_import import garmin-vo2max ExampleExportFiles/VO_Max_Example.csv
python -m health_import import six-week ExampleExportFiles/just6weeksExample.csv
python -m health_import import macrofactor ExampleExportFiles/MacroFactorExample.xlsx
python -m health_import import apple-resting-hr ExampleExportFiles/export.xml

# Specify different database
python -m health_import import garmin-activities file.csv --db ./other/path.db

# Debug/inspect
python -m health_import inspect --table activities
python -m health_import inspect --table body_measurements --limit 10
python -m health_import conflicts --show
python -m health_import conflicts --import-id 5
```

---

# Database Schema

## Metadata Tables

### data_sources
Registry of import source types.
```sql
CREATE TABLE data_sources (
    id INTEGER PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,        -- 'garmin_activities', 'macrofactor', etc.
    description TEXT,
    file_pattern TEXT                 -- Expected file pattern (*.csv, *.xlsx)
);

-- Seed data
INSERT INTO data_sources (name, description, file_pattern) VALUES
    ('garmin_activities', 'Garmin Connect activity exports', '*.csv'),
    ('garmin_weight', 'Garmin Connect weight/body composition', '*.csv'),
    ('garmin_vo2max', 'Garmin VO2 Max tracking CSV', '*.csv'),
    ('six_week', 'Just 6 Weeks strength training app', '*.csv'),
    ('macrofactor', 'MacroFactor nutrition tracking', '*.xlsx'),
    ('apple_healthkit', 'Apple Health export', 'export.xml');
```

### import_log
Audit trail for each import operation.
```sql
CREATE TABLE import_log (
    id INTEGER PRIMARY KEY,
    source_id INTEGER NOT NULL REFERENCES data_sources(id),
    file_path TEXT NOT NULL,
    file_hash TEXT NOT NULL,          -- SHA256 for duplicate detection
    import_timestamp TEXT NOT NULL DEFAULT (datetime('now')),
    records_processed INTEGER DEFAULT 0,
    records_inserted INTEGER DEFAULT 0,
    records_skipped INTEGER DEFAULT 0,
    records_conflicted INTEGER DEFAULT 0,
    status TEXT CHECK(status IN ('running', 'completed', 'failed')) DEFAULT 'running',
    error_message TEXT
);
```

### import_conflicts
Records where incoming data differs from existing.
```sql
CREATE TABLE import_conflicts (
    id INTEGER PRIMARY KEY,
    import_id INTEGER NOT NULL REFERENCES import_log(id),
    table_name TEXT NOT NULL,         -- Which table had the conflict
    record_key TEXT NOT NULL,         -- Natural key as JSON
    existing_value TEXT,              -- Existing record as JSON
    new_value TEXT,                   -- Incoming record as JSON
    conflict_fields TEXT,             -- List of fields that differ
    resolution TEXT CHECK(resolution IN ('kept_existing', 'overwritten', 'manual'))
        DEFAULT 'kept_existing',
    resolved_timestamp TEXT
);
```

---

## Activity Tables

### activity_types
Lookup table mapping activity names across sources.
```sql
CREATE TABLE activity_types (
    id INTEGER PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,        -- Canonical name: 'running', 'cycling'
    category TEXT,                    -- 'cardio', 'strength', 'flexibility'
    healthkit_type TEXT,              -- Apple: 'HKWorkoutActivityTypeRunning'
    garmin_type TEXT                  -- Garmin: 'Running', 'Treadmill Running'
);

-- Seed data
INSERT INTO activity_types (name, category, healthkit_type, garmin_type) VALUES
    ('running', 'cardio', 'HKWorkoutActivityTypeRunning', 'Running'),
    ('treadmill_running', 'cardio', 'HKWorkoutActivityTypeRunning', 'Treadmill Running'),
    ('walking', 'cardio', 'HKWorkoutActivityTypeWalking', 'Walking'),
    ('hiking', 'cardio', 'HKWorkoutActivityTypeHiking', 'Hiking'),
    ('cycling', 'cardio', 'HKWorkoutActivityTypeCycling', 'Cycling'),
    ('ebiking', 'cardio', 'HKWorkoutActivityTypeCycling', 'E-Bike Ride'),
    ('elliptical', 'cardio', 'HKWorkoutActivityTypeElliptical', 'Elliptical'),
    ('strength', 'strength', 'HKWorkoutActivityTypeFunctionalStrengthTraining', 'Strength Training'),
    ('swimming', 'cardio', 'HKWorkoutActivityTypeSwimming', 'Pool Swimming');
```

### activities
Core workout/activity records from all sources.
```sql
CREATE TABLE activities (
    id INTEGER PRIMARY KEY,
    source_id INTEGER NOT NULL REFERENCES data_sources(id),
    source_record_id TEXT,            -- Original ID from source if available
    activity_type_id INTEGER REFERENCES activity_types(id),

    -- Timing
    start_time TEXT NOT NULL,         -- ISO 8601: '2025-11-24T16:00:58'
    end_time TEXT,
    duration_seconds REAL,            -- Total elapsed time
    moving_time_seconds REAL,         -- Time actually moving

    -- Basic metrics
    title TEXT,                       -- User-provided title
    distance_miles REAL,
    calories_total REAL,
    calories_active REAL,

    -- Speed/Pace (imperial)
    avg_speed_mph REAL,
    max_speed_mph REAL,
    avg_pace_min_per_mile REAL,       -- e.g., 9.5 = 9:30/mile
    best_pace_min_per_mile REAL,

    -- Heart rate
    avg_hr INTEGER,
    max_hr INTEGER,

    -- Elevation (feet)
    elevation_gain_ft REAL,
    elevation_loss_ft REAL,
    min_elevation_ft REAL,
    max_elevation_ft REAL,

    -- Metadata
    is_indoor INTEGER DEFAULT 0,
    device_name TEXT,
    import_id INTEGER REFERENCES import_log(id),
    created_at TEXT DEFAULT (datetime('now')),

    UNIQUE(source_id, start_time, activity_type_id)
);

CREATE INDEX idx_activities_date ON activities(start_time);
CREATE INDEX idx_activities_type ON activities(activity_type_id);
```

### activity_running_dynamics
Extended running metrics (Garmin-specific).
```sql
CREATE TABLE activity_running_dynamics (
    activity_id INTEGER PRIMARY KEY REFERENCES activities(id),

    -- Cadence
    avg_cadence INTEGER,              -- steps per minute
    max_cadence INTEGER,

    -- Stride
    avg_stride_length_ft REAL,

    -- Vertical metrics
    avg_vertical_ratio REAL,          -- percentage
    avg_vertical_oscillation_in REAL, -- inches

    -- Ground contact
    avg_ground_contact_time_ms INTEGER,

    -- Grade adjusted pace
    avg_gap_min_per_mile REAL,

    -- Power
    training_stress_score REAL,       -- TSS
    normalized_power_watts INTEGER,
    avg_power_watts INTEGER,
    max_power_watts INTEGER
);
```

### activity_garmin_extras
Garmin-specific fields not in standard schema. Links API data to activities.
```sql
CREATE TABLE activity_garmin_extras (
    activity_id INTEGER PRIMARY KEY REFERENCES activities(id),
    garmin_activity_id BIGINT UNIQUE, -- Garmin's activity ID (for API dedup)
    event_type TEXT,                  -- 'race', 'training', etc.
    location_name TEXT,               -- City/location name
    aerobic_te REAL,                  -- Aerobic Training Effect
    anaerobic_te REAL,                -- Anaerobic Training Effect
    training_load REAL,               -- Training load score
    vo2max_value REAL,                -- VO2 Max from this activity
    steps INTEGER,
    body_battery_drain INTEGER,
    grit REAL,                        -- Mountain biking metric
    flow REAL,                        -- Mountain biking metric
    laps INTEGER,
    best_lap_time_seconds REAL,
    avg_respiration INTEGER,          -- breaths per minute
    min_respiration INTEGER,
    max_respiration INTEGER
);

CREATE INDEX idx_activity_garmin_extras_garmin_id ON activity_garmin_extras(garmin_activity_id);
```

### activity_laps
Per-lap/split data from Garmin API.
```sql
CREATE TABLE activity_laps (
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
);

CREATE INDEX idx_activity_laps_activity ON activity_laps(activity_id);
```

---

## Body Measurements

### body_measurements
Weight and body composition data.
```sql
CREATE TABLE body_measurements (
    id INTEGER PRIMARY KEY,
    source_id INTEGER NOT NULL REFERENCES data_sources(id),

    -- Timing
    measurement_date TEXT NOT NULL,   -- 'YYYY-MM-DD'
    measurement_time TEXT,            -- 'HH:MM:SS' if available

    -- Weight (imperial)
    weight_lbs REAL,
    weight_change_lbs REAL,           -- Change from previous

    -- Body composition
    bmi REAL,
    body_fat_pct REAL,
    muscle_mass_lbs REAL,             -- Skeletal muscle mass
    bone_mass_lbs REAL,
    body_water_pct REAL,
    lean_body_mass_lbs REAL,

    -- Additional metrics
    visceral_fat_level INTEGER,
    basal_metabolic_rate_kcal REAL,

    -- Metadata
    import_id INTEGER REFERENCES import_log(id),
    created_at TEXT DEFAULT (datetime('now')),
    hidden INTEGER DEFAULT 0,         -- 1=excluded from queries

    UNIQUE(source_id, measurement_date, measurement_time)
);

CREATE INDEX idx_body_measurements_date ON body_measurements(measurement_date);
```

### garmin_vo2max
VO2 Max tracking from Garmin.
```sql
CREATE TABLE garmin_vo2max (
    id INTEGER PRIMARY KEY,
    source_id INTEGER NOT NULL REFERENCES data_sources(id),
    measurement_date TEXT NOT NULL,
    activity_type TEXT,               -- 'Running', 'Cycling'
    vo2max_value REAL NOT NULL,       -- ml/kg/min
    import_id INTEGER REFERENCES import_log(id),
    created_at TEXT DEFAULT (datetime('now')),

    UNIQUE(source_id, measurement_date, activity_type)
);

CREATE INDEX idx_garmin_vo2max_date ON garmin_vo2max(measurement_date);
```

### resting_heart_rate
Resting heart rate from Apple HealthKit.
```sql
CREATE TABLE resting_heart_rate (
    id INTEGER PRIMARY KEY,
    source_id INTEGER NOT NULL REFERENCES data_sources(id),
    measurement_date TEXT NOT NULL,   -- 'YYYY-MM-DD'
    resting_hr INTEGER NOT NULL,      -- bpm
    source_name TEXT,                 -- 'Apple Watch', etc.
    hidden INTEGER DEFAULT 0,         -- 1=excluded from queries
    import_id INTEGER REFERENCES import_log(id),
    created_at TEXT DEFAULT (datetime('now')),

    UNIQUE(source_id, measurement_date)
);

CREATE INDEX idx_resting_hr_date ON resting_heart_rate(measurement_date);
```

---

## Strength Training

### strength_exercises
Exercise type lookup.
```sql
CREATE TABLE strength_exercises (
    id INTEGER PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,        -- Canonical: 'push_ups', 'pull_ups'
    display_name TEXT,                -- 'Push-ups'
    category TEXT,                    -- 'upper_body', 'core', 'lower_body'
    unit TEXT DEFAULT 'reps'          -- 'reps' or 'seconds'
);

-- Seed data
INSERT INTO strength_exercises (name, display_name, category, unit) VALUES
    ('push_ups', 'Push-ups', 'upper_body', 'reps'),
    ('pull_ups', 'Pull-ups', 'upper_body', 'reps'),
    ('plank', 'Plank', 'core', 'seconds');
```

### strength_workouts
Individual strength workout sessions.
```sql
CREATE TABLE strength_workouts (
    id INTEGER PRIMARY KEY,
    source_id INTEGER NOT NULL REFERENCES data_sources(id),
    exercise_id INTEGER NOT NULL REFERENCES strength_exercises(id),

    -- Timing
    workout_date TEXT NOT NULL,       -- 'YYYY-MM-DD'
    workout_time TEXT,                -- 'HH:MM:SS'

    -- Program info
    goal_value REAL,                  -- Target reps/seconds
    program_name TEXT,                -- e.g., '6 Week Challenge'
    week_number INTEGER,
    day_number INTEGER,

    -- Sets (up to 5)
    set1 REAL,
    set2 REAL,
    set3 REAL,
    set4 REAL,
    set5 REAL,
    total_value REAL,                 -- Sum of sets

    -- Additional
    duration_seconds INTEGER,
    calories INTEGER,

    -- Metadata
    import_id INTEGER REFERENCES import_log(id),
    created_at TEXT DEFAULT (datetime('now')),

    UNIQUE(source_id, workout_date, exercise_id, workout_time)
);

CREATE INDEX idx_strength_workouts_date ON strength_workouts(workout_date);
```

---

## Nutrition

### nutrition_daily
Daily nutrition summary.
```sql
CREATE TABLE nutrition_daily (
    id INTEGER PRIMARY KEY,
    source_id INTEGER NOT NULL REFERENCES data_sources(id),
    date TEXT NOT NULL,               -- 'YYYY-MM-DD'

    -- Energy
    expenditure_kcal REAL,            -- TDEE
    calories_consumed_kcal REAL,
    target_calories_kcal REAL,

    -- Weight (from nutrition app tracking)
    weight_lbs REAL,
    trend_weight_lbs REAL,            -- Smoothed trend

    -- Macros consumed
    protein_g REAL,
    fat_g REAL,
    carbs_g REAL,
    fiber_g REAL,
    alcohol_g REAL,

    -- Macro targets
    target_protein_g REAL,
    target_fat_g REAL,
    target_carbs_g REAL,

    -- Activity
    steps INTEGER,

    -- Metadata
    import_id INTEGER REFERENCES import_log(id),
    created_at TEXT DEFAULT (datetime('now')),

    UNIQUE(source_id, date)
);

CREATE INDEX idx_nutrition_daily_date ON nutrition_daily(date);
```

### nutrition_entries
Individual food entries.
```sql
CREATE TABLE nutrition_entries (
    id INTEGER PRIMARY KEY,
    daily_id INTEGER REFERENCES nutrition_daily(id),
    source_id INTEGER NOT NULL REFERENCES data_sources(id),

    -- Timing
    date TEXT NOT NULL,
    time TEXT,                        -- 'HH:MM:SS'

    -- Food info
    food_name TEXT NOT NULL,
    serving_size TEXT,                -- '1 cup', '100g'
    serving_qty REAL,
    serving_weight_g REAL,

    -- Macros
    calories_kcal REAL,
    protein_g REAL,
    fat_g REAL,
    carbs_g REAL,
    fiber_g REAL,

    -- Metadata
    import_id INTEGER REFERENCES import_log(id),
    created_at TEXT DEFAULT (datetime('now')),

    UNIQUE(source_id, date, time, food_name)
);
```

### nutrition_micros
Micronutrients per food entry.
```sql
CREATE TABLE nutrition_micros (
    entry_id INTEGER PRIMARY KEY REFERENCES nutrition_entries(id),

    -- Vitamins
    vitamin_a_mcg REAL,
    vitamin_c_mg REAL,
    vitamin_d_mcg REAL,
    vitamin_e_mg REAL,
    vitamin_k_mcg REAL,

    -- B Vitamins
    b1_thiamine_mg REAL,
    b2_riboflavin_mg REAL,
    b3_niacin_mg REAL,
    b5_pantothenic_mg REAL,
    b6_pyridoxine_mg REAL,
    b12_cobalamin_mcg REAL,
    folate_mcg REAL,
    choline_mg REAL,

    -- Minerals
    calcium_mg REAL,
    iron_mg REAL,
    magnesium_mg REAL,
    phosphorus_mg REAL,
    potassium_mg REAL,
    sodium_mg REAL,
    zinc_mg REAL,
    copper_mg REAL,
    manganese_mg REAL,
    selenium_mcg REAL,

    -- Fats breakdown
    saturated_fat_g REAL,
    monounsaturated_fat_g REAL,
    polyunsaturated_fat_g REAL,
    trans_fat_g REAL,
    cholesterol_mg REAL,
    omega3_g REAL,
    omega6_g REAL,

    -- Carbs breakdown
    sugars_g REAL,
    sugars_added_g REAL,
    starch_g REAL,

    -- Other
    caffeine_mg REAL,
    water_g REAL
);
```

---

## Apple HealthKit (Future)

### healthkit_records
Generic storage for HealthKit data points.
```sql
CREATE TABLE healthkit_records (
    id INTEGER PRIMARY KEY,
    source_id INTEGER NOT NULL REFERENCES data_sources(id),
    record_type TEXT NOT NULL,        -- 'HKQuantityTypeIdentifierHeartRate'
    start_time TEXT NOT NULL,
    end_time TEXT,
    value REAL,
    unit TEXT,                        -- 'count/min', 'mL', etc.
    source_name TEXT,                 -- 'Apple Watch', 'HeartWatch'
    source_version TEXT,
    device TEXT,
    import_id INTEGER REFERENCES import_log(id),
    created_at TEXT DEFAULT (datetime('now')),

    UNIQUE(record_type, start_time, source_name)
);

CREATE INDEX idx_healthkit_records_type ON healthkit_records(record_type);
CREATE INDEX idx_healthkit_records_time ON healthkit_records(start_time);
```

### sleep_records
Sleep tracking data.
```sql
CREATE TABLE sleep_records (
    id INTEGER PRIMARY KEY,
    source_id INTEGER NOT NULL REFERENCES data_sources(id),
    date TEXT NOT NULL,               -- Night of sleep
    start_time TEXT NOT NULL,
    end_time TEXT NOT NULL,
    sleep_stage TEXT,                 -- 'asleep', 'awake', 'deep', 'rem', 'core'
    duration_seconds REAL,
    source_name TEXT,
    import_id INTEGER REFERENCES import_log(id),
    created_at TEXT DEFAULT (datetime('now')),

    UNIQUE(source_id, start_time, sleep_stage)
);

CREATE INDEX idx_sleep_records_date ON sleep_records(date);
```

### daily_activity_summary
Apple Activity Rings data.
```sql
CREATE TABLE daily_activity_summary (
    id INTEGER PRIMARY KEY,
    source_id INTEGER NOT NULL REFERENCES data_sources(id),
    date TEXT NOT NULL,

    -- Move ring
    active_energy_burned_kcal REAL,
    active_energy_goal_kcal REAL,

    -- Exercise ring
    exercise_time_min INTEGER,
    exercise_goal_min INTEGER,

    -- Stand ring
    stand_hours INTEGER,
    stand_goal_hours INTEGER,

    -- Metadata
    import_id INTEGER REFERENCES import_log(id),
    created_at TEXT DEFAULT (datetime('now')),

    UNIQUE(source_id, date)
);
```

---

## Example Queries

### Recent activities
```sql
SELECT a.start_time, t.name as activity, a.distance_miles,
       a.duration_seconds/60.0 as minutes, a.avg_hr
FROM activities a
JOIN activity_types t ON a.activity_type_id = t.id
ORDER BY a.start_time DESC
LIMIT 10;
```

### Weight trend
```sql
SELECT measurement_date, weight_lbs, body_fat_pct
FROM body_measurements
WHERE measurement_date >= date('now', '-30 days')
ORDER BY measurement_date;
```

### Weekly nutrition average
```sql
SELECT strftime('%Y-%W', date) as week,
       AVG(calories_consumed_kcal) as avg_calories,
       AVG(protein_g) as avg_protein
FROM nutrition_daily
GROUP BY week
ORDER BY week DESC;
```

### Cross-source activity comparison
```sql
SELECT ds.name as source, COUNT(*) as activities,
       SUM(a.distance_miles) as total_miles
FROM activities a
JOIN data_sources ds ON a.source_id = ds.id
GROUP BY ds.name;
```

---

## MCP Monitoring

### mcp_requests
Logs MCP tool calls for dashboard monitoring.
```sql
CREATE TABLE mcp_requests (
    id INTEGER PRIMARY KEY,
    timestamp TEXT NOT NULL DEFAULT (datetime('now')),
    tool_name TEXT NOT NULL,
    params TEXT,                      -- JSON of request params
    response TEXT,                    -- JSON response (truncated if large)
    response_tokens INTEGER,          -- Estimated token count
    duration_ms INTEGER
);

CREATE INDEX idx_mcp_requests_timestamp ON mcp_requests(timestamp);
CREATE INDEX idx_mcp_requests_tool ON mcp_requests(tool_name);
```
