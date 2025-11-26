-- Health Data Import Schema
-- Units: Imperial (lbs, miles, mph, min/mile)

-- ============================================
-- METADATA & AUDIT TABLES
-- ============================================

CREATE TABLE IF NOT EXISTS data_sources (
    id INTEGER PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    description TEXT,
    file_pattern TEXT
);

CREATE TABLE IF NOT EXISTS import_log (
    id INTEGER PRIMARY KEY,
    source_id INTEGER NOT NULL REFERENCES data_sources(id),
    file_path TEXT NOT NULL,
    import_timestamp TEXT NOT NULL DEFAULT (datetime('now')),
    records_processed INTEGER DEFAULT 0,
    records_inserted INTEGER DEFAULT 0,
    records_skipped INTEGER DEFAULT 0,
    records_conflicted INTEGER DEFAULT 0,
    status TEXT CHECK(status IN ('running', 'completed', 'failed')) DEFAULT 'running',
    error_message TEXT
);

CREATE TABLE IF NOT EXISTS import_conflicts (
    id INTEGER PRIMARY KEY,
    import_id INTEGER NOT NULL REFERENCES import_log(id),
    table_name TEXT NOT NULL,
    record_key TEXT NOT NULL,
    existing_value TEXT,
    new_value TEXT,
    conflict_fields TEXT,
    resolution TEXT CHECK(resolution IN ('kept_existing', 'overwritten', 'manual')) DEFAULT 'kept_existing',
    resolved_timestamp TEXT
);

-- ============================================
-- ACTIVITY TABLES
-- ============================================

CREATE TABLE IF NOT EXISTS activity_types (
    id INTEGER PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    category TEXT,
    healthkit_type TEXT,
    garmin_type TEXT
);

CREATE TABLE IF NOT EXISTS activities (
    id INTEGER PRIMARY KEY,
    source_id INTEGER NOT NULL REFERENCES data_sources(id),
    source_record_id TEXT,
    activity_type_id INTEGER REFERENCES activity_types(id),
    start_time TEXT NOT NULL,
    end_time TEXT,
    duration_seconds REAL,
    moving_time_seconds REAL,
    title TEXT,
    distance_miles REAL,
    calories_total REAL,
    calories_active REAL,
    avg_speed_mph REAL,
    max_speed_mph REAL,
    avg_pace_min_per_mile REAL,
    best_pace_min_per_mile REAL,
    avg_hr INTEGER,
    max_hr INTEGER,
    elevation_gain_ft REAL,
    elevation_loss_ft REAL,
    min_elevation_ft REAL,
    max_elevation_ft REAL,
    is_indoor INTEGER DEFAULT 0,
    device_name TEXT,
    import_id INTEGER REFERENCES import_log(id),
    created_at TEXT DEFAULT (datetime('now')),
    UNIQUE(source_id, start_time, activity_type_id)
);

CREATE TABLE IF NOT EXISTS activity_running_dynamics (
    activity_id INTEGER PRIMARY KEY REFERENCES activities(id),
    avg_cadence INTEGER,
    max_cadence INTEGER,
    avg_stride_length_ft REAL,
    avg_vertical_ratio REAL,
    avg_vertical_oscillation_in REAL,
    avg_ground_contact_time_ms INTEGER,
    avg_gap_min_per_mile REAL,
    training_stress_score REAL,
    normalized_power_watts INTEGER,
    avg_power_watts INTEGER,
    max_power_watts INTEGER
);

CREATE TABLE IF NOT EXISTS activity_garmin_extras (
    activity_id INTEGER PRIMARY KEY REFERENCES activities(id),
    aerobic_te REAL,
    steps INTEGER,
    body_battery_drain INTEGER,
    grit REAL,
    flow REAL,
    laps INTEGER,
    best_lap_time_seconds REAL,
    avg_respiration INTEGER,
    min_respiration INTEGER,
    max_respiration INTEGER
);

-- ============================================
-- BODY MEASUREMENTS
-- ============================================

CREATE TABLE IF NOT EXISTS body_measurements (
    id INTEGER PRIMARY KEY,
    source_id INTEGER NOT NULL REFERENCES data_sources(id),
    measurement_date TEXT NOT NULL,
    measurement_time TEXT,
    weight_lbs REAL,
    weight_change_lbs REAL,
    bmi REAL,
    body_fat_pct REAL,
    muscle_mass_lbs REAL,
    bone_mass_lbs REAL,
    body_water_pct REAL,
    lean_body_mass_lbs REAL,
    visceral_fat_level INTEGER,
    basal_metabolic_rate_kcal REAL,
    import_id INTEGER REFERENCES import_log(id),
    created_at TEXT DEFAULT (datetime('now')),
    UNIQUE(source_id, measurement_date, measurement_time)
);

