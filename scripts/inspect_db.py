#!/usr/bin/env python3
"""Debug script to inspect database contents"""
import sqlite3
import sys
from pathlib import Path

DEFAULT_DB = Path("data/prod/health_data.db")


def list_tables(conn: sqlite3.Connection) -> list:
    """List all tables in database"""
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    )
    return [row[0] for row in cursor.fetchall()]


def table_info(conn: sqlite3.Connection, table: str) -> None:
    """Show table structure and row count"""
    # Get column info
    cursor = conn.execute(f"PRAGMA table_info({table})")
    columns = cursor.fetchall()

    # Get row count
    count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]

    print(f"\n{table} ({count} rows)")
    print("-" * 60)
    print(f"{'Column':<30} {'Type':<15} {'Nullable'}")
    print("-" * 60)
    for col in columns:
        nullable = "NULL" if col[3] == 0 else "NOT NULL"
        print(f"{col[1]:<30} {col[2]:<15} {nullable}")


def show_recent(conn: sqlite3.Connection, table: str, limit: int = 10) -> None:
    """Show recent records from table"""
    conn.row_factory = sqlite3.Row
    cursor = conn.execute(f"SELECT * FROM {table} ORDER BY id DESC LIMIT ?", (limit,))
    rows = cursor.fetchall()

    if not rows:
        print(f"No records in {table}")
        return

    print(f"\nRecent records from {table}:")
    print("-" * 60)
    for row in rows:
        print(dict(row))


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Inspect health database")
    parser.add_argument("--db", default=str(DEFAULT_DB), help="Database path")
    parser.add_argument("--table", "-t", help="Show specific table")
    parser.add_argument("--limit", "-l", type=int, default=10, help="Record limit")
    parser.add_argument("--schema", "-s", action="store_true", help="Show schema only")
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"Database not found: {db_path}")
        sys.exit(1)

    conn = sqlite3.connect(db_path)

    if args.table:
        table_info(conn, args.table)
        if not args.schema:
            show_recent(conn, args.table, args.limit)
    else:
        tables = list_tables(conn)
        print("Tables in database:")
        print("=" * 40)
        for table in tables:
            count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            print(f"  {table:<35} {count:>5} rows")

        if args.schema:
            for table in tables:
                table_info(conn, table)

    conn.close()


if __name__ == "__main__":
    main()
