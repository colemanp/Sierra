"""Activities tab component"""
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from dashboard.utils.queries import (
    get_activities_summary,
    get_weekly_activities,
    get_recent_activities,
)


def render_activities(conn):
    """Render activities tab"""
    st.header("Activities")

    if conn is None:
        st.warning("No database connection")
        return

    # Summary metrics
    summary_df = get_activities_summary(conn)

    if summary_df.empty:
        st.info("No activity data yet")
        return

    # Top metrics
    total_activities = summary_df["count"].sum()
    total_miles = summary_df["total_miles"].sum() or 0
    total_calories = summary_df["total_calories"].sum() or 0

    col1, col2, col3 = st.columns(3)
    col1.metric("Total Activities", f"{total_activities:,}")
    col2.metric("Total Miles", f"{total_miles:,.1f}")
    col3.metric("Total Calories", f"{total_calories:,.0f}")

    st.divider()

    # Charts
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Activities by Type")
        fig = px.bar(
            summary_df,
            x="activity_type",
            y="count",
            color="activity_type",
            title=""
        )
        fig.update_layout(showlegend=False, height=300)
        st.plotly_chart(fig, width="stretch")

    with col2:
        st.subheader("Miles by Type")
        fig = px.pie(
            summary_df[summary_df["total_miles"] > 0],
            values="total_miles",
            names="activity_type",
            title=""
        )
        fig.update_layout(height=300)
        st.plotly_chart(fig, width="stretch")

    # Weekly trend
    st.subheader("Weekly Activity Volume")
    weekly_df = get_weekly_activities(conn)

    if not weekly_df.empty:
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=weekly_df["week"],
            y=weekly_df["activities"],
            name="Activities",
            mode="lines+markers"
        ))
        fig.add_trace(go.Scatter(
            x=weekly_df["week"],
            y=weekly_df["miles"],
            name="Miles",
            yaxis="y2",
            mode="lines+markers"
        ))
        fig.update_layout(
            yaxis=dict(title="Activities"),
            yaxis2=dict(title="Miles", overlaying="y", side="right"),
            height=300,
            legend=dict(orientation="h", yanchor="bottom", y=1.02)
        )
        st.plotly_chart(fig, width="stretch")

    st.divider()

    # Summary table
    st.subheader("Activity Summary by Type")
    display_df = summary_df.copy()
    display_df.columns = ["Type", "Count", "Miles", "Calories", "Avg HR", "Avg Duration (min)"]
    st.dataframe(display_df, width="stretch", hide_index=True)

    # Recent activities
    st.subheader("Recent Activities")
    recent_df = get_recent_activities(conn, limit=15)
    if not recent_df.empty:
        display_df = recent_df.copy()
        display_df.columns = ["Date", "Type", "Title", "Miles", "Duration (min)", "Avg HR", "Calories"]
        st.dataframe(display_df, width="stretch", hide_index=True)
