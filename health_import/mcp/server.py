"""
MCP Server for Sierra Health Data

Exposes Garmin weight/body composition data with LLM-optimized query patterns.

To run: python -m health_import.mcp

For Claude Desktop, add to claude_desktop_config.json:
{
  "mcpServers": {
    "sierra-health": {
      "command": "python",
      "args": ["-m", "health_import.mcp"],
      "cwd": "C:/dev/python/Sierra"
    }
  }
}
"""
import sys
import json
import logging
import sqlite3
import time
from pathlib import Path
from datetime import datetime
from mcp.server import FastMCP

from health_import.mcp.weight import (
    get_weight_summary,
    get_weight_trend,
    get_weight_records,
    get_weight_stats,
    get_weight_compare,
    DB_PATH,
)
from health_import.mcp.nutrition import (
    get_nutrition_summary,
    get_nutrition_trend,
    get_nutrition_day,
    get_nutrition_stats,
    get_nutrition_compare,
)
from health_import.mcp.activity import (
    get_activity_summary,
    get_activity_trend,
    get_activity_records,
    get_activity_stats,
    get_activity_compare,
)
from health_import.mcp.resting_hr import (
    get_rhr_summary,
    get_rhr_trend,
    get_rhr_records,
    get_rhr_stats,
    get_rhr_compare,
)
from health_import.mcp.vo2max import (
    get_vo2max_summary,
    get_vo2max_trend,
    get_vo2max_records,
    get_vo2max_stats,
    get_vo2max_compare,
)
from health_import.mcp.strength import (
    get_strength_summary,
    get_strength_trend,
    get_strength_records,
    get_strength_stats,
    get_strength_exercises,
    get_strength_compare,
)

# Setup logging
LOG_DIR = Path(__file__).parent.parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "mcp.log"),
        logging.StreamHandler(sys.stderr),
    ],
)
logger = logging.getLogger("mcp_server")


def estimate_tokens(data: dict) -> int:
    """Estimate token count from JSON length (len/4 approximation)"""
    return len(json.dumps(data, default=str)) // 4


