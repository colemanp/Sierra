"""VO2 Max tool implementations for MCP server

Token-efficient keys:
  d=date, vo2=VO2 Max (ml/kg/min), n=count
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


def _round1(val: Optional[float]) -> Optional[float]:
    """Round to 1 decimal, return None if None"""
    return round(val, 1) if val is not None else None


def get_vo2max_summary() -> dict:
    """Get quick overview of VO2 Max data (running only)"""
    conn = _get_conn()
    try:
        cur = conn.execute("""
            SELECT measurement_date, vo2max_value
            FROM garmin_vo2max
            WHERE activity_type = 'running'
            ORDER BY measurement_date DESC
            LIMIT 1
        """).fetchone()

        if not cur:
            return {"err": "No VO2 Max data"}

        rng = conn.execute("""
            SELECT MIN(measurement_date) as s,
                   MAX(measurement_date) as e,
                   COUNT(*) as n
            FROM garmin_vo2max
            WHERE activity_type = 'running'
        """).fetchone()

        return {
            "cur": {
                "d": cur["measurement_date"],
                "vo2": _round1(cur["vo2max_value"]),
            },
            "rng": {"s": rng["s"], "e": rng["e"], "n": rng["n"]},
        }
    finally:
        conn.close()


def get_vo2max_trend(period: str = "month", limit: int = 12) -> dict:
    """Get aggregated VO2 Max data by period (running only)"""
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
                    AVG(vo2max_value) as avg_vo2,
                    MIN(vo2max_value) as min_vo2,
                    MAX(vo2max_value) as max_vo2
                FROM garmin_vo2max
                WHERE activity_type = 'running'
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
                    AVG(vo2max_value) as avg_vo2,
                    MIN(vo2max_value) as min_vo2,
                    MAX(vo2max_value) as max_vo2
                FROM garmin_vo2max
                WHERE activity_type = 'running'
                GROUP BY p
                ORDER BY p DESC
                LIMIT ?
            """

        rows = conn.execute(query, (limit,)).fetchall()

        data = []
        for row in rows:
            data.append({
                "p": row["p"],
                "avg": _round1(row["avg_vo2"]),
                "min": _round1(row["min_vo2"]),
                "max": _round1(row["max_vo2"]),
                "n": row["n"],
            })

        return {"d": list(reversed(data))}
    finally:
        conn.close()


def get_vo2max_records(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    page: int = 1,
    page_size: int = 30,
) -> dict:
    """Get paginated VO2 Max records (running only)"""
    conn = _get_conn()
    try:
        conditions = ["activity_type = 'running'"]
        params = []

        if start_date:
            conditions.append("measurement_date >= ?")
            params.append(start_date)
        if end_date:
            conditions.append("measurement_date <= ?")
            params.append(end_date)

        where = f"WHERE {' AND '.join(conditions)}"

        count = conn.execute(f"""
            SELECT COUNT(*) FROM garmin_vo2max
            {where}
        """, params).fetchone()[0]

        offset = (page - 1) * page_size
        query = f"""
            SELECT measurement_date, vo2max_value
            FROM garmin_vo2max
            {where}
            ORDER BY measurement_date DESC
            LIMIT ? OFFSET ?
        """

        rows = conn.execute(query, params + [page_size, offset]).fetchall()

        records = []
        for row in rows:
            records.append({
                "d": row["measurement_date"],
                "vo2": _round1(row["vo2max_value"]),
            })

        pgs = (count + page_size - 1) // page_size if count > 0 else 0

        return {"r": records, "pg": page, "pgs": pgs, "n": count}
    finally:
        conn.close()


def get_vo2max_stats(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> dict:
    """Get statistical summary of VO2 Max (running only)"""
    conn = _get_conn()
    try:
        conditions = ["activity_type = 'running'"]
        params = []

        if start_date:
            conditions.append("measurement_date >= ?")
            params.append(start_date)
        if end_date:
            conditions.append("measurement_date <= ?")
            params.append(end_date)

        where = f"WHERE {' AND '.join(conditions)}"

        row = conn.execute(f"""
            SELECT COUNT(*) as n,
                   AVG(vo2max_value) as avg_vo2,
                   MIN(vo2max_value) as min_vo2,
                   MAX(vo2max_value) as max_vo2
            FROM garmin_vo2max
            {where}
        """, params).fetchone()

        if not row or row["n"] == 0:
            return {"err": "No data in range"}

        # Get all values for std dev calculation
        values = conn.execute(f"""
            SELECT vo2max_value FROM garmin_vo2max {where}
        """, params).fetchall()
        vo2_values = [v["vo2max_value"] for v in values]
        std = statistics.stdev(vo2_values) if len(vo2_values) > 1 else 0

        return {
            "n": row["n"],
            "avg": _round1(row["avg_vo2"]),
            "min": _round1(row["min_vo2"]),
            "max": _round1(row["max_vo2"]),
            "std": _round1(std),
        }
    finally:
        conn.close()
