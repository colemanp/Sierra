"""MCP Activity tab component - shows MCP request/response activity"""
import streamlit as st
import pandas as pd
import json


def get_mcp_requests(conn, limit: int = 50) -> pd.DataFrame:
    """Get recent MCP requests from database"""
    query = """
    SELECT id, timestamp, tool_name, params, response, response_tokens, duration_ms
    FROM mcp_requests
    ORDER BY timestamp DESC
    LIMIT ?
    """
    try:
        return pd.read_sql_query(query, conn, params=(limit,))
    except Exception:
        return pd.DataFrame()


def get_mcp_stats(conn) -> dict:
    """Get MCP usage statistics"""
    try:
        stats = conn.execute("""
            SELECT
                COUNT(*) as total_requests,
                SUM(response_tokens) as total_tokens,
                AVG(response_tokens) as avg_tokens,
                AVG(duration_ms) as avg_duration_ms
            FROM mcp_requests
        """).fetchone()

        by_tool = conn.execute("""
            SELECT tool_name,
                   COUNT(*) as count,
                   SUM(response_tokens) as total_tokens,
                   AVG(response_tokens) as avg_tokens,
                   MIN(response_tokens) as min_tokens,
                   MAX(response_tokens) as max_tokens,
                   AVG(duration_ms) as avg_ms,
                   MAX(timestamp) as last_used
            FROM mcp_requests
            GROUP BY tool_name
            ORDER BY count DESC
        """).fetchall()

        return {
            "total": stats[0] or 0,
            "total_tokens": stats[1] or 0,
            "avg_tokens": stats[2] or 0,
            "avg_duration": stats[3] or 0,
            "by_tool": by_tool,
        }
    except Exception:
        return {"total": 0, "total_tokens": 0, "avg_tokens": 0, "avg_duration": 0, "by_tool": []}


def render_mcp(conn):
    """Render MCP Activity tab"""
    col_header, col_btn = st.columns([4, 1])
    with col_header:
        st.header("MCP Activity")
    with col_btn:
        st.write("")  # spacer
        if st.button("🔄 Reload", key="mcp_reload"):
            st.rerun()

    if conn is None:
        st.warning("No database connection")
        return

    # Check if table exists
    try:
        conn.execute("SELECT 1 FROM mcp_requests LIMIT 1")
    except Exception:
        st.info("No MCP activity yet. The MCP server will log requests when used from Claude Desktop.")
        return

    # Stats overview
    stats = get_mcp_stats(conn)

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Requests", stats["total"])
    col2.metric("Total Tokens", f"{stats['total_tokens']:,}")
    col3.metric("Avg Tokens/Request", f"{stats['avg_tokens']:.0f}")
    col4.metric("Avg Duration", f"{stats['avg_duration']:.0f}ms")

    st.divider()

    # Tool breakdown
    if stats["by_tool"]:
        st.subheader("Requests by Tool")
        tool_data = []
        for row in stats["by_tool"]:
            last_used = pd.to_datetime(row[7]).strftime("%m-%d %H:%M") if row[7] else "-"
            tool_data.append({
                "Tool": row[0],
                "Count": row[1],
                "Tot Tokens": row[2] or 0,
                "Avg": f"{row[3]:.0f}" if row[3] else "-",
                "Min": row[4] or "-",
                "Max": row[5] or "-",
                "Avg ms": f"{row[6]:.0f}" if row[6] else "-",
                "Last Used": last_used,
            })
        st.dataframe(pd.DataFrame(tool_data), width="stretch", hide_index=True)

        st.divider()

    # Get recent requests
    df = get_mcp_requests(conn)

    if df.empty:
        st.info("No MCP requests recorded yet.")
        return

    # Request history table
    st.subheader("Request History")

    # Format for display
    display_df = df.copy()
    display_df["Timestamp"] = pd.to_datetime(display_df["timestamp"]).dt.strftime("%Y-%m-%d %H:%M:%S")
    display_df["Params (truncated)"] = display_df["params"].apply(
        lambda x: (x[:50] + "...") if x and len(x) > 50 else (x or "-")
    )

    # Select columns for display
    history_df = display_df[["Timestamp", "tool_name", "Params (truncated)", "response_tokens", "duration_ms"]]
    history_df.columns = ["Timestamp", "Tool", "Params", "Tokens", "Duration (ms)"]

    # Show table with row selection
    selection = st.dataframe(
        history_df,
        width="stretch",
        hide_index=True,
        selection_mode="single-row",
        on_select="rerun",
    )

    # Get selected row index (default to 0 if none selected)
    selected_rows = selection.selection.rows
    selected_idx = selected_rows[0] if selected_rows else 0

    st.divider()

    # Request/Response detail for selected row
    st.subheader("Request Detail")
    selected = df.iloc[selected_idx]
    sel_ts = pd.to_datetime(selected["timestamp"]).strftime("%Y-%m-%d %H:%M:%S")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Timestamp", sel_ts)
    col2.metric("Tool", selected["tool_name"])
    col3.metric("Tokens", selected["response_tokens"])
    col4.metric("Duration", f"{selected['duration_ms']}ms")

    col1, col2 = st.columns(2)
    with col1:
        st.write("**Parameters:**")
        if selected["params"]:
            try:
                st.json(json.loads(selected["params"]))
            except:
                st.code(selected["params"])
        else:
            st.write("-")

    with col2:
        st.write("**Response:**")
        if selected["response"]:
            try:
                st.json(json.loads(selected["response"]))
            except:
                st.code(selected["response"])
        else:
            st.write("-")
