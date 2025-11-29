"""Resting Heart Rate tool implementations for MCP server

Token-efficient keys:
  d=date, hr=heart rate (bpm), n=count
  cur=current/latest, rng=range, s=start, e=end
  avg=average, min=minimum, max=maximum, std=std deviation
"""
import sqlite3
from pathlib import Path
from typing import Optional
import statistics

# Database paths
DB_PATHS = {
    "prod": Path(__file__).parent.parent.parent / "data" / "prod" / "health_data.db",
    "test": Path(__file__).parent.parent.parent / "data" / "test" / "health_data.db",
}
# Default to test DB
DB_PATH = DB_PATHS["test"]


def _get_conn() -> sqlite3.Connection:
    """Get database connection"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _round0(val: Optional[float]) -> Optional[int]:
    """Round to integer, return None if None"""
    return round(val) if val is not None else None


def get_rhr_summary() -> dict:
    """Get quick overview of resting heart rate data"""
    conn = _get_conn()
    try:
        cur = conn.execute("""
            SELECT measurement_date, resting_hr
            FROM resting_heart_rate
            ORDER BY measurement_date DESC
            LIMIT 1
        """).fetchone()

        if not cur:
            return {"err": "No resting HR data"}

        rng = conn.execute("""
            SELECT MIN(measurement_date) as s,
                   MAX(measurement_date) as e,
                   COUNT(*) as n
            FROM resting_heart_rate
        """).fetchone()

        return {
            "cur": {
                "d": cur["measurement_date"],
                "hr": cur["resting_hr"],
            },
            "rng": {"s": rng["s"], "e": rng["e"], "n": rng["n"]},
        }
    finally:
        conn.close()


def get_rhr_trend(period: str = "month", limit: int = 12) -> dict:
    """Get aggregated resting HR data by period"""
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

        if period == "quarter":
            query = """
                SELECT
                    strftime('%Y', measurement_date) || '-Q' ||
                    ((CAST(strftime('%m', measurement_date) AS INTEGER) - 1) / 3 + 1) as p,
                    COUNT(*) as n,
                    AVG(resting_hr) as avg_hr,
                    MIN(resting_hr) as min_hr,
                    MAX(resting_hr) as max_hr
                FROM resting_heart_rate
                GROUP BY p
                ORDER BY p DESC
                LIMIT ?
            """
        else:
            fmt = period_formats[period]
            query = f"""
                SELECT
                    strftime('{fmt}', measurement_date) as p,
                    COUNT(*) as n,
                    AVG(resting_hr) as avg_hr,
                    MIN(resting_hr) as min_hr,
                    MAX(resting_hr) as max_hr
                FROM resting_heart_rate
                GROUP BY p
                ORDER BY p DESC
                LIMIT ?
            """

        rows = conn.execute(query, (limit,)).fetchall()

        data = []
        for row in rows:
            data.append({
                "p": row["p"],
                "avg": _round0(row["avg_hr"]),
                "min": row["min_hr"],
                "max": row["max_hr"],
                "n": row["n"],
            })

        return {"d": list(reversed(data))}
    finally:
        conn.close()


def get_rhr_records(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    page: int = 1,
    page_size: int = 30,
) -> dict:
    """Get paginated resting HR records"""
    conn = _get_conn()
    try:
        conditions = []
        params = []

        if start_date:
            conditions.append("measurement_date >= ?")
            params.append(start_date)
        if end_date:
            conditions.append("measurement_date <= ?")
            params.append(end_date)

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        count = conn.execute(f"""
            SELECT COUNT(*) FROM resting_heart_rate
            {where}
        """, params).fetchone()[0]

        offset = (page - 1) * page_size
        query = f"""
            SELECT measurement_date, resting_hr
            FROM resting_heart_rate
            {where}
            ORDER BY measurement_date DESC
            LIMIT ? OFFSET ?
        """

        rows = conn.execute(query, params + [page_size, offset]).fetchall()

        records = []
        for row in rows:
            records.append({
                "d": row["measurement_date"],
                "hr": row["resting_hr"],
            })

        pgs = (count + page_size - 1) // page_size if count > 0 else 0

        return {"r": records, "pg": page, "pgs": pgs, "n": count}
    finally:
        conn.close()


def get_rhr_stats(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> dict:
    """Get statistical summary of resting heart rate"""
    conn = _get_conn()
    try:
        conditions = []
        params = []

        if start_date:
            conditions.append("measurement_date >= ?")
            params.append(start_date)
        if end_date:
            conditions.append("measurement_date <= ?")
            params.append(end_date)

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        row = conn.execute(f"""
            SELECT COUNT(*) as n,
                   AVG(resting_hr) as avg_hr,
                   MIN(resting_hr) as min_hr,
                   MAX(resting_hr) as max_hr
            FROM resting_heart_rate
            {where}
        """, params).fetchone()

        if not row or row["n"] == 0:
            return {"err": "No data in range"}

        # Get all values for std dev calculation
        values = conn.execute(f"""
            SELECT resting_hr FROM resting_heart_rate {where}
        """, params).fetchall()
        hr_values = [v["resting_hr"] for v in values]
        std = statistics.stdev(hr_values) if len(hr_values) > 1 else 0

        return {
            "n": row["n"],
            "avg": _round0(row["avg_hr"]),
            "min": row["min_hr"],
            "max": row["max_hr"],
            "std": _round0(std),
        }
    finally:
        conn.close()
