"""Weight tab component - Garmin weight data"""
import streamlit as st
import plotly.graph_objects as go
import pandas as pd


def get_weight_data(conn) -> pd.DataFrame:
    """Get all weight data from Garmin imports"""
    query = """
    SELECT measurement_date as date, measurement_time as time,
           weight_lbs, weight_change_lbs, bmi,
           body_fat_pct, muscle_mass_lbs, bone_mass_lbs, body_water_pct
    FROM body_measurements
    ORDER BY measurement_date, measurement_time
    """
    return pd.read_sql_query(query, conn)


def get_weight_date_range(conn) -> dict:
    """Get date range of weight data"""
    query = """
    SELECT MIN(measurement_date) as earliest,
           MAX(measurement_date) as latest,
           COUNT(*) as count
    FROM body_measurements
    """
    df = pd.read_sql_query(query, conn)
    if len(df) > 0:
        return df.iloc[0].to_dict()
    return {}


def render_weight(conn):
    """Render weight tab"""
    st.header("Weight Data")

    if conn is None:
        st.warning("No database connection")
        return

    # Date range info
    date_range = get_weight_date_range(conn)
    if not date_range.get("count"):
        st.info("No weight data yet. Import Garmin weight CSV to get started.")
        return

    # Show date range at top
    col1, col2, col3 = st.columns(3)
    col1.metric("Earliest", date_range["earliest"])
    col2.metric("Latest", date_range["latest"])
    col3.metric("Total Records", date_range["count"])

    st.divider()

    # Get all data
    weight_df = get_weight_data(conn)

    # Latest stats
    latest = weight_df.iloc[-1]
    first = weight_df.iloc[0]
    total_change = latest["weight_lbs"] - first["weight_lbs"]

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Current Weight", f"{latest['weight_lbs']:.1f} lbs")
    col2.metric("Starting Weight", f"{first['weight_lbs']:.1f} lbs")
    col3.metric("Total Change", f"{total_change:+.1f} lbs")
    col4.metric("Body Fat", f"{latest['body_fat_pct']:.1f}%" if pd.notna(latest['body_fat_pct']) else "N/A")

    st.divider()

    # Weight chart
    st.subheader("Weight Over Time")
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=weight_df["date"],
        y=weight_df["weight_lbs"],
        name="Weight",
        mode="lines+markers",
        line=dict(color="blue")
    ))

    # Add trend line
    if len(weight_df) > 2:
        import numpy as np
        x_num = np.arange(len(weight_df))
        z = np.polyfit(x_num, weight_df["weight_lbs"].fillna(method='ffill'), 1)
        p = np.poly1d(z)
        fig.add_trace(go.Scatter(
            x=weight_df["date"],
            y=p(x_num),
            name="Trend",
            mode="lines",
            line=dict(dash="dash", color="red")
        ))

    fig.update_layout(height=400, yaxis_title="Weight (lbs)")
    st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # Body composition
    st.subheader("Body Composition")
    col1, col2 = st.columns(2)

    with col1:
        if weight_df["body_fat_pct"].notna().any():
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=weight_df["date"],
                y=weight_df["body_fat_pct"],
                name="Body Fat %",
                mode="lines+markers"
            ))
            fig.update_layout(height=300, yaxis_title="Body Fat %")
            st.plotly_chart(fig, use_container_width=True)

    with col2:
        if weight_df["muscle_mass_lbs"].notna().any():
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=weight_df["date"],
                y=weight_df["muscle_mass_lbs"],
                name="Muscle Mass",
                mode="lines+markers",
                line=dict(color="green")
            ))
            fig.update_layout(height=300, yaxis_title="Muscle Mass (lbs)")
            st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # Data table
    st.subheader("All Records")
    display_df = weight_df.copy()
    display_df.columns = ["Date", "Time", "Weight", "Change", "BMI", "Body Fat %", "Muscle", "Bone", "Water %"]
    st.dataframe(display_df, use_container_width=True, hide_index=True)
