"""Resting Heart Rate tab component"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go


def get_resting_hr_data(conn, include_hidden: bool = False) -> pd.DataFrame:
    """Get resting HR data, optionally including hidden records"""
    if include_hidden:
        query = """
        SELECT measurement_date as date, resting_hr as hr, source_name,
               COALESCE(hidden, 0) as hidden
        FROM resting_heart_rate
        ORDER BY measurement_date
        """
    else:
        query = """
        SELECT measurement_date as date, resting_hr as hr, source_name,
               0 as hidden
        FROM resting_heart_rate
        WHERE hidden = 0 OR hidden IS NULL
        ORDER BY measurement_date
        """
    return pd.read_sql_query(query, conn)


def get_resting_hr_stats(conn) -> dict:
    """Get resting HR statistics (excluding hidden records)"""
    query = """
    SELECT
        COUNT(*) as count,
        MIN(measurement_date) as earliest,
        MAX(measurement_date) as latest,
        AVG(resting_hr) as avg_hr,
        MIN(resting_hr) as min_hr,
        MAX(resting_hr) as max_hr
    FROM resting_heart_rate
    WHERE hidden = 0 OR hidden IS NULL
    """
    row = conn.execute(query).fetchone()

    # Count hidden records
    hidden_count = conn.execute(
        "SELECT COUNT(*) FROM resting_heart_rate WHERE hidden = 1"
    ).fetchone()[0]

    return {
        "count": row[0] or 0,
        "hidden_count": hidden_count or 0,
        "earliest": row[1],
        "latest": row[2],
        "avg_hr": row[3],
        "min_hr": row[4],
        "max_hr": row[5],
    }


def get_monthly_avg(conn) -> pd.DataFrame:
    """Get monthly average resting HR (excluding hidden)"""
    query = """
    SELECT strftime('%Y-%m', measurement_date) as month,
           AVG(resting_hr) as avg_hr,
           MIN(resting_hr) as min_hr,
           MAX(resting_hr) as max_hr,
           COUNT(*) as count
    FROM resting_heart_rate
    WHERE hidden = 0 OR hidden IS NULL
    GROUP BY month
    ORDER BY month
    """
    return pd.read_sql_query(query, conn)


def render_resting_hr(conn):
    """Render Resting HR tab"""
    col_header, col_reload = st.columns([6, 1])
    col_header.header("Resting Heart Rate")
    if col_reload.button("🔄 Reload", key="rhr_reload"):
        st.rerun()

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

    col1, col2, col3, col4, col5, col6, col7 = st.columns(7)
    col1.metric("Records", f"{stats['count']:,}")
    col2.metric("Hidden", f"{stats['hidden_count']:,}")
    col3.metric("Earliest", stats["earliest"] or "-")
    col4.metric("Latest", stats["latest"] or "-")
    col5.metric("Average", f"{stats['avg_hr']:.0f} bpm" if stats["avg_hr"] else "-")
    col6.metric("Min", f"{stats['min_hr']} bpm" if stats["min_hr"] else "-")
    col7.metric("Max", f"{stats['max_hr']} bpm" if stats["max_hr"] else "-")

    st.divider()

    # Get all data including hidden
    df = get_resting_hr_data(conn, include_hidden=True)

    if df.empty:
        return

    # Split into visible and hidden
    df_visible = df[df["hidden"] == 0]
    df_hidden = df[df["hidden"] == 1]

    # Daily chart
    st.subheader("Daily Resting Heart Rate")
    fig = go.Figure()

    # Visible records (solid red line)
    if not df_visible.empty:
        fig.add_trace(go.Scatter(
            x=df_visible["date"],
            y=df_visible["hr"],
            name="Visible",
            mode="lines",
            line=dict(color="#e74c3c", width=1.5),
            hovertemplate="Date: %{x}<br>HR: %{y} bpm<extra></extra>"
        ))

    # Hidden records (gray markers)
    if not df_hidden.empty:
        fig.add_trace(go.Scatter(
            x=df_hidden["date"],
            y=df_hidden["hr"],
            name="Hidden",
            mode="markers",
            marker=dict(color="#95a5a6", size=6, symbol="x"),
            hovertemplate="Date: %{x}<br>HR: %{y} bpm (hidden)<extra></extra>"
        ))

    fig.update_layout(
        height=400,
        xaxis_title="Date",
        yaxis_title="Resting HR (bpm)",
        legend=dict(orientation="h", yanchor="bottom", y=1.02)
    )
    st.plotly_chart(fig, width="stretch")

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
        st.plotly_chart(fig, width="stretch")

    st.divider()

    # Recent records table (visible only)
    st.subheader("Recent Records")
    recent_df = df_visible.tail(30).iloc[::-1][["date", "hr", "source_name"]].copy()
    recent_df.columns = ["Date", "Resting HR (bpm)", "Source"]
    st.dataframe(recent_df, width="stretch", hide_index=True)

    # Hidden records table (if any)
    if not df_hidden.empty:
        with st.expander(f"Hidden Records ({len(df_hidden)})"):
            hidden_df = df_hidden.iloc[::-1][["date", "hr", "source_name"]].copy()
            hidden_df.columns = ["Date", "Resting HR (bpm)", "Source"]
            st.dataframe(hidden_df, width="stretch", hide_index=True)
