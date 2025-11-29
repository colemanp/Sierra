# MCP Server - Sierra Health

Model Context Protocol server for Claude Desktop. Exposes health data (weight/body composition, nutrition, activity, resting heart rate, and VO2 Max) with LLM-optimized query patterns.

## Claude Desktop Setup

Add to `%APPDATA%\Claude\claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "sierra-health": {
      "command": "python",
      "args": ["-m", "health_import.mcp"],
      "cwd": "C:/dev/python/Sierra"
    }
  }
}
```

Restart Claude Desktop after adding.

## Weight Tools

### weight_summary

Quick overview for context-setting. ~30 tokens.

```json
{
  "cur": {"d": "2025-11-28", "wt": 157.5, "fat": 22.0, "m": 64.6},
  "rng": {"s": "2018-03-09", "e": "2025-11-28", "n": 1002}
}
```

### weight_trend

Aggregated by period. ~64-253 tokens depending on limit.

**Parameters:**
- `period`: week | month | quarter | year
- `limit`: number of periods (default 12)

```json
{
  "d": [
    {"p": "2025-09", "avg": 160.0, "min": 159.0, "max": 162.1, "fat": 22.3, "m": 65.2},
    {"p": "2025-10", "avg": 159.5, "min": 157.9, "max": 161.1, "fat": 22.6, "m": 65.0}
  ]
}
```

### weight_records

Paginated raw data. ~25 tokens per record.

**Parameters:**
- `start_date`: YYYY-MM-DD (optional)
- `end_date`: YYYY-MM-DD (optional)
- `page`: page number (default 1)
- `page_size`: records per page (max 50)

```json
{
  "r": [
    {"d": "2025-11-28", "t": "10:33:00", "wt": 157.5, "fat": 22.0, "m": 64.6, "b": 8.0, "w": 57.0}
  ],
  "pg": 1,
  "pgs": 201,
  "n": 1002
}
```

### weight_stats

Statistical summary. ~45 tokens.

**Parameters:**
- `start_date`: YYYY-MM-DD (optional)
- `end_date`: YYYY-MM-DD (optional)

```json
{
  "wt": {"avg": 158.2, "med": 158.2, "std": 1.1, "p25": 157.5, "p75": 159.0},
  "fat": {"avg": 22.9, "med": 23.0, "std": 0.8, "p25": 22.5, "p75": 23.4},
  "chg": {"wt": 1.5, "fat": -0.7}
}
```

### weight_compare

Compare two periods. ~59 tokens.

**Parameters:**
- `period1_start`, `period1_end`: first period range
- `period2_start`, `period2_end`: second period range

```json
{
  "p1": {"rng": "2024-01-01/2024-03-31", "avg": 158.4, "fat": 22.9, "min": 156.9, "max": 160.4, "n": 74},
  "p2": {"rng": "2024-04-01/2024-06-30", "avg": 158.3, "fat": 23.4, "min": 156.5, "max": 163.4, "n": 64},
  "d": {"wt": -0.1, "fat": 0.5}
}
```

## Nutrition Tools

### nutrition_summary

Quick overview - latest day totals + date range. ~30 tokens.

```json
{
  "cur": {"d": "2025-11-28", "cal": 290, "p": 20, "f": 11, "c": 29},
  "rng": {"s": "2025-11-21", "e": "2025-11-28", "n": 64}
}
```

### nutrition_trend

Aggregated totals by period. ~50-200 tokens depending on limit.

**Parameters:**
- `period`: day | week | month | quarter | year
- `limit`: number of periods (default 14)

```json
{
  "d": [
    {"p": "2025-11-26", "cal": 2296, "prot": 95, "f": 107, "c": 251},
    {"p": "2025-11-27", "cal": 2544, "prot": 108, "f": 126, "c": 250}
  ]
}
```

### nutrition_day

Full item-level detail for a specific day. ~30 tokens per item.

**Parameters:**
- `date`: YYYY-MM-DD

