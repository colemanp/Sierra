"""Resting Heart Rate tab component"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go


def get_resting_hr_data(conn) -> pd.DataFrame:
    """Get all resting HR data"""
    query = """
    SELECT measurement_date as date, resting_hr as hr, source_name
    FROM resting_heart_rate
    ORDER BY measurement_date
    """
    return pd.read_sql_query(query, conn)


def get_resting_hr_stats(conn) -> dict:
    """Get resting HR statistics"""
    query = """
    SELECT
        COUNT(*) as count,
        MIN(measurement_date) as earliest,
        MAX(measurement_date) as latest,
        AVG(resting_hr) as avg_hr,
        MIN(resting_hr) as min_hr,
        MAX(resting_hr) as max_hr
    FROM resting_heart_rate
    """
    row = conn.execute(query).fetchone()
    return {
        "count": row[0] or 0,
        "earliest": row[1],
        "latest": row[2],
        "avg_hr": row[3],
        "min_hr": row[4],
        "max_hr": row[5],
    }


def get_monthly_avg(conn) -> pd.DataFrame:
    """Get monthly average resting HR"""
    query = """
    SELECT strftime('%Y-%m', measurement_date) as month,
           AVG(resting_hr) as avg_hr,
           MIN(resting_hr) as min_hr,
           MAX(resting_hr) as max_hr,
           COUNT(*) as count
    FROM resting_heart_rate
    GROUP BY month
    ORDER BY month
    """
    return pd.read_sql_query(query, conn)


def render_resting_hr(conn):
    """Render Resting HR tab"""
    st.header("Resting Heart Rate")

    if conn is None:
        st.warning("No database connection")
        return

    # Check if table has data
    try:
        count = conn.execute("SELECT COUNT(*) FROM resting_heart_rate").fetchone()[0]
        if count == 0:
            st.info("No resting heart rate data yet. Import Apple Health data to populate.")
            return
    except Exception:
        st.info("No resting heart rate data yet. Import Apple Health data to populate.")
        return

    # Stats
    stats = get_resting_hr_stats(conn)

    col1, col2, col3, col4, col5, col6 = st.columns(6)
    col1.metric("Records", f"{stats['count']:,}")
    col2.metric("Earliest", stats["earliest"] or "-")
    col3.metric("Latest", stats["latest"] or "-")
    col4.metric("Average", f"{stats['avg_hr']:.0f} bpm" if stats["avg_hr"] else "-")
    col5.metric("Min", f"{stats['min_hr']} bpm" if stats["min_hr"] else "-")
    col6.metric("Max", f"{stats['max_hr']} bpm" if stats["max_hr"] else "-")

    st.divider()

    # Get all data
    df = get_resting_hr_data(conn)

    if df.empty:
        return

    # Daily chart
    st.subheader("Daily Resting Heart Rate")
    fig = px.line(
        df,
        x="date",
        y="hr",
        title="",
        labels={"date": "Date", "hr": "Resting HR (bpm)"}
    )
    fig.update_layout(height=400)
    fig.update_traces(line_color="#e74c3c")
    st.plotly_chart(fig, use_container_width=True)

    # Monthly averages
    st.subheader("Monthly Averages")
    monthly_df = get_monthly_avg(conn)

    if not monthly_df.empty:
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=monthly_df["month"],
            y=monthly_df["avg_hr"],
            name="Average",
            mode="lines+markers",
            line=dict(color="#e74c3c")
        ))
        fig.add_trace(go.Scatter(
            x=monthly_df["month"],
            y=monthly_df["min_hr"],
            name="Min",
            mode="lines",
            line=dict(color="#3498db", dash="dot")
        ))
        fig.add_trace(go.Scatter(
            x=monthly_df["month"],
            y=monthly_df["max_hr"],
            name="Max",
            mode="lines",
            line=dict(color="#e67e22", dash="dot")
        ))
        fig.update_layout(
            height=350,
            yaxis_title="Resting HR (bpm)",
            legend=dict(orientation="h", yanchor="bottom", y=1.02)
        )
        st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # Recent records table
    st.subheader("Recent Records")
    recent_df = df.tail(30).iloc[::-1].copy()
    recent_df.columns = ["Date", "Resting HR (bpm)", "Source"]
    st.dataframe(recent_df, use_container_width=True, hide_index=True)
