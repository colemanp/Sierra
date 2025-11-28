"""Activity tool implementations for MCP server

Token-efficient keys:
  d=date, type=activity_type, dur=duration (minutes), dist=distance (miles)
  pace=min/mile, hr=heart rate, n=count
  last=latest, rng=range, s=start, e=end
  tot=total, avg=average, best=best value
"""
import sqlite3
from pathlib import Path
from typing import Optional

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


def _round0(val: Optional[float]) -> Optional[int]:
    """Round to integer, return None if None"""
    return round(val) if val is not None else None


def get_activity_summary() -> dict:
    """Get quick overview of activity data"""
    conn = _get_conn()
    try:
        # Get latest activity
        last = conn.execute("""
            SELECT a.start_time, t.name as type, a.duration_seconds,
                   a.distance_miles, a.avg_hr
            FROM activities a
            JOIN activity_types t ON a.activity_type_id = t.id
            ORDER BY a.start_time DESC
            LIMIT 1
        """).fetchone()

        if not last:
            return {"err": "No activity data"}

        rng = conn.execute("""
            SELECT MIN(date(start_time)) as s,
                   MAX(date(start_time)) as e,
                   COUNT(*) as n
            FROM activities
        """).fetchone()

        return {
            "last": {
                "d": last["start_time"][:10],
                "type": last["type"],
                "dur": _round0(last["duration_seconds"] / 60) if last["duration_seconds"] else None,
                "dist": _round1(last["distance_miles"]),
                "hr": _round0(last["avg_hr"]),
            },
            "rng": {"s": rng["s"], "e": rng["e"], "n": rng["n"]},
        }
    finally:
        conn.close()


