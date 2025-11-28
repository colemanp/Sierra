"""Weight tool implementations for MCP server

Token-efficient keys:
  d=date, t=time, wt=weight, fat=body_fat, m=muscle, b=bone, w=water
  cur=current/latest, rng=range, s=start, e=end, n=count
  r=records, pg=page, pgs=pages
  avg=mean, med=median, chg=change
  per=period, p1/p2=period1/period2
"""
import sqlite3
from pathlib import Path
from datetime import datetime
from typing import Optional
import statistics

# Database paths
DB_PATHS = {
    "prod": Path(__file__).parent.parent.parent / "data" / "prod" / "health_data.db",
    "test": Path(__file__).parent.parent.parent / "data" / "test" / "health_data.db",
}
# Default to test DB (prod is empty currently)
DB_PATH = DB_PATHS["test"]


def _get_conn() -> sqlite3.Connection:
    """Get database connection"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _round1(val: Optional[float]) -> Optional[float]:
    """Round to 1 decimal, return None if None"""
    return round(val, 1) if val is not None else None


def get_weight_summary() -> dict:
    """Get quick overview of weight data"""
    conn = _get_conn()
    try:
        cur = conn.execute("""
            SELECT measurement_date, weight_lbs, body_fat_pct, muscle_mass_lbs
            FROM body_measurements
            ORDER BY measurement_date DESC, measurement_time DESC
            LIMIT 1
        """).fetchone()

        rng = conn.execute("""
            SELECT MIN(measurement_date) as s,
                   MAX(measurement_date) as e,
                   COUNT(*) as n
            FROM body_measurements
        """).fetchone()

        if not cur:
            return {"err": "No weight data"}

        return {
            "cur": {
                "d": cur["measurement_date"],
                "wt": _round1(cur["weight_lbs"]),
                "fat": _round1(cur["body_fat_pct"]),
                "m": _round1(cur["muscle_mass_lbs"]),
            },
            "rng": {"s": rng["s"], "e": rng["e"], "n": rng["n"]},
        }
    finally:
        conn.close()


def get_weight_trend(period: str = "month", limit: int = 12) -> dict:
    """Get aggregated weight data by period"""
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
                    AVG(weight_lbs) as avg,
                    MIN(weight_lbs) as min,
                    MAX(weight_lbs) as max,
                    AVG(body_fat_pct) as fat,
                    AVG(muscle_mass_lbs) as m
                FROM body_measurements
                GROUP BY p
                ORDER BY p DESC
                LIMIT ?
            """
        else:
            fmt = period_formats[period]
            query = f"""
                SELECT
                    strftime('{fmt}', measurement_date) as p,
                    AVG(weight_lbs) as avg,
                    MIN(weight_lbs) as min,
                    MAX(weight_lbs) as max,
                    AVG(body_fat_pct) as fat,
                    AVG(muscle_mass_lbs) as m
                FROM body_measurements
                GROUP BY p
                ORDER BY p DESC
                LIMIT ?
            """

        rows = conn.execute(query, (limit,)).fetchall()

        data = []
        for row in rows:
            data.append({
                "p": row["p"],
                "avg": _round1(row["avg"]),
                "min": _round1(row["min"]),
                "max": _round1(row["max"]),
                "fat": _round1(row["fat"]),
                "m": _round1(row["m"]),
            })

        return {"d": list(reversed(data))}
    finally:
        conn.close()


def get_weight_records(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    page: int = 1,
    page_size: int = 50,
) -> dict:
    """Get paginated raw weight records"""
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

        count = conn.execute(
            f"SELECT COUNT(*) FROM body_measurements {where}", params
        ).fetchone()[0]

        offset = (page - 1) * page_size
        query = f"""
            SELECT measurement_date, measurement_time,
                   weight_lbs, body_fat_pct,
                   muscle_mass_lbs, bone_mass_lbs, body_water_pct
            FROM body_measurements
            {where}
            ORDER BY measurement_date DESC, measurement_time DESC
            LIMIT ? OFFSET ?
        """

        rows = conn.execute(query, params + [page_size, offset]).fetchall()

        records = []
        for row in rows:
            rec = {"d": row["measurement_date"]}
            if row["measurement_time"]:
                rec["t"] = row["measurement_time"]
            if row["weight_lbs"]:
                rec["wt"] = _round1(row["weight_lbs"])
            if row["body_fat_pct"]:
                rec["fat"] = _round1(row["body_fat_pct"])
            if row["muscle_mass_lbs"]:
                rec["m"] = _round1(row["muscle_mass_lbs"])
            if row["bone_mass_lbs"]:
                rec["b"] = _round1(row["bone_mass_lbs"])
            if row["body_water_pct"]:
                rec["w"] = _round1(row["body_water_pct"])
            records.append(rec)

        pgs = (count + page_size - 1) // page_size if count > 0 else 0

        return {"r": records, "pg": page, "pgs": pgs, "n": count}
    finally:
        conn.close()


