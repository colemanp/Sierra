"""SQL queries for dashboard metrics"""
import sqlite3
import pandas as pd
from typing import Optional


def get_source_metrics(conn: sqlite3.Connection) -> pd.DataFrame:
    """Get metrics per data source"""
    query = """
    SELECT ds.name as source,
           ds.description,
           (SELECT MAX(import_timestamp) FROM import_log WHERE source_id = ds.id AND status='completed') as last_import,
           (SELECT COUNT(*) FROM import_log WHERE source_id = ds.id AND status='completed') as import_count,
           (SELECT SUM(records_inserted) FROM import_log WHERE source_id = ds.id AND status='completed') as total_records
    FROM data_sources ds
    ORDER BY ds.name
    """
    return pd.read_sql_query(query, conn)


def get_table_stats(conn: sqlite3.Connection) -> pd.DataFrame:
    """Get record counts and date ranges for main tables"""
    tables = [
        ("activities", "start_time", "Activities"),
        ("body_measurements", "measurement_date", "Body Measurements"),
        ("garmin_vo2max", "measurement_date", "VO2 Max"),
        ("resting_heart_rate", "measurement_date", "Resting HR"),
        ("strength_workouts", "workout_date", "Strength Workouts"),
        ("nutrition_entries", "date", "Nutrition Entries"),
    ]

    results = []
    for table, date_col, label in tables:
        try:
            query = f"""
            SELECT '{label}' as category,
                   COUNT(*) as records,
                   MIN({date_col}) as earliest,
                   MAX({date_col}) as latest
            FROM {table}
            """
            df = pd.read_sql_query(query, conn)
            results.append(df)
        except Exception:
            pass

    if results:
        return pd.concat(results, ignore_index=True)
    return pd.DataFrame()


def get_recent_imports(conn: sqlite3.Connection, limit: int = 10) -> pd.DataFrame:
    """Get recent import log entries"""
    query = """
    SELECT l.id, s.name as source, l.file_path, l.import_timestamp,
           l.records_processed, l.records_inserted, l.records_skipped,
           l.records_conflicted, l.status
    FROM import_log l
    JOIN data_sources s ON l.source_id = s.id
    ORDER BY l.import_timestamp DESC
    LIMIT ?
    """
    return pd.read_sql_query(query, conn, params=(limit,))


def get_conflict_summary(conn: sqlite3.Connection) -> pd.DataFrame:
    """Get conflict summary by table"""
    query = """
    SELECT table_name, COUNT(*) as conflicts,
           MAX(c.id) as last_conflict_id
    FROM import_conflicts c
    GROUP BY table_name
    ORDER BY conflicts DESC
    """
    return pd.read_sql_query(query, conn)


# Activities queries
def get_activities_summary(conn: sqlite3.Connection) -> pd.DataFrame:
    """Get activities summary by type"""
    query = """
    SELECT COALESCE(t.name, 'Unknown') as activity_type,
           COUNT(*) as count,
           ROUND(SUM(a.distance_miles), 1) as total_miles,
           ROUND(SUM(a.calories_total), 0) as total_calories,
           ROUND(AVG(a.avg_hr), 0) as avg_hr,
           ROUND(AVG(a.duration_seconds)/60, 1) as avg_duration_min
    FROM activities a
    LEFT JOIN activity_types t ON a.activity_type_id = t.id
    GROUP BY t.name
    ORDER BY count DESC
    """
    return pd.read_sql_query(query, conn)


def get_weekly_activities(conn: sqlite3.Connection) -> pd.DataFrame:
    """Get weekly activity volume"""
    query = """
    SELECT strftime('%Y-%W', start_time) as week,
           COUNT(*) as activities,
           ROUND(SUM(distance_miles), 1) as miles,
           ROUND(SUM(calories_total), 0) as calories
    FROM activities
    GROUP BY week
    ORDER BY week
    """
    return pd.read_sql_query(query, conn)


