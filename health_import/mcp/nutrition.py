"""Nutrition tool implementations for MCP server

Token-efficient keys:
  d=date, t=time, cal=calories, p=protein, f=fat, c=carbs
  cur=current, rng=range, s=start, e=end, n=count
  tot=total, items=food items
  avg=mean, med=median, std=standard deviation
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


def get_nutrition_summary() -> dict:
    """Get quick overview of nutrition data"""
    conn = _get_conn()
    try:
        # Get latest day's totals
        latest_date = conn.execute("""
            SELECT date FROM nutrition_entries
            ORDER BY date DESC LIMIT 1
        """).fetchone()

        if not latest_date:
            return {"err": "No nutrition data"}

        date = latest_date["date"]
        cur = conn.execute("""
            SELECT SUM(calories_kcal) as cal,
                   SUM(protein_g) as p,
                   SUM(fat_g) as f,
                   SUM(carbs_g) as c
            FROM nutrition_entries
            WHERE date = ?
        """, (date,)).fetchone()

        rng = conn.execute("""
            SELECT MIN(date) as s,
                   MAX(date) as e,
                   COUNT(*) as n
            FROM nutrition_entries
        """).fetchone()

        return {
            "cur": {
                "d": date,
                "cal": _round0(cur["cal"]),
                "p": _round0(cur["p"]),
                "f": _round0(cur["f"]),
                "c": _round0(cur["c"]),
            },
            "rng": {"s": rng["s"], "e": rng["e"], "n": rng["n"]},
        }
    finally:
        conn.close()


def get_nutrition_trend(period: str = "day", limit: int = 14) -> dict:
    """Get aggregated nutrition data by period"""
    conn = _get_conn()
    try:
        period_formats = {
            "day": "%Y-%m-%d",
            "week": "%Y-W%W",
            "month": "%Y-%m",
            "quarter": None,
            "year": "%Y",
        }

        if period not in period_formats:
            return {"err": f"Invalid period: {period}. Use day/week/month/quarter/year"}

        if period == "quarter":
            query = """
                SELECT
                    strftime('%Y', date) || '-Q' ||
                    ((CAST(strftime('%m', date) AS INTEGER) - 1) / 3 + 1) as p,
                    SUM(calories_kcal) as cal,
                    SUM(protein_g) as prot,
                    SUM(fat_g) as fat,
                    SUM(carbs_g) as carb
                FROM nutrition_entries
                GROUP BY p
                ORDER BY p DESC
                LIMIT ?
            """
        else:
            fmt = period_formats[period]
            query = f"""
                SELECT
                    strftime('{fmt}', date) as p,
                    SUM(calories_kcal) as cal,
                    SUM(protein_g) as prot,
                    SUM(fat_g) as fat,
                    SUM(carbs_g) as carb
                FROM nutrition_entries
                GROUP BY p
                ORDER BY p DESC
                LIMIT ?
            """

        rows = conn.execute(query, (limit,)).fetchall()

        data = []
        for row in rows:
            data.append({
                "p": row["p"],
                "cal": _round0(row["cal"]),
                "prot": _round0(row["prot"]),
                "f": _round0(row["fat"]),
                "c": _round0(row["carb"]),
            })

        return {"d": list(reversed(data))}
    finally:
        conn.close()


def get_nutrition_day(date: str) -> dict:
    """Get full item-level detail for a specific day"""
    conn = _get_conn()
    try:
        # Get totals
        tot = conn.execute("""
            SELECT SUM(calories_kcal) as cal,
                   SUM(protein_g) as p,
                   SUM(fat_g) as f,
                   SUM(carbs_g) as c
            FROM nutrition_entries
            WHERE date = ?
        """, (date,)).fetchone()

        if not tot["cal"]:
            return {"err": f"No data for {date}"}

        # Get items
        rows = conn.execute("""
            SELECT time, food_name, calories_kcal, protein_g, fat_g, carbs_g
            FROM nutrition_entries
            WHERE date = ?
            ORDER BY time
        """, (date,)).fetchall()

        items = []
        for row in rows:
            item = {"food": row["food_name"]}
            if row["time"]:
                item["t"] = row["time"][:5]  # HH:MM only
            if row["calories_kcal"]:
                item["cal"] = _round0(row["calories_kcal"])
            if row["protein_g"]:
                item["p"] = _round0(row["protein_g"])
            if row["fat_g"]:
                item["f"] = _round0(row["fat_g"])
            if row["carbs_g"]:
                item["c"] = _round0(row["carbs_g"])
            items.append(item)

        return {
            "d": date,
            "tot": {
                "cal": _round0(tot["cal"]),
                "p": _round0(tot["p"]),
                "f": _round0(tot["f"]),
                "c": _round0(tot["c"]),
            },
            "items": items,
        }
    finally:
        conn.close()


def get_nutrition_stats(
    start_date: Optional[str] = None, end_date: Optional[str] = None
) -> dict:
    """Get statistical summary of daily nutrition totals"""
    conn = _get_conn()
    try:
        conditions = []
        params = []
        if start_date:
            conditions.append("date >= ?")
            params.append(start_date)
        if end_date:
            conditions.append("date <= ?")
            params.append(end_date)

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        # Get daily totals first
        query = f"""
            SELECT date,
                   SUM(calories_kcal) as cal,
                   SUM(protein_g) as p,
                   SUM(fat_g) as f,
                   SUM(carbs_g) as c
            FROM nutrition_entries
            {where}
            GROUP BY date
            ORDER BY date
        """
        rows = conn.execute(query, params).fetchall()

        if not rows:
            return {"err": "No data in range"}

        cals = [r["cal"] for r in rows if r["cal"]]
        prots = [r["p"] for r in rows if r["p"]]
        fats = [r["f"] for r in rows if r["f"]]
        carbs = [r["c"] for r in rows if r["c"]]

        result = {}

        if cals:
            result["cal"] = {
                "avg": _round0(statistics.mean(cals)),
                "med": _round0(statistics.median(cals)),
                "std": _round0(statistics.stdev(cals)) if len(cals) > 1 else 0,
            }

        if prots:
            result["p"] = {
                "avg": _round0(statistics.mean(prots)),
                "med": _round0(statistics.median(prots)),
            }

        if fats:
            result["f"] = {
                "avg": _round0(statistics.mean(fats)),
                "med": _round0(statistics.median(fats)),
            }

        if carbs:
            result["c"] = {
                "avg": _round0(statistics.mean(carbs)),
                "med": _round0(statistics.median(carbs)),
            }

        return result
    finally:
        conn.close()


def get_nutrition_compare(
    period1_start: str,
    period1_end: str,
    period2_start: str,
    period2_end: str,
) -> dict:
    """Compare two time periods"""
    conn = _get_conn()
    try:

        def get_period_stats(start: str, end: str) -> dict:
            # Get daily totals then average
            rows = conn.execute("""
                SELECT date,
                       SUM(calories_kcal) as cal,
                       SUM(protein_g) as p,
                       SUM(fat_g) as f,
                       SUM(carbs_g) as c
                FROM nutrition_entries
                WHERE date >= ? AND date <= ?
                GROUP BY date
            """, (start, end)).fetchall()

            if not rows:
                return {"avg_cal": None, "avg_p": None, "avg_f": None, "avg_c": None, "n": 0}

            cals = [r["cal"] for r in rows if r["cal"]]
            prots = [r["p"] for r in rows if r["p"]]
            fats = [r["f"] for r in rows if r["f"]]
            carbs = [r["c"] for r in rows if r["c"]]

            return {
                "cal": _round0(statistics.mean(cals)) if cals else None,
                "p": _round0(statistics.mean(prots)) if prots else None,
                "f": _round0(statistics.mean(fats)) if fats else None,
                "c": _round0(statistics.mean(carbs)) if carbs else None,
                "n": len(rows),
            }

        p1 = get_period_stats(period1_start, period1_end)
        p2 = get_period_stats(period2_start, period2_end)

        delta = {}
        if p1["cal"] and p2["cal"]:
            delta["cal"] = _round0(p2["cal"] - p1["cal"])
        if p1["p"] and p2["p"]:
            delta["p"] = _round0(p2["p"] - p1["p"])
        if p1["f"] and p2["f"]:
            delta["f"] = _round0(p2["f"] - p1["f"])
        if p1["c"] and p2["c"]:
            delta["c"] = _round0(p2["c"] - p1["c"])

        return {
            "p1": {"rng": f"{period1_start}/{period1_end}", **p1},
            "p2": {"rng": f"{period2_start}/{period2_end}", **p2},
            "d": delta,
        }
    finally:
        conn.close()
