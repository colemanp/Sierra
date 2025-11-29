"""Weight tab component - Garmin weight data"""
import streamlit as st
import plotly.graph_objects as go
import pandas as pd


def get_weight_data(conn, include_hidden: bool = False) -> pd.DataFrame:
    """Get weight data, optionally including hidden records"""
    if include_hidden:
        query = """
        SELECT id, measurement_date as date, measurement_time as time,
               weight_lbs, weight_change_lbs, bmi,
               body_fat_pct, muscle_mass_lbs, bone_mass_lbs, body_water_pct,
               COALESCE(hidden, 0) as hidden
        FROM body_measurements
        ORDER BY measurement_date, measurement_time
        """
    else:
        query = """
        SELECT id, measurement_date as date, measurement_time as time,
               weight_lbs, weight_change_lbs, bmi,
               body_fat_pct, muscle_mass_lbs, bone_mass_lbs, body_water_pct,
               0 as hidden
        FROM body_measurements
        WHERE hidden = 0 OR hidden IS NULL
        ORDER BY measurement_date, measurement_time
        """
    return pd.read_sql_query(query, conn)


def get_weight_stats(conn) -> dict:
    """Get weight statistics (excluding hidden records)"""
    query = """
    SELECT
        COUNT(*) as count,
        MIN(measurement_date) as earliest,
        MAX(measurement_date) as latest,
        AVG(weight_lbs) as avg_weight,
        MIN(weight_lbs) as min_weight,
        MAX(weight_lbs) as max_weight
    FROM body_measurements
    WHERE hidden = 0 OR hidden IS NULL
    """
    row = conn.execute(query).fetchone()

    # Count hidden records
    hidden_count = conn.execute(
        "SELECT COUNT(*) FROM body_measurements WHERE hidden = 1"
    ).fetchone()[0]

    return {
        "count": row[0] or 0,
        "hidden_count": hidden_count or 0,
        "earliest": row[1],
        "latest": row[2],
        "avg_weight": row[3],
        "min_weight": row[4],
        "max_weight": row[5],
    }


