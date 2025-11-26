#!/usr/bin/env python3
"""Debug script to compare data across sources"""
import sqlite3
import sys
from pathlib import Path
from datetime import datetime, timedelta

DEFAULT_DB = Path("data/prod/health_data.db")


def compare_activities(conn: sqlite3.Connection) -> None:
    """Compare activities across sources"""
    conn.row_factory = sqlite3.Row

    print("\n" + "=" * 80)
    print("ACTIVITIES BY SOURCE")
    print("=" * 80)

    cursor = conn.execute(
        """SELECT s.name, COUNT(*) as count,
                  SUM(a.distance_miles) as total_miles,
                  AVG(a.duration_seconds)/60 as avg_duration_min
           FROM activities a
           JOIN data_sources s ON a.source_id = s.id
           GROUP BY s.name"""
    )

    for row in cursor.fetchall():
        row = dict(row)
        miles = row["total_miles"] or 0
        duration = row["avg_duration_min"] or 0
        print(f"\n{row['name']}:")
        print(f"  Activities: {row['count']}")
        print(f"  Total miles: {miles:.1f}")
        print(f"  Avg duration: {duration:.1f} min")


def compare_weight(conn: sqlite3.Connection) -> None:
    """Compare weight data across sources"""
    conn.row_factory = sqlite3.Row

    print("\n" + "=" * 80)
    print("WEIGHT DATA BY SOURCE")
    print("=" * 80)

    cursor = conn.execute(
        """SELECT s.name, COUNT(*) as count,
                  MIN(b.weight_lbs) as min_weight,
                  MAX(b.weight_lbs) as max_weight,
                  AVG(b.weight_lbs) as avg_weight
           FROM body_measurements b
           JOIN data_sources s ON b.source_id = s.id
           GROUP BY s.name"""
    )

    for row in cursor.fetchall():
        row = dict(row)
        print(f"\n{row['name']}:")
        print(f"  Measurements: {row['count']}")
        print(f"  Weight range: {row['min_weight']:.1f} - {row['max_weight']:.1f} lbs")
        print(f"  Average: {row['avg_weight']:.1f} lbs")


def date_coverage(conn: sqlite3.Connection) -> None:
    """Show date coverage across sources"""
    conn.row_factory = sqlite3.Row

    print("\n" + "=" * 80)
    print("DATE COVERAGE")
    print("=" * 80)

    # Activities
    cursor = conn.execute(
        """SELECT s.name,
                  MIN(date(a.start_time)) as first_date,
                  MAX(date(a.start_time)) as last_date,
                  COUNT(*) as count
           FROM activities a
           JOIN data_sources s ON a.source_id = s.id
           GROUP BY s.name"""
    )

    print("\nActivities:")
    for row in cursor.fetchall():
        row = dict(row)
        print(f"  {row['name']}: {row['first_date']} to {row['last_date']} ({row['count']} records)")

    # Body measurements
    cursor = conn.execute(
        """SELECT s.name,
                  MIN(b.measurement_date) as first_date,
                  MAX(b.measurement_date) as last_date,
                  COUNT(*) as count
           FROM body_measurements b
           JOIN data_sources s ON b.source_id = s.id
           GROUP BY s.name"""
    )

    print("\nBody measurements:")
    for row in cursor.fetchall():
        row = dict(row)
        print(f"  {row['name']}: {row['first_date']} to {row['last_date']} ({row['count']} records)")

    # Nutrition
    cursor = conn.execute(
        """SELECT s.name,
                  MIN(n.date) as first_date,
                  MAX(n.date) as last_date,
                  COUNT(*) as count
           FROM nutrition_daily n
           JOIN data_sources s ON n.source_id = s.id
           GROUP BY s.name"""
    )

    print("\nNutrition:")
    for row in cursor.fetchall():
        row = dict(row)
        print(f"  {row['name']}: {row['first_date']} to {row['last_date']} ({row['count']} records)")


def summary(conn: sqlite3.Connection) -> None:
    """Show overall data summary"""
    conn.row_factory = sqlite3.Row

    print("\n" + "=" * 80)
    print("DATA SUMMARY")
    print("=" * 80)

    tables = [
        ("activities", "Activities"),
        ("body_measurements", "Body measurements"),
        ("garmin_vo2max", "VO2 Max"),
        ("resting_heart_rate", "Resting HR"),
        ("strength_workouts", "Strength workouts"),
        ("nutrition_daily", "Nutrition (daily)"),
        ("nutrition_entries", "Nutrition (entries)"),
    ]

    for table, label in tables:
        try:
            count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            print(f"  {label:<25} {count:>8} records")
        except sqlite3.OperationalError:
            pass


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Compare data across sources")
    parser.add_argument("--db", default=str(DEFAULT_DB), help="Database path")
    parser.add_argument("--activities", "-a", action="store_true", help="Compare activities")
    parser.add_argument("--weight", "-w", action="store_true", help="Compare weight")
    parser.add_argument("--dates", "-d", action="store_true", help="Show date coverage")
    parser.add_argument("--all", action="store_true", help="Show all comparisons")
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"Database not found: {db_path}")
        sys.exit(1)

    conn = sqlite3.connect(db_path)

    # Default to summary if no specific option
    if not any([args.activities, args.weight, args.dates, args.all]):
        summary(conn)
    else:
        if args.all or args.activities:
            compare_activities(conn)
        if args.all or args.weight:
            compare_weight(conn)
        if args.all or args.dates:
            date_coverage(conn)
        if args.all:
            summary(conn)

    conn.close()


if __name__ == "__main__":
    main()
