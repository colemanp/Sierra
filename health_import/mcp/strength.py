"""Strength training tool implementations for MCP server

Token-efficient keys:
  d=date, t=time, ex=exercise, cat=category
  s=sets (array), tot=total, cal=calories
  n=count, exs=exercises count or list
  rng=range, s=start, e=end
  avg=average, max=maximum, sum=sum
"""
import sqlite3
from typing import Optional

from health_import.mcp.config import DB_PATH


def _get_conn() -> sqlite3.Connection:
    """Get database connection"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _round1(val: Optional[float]) -> Optional[float]:
    """Round to 1 decimal, return None if None"""
    return round(val, 1) if val is not None else None


def get_strength_summary() -> dict:
    """Get quick overview of strength training data"""
    conn = _get_conn()
    try:
        # Latest workout
        last = conn.execute("""
            SELECT w.workout_date, e.display_name, w.total_value
            FROM strength_workouts w
            JOIN strength_exercises e ON w.exercise_id = e.id
            ORDER BY w.workout_date DESC, w.workout_time DESC
            LIMIT 1
        """).fetchone()

        if not last:
            return {"err": "No strength data"}

        # Range and count
        rng = conn.execute("""
            SELECT MIN(workout_date) as s,
                   MAX(workout_date) as e,
                   COUNT(*) as n
            FROM strength_workouts
        """).fetchone()

        # Unique exercises
        ex_count = conn.execute("""
            SELECT COUNT(DISTINCT exercise_id) as n
            FROM strength_workouts
        """).fetchone()

        return {
            "last": {
                "d": last["workout_date"],
                "ex": last["display_name"],
                "tot": _round1(last["total_value"]),
            },
            "rng": {"s": rng["s"], "e": rng["e"], "n": rng["n"]},
            "ex": ex_count["n"],
        }
    finally:
        conn.close()


def get_strength_trend(
    period: str = "month",
    limit: int = 12,
    exercise: Optional[str] = None,
) -> dict:
    """Get aggregated strength data by period"""
    conn = _get_conn()
    try:
        period_formats = {
            "week": "%Y-W%W",
            "month": "%Y-%m",
            "quarter": None,
            "year": "%Y",
        }

        if period not in period_formats:
            return {"err": f"Invalid period: {period}. Use week/month/quarter/year"}

        conditions = []
        params = []

        if exercise:
            conditions.append("e.display_name = ?")
            params.append(exercise)

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        if period == "quarter":
            query = f"""
                SELECT
                    strftime('%Y', w.workout_date) || '-Q' ||
                    ((CAST(strftime('%m', w.workout_date) AS INTEGER) - 1) / 3 + 1) as p,
                    COUNT(*) as n,
                    SUM(w.total_value) as tot,
                    COUNT(DISTINCT w.exercise_id) as exs
                FROM strength_workouts w
                JOIN strength_exercises e ON w.exercise_id = e.id
                {where}
                GROUP BY p
                ORDER BY p DESC
                LIMIT ?
            """
        else:
            fmt = period_formats[period]
            query = f"""
                SELECT
                    strftime('{fmt}', w.workout_date) as p,
                    COUNT(*) as n,
                    SUM(w.total_value) as tot,
                    COUNT(DISTINCT w.exercise_id) as exs
                FROM strength_workouts w
                JOIN strength_exercises e ON w.exercise_id = e.id
                {where}
                GROUP BY p
                ORDER BY p DESC
                LIMIT ?
            """

        rows = conn.execute(query, params + [limit]).fetchall()

        data = []
        for row in rows:
            data.append({
                "p": row["p"],
                "n": row["n"],
                "tot": _round1(row["tot"]),
                "exs": row["exs"],
            })

        return {"d": list(reversed(data))}
    finally:
        conn.close()


def get_strength_records(
    exercise: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    """Get paginated strength workout records"""
    conn = _get_conn()
    try:
        conditions = []
        params = []

        if exercise:
            conditions.append("e.display_name = ?")
            params.append(exercise)
        if start_date:
            conditions.append("w.workout_date >= ?")
            params.append(start_date)
        if end_date:
            conditions.append("w.workout_date <= ?")
            params.append(end_date)

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        count = conn.execute(f"""
            SELECT COUNT(*) FROM strength_workouts w
            JOIN strength_exercises e ON w.exercise_id = e.id
            {where}
        """, params).fetchone()[0]

        offset = (page - 1) * page_size
        query = f"""
            SELECT w.workout_date, w.workout_time, e.display_name, e.unit,
                   w.set1, w.set2, w.set3, w.set4, w.set5,
                   w.total_value, w.calories
            FROM strength_workouts w
            JOIN strength_exercises e ON w.exercise_id = e.id
            {where}
            ORDER BY w.workout_date DESC, w.workout_time DESC
            LIMIT ? OFFSET ?
        """

        rows = conn.execute(query, params + [page_size, offset]).fetchall()

        records = []
        for row in rows:
            # Build sets array (only non-null values)
            sets = []
            for i in range(1, 6):
                val = row[f"set{i}"]
                if val is not None:
                    sets.append(_round1(val))

            unit = row["unit"] or "reps"
            rec = {
                "d": row["workout_date"],
                "ex": row["display_name"],
                "tot": _round1(row["total_value"]),
            }
            # Only include unit if not default "reps"
            if unit != "reps":
                rec["unit"] = unit
            if row["workout_time"]:
                rec["t"] = row["workout_time"][:5]  # HH:MM
            if sets:
                rec["s"] = sets
            if row["calories"]:
                rec["cal"] = row["calories"]

            records.append(rec)

        pgs = (count + page_size - 1) // page_size if count > 0 else 0

        return {"r": records, "pg": page, "pgs": pgs, "n": count}
    finally:
        conn.close()


def get_strength_stats(
    exercise: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> dict:
    """Get statistical summary of strength training"""
    conn = _get_conn()
    try:
        conditions = []
        params = []

        if exercise:
            conditions.append("e.display_name = ?")
            params.append(exercise)
        if start_date:
            conditions.append("w.workout_date >= ?")
            params.append(start_date)
        if end_date:
            conditions.append("w.workout_date <= ?")
            params.append(end_date)

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        # Overall stats
        row = conn.execute(f"""
            SELECT COUNT(*) as n,
                   SUM(w.total_value) as sum_tot,
                   AVG(w.total_value) as avg_tot
            FROM strength_workouts w
            JOIN strength_exercises e ON w.exercise_id = e.id
            {where}
        """, params).fetchone()

        if not row or row["n"] == 0:
            return {"err": "No data in range"}

        # Per-exercise breakdown (top 10)
        exs = conn.execute(f"""
            SELECT e.display_name,
                   COUNT(*) as n,
                   AVG(w.total_value) as avg,
                   MAX(w.total_value) as max
            FROM strength_workouts w
            JOIN strength_exercises e ON w.exercise_id = e.id
            {where}
            GROUP BY e.id
            ORDER BY n DESC
            LIMIT 10
        """, params).fetchall()

        ex_list = []
        for ex in exs:
            ex_list.append({
                "ex": ex["display_name"],
                "n": ex["n"],
                "avg": _round1(ex["avg"]),
                "max": _round1(ex["max"]),
            })

        return {
            "n": row["n"],
            "tot": {
                "sum": _round1(row["sum_tot"]),
                "avg": _round1(row["avg_tot"]),
            },
            "exs": ex_list,
        }
    finally:
        conn.close()


def get_strength_exercises() -> dict:
    """Get list of all exercises with workout counts"""
    conn = _get_conn()
    try:
        rows = conn.execute("""
            SELECT e.id, e.display_name, e.category, e.unit,
                   COUNT(w.id) as n
            FROM strength_exercises e
            LEFT JOIN strength_workouts w ON e.id = w.exercise_id
            GROUP BY e.id
            HAVING n > 0
            ORDER BY n DESC
        """).fetchall()

        exercises = []
        for row in rows:
            ex = {
                "id": row["id"],
                "name": row["display_name"],
                "n": row["n"],
                "unit": row["unit"] or "reps",
            }
            if row["category"]:
                ex["cat"] = row["category"]
            exercises.append(ex)

        return {"ex": exercises}
    finally:
        conn.close()


def get_strength_compare(
    period1_start: str,
    period1_end: str,
    period2_start: str,
    period2_end: str,
) -> dict:
    """Compare strength training between two periods"""
    conn = _get_conn()
    try:
        def get_period_stats(start: str, end: str) -> dict:
            row = conn.execute("""
                SELECT COUNT(*) as n,
                       SUM(total_value) as sum_tot,
                       COUNT(DISTINCT exercise_id) as exs
                FROM strength_workouts
                WHERE workout_date >= ? AND workout_date <= ?
            """, (start, end)).fetchone()

            if not row or row["n"] == 0:
                return None

            return {
                "rng": f"{start}/{end}",
                "n": row["n"],
                "tot": _round1(row["sum_tot"]),
                "exs": row["exs"],
            }

        p1 = get_period_stats(period1_start, period1_end)
        p2 = get_period_stats(period2_start, period2_end)

        if not p1 or not p2:
            return {"err": "No data in one or both periods"}

        return {
            "p1": p1,
            "p2": p2,
            "d": {
                "n": p2["n"] - p1["n"],
                "tot": _round1(p2["tot"] - p1["tot"]),
            },
        }
    finally:
        conn.close()
