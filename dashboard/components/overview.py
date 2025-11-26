"""Overview tab component"""
import streamlit as st
import pandas as pd
from dashboard.utils.queries import (
    get_source_metrics,
    get_table_stats,
    get_recent_imports,
    get_conflict_summary,
)


def render_overview(conn):
    """Render overview tab"""
    st.header("Overview")

    if conn is None:
        st.warning("No database connection")
        return

    # Source metrics
    st.subheader("Data Sources")
    source_df = get_source_metrics(conn)

    if not source_df.empty:
        cols = st.columns(3)
        for i, row in source_df.iterrows():
            col = cols[i % 3]
            with col:
                total = row['total_records']
                total = 0 if pd.isna(total) else int(total)
                st.metric(
                    label=row["source"].replace("_", " ").title(),
                    value=f"{total:,} records",
                    delta=f"Last: {row['last_import'][:10] if row['last_import'] else 'Never'}"
                )

    st.divider()

    # Table statistics
    st.subheader("Data Coverage")
    table_df = get_table_stats(conn)

    if not table_df.empty:
        # Format as cards
        cols = st.columns(3)
        for i, row in table_df.iterrows():
            col = cols[i % 3]
            with col:
                with st.container(border=True):
                    st.markdown(f"**{row['category']}**")
                    st.write(f"Records: {int(row['records']):,}")
                    if row['earliest'] and row['latest']:
                        st.caption(f"{row['earliest']} → {row['latest']}")
                    else:
                        st.caption("No data")

    st.divider()

    # Recent imports
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Recent Imports")
        imports_df = get_recent_imports(conn, limit=5)
        if not imports_df.empty:
            # Simplify for display
            display_df = imports_df[["source", "import_timestamp", "records_inserted", "status"]].copy()
            display_df.columns = ["Source", "Time", "Inserted", "Status"]
            st.dataframe(display_df, use_container_width=True, hide_index=True)
        else:
            st.info("No imports yet")

    with col2:
        st.subheader("Conflicts")
        conflicts_df = get_conflict_summary(conn)
        if not conflicts_df.empty:
            st.dataframe(conflicts_df, use_container_width=True, hide_index=True)
        else:
            st.success("No conflicts")
