"""Database connection utilities for dashboard"""
import sqlite3
from pathlib import Path
from typing import Optional
import streamlit as st

DB_PATHS = {
    "prod": Path("data/prod/health_data.db"),
    "test": Path("data/test/health_data.db"),
}


def get_connection(db_key: str = "prod") -> sqlite3.Connection:
    """Get database connection for specified environment"""
    db_path = DB_PATHS.get(db_key, DB_PATHS["prod"])

    if not db_path.exists():
        st.warning(f"Database not found: {db_path}")
        return None

    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db_if_needed(db_key: str = "prod") -> bool:
    """Initialize database schema if needed"""
    db_path = DB_PATHS.get(db_key, DB_PATHS["prod"])
    db_path.parent.mkdir(parents=True, exist_ok=True)

    schema_path = Path("schema/init.sql")
    if not schema_path.exists():
        return False

    conn = sqlite3.connect(db_path)
    conn.executescript(schema_path.read_text())
    conn.commit()
    conn.close()
    return True