def get_weight_stats(
    start_date: Optional[str] = None, end_date: Optional[str] = None
) -> dict:
    """Get statistical summary of weight data"""
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

        query = f"""
            SELECT weight_lbs, body_fat_pct, measurement_date
            FROM body_measurements
            {where}
            ORDER BY measurement_date, measurement_time
        """
        rows = conn.execute(query, params).fetchall()

        if not rows:
            return {"err": "No data in range"}

        weights = [r["weight_lbs"] for r in rows if r["weight_lbs"]]
        fats = [r["body_fat_pct"] for r in rows if r["body_fat_pct"]]

        result = {}

        if weights:
            sorted_wt = sorted(weights)
            result["wt"] = {
                "avg": _round1(statistics.mean(weights)),
                "med": _round1(statistics.median(weights)),
                "std": _round1(statistics.stdev(weights)) if len(weights) > 1 else 0,
                "p25": _round1(sorted_wt[len(sorted_wt) // 4]),
                "p75": _round1(sorted_wt[3 * len(sorted_wt) // 4]),
            }

        if fats:
            sorted_fat = sorted(fats)
            result["fat"] = {
                "avg": _round1(statistics.mean(fats)),
                "med": _round1(statistics.median(fats)),
                "std": _round1(statistics.stdev(fats)) if len(fats) > 1 else 0,
                "p25": _round1(sorted_fat[len(sorted_fat) // 4]),
                "p75": _round1(sorted_fat[3 * len(sorted_fat) // 4]),
            }

        first_wt = next((r["weight_lbs"] for r in rows if r["weight_lbs"]), None)
        last_wt = next(
            (r["weight_lbs"] for r in reversed(rows) if r["weight_lbs"]), None
        )
        first_fat = next((r["body_fat_pct"] for r in rows if r["body_fat_pct"]), None)
        last_fat = next(
            (r["body_fat_pct"] for r in reversed(rows) if r["body_fat_pct"]), None
        )

        result["chg"] = {}
        if first_wt and last_wt:
            result["chg"]["wt"] = _round1(last_wt - first_wt)
        if first_fat and last_fat:
            result["chg"]["fat"] = _round1(last_fat - first_fat)

        return result
    finally:
        conn.close()


def get_weight_compare(
    period1_start: str,
    period1_end: str,
    period2_start: str,
    period2_end: str,
) -> dict:
    """Compare two time periods"""
    conn = _get_conn()
    try:

        def get_period_stats(start: str, end: str) -> dict:
            rows = conn.execute(
                """
                SELECT AVG(weight_lbs) as avg_wt, AVG(body_fat_pct) as avg_fat,
                       MIN(weight_lbs) as min_wt, MAX(weight_lbs) as max_wt,
                       COUNT(*) as n
                FROM body_measurements
                WHERE measurement_date >= ? AND measurement_date <= ?
            """,
                (start, end),
            ).fetchone()

            return {
                "avg": _round1(rows["avg_wt"]),
                "fat": _round1(rows["avg_fat"]),
                "min": _round1(rows["min_wt"]),
                "max": _round1(rows["max_wt"]),
                "n": rows["n"],
            }

        p1 = get_period_stats(period1_start, period1_end)
        p2 = get_period_stats(period2_start, period2_end)

        delta = {}
        if p1["avg"] and p2["avg"]:
            delta["wt"] = _round1(p2["avg"] - p1["avg"])
        if p1["fat"] and p2["fat"]:
            delta["fat"] = _round1(p2["fat"] - p1["fat"])

        return {
            "p1": {"rng": f"{period1_start}/{period1_end}", **p1},
            "p2": {"rng": f"{period2_start}/{period2_end}", **p2},
            "d": delta,
        }
    finally:
        conn.close()
