"""Body measurements tab component"""
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from dashboard.utils.queries import (
    get_weight_trend,
    get_latest_weight,
    get_vo2max_trend,
    get_resting_hr_trend,
)


def render_body(conn):
    """Render body measurements tab"""
    st.header("Body Measurements")

    if conn is None:
        st.warning("No database connection")
        return

    # Latest weight metrics
    latest = get_latest_weight(conn)

    if latest:
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Current Weight", f"{latest['weight_lbs']:.1f} lbs")
        col2.metric("Body Fat", f"{latest['body_fat_pct']:.1f}%" if latest['body_fat_pct'] else "N/A")
        col3.metric("Muscle Mass", f"{latest['muscle_mass_lbs']:.1f} lbs" if latest['muscle_mass_lbs'] else "N/A")
        col4.metric("Last Measured", latest['measurement_date'])
    else:
        st.info("No weight data yet")

    st.divider()

    # Date range selector
    days = st.selectbox("Time Range", [30, 60, 90, 180, 365], index=2, format_func=lambda x: f"Last {x} days")

    # Weight trend
    st.subheader("Weight Trend")
    weight_df = get_weight_trend(conn, days=days)

    if not weight_df.empty:
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
            z = np.polyfit(x_num, weight_df["weight_lbs"], 1)
            p = np.poly1d(z)
            fig.add_trace(go.Scatter(
                x=weight_df["date"],
                y=p(x_num),
                name="Trend",
                mode="lines",
                line=dict(dash="dash", color="red")
            ))

        fig.update_layout(height=350, yaxis_title="Weight (lbs)")
        st.plotly_chart(fig, use_container_width=True)

        # Show weight change
        if len(weight_df) > 1:
            first_weight = weight_df["weight_lbs"].iloc[0]
            last_weight = weight_df["weight_lbs"].iloc[-1]
            change = last_weight - first_weight
            st.caption(f"Change over period: {change:+.1f} lbs")
    else:
        st.info("No weight data for selected period")

    # Body composition
    st.subheader("Body Composition")
    if not weight_df.empty and "body_fat_pct" in weight_df.columns:
        col1, col2 = st.columns(2)

        with col1:
            fig = px.line(
                weight_df,
                x="date",
                y="body_fat_pct",
                title="Body Fat %"
            )
            fig.update_layout(height=250)
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            if "body_water_pct" in weight_df.columns:
                fig = px.line(
                    weight_df,
                    x="date",
                    y="body_water_pct",
                    title="Body Water %"
                )
                fig.update_layout(height=250)
                st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # VO2 Max
    st.subheader("VO2 Max")
    vo2_df = get_vo2max_trend(conn)

    if not vo2_df.empty:
        fig = px.line(
            vo2_df,
            x="date",
            y="vo2max_value",
            color="activity_type",
            markers=True
        )
        fig.update_layout(height=300, yaxis_title="VO2 Max (ml/kg/min)")
        st.plotly_chart(fig, use_container_width=True)

        # Latest VO2 Max
        latest_vo2 = vo2_df.iloc[-1]
        st.metric("Latest VO2 Max", f"{latest_vo2['vo2max_value']:.1f}", delta=f"{latest_vo2['activity_type']}")
    else:
        st.info("No VO2 Max data yet")

    # Resting HR
    st.subheader("Resting Heart Rate")
    rhr_df = get_resting_hr_trend(conn, days=days)

    if not rhr_df.empty:
        fig = px.line(
            rhr_df,
            x="date",
            y="resting_hr",
            markers=True
        )
        fig.update_layout(height=250, yaxis_title="BPM")
        st.plotly_chart(fig, use_container_width=True)

        avg_rhr = rhr_df["resting_hr"].mean()
        st.caption(f"Average: {avg_rhr:.0f} bpm")
    else:
        st.info("No resting heart rate data yet")
