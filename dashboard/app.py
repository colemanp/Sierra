"""Health Data Dashboard - Main App"""
import streamlit as st

st.set_page_config(
    page_title="Health Data Dashboard",
    page_icon="💪",
    layout="wide",
    initial_sidebar_state="expanded"
)

from dashboard.utils.db import get_connection
from dashboard.components.sidebar import render_sidebar, show_import_result_dialog
from dashboard.components.overview import render_overview
from dashboard.components.activities import render_activities
from dashboard.components.body import render_body
from dashboard.components.weight import render_weight
from dashboard.components.strength import render_strength
from dashboard.components.nutrition import render_nutrition
from dashboard.components.imports import render_imports
from dashboard.components.mcp import render_mcp
from dashboard.components.resting_hr import render_resting_hr
from dashboard.components.vo2max import render_vo2max


def main():
    # Show import result dialog if triggered
    if st.session_state.get("show_import_dialog"):
        show_import_result_dialog()

    # Render sidebar and get DB choice
    db_choice = render_sidebar()

    # Check if DB selected
    if db_choice is None:
        st.info("Please select a database from the sidebar to continue.")
        return

    # Get connection
    conn = get_connection(db_choice)

    if conn is None:
        st.warning("Database not found. Use 'Import Data' in the sidebar to create it.")
        return

    # Main content tabs
    tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9, tab10 = st.tabs([
        "Overview",
        "Activities",
        "Body",
        "Weight",
        "Resting HR",
        "VO2 Max",
        "Strength",
        "Nutrition",
        "Imports",
        "MCP"
    ])

    with tab1:
        render_overview(conn)

    with tab2:
        render_activities(conn)

    with tab3:
        render_body(conn)

    with tab4:
        render_weight(conn)

    with tab5:
        render_resting_hr(conn)

    with tab6:
        render_vo2max(conn)

    with tab7:
        render_strength(conn)

    with tab8:
        render_nutrition(conn)

    with tab9:
        render_imports(conn)

    with tab10:
        render_mcp(conn)

    # Close connection
    if conn:
        conn.close()


if __name__ == "__main__":
    main()
