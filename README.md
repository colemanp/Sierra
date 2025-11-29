# Sierra

Health/fitness data import system. Consolidates data from multiple sources into a normalized SQLite database.

## Supported Sources

| Source | Format | Data |
|--------|--------|------|
| Garmin Activities | CSV | workouts, HR, pace, power |
| Garmin Weight | CSV | weight, BMI, body fat, muscle mass |
| Garmin VO2 Max | CSV | VO2max tracking |
| 6-Week Challenge | CSV | strength sets/reps |
| MacroFactor | CSV | nutrition, macros, food entries |
| Apple HealthKit | XML | resting heart rate |

## Install

```bash
pip install -e .
```

## CLI Reference

### Global Options

```
python -m health_import [options] <command>

Options:
  --db DB       Database path (default: data/prod/health_data.db)
  --test        Use test database (data/test/health_data.db)
  -v            Verbose (show inserts)
  -vv           Debug (show all SQL)
  -q            Quiet (errors only)
```

### Commands

#### import

Import data from file.

```
python -m health_import import <source> <file>

Sources:
  garmin-activities   Garmin activity CSV
  garmin-weight       Garmin weight/body comp CSV
  garmin-vo2max       Garmin VO2 Max CSV
  six-week            6-Week Challenge CSV
  macrofactor         MacroFactor nutrition CSV
  apple-resting-hr    Apple Health export XML
```

#### inspect

View database contents.

```
python -m health_import inspect --table <name> [--limit N]

Options:
  -t, --table   Table name (required)
  -l, --limit   Number of records to show
```

#### conflicts

View import conflicts.

```
python -m health_import conflicts [--import-id ID] [--limit N]

Options:
  -i, --import-id   Show conflicts for specific import
  -l, --limit       Number of conflicts to show
```

#### init

Initialize/reset database schema.

```
python -m health_import init
```

### Examples

```bash
# Import from various sources
python -m health_import import garmin-activities Activities.csv
python -m health_import import garmin-weight Weight.csv
python -m health_import import macrofactor nutrition.csv
python -m health_import import apple-resting-hr export.xml

# Inspect data
python -m health_import inspect -t activities -l 10
python -m health_import inspect -t body_measurements

# Use test database
python -m health_import --test import garmin-weight Weight.csv
```

## Dashboard

```bash
# Windows
scripts\start_dashboard.bat

# Or with venv activated
.venv\Scripts\python.exe -m streamlit run dashboard/app.py
```

### Hot Reload

Streamlit auto-reloads on file changes. Restart required for:
- Changes to `health_import/` (core library)
- New dependencies in pyproject.toml
- Schema changes (init.sql)

No restart needed for:
- Dashboard component changes (dashboard/)
- Query changes (dashboard/utils/)

## Project Structure

```
Sierra/
├── health_import/    # Core import library
├── dashboard/        # Streamlit dashboard
├── scripts/          # Debug/utility scripts
├── schema/           # SQLite DDL
└── data/
    ├── prod/         # Production database
    └── test/         # Test database
```

See [ARCHITECTURE.md](ARCHITECTURE.md) for full schema and design details.
