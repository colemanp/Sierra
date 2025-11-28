"""Sidebar component with DB toggle and import controls"""
import streamlit as st
from pathlib import Path
import tempfile
import sys
import csv

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from dashboard.utils.db import DB_PATHS


def detect_source_type(filename: str, content: bytes) -> str:
    """Auto-detect source type from filename and content"""
    filename_lower = filename.lower()

    # Check file extension first
    if filename_lower.endswith('.xml'):
        return "apple-resting-hr"

    # For CSV files, inspect headers
    if filename_lower.endswith('.csv'):
        try:
            # Decode and get first line
            text = content.decode('utf-8')
            first_line = text.split('\n')[0].lower()

            # Check for distinctive headers
            if 'activity type' in first_line and 'aerobic te' in first_line:
                return "garmin-activities"
            if 'weight' in first_line and 'bmi' in first_line and 'body fat' in first_line:
                return "garmin-weight"
            if 'vo2' in first_line or 'vo 2' in first_line:
                return "garmin-vo2max"
            if 'goal' in first_line and ('set1' in first_line or 'set 1' in first_line):
                return "six-week"
            # Check for semicolon delimiter (6-week uses semicolons)
            if ';' in first_line and 'goal' in first_line:
                return "six-week"
            # MacroFactor CSV export
            if 'food name' in first_line and 'calories' in first_line and 'serving' in first_line:
                return "macrofactor"
        except:
            pass

    return None


def render_sidebar():
    """Render sidebar with DB toggle and import controls"""
    st.sidebar.title("Health Data Dashboard")

    # Database toggle
    st.sidebar.subheader("Database")
    db_choice = st.sidebar.radio(
        "Select Database",
        options=[None, "prod", "test"],
        format_func=lambda x: "-- Select --" if x is None else ("Production" if x == "prod" else "Test"),
        key="db_choice"
    )

    # Show DB path and status
    if db_choice is None:
        st.sidebar.warning("Please select a database")
    else:
        db_path = DB_PATHS[db_choice]
        if db_path.exists():
            st.sidebar.success(f"Connected: {db_path.name}")
        else:
            st.sidebar.info(f"Will create: {db_path.name}")

    st.sidebar.divider()

    # Import section
    st.sidebar.subheader("Import Data")

    if db_choice is None:
        st.sidebar.info("Select a database above to enable imports")
        return None

    source_options = {
        "garmin-activities": "Garmin Activities (CSV)",
        "garmin-weight": "Garmin Weight (CSV)",
        "garmin-vo2max": "Garmin VO2 Max (CSV)",
        "six-week": "6-Week Challenge (CSV)",
        "macrofactor": "MacroFactor (CSV)",
        "apple-resting-hr": "Apple Resting HR (XML)",
    }

    # File uploader - accept all supported types
    uploaded_file = st.sidebar.file_uploader(
        "Upload file",
        type=["csv", "xml"],
        key="import_file"
    )

    # Auto-detect or manual source selection
    detected_source = None
    if uploaded_file is not None:
        detected_source = detect_source_type(uploaded_file.name, uploaded_file.getvalue())

        if detected_source:
            st.sidebar.success(f"Detected: {source_options[detected_source]}")
            selected_source = detected_source

            # Allow override
            if st.sidebar.checkbox("Override detected type", key="override_source"):
                selected_source = st.sidebar.selectbox(
                    "Source Type",
                    options=list(source_options.keys()),
                    format_func=lambda x: source_options[x],
                    key="import_source_override"
                )
        else:
            st.sidebar.warning("Could not auto-detect source type")
            selected_source = st.sidebar.selectbox(
                "Source Type",
                options=list(source_options.keys()),
                format_func=lambda x: source_options[x],
                key="import_source_manual"
            )

        # Import button
        if st.sidebar.button("Run Import", type="primary", key="run_import"):
            run_import(db_choice, selected_source, uploaded_file)

    return db_choice


def run_import(db_choice: str, source: str, uploaded_file):
    """Run import with uploaded file"""
    from health_import.core.database import Database
    from health_import.core.logging_setup import setup_logging
    from health_import.importers.garmin_activities import GarminActivitiesImporter
    from health_import.importers.garmin_weight import GarminWeightImporter
    from health_import.importers.garmin_vo2max import GarminVO2MaxImporter
    from health_import.importers.six_week import SixWeekImporter
    from health_import.importers.macrofactor import MacroFactorImporter
    from health_import.importers.apple_resting_hr import AppleRestingHRImporter

    # Setup logging with file output
    setup_logging(verbosity=1, log_to_file=True)

    importers = {
        "garmin-activities": GarminActivitiesImporter,
        "garmin-weight": GarminWeightImporter,
        "garmin-vo2max": GarminVO2MaxImporter,
        "six-week": SixWeekImporter,
        "macrofactor": MacroFactorImporter,
        "apple-resting-hr": AppleRestingHRImporter,
    }

    # Validate file extension matches source type
    filename = uploaded_file.name.lower()
    expected_ext = {
        "garmin-activities": [".csv"],
        "garmin-weight": [".csv"],
        "garmin-vo2max": [".csv"],
        "six-week": [".csv"],
        "macrofactor": [".csv"],
        "apple-resting-hr": [".xml"],
    }

    if not any(filename.endswith(ext) for ext in expected_ext[source]):
        st.sidebar.error(f"File type mismatch: {source} expects {'/'.join(expected_ext[source])} file")
        return

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

        # Store results in session state for dialog
        st.session_state["show_import_dialog"] = True
        st.session_state["last_import_result"] = {
            "processed": result.processed,
            "inserted": result.inserted,
            "skipped": result.skipped,
            "conflicted": result.conflicted,
        }

        # Cleanup
        tmp_path.unlink()

        # Clear file uploader
        if "import_file" in st.session_state:
            del st.session_state["import_file"]
        st.rerun()

    except Exception as e:
        st.sidebar.error(f"Import failed: {e}")


@st.dialog("Import Complete")
def show_import_result_dialog():
    """Show import results in a dialog"""
    result = st.session_state.get("last_import_result", {})

    st.success("Import completed successfully!")

    col1, col2 = st.columns(2)
    with col1:
        st.metric("Processed", result.get("processed", 0))
        st.metric("Inserted", result.get("inserted", 0))
    with col2:
        st.metric("Skipped", result.get("skipped", 0))
        st.metric("Conflicts", result.get("conflicted", 0))

    if st.button("OK", type="primary"):
        st.session_state["show_import_dialog"] = False
        if "last_import_result" in st.session_state:
            del st.session_state["last_import_result"]
        if "import_file" in st.session_state:
            del st.session_state["import_file"]
        st.rerun()
