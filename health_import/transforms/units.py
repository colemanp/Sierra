"""Unit conversion utilities

All conversions are TO imperial (our storage format).
"""
from typing import Optional


# Weight conversions
def kg_to_lbs(kg: Optional[float]) -> Optional[float]:
    """Convert kilograms to pounds"""
    if kg is None:
        return None
    return kg * 2.20462


def lbs_to_kg(lbs: Optional[float]) -> Optional[float]:
    """Convert pounds to kilograms"""
    if lbs is None:
        return None
    return lbs / 2.20462


# Distance conversions
def km_to_miles(km: Optional[float]) -> Optional[float]:
    """Convert kilometers to miles"""
    if km is None:
        return None
    return km * 0.621371


def miles_to_km(miles: Optional[float]) -> Optional[float]:
    """Convert miles to kilometers"""
    if miles is None:
        return None
    return miles / 0.621371


def meters_to_feet(meters: Optional[float]) -> Optional[float]:
    """Convert meters to feet"""
    if meters is None:
        return None
    return meters * 3.28084


def feet_to_meters(feet: Optional[float]) -> Optional[float]:
    """Convert feet to meters"""
    if feet is None:
        return None
    return feet / 3.28084


def cm_to_inches(cm: Optional[float]) -> Optional[float]:
    """Convert centimeters to inches"""
    if cm is None:
        return None
    return cm * 0.393701


def inches_to_cm(inches: Optional[float]) -> Optional[float]:
    """Convert inches to centimeters"""
    if inches is None:
        return None
    return inches / 0.393701


# Speed conversions
def kph_to_mph(kph: Optional[float]) -> Optional[float]:
    """Convert km/h to mph"""
    if kph is None:
        return None
    return kph * 0.621371


def mph_to_kph(mph: Optional[float]) -> Optional[float]:
    """Convert mph to km/h"""
    if mph is None:
        return None
    return mph / 0.621371


# Pace conversions
def pace_min_per_km_to_min_per_mile(pace_km: Optional[float]) -> Optional[float]:
    """Convert min/km pace to min/mile"""
    if pace_km is None:
        return None
    return pace_km * 1.60934


def pace_str_to_min_per_mile(pace_str: Optional[str]) -> Optional[float]:
    """
    Convert pace string (MM:SS or M:SS) to decimal minutes per mile.
    Assumes input is already in min/mile format.

    Examples:
        "9:30" -> 9.5
        "10:15" -> 10.25
        "--" -> None
    """
    if not pace_str or pace_str == "--" or pace_str.strip() == "":
        return None

    try:
        parts = pace_str.split(":")
        if len(parts) == 2:
            minutes = int(parts[0])
            seconds = int(parts[1])
            return minutes + seconds / 60.0
    except (ValueError, IndexError):
        pass

    return None


def duration_str_to_seconds(duration_str: Optional[str]) -> Optional[float]:
    """
    Convert duration string to seconds.
    Supports: HH:MM:SS, MM:SS, SS

    Examples:
        "1:30:00" -> 5400
        "45:30" -> 2730
        "30" -> 30
        "--" -> None
    """
    if not duration_str or duration_str == "--" or duration_str.strip() == "":
        return None

    try:
        parts = duration_str.split(":")
        if len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
        elif len(parts) == 2:
            return int(parts[0]) * 60 + int(parts[1])
        elif len(parts) == 1:
            return int(parts[0])
    except (ValueError, IndexError):
        pass

    return None