CREATE TABLE IF NOT EXISTS garmin_vo2max (
    id INTEGER PRIMARY KEY,
    source_id INTEGER NOT NULL REFERENCES data_sources(id),
    measurement_date TEXT NOT NULL,
    activity_type TEXT,
    vo2max_value REAL NOT NULL,
    import_id INTEGER REFERENCES import_log(id),
    created_at TEXT DEFAULT (datetime('now')),
    UNIQUE(source_id, measurement_date, activity_type)
);

CREATE TABLE IF NOT EXISTS resting_heart_rate (
    id INTEGER PRIMARY KEY,
    source_id INTEGER NOT NULL REFERENCES data_sources(id),
    measurement_date TEXT NOT NULL,
    resting_hr INTEGER NOT NULL,
    source_name TEXT,
    import_id INTEGER REFERENCES import_log(id),
    created_at TEXT DEFAULT (datetime('now')),
    UNIQUE(source_id, measurement_date)
);

-- ============================================
-- STRENGTH TRAINING
-- ============================================

CREATE TABLE IF NOT EXISTS strength_exercises (
    id INTEGER PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    display_name TEXT,
    category TEXT,
    unit TEXT DEFAULT 'reps'
);

CREATE TABLE IF NOT EXISTS strength_workouts (
    id INTEGER PRIMARY KEY,
    source_id INTEGER NOT NULL REFERENCES data_sources(id),
    exercise_id INTEGER NOT NULL REFERENCES strength_exercises(id),
    workout_date TEXT NOT NULL,
    workout_time TEXT,
    goal_value REAL,
    program_name TEXT,
    week_number INTEGER,
    day_number INTEGER,
    set1 REAL,
    set2 REAL,
    set3 REAL,
    set4 REAL,
    set5 REAL,
    total_value REAL,
    duration_seconds INTEGER,
    calories INTEGER,
    import_id INTEGER REFERENCES import_log(id),
    created_at TEXT DEFAULT (datetime('now')),
    UNIQUE(source_id, workout_date, exercise_id, workout_time)
);

-- ============================================
-- NUTRITION
-- ============================================

CREATE TABLE IF NOT EXISTS nutrition_daily (
    id INTEGER PRIMARY KEY,
    source_id INTEGER NOT NULL REFERENCES data_sources(id),
    date TEXT NOT NULL,
    expenditure_kcal REAL,
    calories_consumed_kcal REAL,
    target_calories_kcal REAL,
    weight_lbs REAL,
    trend_weight_lbs REAL,
    protein_g REAL,
    fat_g REAL,
    carbs_g REAL,
    fiber_g REAL,
    alcohol_g REAL,
    target_protein_g REAL,
    target_fat_g REAL,
    target_carbs_g REAL,
    steps INTEGER,
    import_id INTEGER REFERENCES import_log(id),
    created_at TEXT DEFAULT (datetime('now')),
    UNIQUE(source_id, date)
);

CREATE TABLE IF NOT EXISTS nutrition_entries (
    id INTEGER PRIMARY KEY,
    daily_id INTEGER REFERENCES nutrition_daily(id),
    source_id INTEGER NOT NULL REFERENCES data_sources(id),
    date TEXT NOT NULL,
    time TEXT,
    food_name TEXT NOT NULL,
    serving_size TEXT,
    serving_qty REAL,
    serving_weight_g REAL,
    calories_kcal REAL,
    protein_g REAL,
    fat_g REAL,
    carbs_g REAL,
    fiber_g REAL,
    import_id INTEGER REFERENCES import_log(id),
    created_at TEXT DEFAULT (datetime('now')),
    UNIQUE(source_id, date, time, food_name)
);

CREATE TABLE IF NOT EXISTS nutrition_micros (
    entry_id INTEGER PRIMARY KEY REFERENCES nutrition_entries(id),
    vitamin_a_mcg REAL,
    vitamin_c_mg REAL,
    vitamin_d_mcg REAL,
    vitamin_e_mg REAL,
    vitamin_k_mcg REAL,
    b1_thiamine_mg REAL,
    b2_riboflavin_mg REAL,
    b3_niacin_mg REAL,
    b5_pantothenic_mg REAL,
    b6_pyridoxine_mg REAL,
    b12_cobalamin_mcg REAL,
    folate_mcg REAL,
    choline_mg REAL,
    calcium_mg REAL,
    iron_mg REAL,
    magnesium_mg REAL,
    phosphorus_mg REAL,
    potassium_mg REAL,
    sodium_mg REAL,
    zinc_mg REAL,
    copper_mg REAL,
    manganese_mg REAL,
    selenium_mcg REAL,
    saturated_fat_g REAL,
    monounsaturated_fat_g REAL,
    polyunsaturated_fat_g REAL,
    trans_fat_g REAL,
    cholesterol_mg REAL,
    omega3_g REAL,
    omega6_g REAL,
    sugars_g REAL,
    sugars_added_g REAL,
    starch_g REAL,
    caffeine_mg REAL,
    water_g REAL
);

-- ============================================
-- APPLE HEALTHKIT (future expansion)
-- ============================================

