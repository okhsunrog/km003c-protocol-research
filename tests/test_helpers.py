import sys
from pathlib import Path

import polars as pl
import pytest

# Add the analysis scripts directory to the Python path
project_root = Path(__file__).parent.parent
analysis_scripts_path = project_root / "src" / "analysis" / "scripts"
sys.path.insert(0, str(analysis_scripts_path))

from helpers import get_transactions  # noqa: E402


@pytest.fixture
def sample_packet_data():
    """Provides a sample Polars DataFrame simulating raw USB packet data."""
    data = [
        {
            "timestamp": 1.0,
            "urb_id": "0x1",
            "urb_type": "S",
            "transfer_type": "0x03",
            "direction": "H->D",
            "payload_hex": "aabb",
            "data_length": 2,
            "bmrequest_type": None,
            "brequest": None,
        },
        {
            "timestamp": 1.1,
            "urb_id": "0x1",
            "urb_type": "C",
            "transfer_type": "0x03",
            "direction": "H->D",
            "payload_hex": "",
            "data_length": 0,
            "bmrequest_type": None,
            "brequest": None,
        },
        {
            "timestamp": 1.2,
            "urb_id": "0x2",
            "urb_type": "S",
            "transfer_type": "0x02",
            "direction": "D->H",
            "payload_hex": "",
            "data_length": 0,
            "bmrequest_type": "0x80",
            "brequest": "0x06",
        },
        {
            "timestamp": 1.3,
            "urb_id": "0x2",
            "urb_type": "C",
            "transfer_type": "0x02",
            "direction": "D->H",
            "payload_hex": "ccdd",
            "data_length": 2,
            "bmrequest_type": "0x80",
            "brequest": "0x06",
        },
    ]
    return pl.DataFrame(data)


def test_get_transactions_runs_without_error(sample_packet_data):
    """
    Tests that get_transactions runs without raising an exception and returns a DataFrame.
    """
    try:
        result_df = get_transactions(sample_packet_data)
        assert isinstance(result_df, pl.DataFrame), (
            "Function should return a Polars DataFrame."
        )
        assert not result_df.is_empty(), "Resulting DataFrame should not be empty."
        assert "type" in result_df.columns, (
            "Result DataFrame should have a 'type' column."
        )
    except Exception as e:
        pytest.fail(f"get_transactions raised an unexpected exception: {e}")