def get_activity_trend(period: str = "week", limit: int = 12) -> dict:
    """Get aggregated activity data by period"""
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
                    strftime('%Y', start_time) || '-Q' ||
                    ((CAST(strftime('%m', start_time) AS INTEGER) - 1) / 3 + 1) as p,
                    COUNT(*) as n,
                    SUM(duration_seconds) as dur,
                    SUM(distance_miles) as dist,
                    AVG(avg_hr) as hr
                FROM activities
                GROUP BY p
                ORDER BY p DESC
                LIMIT ?
            """
        else:
            fmt = period_formats[period]
            query = f"""
                SELECT
                    strftime('{fmt}', start_time) as p,
                    COUNT(*) as n,
                    SUM(duration_seconds) as dur,
                    SUM(distance_miles) as dist,
                    AVG(avg_hr) as hr
                FROM activities
                GROUP BY p
                ORDER BY p DESC
                LIMIT ?
            """

        rows = conn.execute(query, (limit,)).fetchall()

        data = []
        for row in rows:
            data.append({
                "p": row["p"],
                "n": row["n"],
                "dur": _round0(row["dur"] / 60) if row["dur"] else None,
                "dist": _round1(row["dist"]),
                "hr": _round0(row["hr"]),
            })

        return {"d": list(reversed(data))}
    finally:
        conn.close()


def get_activity_records(
    activity_type: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    """Get paginated activity records"""
    conn = _get_conn()
    try:
        conditions = []
        params = []

        if activity_type:
            conditions.append("t.name = ?")
            params.append(activity_type)
        if start_date:
            conditions.append("date(a.start_time) >= ?")
            params.append(start_date)
        if end_date:
            conditions.append("date(a.start_time) <= ?")
            params.append(end_date)

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        count = conn.execute(f"""
            SELECT COUNT(*) FROM activities a
            JOIN activity_types t ON a.activity_type_id = t.id
            {where}
        """, params).fetchone()[0]

        offset = (page - 1) * page_size
        query = f"""
            SELECT a.start_time, t.name as type, a.title,
                   a.duration_seconds, a.distance_miles,
                   a.avg_pace_min_per_mile, a.avg_hr
            FROM activities a
            JOIN activity_types t ON a.activity_type_id = t.id
            {where}
            ORDER BY a.start_time DESC
            LIMIT ? OFFSET ?
        """

        rows = conn.execute(query, params + [page_size, offset]).fetchall()

        records = []
        for row in rows:
            rec = {
                "d": row["start_time"][:10],
                "type": row["type"],
            }
            if row["title"]:
                rec["title"] = row["title"]
            if row["duration_seconds"]:
                rec["dur"] = _round0(row["duration_seconds"] / 60)
            if row["distance_miles"]:
                rec["dist"] = _round1(row["distance_miles"])
            if row["avg_pace_min_per_mile"]:
                rec["pace"] = _round1(row["avg_pace_min_per_mile"])
            if row["avg_hr"]:
                rec["hr"] = _round0(row["avg_hr"])
            records.append(rec)

        pgs = (count + page_size - 1) // page_size if count > 0 else 0

        return {"r": records, "pg": page, "pgs": pgs, "n": count}
    finally:
        conn.close()


def get_activity_stats(
    activity_type: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> dict:
    """Get statistical summary of activities"""
    conn = _get_conn()
    try:
        conditions = []
        params = []

        if activity_type:
            conditions.append("t.name = ?")
            params.append(activity_type)
        if start_date:
            conditions.append("date(a.start_time) >= ?")
            params.append(start_date)
        if end_date:
            conditions.append("date(a.start_time) <= ?")
            params.append(end_date)

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        row = conn.execute(f"""
            SELECT COUNT(*) as n,
                   SUM(a.duration_seconds) as dur_tot,
                   AVG(a.duration_seconds) as dur_avg,
                   SUM(a.distance_miles) as dist_tot,
                   AVG(a.distance_miles) as dist_avg,
                   AVG(a.avg_pace_min_per_mile) as pace_avg,
                   MIN(a.best_pace_min_per_mile) as pace_best,
                   AVG(a.avg_hr) as hr_avg,
                   MAX(a.max_hr) as hr_max
            FROM activities a
            JOIN activity_types t ON a.activity_type_id = t.id
            {where}
        """, params).fetchone()

        if not row or row["n"] == 0:
            return {"err": "No data in range"}

        result = {"n": row["n"]}

        if row["dur_tot"]:
            result["dur"] = {
                "tot": _round0(row["dur_tot"] / 60),
                "avg": _round0(row["dur_avg"] / 60),
            }

        if row["dist_tot"]:
            result["dist"] = {
                "tot": _round1(row["dist_tot"]),
                "avg": _round1(row["dist_avg"]),
            }

        if row["pace_avg"]:
            result["pace"] = {"avg": _round1(row["pace_avg"])}
            if row["pace_best"]:
                result["pace"]["best"] = _round1(row["pace_best"])

        if row["hr_avg"]:
            result["hr"] = {"avg": _round0(row["hr_avg"])}
            if row["hr_max"]:
                result["hr"]["max"] = _round0(row["hr_max"])

        return result
    finally:
        conn.close()


def get_activity_compare(
    period1_start: str,
    period1_end: str,
    period2_start: str,
    period2_end: str,
) -> dict:
    """Compare two time periods"""
    conn = _get_conn()
    try:

        def get_period_stats(start: str, end: str) -> dict:
            row = conn.execute("""
                SELECT COUNT(*) as n,
                       SUM(distance_miles) as dist,
                       SUM(duration_seconds) as dur,
                       AVG(avg_hr) as hr
                FROM activities
                WHERE date(start_time) >= ? AND date(start_time) <= ?
            """, (start, end)).fetchone()

            return {
                "n": row["n"] or 0,
                "dist": _round1(row["dist"]) if row["dist"] else 0,
                "dur": _round0(row["dur"] / 60) if row["dur"] else 0,
                "hr": _round0(row["hr"]) if row["hr"] else None,
            }

        p1 = get_period_stats(period1_start, period1_end)
        p2 = get_period_stats(period2_start, period2_end)

        delta = {
            "n": p2["n"] - p1["n"],
            "dist": _round1(p2["dist"] - p1["dist"]) if p2["dist"] and p1["dist"] else None,
            "dur": _round0(p2["dur"] - p1["dur"]) if p2["dur"] and p1["dur"] else None,
        }
        if p1["hr"] and p2["hr"]:
            delta["hr"] = _round0(p2["hr"] - p1["hr"])

        return {
            "p1": {"rng": f"{period1_start}/{period1_end}", **p1},
            "p2": {"rng": f"{period2_start}/{period2_end}", **p2},
            "d": delta,
        }
    finally:
        conn.close()
