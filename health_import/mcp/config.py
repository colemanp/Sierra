"""MCP server configuration"""
from pathlib import Path

# Database paths
DB_PATHS = {
    "prod": Path(__file__).parent.parent.parent / "data" / "prod" / "health_data.db",
    "test": Path(__file__).parent.parent.parent / "data" / "test" / "health_data.db",
}

# Active database - change this to switch environments
DB_PATH = DB_PATHS["prod"]