def render_weight(conn):
    """Render weight tab"""
    col_header, col_reload = st.columns([6, 1])
    col_header.header("Weight Data")
    if col_reload.button("Reload", key="weight_reload"):
        st.rerun()

    if conn is None:
        st.warning("No database connection")
        return

    # Stats
    stats = get_weight_stats(conn)
    if not stats.get("count") and not stats.get("hidden_count"):
        st.info("No weight data yet. Import Garmin weight data to get started.")
        return

    # Show stats at top
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    col1.metric("Records", f"{stats['count']:,}")
    col2.metric("Hidden", f"{stats['hidden_count']:,}")
    col3.metric("Earliest", stats["earliest"] or "-")
    col4.metric("Latest", stats["latest"] or "-")
    col5.metric("Min", f"{stats['min_weight']:.1f} lbs" if stats["min_weight"] else "-")
    col6.metric("Max", f"{stats['max_weight']:.1f} lbs" if stats["max_weight"] else "-")

    st.divider()

    # Get all data including hidden
    df = get_weight_data(conn, include_hidden=True)

    if df.empty:
        return

    # Split into visible and hidden
    df_visible = df[df["hidden"] == 0]
    df_hidden = df[df["hidden"] == 1]

    # Latest stats (from visible only)
    if not df_visible.empty:
        latest = df_visible.iloc[-1]
        first = df_visible.iloc[0]
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

    # Visible records (solid blue line)
    if not df_visible.empty:
        fig.add_trace(go.Scatter(
            x=df_visible["date"],
            y=df_visible["weight_lbs"],
            name="Visible",
            mode="lines+markers",
            line=dict(color="blue", width=1.5),
            hovertemplate="Date: %{x}<br>Weight: %{y:.1f} lbs<extra></extra>"
        ))

        # Add trend line
        if len(df_visible) > 2:
            import numpy as np
            x_num = np.arange(len(df_visible))
            z = np.polyfit(x_num, df_visible["weight_lbs"].fillna(method='ffill'), 1)
            p = np.poly1d(z)
            fig.add_trace(go.Scatter(
                x=df_visible["date"],
                y=p(x_num),
                name="Trend",
                mode="lines",
                line=dict(dash="dash", color="red")
            ))

    # Hidden records (gray markers)
    if not df_hidden.empty:
        fig.add_trace(go.Scatter(
            x=df_hidden["date"],
            y=df_hidden["weight_lbs"],
            name="Hidden",
            mode="markers",
            marker=dict(color="#95a5a6", size=6, symbol="x"),
            hovertemplate="Date: %{x}<br>Weight: %{y:.1f} lbs (hidden)<extra></extra>"
        ))

    fig.update_layout(
        height=400,
        yaxis_title="Weight (lbs)",
        legend=dict(orientation="h", yanchor="bottom", y=1.02)
    )
    st.plotly_chart(fig, width="stretch")

    st.divider()

    # Body composition (visible only)
    if not df_visible.empty:
        st.subheader("Body Composition")
        col1, col2 = st.columns(2)

        with col1:
            if df_visible["body_fat_pct"].notna().any():
                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=df_visible["date"],
                    y=df_visible["body_fat_pct"],
                    name="Body Fat %",
                    mode="lines+markers"
                ))
                fig.update_layout(height=300, yaxis_title="Body Fat %")
                st.plotly_chart(fig, width="stretch")

        with col2:
            if df_visible["muscle_mass_lbs"].notna().any():
                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=df_visible["date"],
                    y=df_visible["muscle_mass_lbs"],
                    name="Muscle Mass",
                    mode="lines+markers",
                    line=dict(color="green")
                ))
                fig.update_layout(height=300, yaxis_title="Muscle Mass (lbs)")
                st.plotly_chart(fig, width="stretch")

        st.divider()

    # Hide by threshold section
    with st.expander("Hide Records by Weight Threshold"):
        col1, col2 = st.columns(2)
        with col1:
            hide_below = st.number_input(
                "Hide records below (lbs)",
                min_value=0.0,
                max_value=500.0,
                value=0.0,
                step=1.0,
                key="weight_hide_below"
            )
        with col2:
            hide_above = st.number_input(
                "Hide records above (lbs)",
                min_value=0.0,
                max_value=500.0,
                value=0.0,
                step=1.0,
                key="weight_hide_above"
            )

        # Preview what would be hidden
        preview_hidden = df_visible.copy()
        if hide_below > 0:
            preview_hidden = preview_hidden[preview_hidden["weight_lbs"] < hide_below]
        if hide_above > 0:
            above_mask = df_visible["weight_lbs"] > hide_above
            if hide_below > 0:
                preview_hidden = pd.concat([preview_hidden, df_visible[above_mask]])
            else:
                preview_hidden = df_visible[above_mask]

        if len(preview_hidden) > 0:
            st.warning(f"Would hide {len(preview_hidden)} records")
            st.dataframe(
                preview_hidden[["date", "weight_lbs"]].rename(columns={"date": "Date", "weight_lbs": "Weight (lbs)"}),
                hide_index=True,
                width="stretch"
            )

            if st.button("Hide These Records", type="primary", key="weight_hide_btn"):
                ids = preview_hidden["id"].tolist()
                conn.executemany(
                    "UPDATE body_measurements SET hidden = 1 WHERE id = ?",
                    [(id,) for id in ids]
                )
                conn.commit()
                st.success(f"Hidden {len(ids)} records")
                st.rerun()
        else:
            st.info("No records match the threshold criteria")

    # Recent records table (visible only)
    st.subheader("Recent Records")
    if not df_visible.empty:
        recent_df = df_visible.tail(30).iloc[::-1][["date", "weight_lbs", "bmi", "body_fat_pct"]].copy()
        recent_df.columns = ["Date", "Weight (lbs)", "BMI", "Body Fat %"]
        st.dataframe(recent_df, width="stretch", hide_index=True)

    # Hidden records table (if any)
    if not df_hidden.empty:
        with st.expander(f"Hidden Records ({len(df_hidden)})"):
            hidden_display = df_hidden.iloc[::-1][["id", "date", "weight_lbs"]].copy()
            hidden_display.columns = ["ID", "Date", "Weight (lbs)"]
            st.dataframe(hidden_display, width="stretch", hide_index=True)

            if st.button("Unhide All Records", key="weight_unhide_btn"):
                conn.execute("UPDATE body_measurements SET hidden = 0 WHERE hidden = 1")
                conn.commit()
                st.success("Unhid all records")
                st.rerun()
