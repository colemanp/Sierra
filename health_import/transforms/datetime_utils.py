"""Date and time parsing utilities"""
from datetime import datetime
from typing import Optional, Tuple


def parse_garmin_datetime(dt_str: Optional[str]) -> Optional[str]:
    """
    Parse Garmin datetime format to ISO 8601.

    Input: "2025-11-24 16:00:58" or "2025-11-24"
    Output: "2025-11-24T16:00:58" or "2025-11-24"
    """
    if not dt_str or dt_str.strip() == "":
        return None

    dt_str = dt_str.strip()

    # Already ISO format
    if "T" in dt_str:
        return dt_str

    # Garmin format with space
    if " " in dt_str:
        try:
            dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
            return dt.isoformat()
        except ValueError:
            pass

    # Date only
    try:
        dt = datetime.strptime(dt_str, "%Y-%m-%d")
        return dt_str
    except ValueError:
        pass

    return dt_str


def parse_garmin_date(date_str: Optional[str]) -> Optional[str]:
    """
    Parse various date formats to YYYY-MM-DD.

    Supports:
        - "Nov 25, 2025"
        - "11/25/2025"
        - "2025-11-25"
    """
    if not date_str or date_str.strip() == "":
        return None

    date_str = date_str.strip()

    # Try various formats
    formats = [
        "%b %d, %Y",      # Nov 25, 2025
        "%B %d, %Y",      # November 25, 2025
        "%m/%d/%Y",       # 11/25/2025
        "%Y-%m-%d",       # 2025-11-25
        "%d/%m/%Y",       # 25/11/2025 (EU format)
    ]

    for fmt in formats:
        try:
            dt = datetime.strptime(date_str, fmt)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue

    return None


def parse_garmin_duration(duration_str: Optional[str]) -> Optional[float]:
    """
    Parse Garmin duration string to seconds.

    Supports:
        - "1:30:00" (HH:MM:SS)
        - "45:30" (MM:SS)
        - "30" (SS)
        - "--" (empty)
    """
    if not duration_str or duration_str == "--" or duration_str.strip() == "":
        return None

    try:
        parts = duration_str.strip().split(":")
        if len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
        elif len(parts) == 2:
            return int(parts[0]) * 60 + float(parts[1])
        elif len(parts) == 1:
            return float(parts[0])
    except (ValueError, IndexError):
        pass

    return None


def parse_time_12h(time_str: Optional[str]) -> Optional[str]:
    """
    Parse 12-hour time format to 24-hour HH:MM:SS.

    Input: "9:25 AM", "3:45 PM"
    Output: "09:25:00", "15:45:00"
    """
    if not time_str or time_str.strip() == "":
        return None

    time_str = time_str.strip().upper()

    try:
        # Try with seconds
        dt = datetime.strptime(time_str, "%I:%M:%S %p")
        return dt.strftime("%H:%M:%S")
    except ValueError:
        pass

    try:
        # Without seconds
        dt = datetime.strptime(time_str, "%I:%M %p")
        return dt.strftime("%H:%M:%S")
    except ValueError:
        pass

    return None


def parse_datetime_combined(date_str: str, time_str: Optional[str]) -> Tuple[str, Optional[str]]:
    """
    Parse date and optional time strings.

    Returns: (date_iso, time_24h or None)
    """
    date_iso = parse_garmin_date(date_str)
    if not date_iso:
        raise ValueError(f"Could not parse date: {date_str}")

    time_24h = None
    if time_str:
        time_24h = parse_time_12h(time_str)

    return (date_iso, time_24h)


def parse_six_week_datetime(dt_str: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
    """
    Parse 6-week challenge datetime format.

    Input: "1/24/2024 8:16 PM"
    Output: ("2024-01-24", "20:16:00")
    """
    if not dt_str or dt_str.strip() == "":
        return (None, None)

    parts = dt_str.strip().split(" ", 1)
    if len(parts) < 2:
        # Date only
        date_iso = parse_garmin_date(parts[0])
        return (date_iso, None)

    date_part = parts[0]
    time_part = parts[1] if len(parts) > 1 else None

    date_iso = parse_garmin_date(date_part)
    time_24h = parse_time_12h(time_part) if time_part else None

    return (date_iso, time_24h)
