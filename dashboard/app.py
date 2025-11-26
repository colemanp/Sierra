"""Health Data Dashboard - Main App"""
import streamlit as st

st.set_page_config(
    page_title="Health Data Dashboard",
    page_icon="💪",
    layout="wide",
    initial_sidebar_state="expanded"
)

from dashboard.utils.db import get_connection
from dashboard.components.sidebar import render_sidebar
from dashboard.components.overview import render_overview
from dashboard.components.activities import render_activities
from dashboard.components.body import render_body
from dashboard.components.strength import render_strength
from dashboard.components.nutrition import render_nutrition
from dashboard.components.imports import render_imports


def main():
    # Render sidebar and get DB choice
    db_choice = render_sidebar()

    # Get connection
    conn = get_connection(db_choice)

    # Main content tabs
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "Overview",
        "Activities",
        "Body",
        "Strength",
        "Nutrition",
        "Imports"
    ])

    with tab1:
        render_overview(conn)

    with tab2:
        render_activities(conn)

    with tab3:
        render_body(conn)

    with tab4:
        render_strength(conn)

    with tab5:
        render_nutrition(conn)

    with tab6:
        render_imports(conn)

    # Close connection
    if conn:
        conn.close()


if __name__ == "__main__":
    main()
