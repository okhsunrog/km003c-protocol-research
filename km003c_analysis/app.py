"""
Main entry point for the KM003C Analysis application.

This module provides the main Streamlit GUI for analyzing KM003C USB protocol captures.
The actual implementation is in the dashboards.main module.
"""

# Import and run the main dashboard
from .dashboards.main import *

# This allows the app to be run with: streamlit run km003c_analysis/app.py
# or: uv run python -m streamlit run km003c_analysis/app.py