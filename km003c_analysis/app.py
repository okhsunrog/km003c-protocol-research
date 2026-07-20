"""
Main entry point for the KM003C Analysis application.

This module provides the main Streamlit GUI for analyzing KM003C USB protocol captures.
The actual implementation is in the dashboards.main module.
"""

from km003c_analysis.dashboards.main import main

if __name__ == "__main__":
    main()
