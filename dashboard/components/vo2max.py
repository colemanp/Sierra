"""VO2 Max import and display tab"""
import streamlit as st
import pandas as pd
import altair as alt
from datetime import date, timedelta

from health_import.garmin.vo2max import (
    GarminVO2MaxFetcher,
    import_vo2max_to_db,
    get_existing_vo2max,
)


def render_vo2max(conn):
    """Render VO2 Max import tab"""
    st.header("VO2 Max")

    # Initialize session state
    if 'garmin_fetcher' not in st.session_state:
        st.session_state.garmin_fetcher = GarminVO2MaxFetcher()
    if 'vo2max_preview' not in st.session_state:
        st.session_state.vo2max_preview = None

    fetcher = st.session_state.garmin_fetcher

    # Check login status
    logged_in = fetcher.is_logged_in()

    # Login section
    if not logged_in:
        st.warning("Not logged in to Garmin Connect")
        with st.expander("Login to Garmin Connect", expanded=True):
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")
            if st.button("Login"):
                try:
                    fetcher.login(email, password)
                    st.success("Login successful!")
                    st.rerun()
                except Exception as e:
                    st.error(str(e))
        return

    # Logged in - show user
    st.success(f"Logged in as: {fetcher.get_user_name()}")

    # Show existing data
    st.subheader("Existing VO2 Max Data")
    existing = get_existing_vo2max(conn)

    if existing:
        df = pd.DataFrame(existing)
        df.columns = ['Date', 'VO2 Max', 'Type']

        col1, col2, col3 = st.columns(3)
        col1.metric("Total Records", len(df))
        col2.metric("Latest", f"{df.iloc[0]['VO2 Max']:.1f}")
        col3.metric("Date Range", f"{df.iloc[-1]['Date']} to {df.iloc[0]['Date']}")

        # Chart with tight Y axis
        chart_df = df[df['Type'] == 'running'].copy()
        if not chart_df.empty:
            chart_df['Date'] = pd.to_datetime(chart_df['Date'])
            chart_df = chart_df.sort_values('Date')

            # Calculate Y axis range with padding
            vo2_min = chart_df['VO2 Max'].min()
            vo2_max = chart_df['VO2 Max'].max()
            padding = (vo2_max - vo2_min) * 0.2
            y_min = vo2_min - padding
            y_max = vo2_max + padding

            chart = alt.Chart(chart_df).mark_line(point=True).encode(
                x=alt.X('Date:T', title='Date'),
                y=alt.Y('VO2 Max:Q', title='VO2 Max (ml/kg/min)',
                        scale=alt.Scale(domain=[y_min, y_max])),
                tooltip=['Date:T', alt.Tooltip('VO2 Max:Q', format='.1f')]
            ).properties(height=250)

            st.altair_chart(chart, use_container_width=True)
    else:
        st.info("No VO2 Max data in database yet")

    st.divider()

    # Fetch section
    st.subheader("Fetch from Garmin")

    fetch_mode = st.radio("Date Range", ["Days Back", "Custom Range"], horizontal=True)

    if fetch_mode == "Days Back":
        days_back = st.slider("Days to fetch", 7, 365, 30)
        start_date = None
        end_date = None
    else:
        col1, col2 = st.columns(2)
        with col1:
            start_date = st.date_input("Start Date", date.today() - timedelta(days=30))
        with col2:
            end_date = st.date_input("End Date", date.today())
        days_back = None

    if st.button("Fetch VO2 Max Data", type="primary"):
        with st.spinner("Fetching from Garmin..."):
            try:
                readings = fetcher.fetch_vo2max(
                    days_back=days_back,
                    start_date=start_date,
                    end_date=end_date
                )
                st.session_state.vo2max_preview = readings
            except Exception as e:
                st.error(f"Fetch failed: {e}")

    # Show preview
    if st.session_state.vo2max_preview:
        readings = st.session_state.vo2max_preview

        st.subheader("Preview")
        st.info(f"Found {len(readings)} VO2 Max readings")

        if readings:
            preview_df = pd.DataFrame(readings)
            preview_df.columns = ['Date', 'VO2 Max', 'Type']
            st.dataframe(preview_df, hide_index=True, use_container_width=True)

            # Import button
            col1, col2 = st.columns([1, 4])
            with col1:
                if st.button("Import to Database", type="primary"):
                    try:
                        # Get source ID
                        source_row = conn.execute(
                            "SELECT id FROM data_sources WHERE name = 'garmin_vo2max'"
                        ).fetchone()
                        if not source_row:
                            st.error("garmin_vo2max source not found in database")
                            return
                        source_id = source_row[0]

                        result = import_vo2max_to_db(conn, readings, source_id)
                        st.success(
                            f"Imported: {result['inserted']} new, "
                            f"{result['skipped']} already existed"
                        )
                        st.session_state.vo2max_preview = None
                        st.rerun()
                    except Exception as e:
                        st.error(f"Import failed: {e}")

            with col2:
                if st.button("Clear Preview"):
                    st.session_state.vo2max_preview = None
                    st.rerun()
