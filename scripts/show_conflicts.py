#!/usr/bin/env python3
"""Debug script to view import conflicts"""
import json
import sqlite3
import sys
from pathlib import Path

DEFAULT_DB = Path("data/prod/health_data.db")


def show_conflicts(conn: sqlite3.Connection, import_id: int = None, limit: int = 50) -> None:
    """Show import conflicts"""
    conn.row_factory = sqlite3.Row

    if import_id:
        cursor = conn.execute(
            """SELECT c.*, l.file_path, l.import_timestamp, s.name as source_name
               FROM import_conflicts c
               JOIN import_log l ON c.import_id = l.id
               JOIN data_sources s ON l.source_id = s.id
               WHERE c.import_id = ?
               ORDER BY c.id""",
            (import_id,)
        )
    else:
        cursor = conn.execute(
            """SELECT c.*, l.file_path, l.import_timestamp, s.name as source_name
               FROM import_conflicts c
               JOIN import_log l ON c.import_id = l.id
               JOIN data_sources s ON l.source_id = s.id
               ORDER BY c.id DESC
               LIMIT ?""",
            (limit,)
        )

    rows = cursor.fetchall()

    if not rows:
        print("No conflicts found")
        return

    print(f"\n{'='*80}")
    print(f"IMPORT CONFLICTS ({len(rows)} found)")
    print(f"{'='*80}")

    current_import = None
    for row in rows:
        row = dict(row)

        if row["import_id"] != current_import:
            current_import = row["import_id"]
            print(f"\n[Import #{current_import}] {row['source_name']}")
            print(f"  File: {row['file_path']}")
            print(f"  Time: {row['import_timestamp']}")
            print("-" * 60)

        print(f"\n  Conflict in: {row['table_name']}")

        # Parse and pretty-print JSON
        try:
            key = json.loads(row["record_key"])
            print(f"  Record key:")
            for k, v in key.items():
                print(f"    {k}: {v}")
        except json.JSONDecodeError:
            print(f"  Record key: {row['record_key']}")

        try:
            existing = json.loads(row["existing_value"])
            new = json.loads(row["new_value"])
            fields = json.loads(row["conflict_fields"])

            print(f"  Conflicting fields:")
            for field in fields:
                print(f"    {field}:")
                print(f"      existing: {existing.get(field)}")
                print(f"      new:      {new.get(field)}")
        except json.JSONDecodeError:
            print(f"  Existing: {row['existing_value']}")
            print(f"  New: {row['new_value']}")

        print(f"  Resolution: {row['resolution']}")


def show_import_log(conn: sqlite3.Connection, limit: int = 20) -> None:
    """Show recent import logs"""
    conn.row_factory = sqlite3.Row
    cursor = conn.execute(
        """SELECT l.*, s.name as source_name
           FROM import_log l
           JOIN data_sources s ON l.source_id = s.id
           ORDER BY l.id DESC
           LIMIT ?""",
        (limit,)
    )

    rows = cursor.fetchall()

    if not rows:
        print("No import logs found")
        return

    print(f"\n{'='*80}")
    print("RECENT IMPORTS")
    print(f"{'='*80}")

    for row in rows:
        row = dict(row)
        status_icon = "✓" if row["status"] == "completed" else "✗" if row["status"] == "failed" else "⋯"
        conflict_str = f" ({row['records_conflicted']} conflicts)" if row["records_conflicted"] else ""

        print(f"\n[#{row['id']}] {status_icon} {row['source_name']} - {row['import_timestamp']}")
        print(f"  File: {row['file_path']}")
        print(f"  Records: {row['records_inserted']} inserted, {row['records_skipped']} skipped{conflict_str}")
        if row["error_message"]:
            print(f"  Error: {row['error_message']}")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="View import conflicts")
    parser.add_argument("--db", default=str(DEFAULT_DB), help="Database path")
    parser.add_argument("--import-id", "-i", type=int, help="Show specific import")
    parser.add_argument("--limit", "-l", type=int, default=50, help="Conflict limit")
    parser.add_argument("--logs", action="store_true", help="Show import logs")
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"Database not found: {db_path}")
        sys.exit(1)

    conn = sqlite3.connect(db_path)

    if args.logs:
        show_import_log(conn, args.limit)
    else:
        show_conflicts(conn, args.import_id, args.limit)

    conn.close()


if __name__ == "__main__":
    main()
