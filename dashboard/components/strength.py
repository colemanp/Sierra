"""Strength training tab component"""
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from dashboard.utils.queries import (
    get_strength_summary,
    get_strength_progress,
    get_recent_workouts,
)


def render_strength(conn):
    """Render strength training tab"""
    st.header("Strength Training")

    if conn is None:
        st.warning("No database connection")
        return

    # Summary by exercise
    summary_df = get_strength_summary(conn)

    if summary_df.empty:
        st.info("No strength training data yet")
        return

    # Top metrics
    total_workouts = summary_df["workouts"].sum()
    unique_exercises = len(summary_df)

    col1, col2 = st.columns(2)
    col1.metric("Total Workouts", f"{total_workouts:,}")
    col2.metric("Exercises Tracked", unique_exercises)

    st.divider()

    # Charts
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Workouts by Exercise")
        fig = px.bar(
            summary_df.head(10),
            x="exercise",
            y="workouts",
            color="category",
            title=""
        )
        fig.update_layout(height=300, xaxis_tickangle=-45)
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("By Category")
        category_df = summary_df.groupby("category")["workouts"].sum().reset_index()
        fig = px.pie(
            category_df,
            values="workouts",
            names="category",
            title=""
        )
        fig.update_layout(height=300)
        st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # Progress chart
    st.subheader("Exercise Progress")
    exercises = summary_df["exercise"].tolist()
    selected_exercise = st.selectbox("Select Exercise", exercises)

    if selected_exercise:
        progress_df = get_strength_progress(conn, selected_exercise)
        if not progress_df.empty:
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=progress_df["date"],
                y=progress_df["total_value"],
                name="Actual",
                mode="lines+markers"
            ))
            if "goal_value" in progress_df.columns:
                goal_df = progress_df[progress_df["goal_value"].notna()]
                if not goal_df.empty:
                    fig.add_trace(go.Scatter(
                        x=goal_df["date"],
                        y=goal_df["goal_value"],
                        name="Goal",
                        mode="lines",
                        line=dict(dash="dash")
                    ))
            fig.update_layout(height=300, yaxis_title="Total Reps/Value")
            st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # Summary table
    st.subheader("Exercise Summary")
    display_df = summary_df.copy()
    display_df.columns = ["Exercise", "Category", "Workouts", "Avg Total", "Max Total"]
    st.dataframe(display_df, use_container_width=True, hide_index=True)

    # Recent workouts
    st.subheader("Recent Workouts")
    recent_df = get_recent_workouts(conn, limit=15)
    if not recent_df.empty:
        display_df = recent_df.copy()
        display_df.columns = ["Date", "Time", "Exercise", "Set1", "Set2", "Set3", "Set4", "Set5", "Total", "Cals"]
        st.dataframe(display_df, use_container_width=True, hide_index=True)