```json
{
  "d": "2025-11-27",
  "tot": {"cal": 2544, "p": 108, "f": 126, "c": 250},
  "items": [
    {"t": "07:38", "food": "Builders Protein Bar", "cal": 290, "p": 20, "f": 10, "c": 29},
    {"t": "11:59", "food": "PBJ Sandwich", "cal": 603, "p": 18, "f": 32, "c": 69}
  ]
}
```

### nutrition_stats

Statistical summary of daily totals. ~34 tokens.

**Parameters:**
- `start_date`: YYYY-MM-DD (optional)
- `end_date`: YYYY-MM-DD (optional)

```json
{
  "cal": {"avg": 2185, "med": 2453, "std": 821},
  "p": {"avg": 94, "med": 102},
  "f": {"avg": 102, "med": 112},
  "c": {"avg": 236, "med": 256}
}
```

### nutrition_compare

Compare two periods. ~56 tokens.

**Parameters:**
- `period1_start`, `period1_end`: first period range
- `period2_start`, `period2_end`: second period range

```json
{
  "p1": {"rng": "2025-11-20/2025-11-23", "cal": 2483, "p": 104, "f": 114, "c": 284, "n": 3},
  "p2": {"rng": "2025-11-24/2025-11-27", "cal": 2435, "p": 105, "f": 117, "c": 252, "n": 4},
  "d": {"cal": -48, "p": 1, "f": 3, "c": -32}
}
```

## Activity Tools

### activity_summary

Quick overview - latest activity + date range. ~34 tokens.

```json
{
  "last": {"d": "2025-11-24", "type": "walking", "dur": 74, "dist": 3.6, "hr": 77},
  "rng": {"s": "2025-09-14", "e": "2025-11-24", "n": 40}
}
```

### activity_trend

Aggregated by period. ~65-200 tokens depending on limit.

**Parameters:**
- `period`: week | month | quarter | year
- `limit`: number of periods (default 12)

```json
{
  "d": [
    {"p": "2025-W46", "n": 4, "dur": 188, "dist": 18.9, "hr": 142},
    {"p": "2025-W47", "n": 1, "dur": 74, "dist": 3.6, "hr": 77}
  ]
}
```

### activity_records

Paginated activity list. ~32 tokens per record.

**Parameters:**
- `activity_type`: filter by type (optional) - running, walking, cycling, etc.
- `start_date`: YYYY-MM-DD (optional)
- `end_date`: YYYY-MM-DD (optional)
- `page`: page number (default 1)
- `page_size`: records per page (default 20)

```json
{
  "r": [
    {"d": "2025-11-23", "type": "running", "title": "San Ramon Running", "dur": 63, "dist": 6.2, "pace": 10.1, "hr": 143}
  ],
  "pg": 1,
  "pgs": 8,
  "n": 40
}
```

### activity_stats

Statistical summary. ~36 tokens.

**Parameters:**
- `activity_type`: filter by type (optional)
- `start_date`: YYYY-MM-DD (optional)
- `end_date`: YYYY-MM-DD (optional)

```json
{
  "n": 40,
  "dur": {"tot": 1940, "avg": 48},
  "dist": {"tot": 182.1, "avg": 4.6},
  "pace": {"avg": 10.9, "best": 7.3},
  "hr": {"avg": 138, "max": 173}
}
```

### activity_compare

Compare two periods. ~55 tokens.

**Parameters:**
- `period1_start`, `period1_end`: first period range
- `period2_start`, `period2_end`: second period range

```json
{
  "p1": {"rng": "2025-10-01/2025-10-31", "n": 16, "dist": 69.0, "dur": 766, "hr": 136},
  "p2": {"rng": "2025-11-01/2025-11-24", "n": 15, "dist": 68.8, "dur": 733, "hr": 137},
  "d": {"n": -1, "dist": -0.2, "dur": -33, "hr": 1}
}
```

## Resting HR Tools

### rhr_summary

Quick overview - latest reading + date range. ~24 tokens.

```json
{
  "cur": {"d": "2025-11-24", "hr": 52},
  "rng": {"s": "2018-09-12", "e": "2025-11-24", "n": 1654}
}
```

### rhr_trend

Aggregated by period. ~46-150 tokens.

**Parameters:**
- `period`: week | month | quarter | year
- `limit`: number of periods (default 12)

