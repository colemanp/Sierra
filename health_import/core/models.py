"""Data models for health data import"""
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ImportResult:
    """Result of an import operation"""
    processed: int = 0
    inserted: int = 0
    skipped: int = 0
    conflicted: int = 0

    def __str__(self) -> str:
        return (
            f"Processed: {self.processed}, "
            f"Inserted: {self.inserted}, "
            f"Skipped: {self.skipped}, "
            f"Conflicts: {self.conflicted}"
        )


@dataclass
class Activity:
    """Activity record"""
    source_id: int
    start_time: str
    activity_type_id: Optional[int] = None
    source_record_id: Optional[str] = None
    end_time: Optional[str] = None
    duration_seconds: Optional[float] = None
    moving_time_seconds: Optional[float] = None
    title: Optional[str] = None
    distance_miles: Optional[float] = None
    calories_total: Optional[float] = None
    calories_active: Optional[float] = None
    avg_speed_mph: Optional[float] = None
    max_speed_mph: Optional[float] = None
    avg_pace_min_per_mile: Optional[float] = None
    best_pace_min_per_mile: Optional[float] = None
    avg_hr: Optional[int] = None
    max_hr: Optional[int] = None
    elevation_gain_ft: Optional[float] = None
    elevation_loss_ft: Optional[float] = None
    min_elevation_ft: Optional[float] = None
    max_elevation_ft: Optional[float] = None
    is_indoor: int = 0
    device_name: Optional[str] = None


@dataclass
class RunningDynamics:
    """Running dynamics for an activity"""
    activity_id: int
    avg_cadence: Optional[int] = None
    max_cadence: Optional[int] = None
    avg_stride_length_ft: Optional[float] = None
    avg_vertical_ratio: Optional[float] = None
    avg_vertical_oscillation_in: Optional[float] = None
    avg_ground_contact_time_ms: Optional[int] = None
    avg_gap_min_per_mile: Optional[float] = None
    training_stress_score: Optional[float] = None
    normalized_power_watts: Optional[int] = None
    avg_power_watts: Optional[int] = None
    max_power_watts: Optional[int] = None


@dataclass
class GarminExtras:
    """Garmin-specific activity extras"""
    activity_id: int
    aerobic_te: Optional[float] = None
    steps: Optional[int] = None
    body_battery_drain: Optional[int] = None
    grit: Optional[float] = None
    flow: Optional[float] = None
    laps: Optional[int] = None
    best_lap_time_seconds: Optional[float] = None
    avg_respiration: Optional[int] = None
    min_respiration: Optional[int] = None
    max_respiration: Optional[int] = None


@dataclass
class BodyMeasurement:
    """Body measurement record"""
    source_id: int
    measurement_date: str
    measurement_time: Optional[str] = None
    weight_lbs: Optional[float] = None
    weight_change_lbs: Optional[float] = None
    bmi: Optional[float] = None
    body_fat_pct: Optional[float] = None
    muscle_mass_lbs: Optional[float] = None
    bone_mass_lbs: Optional[float] = None
    body_water_pct: Optional[float] = None
    lean_body_mass_lbs: Optional[float] = None
    visceral_fat_level: Optional[int] = None
    basal_metabolic_rate_kcal: Optional[float] = None


@dataclass
class VO2Max:
    """VO2 Max measurement"""
    source_id: int
    measurement_date: str
    vo2max_value: float
    activity_type: Optional[str] = None


@dataclass
class RestingHeartRate:
    """Resting heart rate measurement"""
    source_id: int
    measurement_date: str
    resting_hr: int
    source_name: Optional[str] = None


@dataclass
class StrengthWorkout:
    """Strength training workout"""
    source_id: int
    exercise_id: int
    workout_date: str
    workout_time: Optional[str] = None
    goal_value: Optional[float] = None
    program_name: Optional[str] = None
    week_number: Optional[int] = None
    day_number: Optional[int] = None
    set1: Optional[float] = None
    set2: Optional[float] = None
    set3: Optional[float] = None
    set4: Optional[float] = None
    set5: Optional[float] = None
    total_value: Optional[float] = None
    duration_seconds: Optional[int] = None
    calories: Optional[int] = None


@dataclass
class NutritionDaily:
    """Daily nutrition summary"""
    source_id: int
    date: str
    expenditure_kcal: Optional[float] = None
    calories_consumed_kcal: Optional[float] = None
    target_calories_kcal: Optional[float] = None
    weight_lbs: Optional[float] = None
    trend_weight_lbs: Optional[float] = None
    protein_g: Optional[float] = None
    fat_g: Optional[float] = None
    carbs_g: Optional[float] = None
    fiber_g: Optional[float] = None
    alcohol_g: Optional[float] = None
    target_protein_g: Optional[float] = None
    target_fat_g: Optional[float] = None
    target_carbs_g: Optional[float] = None
    steps: Optional[int] = None


@dataclass
class NutritionEntry:
    """Individual food entry"""
    source_id: int
    date: str
    food_name: str
    daily_id: Optional[int] = None
    time: Optional[str] = None
    serving_size: Optional[str] = None
    serving_qty: Optional[float] = None
    serving_weight_g: Optional[float] = None
    calories_kcal: Optional[float] = None
    protein_g: Optional[float] = None
    fat_g: Optional[float] = None
    carbs_g: Optional[float] = None
    fiber_g: Optional[float] = None
