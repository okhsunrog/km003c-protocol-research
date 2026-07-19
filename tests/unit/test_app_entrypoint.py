import runpy
import sys
from pathlib import Path
from types import ModuleType

import pytest

pytestmark = pytest.mark.unit


def test_app_entrypoint_invokes_dashboard(monkeypatch):
    """Executing the Streamlit entry point must render the dashboard."""
    calls = []
    dashboard = ModuleType("km003c_analysis.dashboards.main")
    dashboard.main = lambda: calls.append(True)
    monkeypatch.setitem(sys.modules, dashboard.__name__, dashboard)

    app_path = Path(__file__).parents[2] / "km003c_analysis" / "app.py"
    runpy.run_path(app_path, run_name="__main__")

    assert calls == [True]