def log_mcp_request(
    tool_name: str,
    params: dict,
    response: dict,
    duration_ms: int,
    response_tokens: int,
):
    """Log MCP request to database for dashboard monitoring"""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS mcp_requests (
                id INTEGER PRIMARY KEY,
                timestamp TEXT NOT NULL DEFAULT (datetime('now')),
                tool_name TEXT NOT NULL,
                params TEXT,
                response TEXT,
                response_tokens INTEGER,
                duration_ms INTEGER
            )
        """)
        resp_json = json.dumps(response, default=str)
        if len(resp_json) > 10000:
            resp_json = resp_json[:10000] + "...(truncated)"

        conn.execute(
            """
            INSERT INTO mcp_requests (tool_name, params, response, response_tokens, duration_ms)
            VALUES (?, ?, ?, ?, ?)
        """,
            (
                tool_name,
                json.dumps(params, default=str) if params else None,
                resp_json,
                response_tokens,
                duration_ms,
            ),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.warning(f"Failed to log MCP request: {e}")


# Create MCP server
mcp = FastMCP(
    name="sierra-health",
    instructions=(
        "Health metrics tool for weight, nutrition, activity, resting heart rate, VO2 Max, and strength data. "
        "Weight tools: weight_summary, weight_trend, weight_records, weight_stats, weight_compare. "
        "Nutrition tools: nutrition_summary, nutrition_trend, nutrition_day, nutrition_stats, nutrition_compare. "
        "Activity tools: activity_summary, activity_trend, activity_records, activity_stats, activity_compare. "
        "Resting HR tools: rhr_summary, rhr_trend, rhr_records, rhr_stats, rhr_compare. "
        "VO2 Max tools: vo2max_summary, vo2max_trend, vo2max_records, vo2max_stats, vo2max_compare. "
        "Strength tools: strength_summary, strength_trend, strength_records, strength_stats, strength_exercises, strength_compare."
    ),
)


@mcp.tool()
async def weight_summary() -> dict:
    """
    Quick overview of weight data for context-setting.

    Returns latest measurement, date range, and record count.
    Optimized for minimal tokens (~95).
    """
    logger.info("MCP Tool Call: weight_summary()")
    start = time.time()
    try:
        result = get_weight_summary()
        result["_tokens"] = estimate_tokens(result)
        duration_ms = int((time.time() - start) * 1000)
        logger.info(f"weight_summary: {result['_tokens']} tokens, {duration_ms}ms")
        log_mcp_request("weight_summary", {}, result, duration_ms, result["_tokens"])
        return result
    except Exception as e:
        logger.error(f"weight_summary error: {e}", exc_info=True)
        return {"error": str(e)}


@mcp.tool()
async def weight_trend(period: str = "month", limit: int = 12) -> dict:
    """
    Aggregated weight data by time period.

    Args:
        period: Aggregation period - week, month, quarter, or year
        limit: Number of periods to return (default 12)

    Returns aggregated stats (avg, min, max, body fat) per period.
    Optimized for trend analysis without raw data (~280 tokens).
    """
    logger.info(f"MCP Tool Call: weight_trend(period={period}, limit={limit})")
    start = time.time()
    try:
        result = get_weight_trend(period, limit)
        result["_tokens"] = estimate_tokens(result)
        duration_ms = int((time.time() - start) * 1000)
        logger.info(f"weight_trend: {result['_tokens']} tokens, {duration_ms}ms")
        log_mcp_request(
            "weight_trend",
            {"period": period, "limit": limit},
            result,
            duration_ms,
            result["_tokens"],
        )
        return result
    except Exception as e:
        logger.error(f"weight_trend error: {e}", exc_info=True)
        return {"error": str(e)}


@mcp.tool()
async def weight_records(
    start_date: str = None,
    end_date: str = None,
    page: int = 1,
    page_size: int = 50,
) -> dict:
    """
    Paginated raw weight records.

    Args:
        start_date: Filter start (YYYY-MM-DD)
        end_date: Filter end (YYYY-MM-DD)
        page: Page number (default 1)
        page_size: Records per page (max 50)

    Returns individual measurements with pagination info.
    """
    logger.info(
        f"MCP Tool Call: weight_records(start={start_date}, end={end_date}, "
        f"page={page}, size={page_size})"
    )
    start = time.time()
    try:
        result = get_weight_records(start_date, end_date, page, min(page_size, 50))
        result["_tokens"] = estimate_tokens(result)
        duration_ms = int((time.time() - start) * 1000)
        logger.info(f"weight_records: {result['_tokens']} tokens, {duration_ms}ms")
        log_mcp_request(
            "weight_records",
            {
                "start_date": start_date,
                "end_date": end_date,
                "page": page,
                "page_size": page_size,
            },
            result,
            duration_ms,
            result["_tokens"],
        )
        return result
    except Exception as e:
        logger.error(f"weight_records error: {e}", exc_info=True)
        return {"error": str(e)}


@mcp.tool()
async def weight_stats(start_date: str = None, end_date: str = None) -> dict:
    """
    Statistical summary of weight data.

    Args:
        start_date: Filter start (YYYY-MM-DD), optional
        end_date: Filter end (YYYY-MM-DD), optional

    Returns mean, median, std, percentiles for weight and body fat,
    plus net change over the period (~180 tokens).
    """
    logger.info(f"MCP Tool Call: weight_stats(start={start_date}, end={end_date})")
    start = time.time()
    try:
        result = get_weight_stats(start_date, end_date)
        result["_tokens"] = estimate_tokens(result)
        duration_ms = int((time.time() - start) * 1000)
        logger.info(f"weight_stats: {result['_tokens']} tokens, {duration_ms}ms")
        log_mcp_request(
            "weight_stats",
            {"start_date": start_date, "end_date": end_date},
            result,
            duration_ms,
            result["_tokens"],
        )
        return result
    except Exception as e:
        logger.error(f"weight_stats error: {e}", exc_info=True)
        return {"error": str(e)}


@mcp.tool()
async def weight_compare(
    period1_start: str,
    period1_end: str,
    period2_start: str,
    period2_end: str,
) -> dict:
    """
    Compare two time periods.

    Args:
        period1_start: First period start (YYYY-MM-DD)
        period1_end: First period end (YYYY-MM-DD)
        period2_start: Second period start (YYYY-MM-DD)
        period2_end: Second period end (YYYY-MM-DD)

    Returns averages for each period and delta between them (~150 tokens).
    """
    logger.info(
        f"MCP Tool Call: weight_compare({period1_start}-{period1_end} vs "
        f"{period2_start}-{period2_end})"
    )
    start = time.time()
    try:
        result = get_weight_compare(
            period1_start, period1_end, period2_start, period2_end
        )
        result["_tokens"] = estimate_tokens(result)
        duration_ms = int((time.time() - start) * 1000)
        logger.info(f"weight_compare: {result['_tokens']} tokens, {duration_ms}ms")
        log_mcp_request(
            "weight_compare",
            {
                "period1_start": period1_start,
                "period1_end": period1_end,
                "period2_start": period2_start,
                "period2_end": period2_end,
            },
            result,
            duration_ms,
            result["_tokens"],
        )
        return result
    except Exception as e:
        logger.error(f"weight_compare error: {e}", exc_info=True)
        return {"error": str(e)}


# ============================================================================
# Nutrition Tools
# ============================================================================


@mcp.tool()
async def nutrition_summary() -> dict:
    """
    Quick overview of nutrition data for context-setting.

    Returns latest day's totals (calories, protein, fat, carbs) and date range.
    Optimized for minimal tokens (~40).
    """
    logger.info("MCP Tool Call: nutrition_summary()")
    start = time.time()
    try:
        result = get_nutrition_summary()
        result["_tokens"] = estimate_tokens(result)
        duration_ms = int((time.time() - start) * 1000)
        logger.info(f"nutrition_summary: {result['_tokens']} tokens, {duration_ms}ms")
        log_mcp_request("nutrition_summary", {}, result, duration_ms, result["_tokens"])
        return result
    except Exception as e:
        logger.error(f"nutrition_summary error: {e}", exc_info=True)
        return {"error": str(e)}


@mcp.tool()
async def nutrition_trend(period: str = "day", limit: int = 14) -> dict:
    """
    Aggregated nutrition totals by time period.

    Args:
        period: Aggregation period - day, week, month, quarter, or year
        limit: Number of periods to return (default 14)

    Returns total calories, protein, fat, carbs per period (~60-250 tokens).
    """
    logger.info(f"MCP Tool Call: nutrition_trend(period={period}, limit={limit})")
    start = time.time()
    try:
        result = get_nutrition_trend(period, limit)
        result["_tokens"] = estimate_tokens(result)
        duration_ms = int((time.time() - start) * 1000)
        logger.info(f"nutrition_trend: {result['_tokens']} tokens, {duration_ms}ms")
        log_mcp_request(
            "nutrition_trend",
            {"period": period, "limit": limit},
            result,
            duration_ms,
            result["_tokens"],
        )
        return result
    except Exception as e:
        logger.error(f"nutrition_trend error: {e}", exc_info=True)
        return {"error": str(e)}


@mcp.tool()
async def nutrition_day(date: str) -> dict:
    """
    Full item-level detail for a specific day.

    Args:
        date: Date to get details for (YYYY-MM-DD)

    Returns day total and list of individual food items with times and macros.
    ~30 tokens per food item.
    """
    logger.info(f"MCP Tool Call: nutrition_day(date={date})")
    start = time.time()
    try:
        result = get_nutrition_day(date)
        result["_tokens"] = estimate_tokens(result)
        duration_ms = int((time.time() - start) * 1000)
        logger.info(f"nutrition_day: {result['_tokens']} tokens, {duration_ms}ms")
        log_mcp_request(
            "nutrition_day",
            {"date": date},
            result,
            duration_ms,
            result["_tokens"],
        )
        return result
    except Exception as e:
        logger.error(f"nutrition_day error: {e}", exc_info=True)
        return {"error": str(e)}


@mcp.tool()
async def nutrition_stats(start_date: str = None, end_date: str = None) -> dict:
    """
    Statistical summary of daily nutrition totals.

    Args:
        start_date: Filter start (YYYY-MM-DD), optional
        end_date: Filter end (YYYY-MM-DD), optional

    Returns mean, median, std for daily calories, protein, fat, carbs (~60 tokens).
    """
    logger.info(f"MCP Tool Call: nutrition_stats(start={start_date}, end={end_date})")
    start = time.time()
    try:
        result = get_nutrition_stats(start_date, end_date)
        result["_tokens"] = estimate_tokens(result)
        duration_ms = int((time.time() - start) * 1000)
        logger.info(f"nutrition_stats: {result['_tokens']} tokens, {duration_ms}ms")
        log_mcp_request(
            "nutrition_stats",
            {"start_date": start_date, "end_date": end_date},
            result,
            duration_ms,
            result["_tokens"],
        )
        return result
    except Exception as e:
        logger.error(f"nutrition_stats error: {e}", exc_info=True)
        return {"error": str(e)}


@mcp.tool()
async def nutrition_compare(
    period1_start: str,
    period1_end: str,
    period2_start: str,
    period2_end: str,
) -> dict:
    """
    Compare nutrition between two time periods.

    Args:
        period1_start: First period start (YYYY-MM-DD)
        period1_end: First period end (YYYY-MM-DD)
        period2_start: Second period start (YYYY-MM-DD)
        period2_end: Second period end (YYYY-MM-DD)

    Returns daily averages for each period and delta between them (~70 tokens).
    """
    logger.info(
        f"MCP Tool Call: nutrition_compare({period1_start}-{period1_end} vs "
        f"{period2_start}-{period2_end})"
    )
    start = time.time()
    try:
        result = get_nutrition_compare(
            period1_start, period1_end, period2_start, period2_end
        )
        result["_tokens"] = estimate_tokens(result)
        duration_ms = int((time.time() - start) * 1000)
        logger.info(f"nutrition_compare: {result['_tokens']} tokens, {duration_ms}ms")
        log_mcp_request(
            "nutrition_compare",
            {
                "period1_start": period1_start,
                "period1_end": period1_end,
                "period2_start": period2_start,
                "period2_end": period2_end,
            },
            result,
            duration_ms,
            result["_tokens"],
        )
        return result
    except Exception as e:
        logger.error(f"nutrition_compare error: {e}", exc_info=True)
        return {"error": str(e)}


# ============================================================================
# Activity Tools
# ============================================================================


@mcp.tool()
async def activity_summary() -> dict:
    """
    Quick overview of activity data for context-setting.

    Returns latest activity (date, type, duration, distance, HR) and date range.
    Optimized for minimal tokens (~50).
    """
    logger.info("MCP Tool Call: activity_summary()")
    start = time.time()
    try:
        result = get_activity_summary()
        result["_tokens"] = estimate_tokens(result)
        duration_ms = int((time.time() - start) * 1000)
        logger.info(f"activity_summary: {result['_tokens']} tokens, {duration_ms}ms")
        log_mcp_request("activity_summary", {}, result, duration_ms, result["_tokens"])
        return result
    except Exception as e:
        logger.error(f"activity_summary error: {e}", exc_info=True)
        return {"error": str(e)}


@mcp.tool()
async def activity_trend(period: str = "week", limit: int = 12) -> dict:
    """
    Aggregated activity data by time period.

    Args:
        period: Aggregation period - week, month, quarter, or year
        limit: Number of periods to return (default 12)

    Returns count, total duration, total distance, avg HR per period (~60-200 tokens).
    """
    logger.info(f"MCP Tool Call: activity_trend(period={period}, limit={limit})")
    start = time.time()
    try:
        result = get_activity_trend(period, limit)
        result["_tokens"] = estimate_tokens(result)
        duration_ms = int((time.time() - start) * 1000)
        logger.info(f"activity_trend: {result['_tokens']} tokens, {duration_ms}ms")
        log_mcp_request(
            "activity_trend",
            {"period": period, "limit": limit},
            result,
            duration_ms,
            result["_tokens"],
        )
        return result
    except Exception as e:
        logger.error(f"activity_trend error: {e}", exc_info=True)
        return {"error": str(e)}


@mcp.tool()
async def activity_records(
    activity_type: str = None,
    start_date: str = None,
    end_date: str = None,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    """
    Paginated activity records.

    Args:
        activity_type: Filter by type (running, walking, cycling, etc.), optional
        start_date: Filter start (YYYY-MM-DD), optional
        end_date: Filter end (YYYY-MM-DD), optional
        page: Page number (default 1)
        page_size: Records per page (default 20, max 50)

    Returns individual activities with duration, distance, pace, HR.
    ~40 tokens per record.
    """
    logger.info(
        f"MCP Tool Call: activity_records(type={activity_type}, start={start_date}, "
        f"end={end_date}, page={page}, size={page_size})"
    )
    start = time.time()
    try:
        result = get_activity_records(
            activity_type, start_date, end_date, page, min(page_size, 50)
        )
        result["_tokens"] = estimate_tokens(result)
        duration_ms = int((time.time() - start) * 1000)
        logger.info(f"activity_records: {result['_tokens']} tokens, {duration_ms}ms")
        log_mcp_request(
            "activity_records",
            {
                "activity_type": activity_type,
                "start_date": start_date,
                "end_date": end_date,
                "page": page,
                "page_size": page_size,
            },
            result,
            duration_ms,
            result["_tokens"],
        )
        return result
    except Exception as e:
        logger.error(f"activity_records error: {e}", exc_info=True)
        return {"error": str(e)}


@mcp.tool()
async def activity_stats(
    activity_type: str = None,
    start_date: str = None,
    end_date: str = None,
) -> dict:
    """
    Statistical summary of activities.

    Args:
        activity_type: Filter by type (running, walking, cycling, etc.), optional
        start_date: Filter start (YYYY-MM-DD), optional
        end_date: Filter end (YYYY-MM-DD), optional

    Returns totals and averages for duration, distance, pace, HR (~60 tokens).
    """
    logger.info(
        f"MCP Tool Call: activity_stats(type={activity_type}, start={start_date}, end={end_date})"
    )
    start = time.time()
    try:
        result = get_activity_stats(activity_type, start_date, end_date)
        result["_tokens"] = estimate_tokens(result)
        duration_ms = int((time.time() - start) * 1000)
        logger.info(f"activity_stats: {result['_tokens']} tokens, {duration_ms}ms")
        log_mcp_request(
            "activity_stats",
            {
                "activity_type": activity_type,
                "start_date": start_date,
                "end_date": end_date,
            },
            result,
            duration_ms,
            result["_tokens"],
        )
        return result
    except Exception as e:
        logger.error(f"activity_stats error: {e}", exc_info=True)
        return {"error": str(e)}


@mcp.tool()
async def activity_compare(
    period1_start: str,
    period1_end: str,
    period2_start: str,
    period2_end: str,
) -> dict:
    """
    Compare activity between two time periods.

    Args:
        period1_start: First period start (YYYY-MM-DD)
        period1_end: First period end (YYYY-MM-DD)
        period2_start: Second period start (YYYY-MM-DD)
        period2_end: Second period end (YYYY-MM-DD)

    Returns count, distance, duration, HR for each period and delta (~70 tokens).
    """
    logger.info(
        f"MCP Tool Call: activity_compare({period1_start}-{period1_end} vs "
        f"{period2_start}-{period2_end})"
    )
    start = time.time()
    try:
        result = get_activity_compare(
            period1_start, period1_end, period2_start, period2_end
        )
        result["_tokens"] = estimate_tokens(result)
        duration_ms = int((time.time() - start) * 1000)
        logger.info(f"activity_compare: {result['_tokens']} tokens, {duration_ms}ms")
        log_mcp_request(
            "activity_compare",
            {
                "period1_start": period1_start,
                "period1_end": period1_end,
                "period2_start": period2_start,
                "period2_end": period2_end,
            },
            result,
            duration_ms,
            result["_tokens"],
        )
        return result
    except Exception as e:
        logger.error(f"activity_compare error: {e}", exc_info=True)
        return {"error": str(e)}


# ============================================================================
# Resting Heart Rate Tools
# ============================================================================


@mcp.tool()
async def rhr_summary() -> dict:
    """
    Quick overview of resting heart rate data.

    Returns latest reading, date range, and record count.
    Optimized for minimal tokens (~30).
    """
    logger.info("MCP Tool Call: rhr_summary()")
    start = time.time()
    try:
        result = get_rhr_summary()
        result["_tokens"] = estimate_tokens(result)
        duration_ms = int((time.time() - start) * 1000)
        logger.info(f"rhr_summary: {result['_tokens']} tokens, {duration_ms}ms")
        log_mcp_request("rhr_summary", {}, result, duration_ms, result["_tokens"])
        return result
    except Exception as e:
        logger.error(f"rhr_summary error: {e}", exc_info=True)
        return {"error": str(e)}


@mcp.tool()
async def rhr_trend(period: str = "month", limit: int = 12) -> dict:
    """
    Aggregated resting heart rate by time period.

    Args:
        period: Aggregation period - week, month, quarter, or year
        limit: Number of periods to return (default 12)

    Returns avg, min, max, count per period (~50-150 tokens).
    """
    logger.info(f"MCP Tool Call: rhr_trend(period={period}, limit={limit})")
    start = time.time()
    try:
        result = get_rhr_trend(period, limit)
        result["_tokens"] = estimate_tokens(result)
        duration_ms = int((time.time() - start) * 1000)
        logger.info(f"rhr_trend: {result['_tokens']} tokens, {duration_ms}ms")
        log_mcp_request(
            "rhr_trend",
            {"period": period, "limit": limit},
            result,
            duration_ms,
            result["_tokens"],
        )
        return result
    except Exception as e:
        logger.error(f"rhr_trend error: {e}", exc_info=True)
        return {"error": str(e)}


@mcp.tool()
async def rhr_records(
    start_date: str = None,
    end_date: str = None,
    page: int = 1,
    page_size: int = 30,
) -> dict:
    """
    Paginated daily resting heart rate readings.

    Args:
        start_date: Filter start (YYYY-MM-DD), optional
        end_date: Filter end (YYYY-MM-DD), optional
        page: Page number (default 1)
        page_size: Records per page (default 30, max 50)

    Returns daily readings with pagination info. ~15 tokens per record.
    """
    logger.info(
        f"MCP Tool Call: rhr_records(start={start_date}, end={end_date}, "
        f"page={page}, size={page_size})"
    )
    start = time.time()
    try:
        result = get_rhr_records(start_date, end_date, page, min(page_size, 50))
        result["_tokens"] = estimate_tokens(result)
        duration_ms = int((time.time() - start) * 1000)
        logger.info(f"rhr_records: {result['_tokens']} tokens, {duration_ms}ms")
        log_mcp_request(
            "rhr_records",
            {
                "start_date": start_date,
                "end_date": end_date,
                "page": page,
                "page_size": page_size,
            },
            result,
            duration_ms,
            result["_tokens"],
        )
        return result
    except Exception as e:
        logger.error(f"rhr_records error: {e}", exc_info=True)
        return {"error": str(e)}


@mcp.tool()
async def rhr_stats(start_date: str = None, end_date: str = None) -> dict:
    """
    Statistical summary of resting heart rate.

    Args:
        start_date: Filter start (YYYY-MM-DD), optional
        end_date: Filter end (YYYY-MM-DD), optional

    Returns count, avg, min, max, std deviation (~40 tokens).
    """
    logger.info(f"MCP Tool Call: rhr_stats(start={start_date}, end={end_date})")
    start = time.time()
    try:
        result = get_rhr_stats(start_date, end_date)
        result["_tokens"] = estimate_tokens(result)
        duration_ms = int((time.time() - start) * 1000)
        logger.info(f"rhr_stats: {result['_tokens']} tokens, {duration_ms}ms")
        log_mcp_request(
            "rhr_stats",
            {"start_date": start_date, "end_date": end_date},
            result,
            duration_ms,
            result["_tokens"],
        )
        return result
    except Exception as e:
        logger.error(f"rhr_stats error: {e}", exc_info=True)
        return {"error": str(e)}


@mcp.tool()
async def rhr_compare(
    period1_start: str,
    period1_end: str,
    period2_start: str,
    period2_end: str,
) -> dict:
    """
    Compare resting heart rate between two time periods.

    Args:
        period1_start: First period start (YYYY-MM-DD)
        period1_end: First period end (YYYY-MM-DD)
        period2_start: Second period start (YYYY-MM-DD)
        period2_end: Second period end (YYYY-MM-DD)

    Returns averages for each period and delta between them (~50 tokens).
    """
    logger.info(
        f"MCP Tool Call: rhr_compare({period1_start}-{period1_end} vs "
        f"{period2_start}-{period2_end})"
    )
    start = time.time()
    try:
        result = get_rhr_compare(
            period1_start, period1_end, period2_start, period2_end
        )
        result["_tokens"] = estimate_tokens(result)
        duration_ms = int((time.time() - start) * 1000)
        logger.info(f"rhr_compare: {result['_tokens']} tokens, {duration_ms}ms")
        log_mcp_request(
            "rhr_compare",
            {
                "period1_start": period1_start,
                "period1_end": period1_end,
                "period2_start": period2_start,
                "period2_end": period2_end,
            },
            result,
            duration_ms,
            result["_tokens"],
        )
        return result
    except Exception as e:
        logger.error(f"rhr_compare error: {e}", exc_info=True)
        return {"error": str(e)}


# ============================================================================
# VO2 Max Tools
# ============================================================================


@mcp.tool()
async def vo2max_summary() -> dict:
    """
    Quick overview of VO2 Max data (running only).

    Returns latest reading, date range, and record count.
    Optimized for minimal tokens (~30).
    """
    logger.info("MCP Tool Call: vo2max_summary()")
    start = time.time()
    try:
        result = get_vo2max_summary()
        result["_tokens"] = estimate_tokens(result)
        duration_ms = int((time.time() - start) * 1000)
        logger.info(f"vo2max_summary: {result['_tokens']} tokens, {duration_ms}ms")
        log_mcp_request("vo2max_summary", {}, result, duration_ms, result["_tokens"])
        return result
    except Exception as e:
        logger.error(f"vo2max_summary error: {e}", exc_info=True)
        return {"error": str(e)}


@mcp.tool()
async def vo2max_trend(period: str = "month", limit: int = 12) -> dict:
    """
    Aggregated VO2 Max by time period (running only).

    Args:
        period: Aggregation period - week, month, quarter, or year
        limit: Number of periods to return (default 12)

    Returns avg, min, max, count per period (~50-150 tokens).
    """
    logger.info(f"MCP Tool Call: vo2max_trend(period={period}, limit={limit})")
    start = time.time()
    try:
        result = get_vo2max_trend(period, limit)
        result["_tokens"] = estimate_tokens(result)
        duration_ms = int((time.time() - start) * 1000)
        logger.info(f"vo2max_trend: {result['_tokens']} tokens, {duration_ms}ms")
        log_mcp_request(
            "vo2max_trend",
            {"period": period, "limit": limit},
            result,
            duration_ms,
            result["_tokens"],
        )
        return result
    except Exception as e:
        logger.error(f"vo2max_trend error: {e}", exc_info=True)
        return {"error": str(e)}


@mcp.tool()
async def vo2max_records(
    start_date: str = None,
    end_date: str = None,
    page: int = 1,
    page_size: int = 30,
) -> dict:
    """
    Paginated VO2 Max readings (running only).

    Args:
        start_date: Filter start (YYYY-MM-DD), optional
        end_date: Filter end (YYYY-MM-DD), optional
        page: Page number (default 1)
        page_size: Records per page (default 30, max 50)

    Returns readings with pagination info. ~12 tokens per record.
    """
    logger.info(
        f"MCP Tool Call: vo2max_records(start={start_date}, end={end_date}, "
        f"page={page}, size={page_size})"
    )
    start = time.time()
    try:
        result = get_vo2max_records(start_date, end_date, page, min(page_size, 50))
        result["_tokens"] = estimate_tokens(result)
        duration_ms = int((time.time() - start) * 1000)
        logger.info(f"vo2max_records: {result['_tokens']} tokens, {duration_ms}ms")
        log_mcp_request(
            "vo2max_records",
            {
                "start_date": start_date,
                "end_date": end_date,
                "page": page,
                "page_size": page_size,
            },
            result,
            duration_ms,
            result["_tokens"],
        )
        return result
    except Exception as e:
        logger.error(f"vo2max_records error: {e}", exc_info=True)
        return {"error": str(e)}


@mcp.tool()
async def vo2max_stats(start_date: str = None, end_date: str = None) -> dict:
    """
    Statistical summary of VO2 Max (running only).

    Args:
        start_date: Filter start (YYYY-MM-DD), optional
        end_date: Filter end (YYYY-MM-DD), optional

    Returns count, avg, min, max, std deviation (~40 tokens).
    """
    logger.info(f"MCP Tool Call: vo2max_stats(start={start_date}, end={end_date})")
    start = time.time()
    try:
        result = get_vo2max_stats(start_date, end_date)
        result["_tokens"] = estimate_tokens(result)
        duration_ms = int((time.time() - start) * 1000)
        logger.info(f"vo2max_stats: {result['_tokens']} tokens, {duration_ms}ms")
        log_mcp_request(
            "vo2max_stats",
            {"start_date": start_date, "end_date": end_date},
            result,
            duration_ms,
            result["_tokens"],
        )
        return result
    except Exception as e:
        logger.error(f"vo2max_stats error: {e}", exc_info=True)
        return {"error": str(e)}


@mcp.tool()
async def vo2max_compare(
    period1_start: str,
    period1_end: str,
    period2_start: str,
    period2_end: str,
) -> dict:
    """
    Compare VO2 Max between two time periods (running only).

    Args:
        period1_start: First period start (YYYY-MM-DD)
        period1_end: First period end (YYYY-MM-DD)
        period2_start: Second period start (YYYY-MM-DD)
        period2_end: Second period end (YYYY-MM-DD)

    Returns averages for each period and delta between them (~50 tokens).
    """
    logger.info(
        f"MCP Tool Call: vo2max_compare({period1_start}-{period1_end} vs "
        f"{period2_start}-{period2_end})"
    )
    start = time.time()
    try:
        result = get_vo2max_compare(
            period1_start, period1_end, period2_start, period2_end
        )
        result["_tokens"] = estimate_tokens(result)
        duration_ms = int((time.time() - start) * 1000)
        logger.info(f"vo2max_compare: {result['_tokens']} tokens, {duration_ms}ms")
        log_mcp_request(
            "vo2max_compare",
            {
                "period1_start": period1_start,
                "period1_end": period1_end,
                "period2_start": period2_start,
                "period2_end": period2_end,
            },
            result,
            duration_ms,
            result["_tokens"],
        )
        return result
    except Exception as e:
        logger.error(f"vo2max_compare error: {e}", exc_info=True)
        return {"error": str(e)}


# ============================================================================
# Strength Tools
# ============================================================================


@mcp.tool()
async def strength_summary() -> dict:
    """
    Quick overview of strength training data.

    Returns latest workout, date range, record count, and unique exercise count.
    Optimized for minimal tokens (~40).
    """
    logger.info("MCP Tool Call: strength_summary()")
    start = time.time()
    try:
        result = get_strength_summary()
        result["_tokens"] = estimate_tokens(result)
        duration_ms = int((time.time() - start) * 1000)
        logger.info(f"strength_summary: {result['_tokens']} tokens, {duration_ms}ms")
        log_mcp_request("strength_summary", {}, result, duration_ms, result["_tokens"])
        return result
    except Exception as e:
        logger.error(f"strength_summary error: {e}", exc_info=True)
        return {"error": str(e)}


@mcp.tool()
async def strength_trend(
    period: str = "month",
    limit: int = 12,
    exercise: str = None,
) -> dict:
    """
    Aggregated strength training data by time period.

    Args:
        period: Aggregation period - week, month, quarter, or year
        limit: Number of periods to return (default 12)
        exercise: Filter by exercise name (optional)

    Returns workout count, total reps, unique exercises per period (~60-200 tokens).
    """
    logger.info(f"MCP Tool Call: strength_trend(period={period}, limit={limit}, exercise={exercise})")
    start = time.time()
    try:
        result = get_strength_trend(period, limit, exercise)
        result["_tokens"] = estimate_tokens(result)
        duration_ms = int((time.time() - start) * 1000)
        logger.info(f"strength_trend: {result['_tokens']} tokens, {duration_ms}ms")
        log_mcp_request(
            "strength_trend",
            {"period": period, "limit": limit, "exercise": exercise},
            result,
            duration_ms,
            result["_tokens"],
        )
        return result
    except Exception as e:
        logger.error(f"strength_trend error: {e}", exc_info=True)
        return {"error": str(e)}


@mcp.tool()
async def strength_records(
    exercise: str = None,
    start_date: str = None,
    end_date: str = None,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    """
    Paginated strength workout records.

    Args:
        exercise: Filter by exercise name (optional)
        start_date: Filter start (YYYY-MM-DD), optional
        end_date: Filter end (YYYY-MM-DD), optional
        page: Page number (default 1)
        page_size: Records per page (default 20, max 50)

    Returns individual workouts with sets, totals, and calories.
    ~25 tokens per record.
    """
    logger.info(
        f"MCP Tool Call: strength_records(exercise={exercise}, start={start_date}, "
        f"end={end_date}, page={page}, size={page_size})"
    )
    start = time.time()
    try:
        result = get_strength_records(exercise, start_date, end_date, page, min(page_size, 50))
        result["_tokens"] = estimate_tokens(result)
        duration_ms = int((time.time() - start) * 1000)
        logger.info(f"strength_records: {result['_tokens']} tokens, {duration_ms}ms")
        log_mcp_request(
            "strength_records",
            {
                "exercise": exercise,
                "start_date": start_date,
                "end_date": end_date,
                "page": page,
                "page_size": page_size,
            },
            result,
            duration_ms,
            result["_tokens"],
        )
        return result
    except Exception as e:
        logger.error(f"strength_records error: {e}", exc_info=True)
        return {"error": str(e)}


@mcp.tool()
async def strength_stats(
    exercise: str = None,
    start_date: str = None,
    end_date: str = None,
) -> dict:
    """
    Statistical summary of strength training.

    Args:
        exercise: Filter by exercise name (optional)
        start_date: Filter start (YYYY-MM-DD), optional
        end_date: Filter end (YYYY-MM-DD), optional

    Returns total workouts, sum/avg totals, and per-exercise breakdown (~60 tokens).
    """
    logger.info(
        f"MCP Tool Call: strength_stats(exercise={exercise}, start={start_date}, end={end_date})"
    )
    start = time.time()
    try:
        result = get_strength_stats(exercise, start_date, end_date)
        result["_tokens"] = estimate_tokens(result)
        duration_ms = int((time.time() - start) * 1000)
        logger.info(f"strength_stats: {result['_tokens']} tokens, {duration_ms}ms")
        log_mcp_request(
            "strength_stats",
            {
                "exercise": exercise,
                "start_date": start_date,
                "end_date": end_date,
            },
            result,
            duration_ms,
            result["_tokens"],
        )
        return result
    except Exception as e:
        logger.error(f"strength_stats error: {e}", exc_info=True)
        return {"error": str(e)}


@mcp.tool()
async def strength_exercises() -> dict:
    """
    List all exercises with workout counts.

    Returns exercise names, categories, and workout counts.
    ~15 tokens per exercise.
    """
    logger.info("MCP Tool Call: strength_exercises()")
    start = time.time()
    try:
        result = get_strength_exercises()
        result["_tokens"] = estimate_tokens(result)
        duration_ms = int((time.time() - start) * 1000)
        logger.info(f"strength_exercises: {result['_tokens']} tokens, {duration_ms}ms")
        log_mcp_request("strength_exercises", {}, result, duration_ms, result["_tokens"])
        return result
    except Exception as e:
        logger.error(f"strength_exercises error: {e}", exc_info=True)
        return {"error": str(e)}


@mcp.tool()
async def strength_compare(
    period1_start: str,
    period1_end: str,
    period2_start: str,
    period2_end: str,
) -> dict:
    """
    Compare strength training between two time periods.

    Args:
        period1_start: First period start (YYYY-MM-DD)
        period1_end: First period end (YYYY-MM-DD)
        period2_start: Second period start (YYYY-MM-DD)
        period2_end: Second period end (YYYY-MM-DD)

    Returns workout count and totals for each period and delta (~50 tokens).
    """
    logger.info(
        f"MCP Tool Call: strength_compare({period1_start}-{period1_end} vs "
        f"{period2_start}-{period2_end})"
    )
    start = time.time()
    try:
        result = get_strength_compare(
            period1_start, period1_end, period2_start, period2_end
        )
        result["_tokens"] = estimate_tokens(result)
        duration_ms = int((time.time() - start) * 1000)
        logger.info(f"strength_compare: {result['_tokens']} tokens, {duration_ms}ms")
        log_mcp_request(
            "strength_compare",
            {
                "period1_start": period1_start,
                "period1_end": period1_end,
                "period2_start": period2_start,
                "period2_end": period2_end,
            },
            result,
            duration_ms,
            result["_tokens"],
        )
        return result
    except Exception as e:
        logger.error(f"strength_compare error: {e}", exc_info=True)
        return {"error": str(e)}


def main():
    """Main entry point for MCP server"""
    try:
        logger.info("=" * 60)
        logger.info("Sierra Health MCP Server")
        logger.info("=" * 60)
        logger.info("Starting MCP server via stdio...")

        import asyncio
        asyncio.run(mcp.run_stdio_async())

    except KeyboardInterrupt:
        logger.info("Server shutting down...")
        return 0
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
