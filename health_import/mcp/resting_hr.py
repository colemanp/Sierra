"""Resting Heart Rate tool implementations for MCP server

Token-efficient keys:
  d=date, hr=heart rate (bpm), n=count
  cur=current/latest, rng=range, s=start, e=end
  avg=average, min=minimum, max=maximum, std=std deviation, chg=change
  hidden=excluded from queries
"""
import sqlite3
from typing import Optional
import statistics

from health_import.mcp.config import DB_PATH


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
            WHERE hidden = 0 OR hidden IS NULL
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
            WHERE hidden = 0 OR hidden IS NULL
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
                WHERE hidden = 0 OR hidden IS NULL
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
                WHERE hidden = 0 OR hidden IS NULL
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
        conditions = ["(hidden = 0 OR hidden IS NULL)"]
        params = []

        if start_date:
            conditions.append("measurement_date >= ?")
            params.append(start_date)
        if end_date:
            conditions.append("measurement_date <= ?")
            params.append(end_date)

        where = f"WHERE {' AND '.join(conditions)}"

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
        conditions = ["(hidden = 0 OR hidden IS NULL)"]
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

        # Get first and last readings for change calculation
        first = conn.execute(f"""
            SELECT resting_hr FROM resting_heart_rate {where}
            ORDER BY measurement_date ASC LIMIT 1
        """, params).fetchone()
        last = conn.execute(f"""
            SELECT resting_hr FROM resting_heart_rate {where}
            ORDER BY measurement_date DESC LIMIT 1
        """, params).fetchone()

        result = {
            "n": row["n"],
            "avg": _round0(row["avg_hr"]),
            "min": row["min_hr"],
            "max": row["max_hr"],
            "std": _round0(std),
        }

        if first and last and row["n"] > 1:
            result["chg"] = last["resting_hr"] - first["resting_hr"]

        return result
    finally:
        conn.close()


def get_rhr_compare(
    period1_start: str,
    period1_end: str,
    period2_start: str,
    period2_end: str,
) -> dict:
    """Compare resting heart rate between two periods"""
    conn = _get_conn()
    try:
        def get_period_stats(start: str, end: str) -> dict:
            row = conn.execute("""
                SELECT COUNT(*) as n,
                       AVG(resting_hr) as avg_hr,
                       MIN(resting_hr) as min_hr,
                       MAX(resting_hr) as max_hr
                FROM resting_heart_rate
                WHERE (hidden = 0 OR hidden IS NULL)
                  AND measurement_date >= ? AND measurement_date <= ?
            """, (start, end)).fetchone()

            if not row or row["n"] == 0:
                return None

            return {
                "rng": f"{start}/{end}",
                "avg": _round0(row["avg_hr"]),
                "min": row["min_hr"],
                "max": row["max_hr"],
                "n": row["n"],
            }

        p1 = get_period_stats(period1_start, period1_end)
        p2 = get_period_stats(period2_start, period2_end)

        if not p1 or not p2:
            return {"err": "No data in one or both periods"}

        return {
            "p1": p1,
            "p2": p2,
            "d": {
                "avg": p2["avg"] - p1["avg"],
                "min": p2["min"] - p1["min"],
                "max": p2["max"] - p1["max"],
            },
        }
    finally:
        conn.close()


def hide_rhr_record(date: str, hidden: bool = True) -> dict:
    """Hide or unhide a resting heart rate record by date"""
    conn = _get_conn()
    try:
        # Check if record exists
        row = conn.execute("""
            SELECT id, resting_hr, hidden
            FROM resting_heart_rate
            WHERE measurement_date = ?
        """, (date,)).fetchone()

        if not row:
            return {"err": f"No RHR record found for {date}"}

        hidden_val = 1 if hidden else 0
        conn.execute("""
            UPDATE resting_heart_rate
            SET hidden = ?
            WHERE measurement_date = ?
        """, (hidden_val, date))
        conn.commit()

        action = "hidden" if hidden else "unhidden"
        return {
            "ok": True,
            "d": date,
            "hr": row["resting_hr"],
            "action": action,
        }
    finally:
        conn.close()


def hide_rhr_above(hr: int) -> dict:
    """Hide all resting heart rate records above a threshold"""
    conn = _get_conn()
    try:
        # Find records to hide
        rows = conn.execute("""
            SELECT measurement_date, resting_hr
            FROM resting_heart_rate
            WHERE resting_hr > ? AND (hidden = 0 OR hidden IS NULL)
            ORDER BY resting_hr DESC
        """, (hr,)).fetchall()

        if not rows:
            return {"ok": True, "n": 0, "msg": f"No visible records above {hr} bpm"}

        # Hide them
        conn.execute("""
            UPDATE resting_heart_rate
            SET hidden = 1
            WHERE resting_hr > ? AND (hidden = 0 OR hidden IS NULL)
        """, (hr,))
        conn.commit()

        # Return summary
        hidden_hrs = [r["resting_hr"] for r in rows]
        return {
            "ok": True,
            "n": len(rows),
            "threshold": hr,
            "range": {"min": min(hidden_hrs), "max": max(hidden_hrs)},
        }
    finally:
        conn.close()


def hide_rhr_below(hr: int) -> dict:
    """Hide all resting heart rate records below a threshold"""
    conn = _get_conn()
    try:
        # Find records to hide
        rows = conn.execute("""
            SELECT measurement_date, resting_hr
            FROM resting_heart_rate
            WHERE resting_hr < ? AND (hidden = 0 OR hidden IS NULL)
            ORDER BY resting_hr ASC
        """, (hr,)).fetchall()

        if not rows:
            return {"ok": True, "n": 0, "msg": f"No visible records below {hr} bpm"}

        # Hide them
        conn.execute("""
            UPDATE resting_heart_rate
            SET hidden = 1
            WHERE resting_hr < ? AND (hidden = 0 OR hidden IS NULL)
        """, (hr,))
        conn.commit()

        # Return summary
        hidden_hrs = [r["resting_hr"] for r in rows]
        return {
            "ok": True,
            "n": len(rows),
            "threshold": hr,
            "range": {"min": min(hidden_hrs), "max": max(hidden_hrs)},
        }
    finally:
        conn.close()
