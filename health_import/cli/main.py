"""CLI entry point for health data import"""
import argparse
import sys
from pathlib import Path
from typing import Optional

from ..core.database import Database, DEFAULT_DB_PATH
from ..core.logging_setup import setup_logging, get_logger
from ..importers.garmin_activities import GarminActivitiesImporter
from ..importers.garmin_weight import GarminWeightImporter
from ..importers.garmin_vo2max import GarminVO2MaxImporter
from ..importers.six_week import SixWeekImporter
from ..importers.macrofactor import MacroFactorImporter
from ..importers.apple_resting_hr import AppleRestingHRImporter


IMPORTERS = {
    "garmin-activities": GarminActivitiesImporter,
    "garmin-weight": GarminWeightImporter,
    "garmin-vo2max": GarminVO2MaxImporter,
    "six-week": SixWeekImporter,
    "macrofactor": MacroFactorImporter,
    "apple-resting-hr": AppleRestingHRImporter,
}


def cmd_import(args: argparse.Namespace) -> int:
    """Handle import command"""
    logger = get_logger()

    # Get importer class
    importer_class = IMPORTERS.get(args.source)
    if not importer_class:
        logger.error(f"Unknown source: {args.source}")
        logger.error(f"Available sources: {', '.join(IMPORTERS.keys())}")
        return 1

    # Initialize database
    db_path = Path(args.db) if args.db else DEFAULT_DB_PATH
    file_path = Path(args.file)

    try:
        with Database(db_path) as db:
            db.init_schema()

            importer = importer_class(db, verbosity=args.verbose)
            result = importer.import_file(file_path)

            return 0 if result.conflicted == 0 else 0  # Still success even with conflicts

    except FileNotFoundError as e:
        logger.error(str(e))
        return 1
    except Exception as e:
        logger.error(f"Import failed: {e}")
        if args.verbose >= 2:
            import traceback
            traceback.print_exc()
        return 1


def cmd_inspect(args: argparse.Namespace) -> int:
    """Handle inspect command"""
    logger = get_logger()
    db_path = Path(args.db) if args.db else DEFAULT_DB_PATH

    try:
        with Database(db_path) as db:
            db.init_schema()

            table = args.table
            limit = args.limit or 20

            cursor = db.conn.execute(
                f"SELECT * FROM {table} ORDER BY id DESC LIMIT ?",
                (limit,)
            )
            rows = cursor.fetchall()

            if not rows:
                print(f"No records in {table}")
                return 0

            # Get column names
            columns = [desc[0] for desc in cursor.description]

            # Print header
            print(f"\n{table} (showing {len(rows)} records)")
            print("-" * 80)

            for row in rows:
                print(dict(row))

            return 0

    except Exception as e:
        logger.error(f"Inspect failed: {e}")
        return 1


def cmd_conflicts(args: argparse.Namespace) -> int:
    """Handle conflicts command"""
    logger = get_logger()
    db_path = Path(args.db) if args.db else DEFAULT_DB_PATH

    try:
        with Database(db_path) as db:
            db.init_schema()

            if args.import_id:
                cursor = db.conn.execute(
                    """SELECT c.*, l.file_path, s.name as source_name
                       FROM import_conflicts c
                       JOIN import_log l ON c.import_id = l.id
                       JOIN data_sources s ON l.source_id = s.id
                       WHERE c.import_id = ?
                       ORDER BY c.id""",
                    (args.import_id,)
                )
            else:
                cursor = db.conn.execute(
                    """SELECT c.*, l.file_path, s.name as source_name
                       FROM import_conflicts c
                       JOIN import_log l ON c.import_id = l.id
                       JOIN data_sources s ON l.source_id = s.id
                       ORDER BY c.id DESC
                       LIMIT ?""",
                    (args.limit or 50,)
                )

            rows = cursor.fetchall()

            if not rows:
                print("No conflicts found")
                return 0

            print(f"\nConflicts ({len(rows)} records)")
            print("=" * 80)

            current_import = None
            for row in rows:
                row = dict(row)
                import_id = row["import_id"]

                if import_id != current_import:
                    current_import = import_id
                    print(f"\nImport #{import_id} ({row['source_name']}) - {row['file_path']}")
                    print("-" * 60)

                print(f"\n  Table: {row['table_name']}")
                print(f"  Key: {row['record_key']}")
                print(f"  Differences:")
                print(f"    Existing: {row['existing_value']}")
                print(f"    New:      {row['new_value']}")
                print(f"  Resolution: {row['resolution']}")

            return 0

    except Exception as e:
        logger.error(f"Conflicts query failed: {e}")
        return 1


def cmd_init(args: argparse.Namespace) -> int:
    """Initialize database"""
    logger = get_logger()
    db_path = Path(args.db) if args.db else DEFAULT_DB_PATH

    try:
        with Database(db_path) as db:
            db.init_schema()
            logger.info(f"Database initialized: {db_path}")
            return 0
    except Exception as e:
        logger.error(f"Init failed: {e}")
        return 1


def main(argv: Optional[list] = None) -> int:
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        prog="health-import",
        description="Import health data from various sources"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="count",
        default=0,
        help="Increase verbosity (-v for inserts, -vv for debug)"
    )
    parser.add_argument(
        "-q", "--quiet",
        action="store_true",
        help="Quiet mode (errors only)"
    )
    parser.add_argument(
        "--db",
        help=f"Database path (default: {DEFAULT_DB_PATH})"
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Import command
    import_parser = subparsers.add_parser("import", help="Import data from file")
    import_parser.add_argument(
        "source",
        choices=list(IMPORTERS.keys()),
        help="Data source type"
    )
    import_parser.add_argument(
        "file",
        help="Path to import file"
    )
    import_parser.set_defaults(func=cmd_import)

    # Inspect command
    inspect_parser = subparsers.add_parser("inspect", help="Inspect database tables")
    inspect_parser.add_argument(
        "--table", "-t",
        required=True,
        help="Table name to inspect"
    )
    inspect_parser.add_argument(
        "--limit", "-l",
        type=int,
        default=20,
        help="Number of records to show"
    )
    inspect_parser.set_defaults(func=cmd_inspect)

    # Conflicts command
    conflicts_parser = subparsers.add_parser("conflicts", help="View import conflicts")
    conflicts_parser.add_argument(
        "--import-id", "-i",
        type=int,
        help="Show conflicts for specific import"
    )
    conflicts_parser.add_argument(
        "--limit", "-l",
        type=int,
        default=50,
        help="Number of conflicts to show"
    )
    conflicts_parser.set_defaults(func=cmd_conflicts)

    # Init command
    init_parser = subparsers.add_parser("init", help="Initialize database")
    init_parser.set_defaults(func=cmd_init)

    args = parser.parse_args(argv)

    # Setup logging
    setup_logging(verbosity=args.verbose, quiet=args.quiet)

    if not args.command:
        parser.print_help()
        return 0

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