def get_recent_activities(conn: sqlite3.Connection, limit: int = 20) -> pd.DataFrame:
    """Get recent activities"""
    query = """
    SELECT a.start_time, COALESCE(t.name, 'Unknown') as type, a.title,
           a.distance_miles, a.duration_seconds/60.0 as duration_min,
           a.avg_hr, a.calories_total
    FROM activities a
    LEFT JOIN activity_types t ON a.activity_type_id = t.id
    ORDER BY a.start_time DESC
    LIMIT ?
    """
    return pd.read_sql_query(query, conn, params=(limit,))


# Body measurements queries
def get_weight_trend(conn: sqlite3.Connection, days: int = 90) -> pd.DataFrame:
    """Get weight trend over time"""
    query = f"""
    SELECT measurement_date as date, weight_lbs, body_fat_pct,
           muscle_mass_lbs, body_water_pct
    FROM body_measurements
    WHERE measurement_date >= date('now', '-{days} days')
    ORDER BY measurement_date
    """
    return pd.read_sql_query(query, conn)


def get_latest_weight(conn: sqlite3.Connection) -> Optional[dict]:
    """Get most recent weight measurement"""
    query = """
    SELECT measurement_date, weight_lbs, body_fat_pct, muscle_mass_lbs
    FROM body_measurements
    ORDER BY measurement_date DESC
    LIMIT 1
    """
    df = pd.read_sql_query(query, conn)
    if len(df) > 0:
        return df.iloc[0].to_dict()
    return None


def get_vo2max_trend(conn: sqlite3.Connection) -> pd.DataFrame:
    """Get VO2 Max over time"""
    query = """
    SELECT measurement_date as date, activity_type, vo2max_value
    FROM garmin_vo2max
    ORDER BY measurement_date
    """
    return pd.read_sql_query(query, conn)


def get_resting_hr_trend(conn: sqlite3.Connection, days: int = 90) -> pd.DataFrame:
    """Get resting heart rate trend"""
    query = f"""
    SELECT measurement_date as date, resting_hr
    FROM resting_heart_rate
    WHERE measurement_date >= date('now', '-{days} days')
    ORDER BY measurement_date
    """
    return pd.read_sql_query(query, conn)


# Strength queries
def get_strength_summary(conn: sqlite3.Connection) -> pd.DataFrame:
    """Get strength training summary by exercise"""
    query = """
    SELECT e.display_name as exercise, e.category,
           COUNT(*) as workouts,
           ROUND(AVG(w.total_value), 1) as avg_total,
           MAX(w.total_value) as max_total
    FROM strength_workouts w
    JOIN strength_exercises e ON w.exercise_id = e.id
    GROUP BY e.id
    ORDER BY workouts DESC
    """
    return pd.read_sql_query(query, conn)


def get_strength_progress(conn: sqlite3.Connection, exercise_name: Optional[str] = None) -> pd.DataFrame:
    """Get strength progress over time"""
    where_clause = ""
    if exercise_name:
        where_clause = f"WHERE e.display_name = '{exercise_name}'"

    query = f"""
    SELECT w.workout_date as date, e.display_name as exercise,
           w.total_value, w.goal_value
    FROM strength_workouts w
    JOIN strength_exercises e ON w.exercise_id = e.id
    {where_clause}
    ORDER BY w.workout_date
    """
    return pd.read_sql_query(query, conn)


def get_recent_workouts(conn: sqlite3.Connection, limit: int = 20) -> pd.DataFrame:
    """Get recent strength workouts"""
    query = """
    SELECT w.workout_date, w.workout_time, e.display_name as exercise,
           w.set1, w.set2, w.set3, w.set4, w.set5, w.total_value, w.calories
    FROM strength_workouts w
    JOIN strength_exercises e ON w.exercise_id = e.id
    ORDER BY w.workout_date DESC, w.workout_time DESC
    LIMIT ?
    """
    return pd.read_sql_query(query, conn, params=(limit,))


