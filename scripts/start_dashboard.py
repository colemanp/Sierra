#!/usr/bin/env python3
"""Start the Streamlit dashboard"""
import subprocess
import sys
from pathlib import Path

# Get project root
project_root = Path(__file__).parent.parent
app_path = project_root / "dashboard" / "app.py"

subprocess.run([sys.executable, "-m", "streamlit", "run", str(app_path)])
