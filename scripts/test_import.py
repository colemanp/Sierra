#!/usr/bin/env python3
"""Test script for health data imports using a test database"""
import os
import sys
from pathlib import Path

# Use test database
TEST_DB = Path("data/test/health_data.db")

# Remove existing test DB for clean run
if TEST_DB.exists():
    TEST_DB.unlink()
    print(f"Removed existing test DB: {TEST_DB}")

# Run imports
from health_import.cli.main import main

test_cases = [
    ("garmin-activities", "ExampleExportFiles/GarminExportExample.csv"),
    ("garmin-weight", "ExampleExportFiles/GarminWeightExample.csv"),
    ("garmin-vo2max", "ExampleExportFiles/VO_Max_Example.csv"),
    ("six-week", "ExampleExportFiles/just6weeksExample.csv"),
]

print("=" * 60)
print("HEALTH DATA IMPORT TEST")
print(f"Database: {TEST_DB}")
print("=" * 60)

for source, file_path in test_cases:
    print(f"\n--- Testing {source} ---")
    result = main(["--db", str(TEST_DB), "-v", "import", source, file_path])
    print(f"Exit code: {result}")

# Show summary
print("\n" + "=" * 60)
print("TEST SUMMARY")
print("=" * 60)
main(["--db", str(TEST_DB), "inspect", "-t", "activities", "-l", "5"])
main(["--db", str(TEST_DB), "inspect", "-t", "body_measurements", "-l", "5"])
main(["--db", str(TEST_DB), "inspect", "-t", "garmin_vo2max", "-l", "5"])
main(["--db", str(TEST_DB), "inspect", "-t", "strength_workouts", "-l", "5"])