# Nutrition queries (aggregated from nutrition_entries)
def get_nutrition_summary(conn: sqlite3.Connection, days: int = 30) -> pd.DataFrame:
    """Get nutrition daily summary aggregated from food entries"""
    query = f"""
    SELECT date,
           ROUND(SUM(calories_kcal), 0) as calories,
           ROUND(SUM(protein_g), 1) as protein_g,
           ROUND(SUM(fat_g), 1) as fat_g,
           ROUND(SUM(carbs_g), 1) as carbs_g,
           ROUND(SUM(fiber_g), 1) as fiber_g
    FROM nutrition_entries
    WHERE date >= date('now', '-{days} days')
    GROUP BY date
    ORDER BY date
    """
    return pd.read_sql_query(query, conn)


def get_nutrition_averages(conn: sqlite3.Connection, days: int = 30) -> Optional[dict]:
    """Get average nutrition metrics from food entries"""
    query = f"""
    SELECT ROUND(AVG(daily_cal), 0) as avg_calories,
           ROUND(AVG(daily_protein), 1) as avg_protein,
           ROUND(AVG(daily_fat), 1) as avg_fat,
           ROUND(AVG(daily_carbs), 1) as avg_carbs,
           ROUND(AVG(daily_fiber), 1) as avg_fiber
    FROM (
        SELECT date,
               SUM(calories_kcal) as daily_cal,
               SUM(protein_g) as daily_protein,
               SUM(fat_g) as daily_fat,
               SUM(carbs_g) as daily_carbs,
               SUM(fiber_g) as daily_fiber
        FROM nutrition_entries
        WHERE date >= date('now', '-{days} days')
        GROUP BY date
    )
    """
    df = pd.read_sql_query(query, conn)
    if len(df) > 0:
        return df.iloc[0].to_dict()
    return None


def get_weekly_nutrition(conn: sqlite3.Connection) -> pd.DataFrame:
    """Get weekly nutrition averages from food entries"""
    query = """
    SELECT week,
           ROUND(AVG(daily_cal), 0) as avg_calories,
           ROUND(AVG(daily_protein), 1) as avg_protein,
           ROUND(AVG(daily_fat), 1) as avg_fat,
           ROUND(AVG(daily_carbs), 1) as avg_carbs
    FROM (
        SELECT strftime('%Y-%W', date) as week, date,
               SUM(calories_kcal) as daily_cal,
               SUM(protein_g) as daily_protein,
               SUM(fat_g) as daily_fat,
               SUM(carbs_g) as daily_carbs
        FROM nutrition_entries
        GROUP BY date
    )
    GROUP BY week
    ORDER BY week DESC
    LIMIT 12
    """
    return pd.read_sql_query(query, conn)


# Import management queries
def get_all_imports(conn: sqlite3.Connection, source_filter: Optional[str] = None) -> pd.DataFrame:
    """Get all imports with optional source filter"""
    where_clause = ""
    if source_filter:
        where_clause = f"WHERE s.name = '{source_filter}'"

    query = f"""
    SELECT l.id, s.name as source, l.file_path, l.import_timestamp,
           l.records_processed, l.records_inserted, l.records_skipped,
           l.records_conflicted, l.status, l.error_message
    FROM import_log l
    JOIN data_sources s ON l.source_id = s.id
    {where_clause}
    ORDER BY l.import_timestamp DESC
    """
    return pd.read_sql_query(query, conn)


def get_conflicts_detail(conn: sqlite3.Connection, import_id: Optional[int] = None) -> pd.DataFrame:
    """Get detailed conflict information"""
    where_clause = ""
    if import_id:
        where_clause = f"WHERE c.import_id = {import_id}"

    query = f"""
    SELECT c.id, c.import_id, c.table_name, c.record_key,
           c.existing_value, c.new_value, c.conflict_fields, c.resolution
    FROM import_conflicts c
    {where_clause}
    ORDER BY c.id DESC
    LIMIT 100
    """
    return pd.read_sql_query(query, conn)
