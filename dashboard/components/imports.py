"""Import management tab component"""
import streamlit as st
import pandas as pd
from dashboard.utils.queries import (
    get_all_imports,
    get_conflicts_detail,
    get_source_metrics,
)


def render_imports(conn):
    """Render import management tab"""
    st.header("Import Management")

    # Show last import result if exists
    if "last_import_result" in st.session_state:
        result = st.session_state["last_import_result"]
        st.success("Import completed!")
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Processed", result["processed"])
        col2.metric("Inserted", result["inserted"])
        col3.metric("Skipped", result["skipped"])
        col4.metric("Conflicts", result["conflicted"])
        st.divider()
        # Clear after displaying
        del st.session_state["last_import_result"]

    if conn is None:
        st.warning("No database connection")
        return

    # Source filter
    source_df = get_source_metrics(conn)
    sources = ["All"] + source_df["source"].tolist()
    selected_source = st.selectbox("Filter by Source", sources)

    source_filter = None if selected_source == "All" else selected_source

    # Import history
    st.subheader("Import History")
    imports_df = get_all_imports(conn, source_filter=source_filter)

    if imports_df.empty:
        st.info("No imports recorded yet")
        return

    # Summary metrics
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Imports", len(imports_df))
    col2.metric("Total Inserted", f"{imports_df['records_inserted'].sum():,}")
    col3.metric("Total Skipped", f"{imports_df['records_skipped'].sum():,}")
    col4.metric("Total Conflicts", f"{imports_df['records_conflicted'].sum():,}")

    st.divider()

    # Import table
    display_df = imports_df[[
        "id", "source", "import_timestamp", "records_processed",
        "records_inserted", "records_skipped", "records_conflicted", "status"
    ]].copy()
    display_df.columns = ["ID", "Source", "Timestamp", "Processed", "Inserted", "Skipped", "Conflicts", "Status"]

    # Color status
    def status_color(status):
        if status == "completed":
            return "✅"
        elif status == "failed":
            return "❌"
        return "⏳"

    display_df["Status"] = display_df["Status"].apply(status_color)
    st.dataframe(display_df, width="stretch", hide_index=True)

    st.divider()

    # Conflict details
    st.subheader("Conflict Details")
    conflicts_df = get_conflicts_detail(conn)

    if conflicts_df.empty:
        st.success("No conflicts recorded")
    else:
        st.warning(f"{len(conflicts_df)} conflicts found")

        # Group by table
        table_counts = conflicts_df.groupby("table_name").size().reset_index(name="count")
        col1, col2 = st.columns([1, 2])

        with col1:
            st.dataframe(table_counts, width="stretch", hide_index=True)

        with col2:
            # Show recent conflicts
            display_df = conflicts_df[["id", "table_name", "record_key", "conflict_fields"]].head(20)
            display_df.columns = ["ID", "Table", "Record Key", "Fields"]
            st.dataframe(display_df, width="stretch", hide_index=True)

        # Expandable conflict detail
        with st.expander("View Conflict Values"):
            selected_id = st.number_input("Conflict ID", min_value=1, value=int(conflicts_df["id"].iloc[0]))
            conflict = conflicts_df[conflicts_df["id"] == selected_id]
            if not conflict.empty:
                c = conflict.iloc[0]
                st.write(f"**Table:** {c['table_name']}")
                st.write(f"**Record Key:** {c['record_key']}")
                st.write(f"**Conflict Fields:** {c['conflict_fields']}")
                col1, col2 = st.columns(2)
                with col1:
                    st.write("**Existing Value:**")
                    st.code(c["existing_value"])
                with col2:
                    st.write("**New Value:**")
                    st.code(c["new_value"])