CREATE TABLE IF NOT EXISTS healthkit_records (
    id INTEGER PRIMARY KEY,
    source_id INTEGER NOT NULL REFERENCES data_sources(id),
    record_type TEXT NOT NULL,
    start_time TEXT NOT NULL,
    end_time TEXT,
    value REAL,
    unit TEXT,
    source_name TEXT,
    source_version TEXT,
    device TEXT,
    import_id INTEGER REFERENCES import_log(id),
    created_at TEXT DEFAULT (datetime('now')),
    UNIQUE(record_type, start_time, source_name)
);

CREATE TABLE IF NOT EXISTS sleep_records (
    id INTEGER PRIMARY KEY,
    source_id INTEGER NOT NULL REFERENCES data_sources(id),
    date TEXT NOT NULL,
    start_time TEXT NOT NULL,
    end_time TEXT NOT NULL,
    sleep_stage TEXT,
    duration_seconds REAL,
    source_name TEXT,
    import_id INTEGER REFERENCES import_log(id),
    created_at TEXT DEFAULT (datetime('now')),
    UNIQUE(source_id, start_time, sleep_stage)
);

CREATE TABLE IF NOT EXISTS daily_activity_summary (
    id INTEGER PRIMARY KEY,
    source_id INTEGER NOT NULL REFERENCES data_sources(id),
    date TEXT NOT NULL,
    active_energy_burned_kcal REAL,
    active_energy_goal_kcal REAL,
    exercise_time_min INTEGER,
    exercise_goal_min INTEGER,
    stand_hours INTEGER,
    stand_goal_hours INTEGER,
    import_id INTEGER REFERENCES import_log(id),
    created_at TEXT DEFAULT (datetime('now')),
    UNIQUE(source_id, date)
);

-- ============================================
-- INDEXES
-- ============================================

CREATE INDEX IF NOT EXISTS idx_activities_date ON activities(start_time);
CREATE INDEX IF NOT EXISTS idx_activities_type ON activities(activity_type_id);
CREATE INDEX IF NOT EXISTS idx_body_measurements_date ON body_measurements(measurement_date);
CREATE INDEX IF NOT EXISTS idx_garmin_vo2max_date ON garmin_vo2max(measurement_date);
CREATE INDEX IF NOT EXISTS idx_resting_hr_date ON resting_heart_rate(measurement_date);
CREATE INDEX IF NOT EXISTS idx_nutrition_daily_date ON nutrition_daily(date);
CREATE INDEX IF NOT EXISTS idx_strength_workouts_date ON strength_workouts(workout_date);
CREATE INDEX IF NOT EXISTS idx_healthkit_records_type ON healthkit_records(record_type);
CREATE INDEX IF NOT EXISTS idx_healthkit_records_time ON healthkit_records(start_time);
CREATE INDEX IF NOT EXISTS idx_sleep_records_date ON sleep_records(date);
CREATE INDEX IF NOT EXISTS idx_import_log_source ON import_log(source_id);

-- ============================================
-- SEED DATA
-- ============================================

INSERT OR IGNORE INTO data_sources (name, description, file_pattern) VALUES
    ('garmin_activities', 'Garmin Connect activity exports', '*.csv'),
    ('garmin_weight', 'Garmin Connect weight/body composition', '*.csv'),
    ('garmin_vo2max', 'Garmin VO2 Max tracking CSV', '*.csv'),
    ('six_week', 'Just 6 Weeks strength training app', '*.csv'),
    ('macrofactor', 'MacroFactor nutrition tracking', '*.xlsx'),
    ('apple_healthkit', 'Apple Health export', 'export.xml');

INSERT OR IGNORE INTO activity_types (name, category, healthkit_type, garmin_type) VALUES
    ('running', 'cardio', 'HKWorkoutActivityTypeRunning', 'Running'),
    ('treadmill_running', 'cardio', 'HKWorkoutActivityTypeRunning', 'Treadmill Running'),
    ('walking', 'cardio', 'HKWorkoutActivityTypeWalking', 'Walking'),
    ('hiking', 'cardio', 'HKWorkoutActivityTypeHiking', 'Hiking'),
    ('cycling', 'cardio', 'HKWorkoutActivityTypeCycling', 'Cycling'),
    ('ebiking', 'cardio', 'HKWorkoutActivityTypeCycling', 'E-Bike Ride'),
    ('elliptical', 'cardio', 'HKWorkoutActivityTypeElliptical', 'Elliptical'),
    ('strength', 'strength', 'HKWorkoutActivityTypeFunctionalStrengthTraining', 'Strength Training'),
    ('swimming', 'cardio', 'HKWorkoutActivityTypeSwimming', 'Pool Swimming');

INSERT OR IGNORE INTO strength_exercises (name, display_name, category, unit) VALUES
    ('push_ups', 'Push-ups', 'upper_body', 'reps'),
    ('pull_ups', 'Pull-ups', 'upper_body', 'reps'),
    ('plank', 'Plank', 'core', 'seconds');
