"""Nutrition tab component"""
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from dashboard.utils.queries import (
    get_nutrition_summary,
    get_nutrition_averages,
    get_weekly_nutrition,
)


def render_nutrition(conn):
    """Render nutrition tab"""
    st.header("Nutrition")

    if conn is None:
        st.warning("No database connection")
        return

    # Date range
    days = st.selectbox("Time Range", [7, 14, 30, 60, 90], index=2, format_func=lambda x: f"Last {x} days")

    # Averages
    avgs = get_nutrition_averages(conn, days=days)

    if avgs is None or avgs.get("avg_calories") is None:
        st.info("No nutrition data yet")
        return

    # Metrics row
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Avg Calories", f"{avgs['avg_calories']:.0f}")
    col2.metric("Avg Protein", f"{avgs['avg_protein']:.1f}g")
    col3.metric("Avg Fat", f"{avgs['avg_fat']:.1f}g")
    col4.metric("Avg Carbs", f"{avgs['avg_carbs']:.1f}g")

    st.divider()

    # Calorie trend
    st.subheader("Calorie Intake")
    nutrition_df = get_nutrition_summary(conn, days=days)

    if not nutrition_df.empty:
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=nutrition_df["date"],
            y=nutrition_df["calories"],
            name="Consumed",
            mode="lines+markers"
        ))
        if "target" in nutrition_df.columns:
            fig.add_trace(go.Scatter(
                x=nutrition_df["date"],
                y=nutrition_df["target"],
                name="Target",
                mode="lines",
                line=dict(dash="dash", color="red")
            ))
        fig.update_layout(height=300, yaxis_title="Calories (kcal)")
        st.plotly_chart(fig, use_container_width=True)

        # Calorie difference
        if "target" in nutrition_df.columns:
            nutrition_df["diff"] = nutrition_df["calories"] - nutrition_df["target"]
            avg_diff = nutrition_df["diff"].mean()
            st.caption(f"Avg vs target: {avg_diff:+.0f} kcal/day")

    st.divider()

    # Macros
    st.subheader("Macronutrients")
    col1, col2 = st.columns(2)

    with col1:
        if not nutrition_df.empty:
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=nutrition_df["date"], y=nutrition_df["protein_g"],
                name="Protein", mode="lines"
            ))
            fig.add_trace(go.Scatter(
                x=nutrition_df["date"], y=nutrition_df["fat_g"],
                name="Fat", mode="lines"
            ))
            fig.add_trace(go.Scatter(
                x=nutrition_df["date"], y=nutrition_df["carbs_g"],
                name="Carbs", mode="lines"
            ))
            fig.update_layout(height=250, yaxis_title="Grams")
            st.plotly_chart(fig, use_container_width=True)

    with col2:
        # Macro distribution pie
        if avgs:
            macro_vals = [
                avgs.get("avg_protein", 0) or 0,
                avgs.get("avg_fat", 0) or 0,
                avgs.get("avg_carbs", 0) or 0,
            ]
            if sum(macro_vals) > 0:
                fig = px.pie(
                    values=macro_vals,
                    names=["Protein", "Fat", "Carbs"],
                    title="Avg Macro Split"
                )
                fig.update_layout(height=250)
                st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # Weekly summary
    st.subheader("Weekly Averages")
    weekly_df = get_weekly_nutrition(conn)
    if not weekly_df.empty:
        display_df = weekly_df.copy()
        display_df.columns = ["Week", "Avg Cal", "Avg Protein", "Avg Fat", "Avg Carbs"]
        st.dataframe(display_df, use_container_width=True, hide_index=True)
