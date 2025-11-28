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

## Usage

```bash
# Import data
python -m health_import import garmin-activities path/to/file.csv
python -m health_import import garmin-weight path/to/file.csv
python -m health_import import garmin-vo2max path/to/file.csv
python -m health_import import six-week path/to/file.csv
python -m health_import import macrofactor path/to/file.csv

# Inspect database
python -m health_import inspect --table activities
python -m health_import inspect --table body_measurements --limit 10

# View conflicts
python -m health_import conflicts --show

# Use test database
python -m health_import --db data/test/health_data.db import ...
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