```json
{
  "d": [
    {"p": "2025-10", "avg": 51, "min": 49, "max": 57, "n": 24},
    {"p": "2025-11", "avg": 53, "min": 51, "max": 58, "n": 16}
  ]
}
```

### rhr_records

Paginated daily readings. ~9 tokens per record.

**Parameters:**
- `start_date`: YYYY-MM-DD (optional)
- `end_date`: YYYY-MM-DD (optional)
- `page`: page number (default 1)
- `page_size`: records per page (default 30, max 50)

```json
{
  "r": [
    {"d": "2025-11-24", "hr": 52},
    {"d": "2025-11-22", "hr": 53}
  ],
  "pg": 1,
  "pgs": 166,
  "n": 1654
}
```

### rhr_stats

Statistical summary. ~13 tokens.

**Parameters:**
- `start_date`: YYYY-MM-DD (optional)
- `end_date`: YYYY-MM-DD (optional)

```json
{
  "n": 1654,
  "avg": 56,
  "min": 39,
  "max": 103,
  "std": 6
}
```

## VO2 Max Tools

### vo2max_summary

Quick overview - latest reading + date range. ~30 tokens.

```json
{
  "cur": {"d": "2025-11-27", "vo2": 50.1},
  "rng": {"s": "2024-01-01", "e": "2025-11-27", "n": 738}
}
```

### vo2max_trend

Aggregated by period. ~50-150 tokens.

**Parameters:**
- `period`: week | month | quarter | year
- `limit`: number of periods (default 12)

```json
{
  "d": [
    {"p": "2025-10", "avg": 49.8, "min": 49.2, "max": 50.3, "n": 12},
    {"p": "2025-11", "avg": 50.0, "min": 49.6, "max": 50.3, "n": 15}
  ]
}
```

### vo2max_records

Paginated readings. ~12 tokens per record.

**Parameters:**
- `start_date`: YYYY-MM-DD (optional)
- `end_date`: YYYY-MM-DD (optional)
- `page`: page number (default 1)
- `page_size`: records per page (default 30, max 50)

```json
{
  "r": [
    {"d": "2025-11-27", "vo2": 50.1},
    {"d": "2025-11-25", "vo2": 49.9}
  ],
  "pg": 1,
  "pgs": 74,
  "n": 738
}
```

### vo2max_stats

Statistical summary. ~15 tokens.

**Parameters:**
- `start_date`: YYYY-MM-DD (optional)
- `end_date`: YYYY-MM-DD (optional)

```json
{
  "n": 738,
  "avg": 47.7,
  "min": 44.8,
  "max": 50.9,
  "std": 1.3
}
```

## Token Efficiency

Key mappings:
- `d`=date, `t`=time, `wt`=weight, `fat`=body_fat, `m`=muscle, `b`=bone, `w`=water
- `cal`=calories, `prot`=protein (in trend), `p`=protein (elsewhere), `f`=fat, `c`=carbs
- `type`=activity_type, `dur`=duration (minutes), `dist`=distance (miles), `pace`=min/mile, `hr`=heart rate
- `vo2`=VO2 Max (ml/kg/min)
- `cur`=current/latest, `last`=latest, `rng`=range, `s`=start, `e`=end, `n`=count
- `tot`=total, `items`=food items, `p`=period (in trend), `best`=best value
- `r`=records, `pg`=page, `pgs`=pages
- `avg`=mean, `med`=median, `std`=standard deviation, `chg`=change

Other optimizations:
- 1 decimal precision
- Nulls omitted
- Max 50 records per page

## Request Logging

All requests logged to `mcp_requests` table. View in dashboard MCP tab.

## Testing

```bash
python scripts/test_mcp.py
```

## Files

```
health_import/mcp/
├── __init__.py    # Package init
├── __main__.py    # Entry point
├── server.py      # FastMCP server
├── weight.py      # Weight tool implementations
├── nutrition.py   # Nutrition tool implementations
├── activity.py    # Activity tool implementations
├── resting_hr.py  # Resting HR tool implementations
└── vo2max.py      # VO2 Max tool implementations
```

Logs: `logs/mcp.log`
