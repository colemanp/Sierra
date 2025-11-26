"""Sidebar component with DB toggle and import controls"""
import streamlit as st
from pathlib import Path
import tempfile
import sys

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from dashboard.utils.db import DB_PATHS


def render_sidebar():
    """Render sidebar with DB toggle and import controls"""
    st.sidebar.title("Health Data Dashboard")

    # Database toggle
    st.sidebar.subheader("Database")
    db_choice = st.sidebar.radio(
        "Select Database",
        options=["prod", "test"],
        format_func=lambda x: f"{'Production' if x == 'prod' else 'Test'} DB",
        key="db_choice"
    )

    # Show DB path and status
    db_path = DB_PATHS[db_choice]
    if db_path.exists():
        st.sidebar.success(f"Connected: {db_path.name}")
    else:
        st.sidebar.warning(f"Not found: {db_path}")

    st.sidebar.divider()

    # Import section
    st.sidebar.subheader("Import Data")

    source_options = {
        "garmin-activities": "Garmin Activities (CSV)",
        "garmin-weight": "Garmin Weight (CSV)",
        "garmin-vo2max": "Garmin VO2 Max (CSV)",
        "six-week": "6-Week Challenge (CSV)",
        "macrofactor": "MacroFactor (XLSX)",
        "apple-resting-hr": "Apple Resting HR (XML)",
    }

    selected_source = st.sidebar.selectbox(
        "Source Type",
        options=list(source_options.keys()),
        format_func=lambda x: source_options[x],
        key="import_source"
    )

    # File uploader
    file_ext = "xlsx" if selected_source == "macrofactor" else ("xml" if selected_source == "apple-resting-hr" else "csv")
    uploaded_file = st.sidebar.file_uploader(
        f"Upload {file_ext.upper()} file",
        type=[file_ext],
        key="import_file"
    )

    # Import button
    if uploaded_file is not None:
        if st.sidebar.button("Run Import", type="primary", key="run_import"):
            run_import(db_choice, selected_source, uploaded_file)

    return db_choice


def run_import(db_choice: str, source: str, uploaded_file):
    """Run import with uploaded file"""
    from health_import.core.database import Database
    from health_import.importers.garmin_activities import GarminActivitiesImporter
    from health_import.importers.garmin_weight import GarminWeightImporter
    from health_import.importers.garmin_vo2max import GarminVO2MaxImporter
    from health_import.importers.six_week import SixWeekImporter
    from health_import.importers.macrofactor import MacroFactorImporter
    from health_import.importers.apple_resting_hr import AppleRestingHRImporter

    importers = {
        "garmin-activities": GarminActivitiesImporter,
        "garmin-weight": GarminWeightImporter,
        "garmin-vo2max": GarminVO2MaxImporter,
        "six-week": SixWeekImporter,
        "macrofactor": MacroFactorImporter,
        "apple-resting-hr": AppleRestingHRImporter,
    }

    try:
        # Save uploaded file to temp location
        with tempfile.NamedTemporaryFile(delete=False, suffix=Path(uploaded_file.name).suffix) as tmp:
            tmp.write(uploaded_file.getvalue())
            tmp_path = Path(tmp.name)

        # Run import
        db_path = DB_PATHS[db_choice]
        with Database(db_path) as db:
            db.init_schema()
            importer_class = importers[source]
            importer = importer_class(db, verbosity=1)
            result = importer.import_file(tmp_path)

        # Show results
        st.sidebar.success(f"Import complete!")
        st.sidebar.info(
            f"Processed: {result.processed}\n"
            f"Inserted: {result.inserted}\n"
            f"Skipped: {result.skipped}\n"
            f"Conflicts: {result.conflicted}"
        )

        # Cleanup
        tmp_path.unlink()

        # Trigger refresh
        st.rerun()

    except Exception as e:
        st.sidebar.error(f"Import failed: {e}")
