"""Garmin Import tab component"""
import streamlit as st
from datetime import date, timedelta

from health_import.garmin.vo2max import GarminVO2MaxFetcher, import_vo2max_to_db
from health_import.garmin.activities import GarminActivityFetcher, import_activities_to_db
from health_import.garmin.weight import GarminWeightFetcher, import_weight_to_db, convert_api_weight


def _get_source_id(conn, source_name: str) -> int:
    """Get or create data source ID"""
    row = conn.execute(
        "SELECT id FROM data_sources WHERE name = ?", (source_name,)
    ).fetchone()
    if row:
        return row[0]
    # Create if missing
    cursor = conn.execute(
        "INSERT INTO data_sources (name, description) VALUES (?, ?)",
        (source_name, f"Garmin Connect API - {source_name}")
    )
    conn.commit()
    return cursor.lastrowid


def render_garmin_import(conn):
    """Render Garmin Import tab"""
    col_header, col_reload = st.columns([6, 1])
    col_header.header("Garmin Import")
    if col_reload.button("Reload", key="garmin_reload"):
        st.rerun()

    # Check login status
    fetcher = GarminVO2MaxFetcher()
    logged_in = fetcher.is_logged_in()

    if logged_in:
        st.success(f"Logged in as {fetcher.get_user_name()}")
    else:
        st.warning("Not logged in to Garmin Connect")
        st.info("Run the test_garmin.py script to authenticate, or credentials will be cached from previous sessions.")
        return

    st.divider()

    # Date range selection
    st.subheader("Date Range")

    range_mode = st.radio("Mode", ["Last N Days", "Custom Range"], horizontal=True, key="garmin_range_mode")

    if range_mode == "Last N Days":
        days_back = st.number_input("Days", min_value=1, max_value=9999, value=90, key="garmin_days_back")
        start_date = date.today() - timedelta(days=days_back)
        end_date = date.today()
    else:
        col1, col2 = st.columns(2)
        default_start = date.today() - timedelta(days=90)
        min_date = date(2000, 1, 1)
        with col1:
            start_date = st.date_input("Start Date", value=default_start, min_value=min_date, key="garmin_start")
        with col2:
            end_date = st.date_input("End Date", value=date.today(), min_value=min_date, key="garmin_end")

        if not start_date or not end_date:
            st.error("Please select both start and end dates")
            return

        if start_date > end_date:
            st.error("Start date must be before end date")
            return

    st.divider()

    # Import buttons
    st.subheader("Import Data")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        import_activities = st.button("Import Activities", type="primary", key="import_activities")
    with col2:
        import_vo2max = st.button("Import VO2 Max", type="primary", key="import_vo2max")
    with col3:
        import_weight = st.button("Import Weight", type="primary", key="import_weight")
    with col4:
        import_all = st.button("Import All", type="secondary", key="import_all")

    st.divider()

    # Results container
    results_container = st.container()

    # Initialize session state for results
    if "garmin_results" not in st.session_state:
        st.session_state.garmin_results = {}

    # Handle imports
    if import_activities or import_all:
        with st.status("Importing activities...", expanded=True) as status:
            result = _import_activities(conn, start_date, end_date, status)
            st.session_state.garmin_results["activities"] = result
            if "error" in result:
                status.update(label="Activities: Error", state="error")
            else:
                status.update(label=f"Activities: {result.get('inserted', 0)} new, {result.get('skipped', 0)} skipped", state="complete")

    if import_vo2max or import_all:
        with st.status("Importing VO2 Max...", expanded=True) as status:
            result = _import_vo2max(conn, start_date, end_date, status)
            st.session_state.garmin_results["vo2max"] = result
            if "error" in result:
                status.update(label="VO2 Max: Error", state="error")
            else:
                status.update(label=f"VO2 Max: {result.get('inserted', 0)} new, {result.get('skipped', 0)} skipped", state="complete")

    if import_weight or import_all:
        with st.status("Importing weight...", expanded=True) as status:
            result = _import_weight(conn, start_date, end_date, status)
            st.session_state.garmin_results["weight"] = result
            if "error" in result:
                status.update(label="Weight: Error", state="error")
            else:
                status.update(label=f"Weight: {result.get('inserted', 0)} new, {result.get('skipped', 0)} skipped", state="complete")

    # Display results
    with results_container:
        if st.session_state.garmin_results:
            st.subheader("Import Results")

            for key, result in st.session_state.garmin_results.items():
                if "error" in result:
                    st.error(f"{key.title()}: {result['error']}")
                else:
                    processed = result.get("processed", 0)
                    inserted = result.get("inserted", 0)
                    enriched = result.get("enriched", 0)
                    skipped = result.get("skipped", 0)
                    laps = result.get("laps_inserted", 0)

                    parts = [f"{processed} processed"]
                    if inserted:
                        parts.append(f"{inserted} new")
                    if enriched:
                        parts.append(f"{enriched} enriched")
                    if skipped:
                        parts.append(f"{skipped} skipped")
                    if laps:
                        parts.append(f"{laps} laps")

                    st.success(f"{key.title()}: {', '.join(parts)}")


def _import_activities(conn, start_date: date, end_date: date, status) -> dict:
    """Import activities from Garmin"""
    try:
        fetcher = GarminActivityFetcher()
        if not fetcher.is_logged_in():
            return {"error": "Not logged in"}

        status.write(f"Fetching activities from {start_date} to {end_date}...")
        source_id = _get_source_id(conn, "garmin_api")
        activities = fetcher.fetch_activities(start_date, end_date)

        if not activities:
            status.write("No activities found in date range")
            return {"processed": 0, "inserted": 0, "skipped": 0, "laps_inserted": 0}

        status.write(f"Found {len(activities)} activities, importing with laps...")
        result = import_activities_to_db(conn, fetcher, activities, source_id, status)
        return result
    except Exception as e:
        return {"error": str(e)}


def _import_vo2max(conn, start_date: date, end_date: date, status) -> dict:
    """Import VO2 Max from Garmin"""
    try:
        fetcher = GarminVO2MaxFetcher()
        if not fetcher.is_logged_in():
            return {"error": "Not logged in"}

        status.write(f"Fetching VO2 Max from {start_date} to {end_date}...")
        source_id = _get_source_id(conn, "garmin_api")
        readings = fetcher.fetch_vo2max(start_date=start_date, end_date=end_date)

        if not readings:
            status.write("No VO2 Max readings found")
            return {"processed": 0, "inserted": 0, "skipped": 0}

        status.write(f"Found {len(readings)} readings, importing...")
        result = import_vo2max_to_db(conn, readings, source_id)
        return result
    except Exception as e:
        return {"error": str(e)}


def _import_weight(conn, start_date: date, end_date: date, status) -> dict:
    """Import weight from Garmin"""
    try:
        fetcher = GarminWeightFetcher()
        if not fetcher.is_logged_in():
            return {"error": "Not logged in"}

        status.write(f"Fetching weight from {start_date} to {end_date}...")
        source_id = _get_source_id(conn, "garmin_api")
        api_entries = fetcher.fetch_weight(start_date, end_date)

        if not api_entries:
            status.write("No weight entries found")
            return {"processed": 0, "inserted": 0, "skipped": 0}

        status.write(f"Found {len(api_entries)} entries, importing...")
        # Convert API format to standard format
        entries = [convert_api_weight(e) for e in api_entries]
        result = import_weight_to_db(conn, entries, source_id)
        return result
    except Exception as e:
        return {"error": str(e)}
