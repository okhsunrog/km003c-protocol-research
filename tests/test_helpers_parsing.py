"""
Tests for the updated helpers.py parsing functions.

Tests the new add_parsed_packet_data and updated add_parsed_adc_data functions.
"""

import sys
from pathlib import Path

import polars as pl
import pytest

# Add the analysis scripts directory to the Python path
project_root = Path(__file__).parent.parent
analysis_scripts_path = project_root / "src" / "analysis" / "scripts"
sys.path.insert(0, str(analysis_scripts_path))

import helpers


class TestHelpersParsing:
    """Test the updated parsing functions in helpers.py"""

    @pytest.fixture
    def sample_payload_data(self):
        """Create sample DataFrame with various payload types."""
        return pl.DataFrame(
            [
                {
                    "frame_number": 1,
                    "timestamp": 5.930,
                    "payload_hex": "410a82020100000b5c0f0000faffffffa00f0000f2ffffff04100000500000007e0d7b7ed40471014201837e0080780025002100",  # ADC response
                    "data_length": 52,
                },
                {
                    "frame_number": 2,
                    "timestamp": 5.991,
                    "payload_hex": "0c0a0200",  # ADC request
                    "data_length": 4,
                },
                {
                    "frame_number": 3,
                    "timestamp": 5.372,
                    "payload_hex": "02010000",  # Control command
                    "data_length": 4,
                },
                {
                    "frame_number": 4,
                    "timestamp": 5.374,
                    "payload_hex": "4402010133f8860c0054288cdc7e52729826872dd18b539a39c407d5c063d91102e36a9e",  # Extended command
                    "data_length": 36,
                },
                {
                    "frame_number": 5,
                    "timestamp": 5.400,
                    "payload_hex": "",  # Empty payload
                    "data_length": 0,
                },
            ]
        )

    def test_add_parsed_packet_data(self, sample_payload_data):
        """Test the new add_parsed_packet_data function."""
        result_df = helpers.add_parsed_packet_data(sample_payload_data)

        # Check that new columns are added
        assert "packet_type" in result_df.columns
        assert "vbus_v" in result_df.columns
        assert "ibus_a" in result_df.columns
        assert "temp_c" in result_df.columns

        # Check that original columns are preserved
        assert "frame_number" in result_df.columns
        assert "timestamp" in result_df.columns
        assert "payload_hex" in result_df.columns

        # Check packet type classification
        packet_types = result_df["packet_type"].to_list()
        assert "SimpleAdcData" in packet_types  # ADC response
        assert "CmdGetSimpleAdcData" in packet_types  # ADC request
        assert "Generic" in packet_types  # Control and extended commands
        assert "UNPARSEABLE" in packet_types  # Empty payload

    def test_add_parsed_packet_data_adc_extraction(self, sample_payload_data):
        """Test that ADC data is correctly extracted."""
        result_df = helpers.add_parsed_packet_data(sample_payload_data)

        # Find the ADC data row
        adc_row = result_df.filter(pl.col("packet_type") == "SimpleAdcData")
        assert len(adc_row) == 1

        adc_data = adc_row.to_dicts()[0]

        # Check ADC values are populated
        assert adc_data["vbus_v"] is not None
        assert adc_data["ibus_a"] is not None
        assert adc_data["temp_c"] is not None
        assert adc_data["power_w"] is not None

        # Check values are reasonable
        assert -1.0 <= adc_data["vbus_v"] <= 30.0
        assert -10.0 <= adc_data["ibus_a"] <= 10.0
        assert -40.0 <= adc_data["temp_c"] <= 85.0

    def test_add_parsed_packet_data_non_adc_packets(self, sample_payload_data):
        """Test that non-ADC packets don't have ADC data."""
        result_df = helpers.add_parsed_packet_data(sample_payload_data)

        # Check non-ADC packets
        non_adc_rows = result_df.filter(pl.col("packet_type") != "SimpleAdcData")

        for row in non_adc_rows.to_dicts():
            # ADC fields should be None for non-ADC packets
            assert row["vbus_v"] is None
            assert row["ibus_a"] is None
            assert row["temp_c"] is None
            assert row["power_w"] is None

    def test_add_parsed_adc_data_legacy_compatibility(self, sample_payload_data):
        """Test that the legacy add_parsed_adc_data function still works."""
        result_df = helpers.add_parsed_adc_data(sample_payload_data)

        # Check that it has the legacy packet_type values
        packet_types = result_df["packet_type"].to_list()
        assert "ADC_DATA" in packet_types
        assert "OTHER" in packet_types

        # Check that ADC data is extracted for ADC_DATA packets
        adc_rows = result_df.filter(pl.col("packet_type") == "ADC_DATA")
        assert len(adc_rows) == 1

        adc_data = adc_rows.to_dicts()[0]
        assert adc_data["vbus_v"] is not None
        assert adc_data["temp_c"] is not None

    def test_packet_type_distribution(self, sample_payload_data):
        """Test the distribution of packet types."""
        result_df = helpers.add_parsed_packet_data(sample_payload_data)

        packet_counts = result_df["packet_type"].value_counts().sort("packet_type")
        packet_dict = {
            row["packet_type"]: row["count"] for row in packet_counts.to_dicts()
        }

        # Verify expected packet types and counts
        assert packet_dict.get("SimpleAdcData", 0) == 1  # 1 ADC response
        assert packet_dict.get("CmdGetSimpleAdcData", 0) == 1  # 1 ADC request
        assert packet_dict.get("Generic", 0) == 2  # 2 generic commands
        assert packet_dict.get("UNPARSEABLE", 0) == 1  # 1 empty payload

    def test_error_handling_invalid_hex(self):
        """Test error handling for invalid hex data."""
        invalid_data = pl.DataFrame(
            [
                {"payload_hex": "invalid_hex", "data_length": 5},
                {"payload_hex": "0c0a02", "data_length": 3},  # Too short
            ]
        )

        result_df = helpers.add_parsed_packet_data(invalid_data)

        # Should handle errors gracefully
        packet_types = result_df["packet_type"].to_list()
        assert all(pt == "UNPARSEABLE" for pt in packet_types)

    def test_empty_dataframe(self):
        """Test handling of empty DataFrame."""
        empty_df = pl.DataFrame(
            {"payload_hex": [], "data_length": []},
            schema={"payload_hex": pl.String, "data_length": pl.Int64},
        )

        result_df = helpers.add_parsed_packet_data(empty_df)

        # Should return empty DataFrame with correct schema
        assert len(result_df) == 0
        assert "packet_type" in result_df.columns
        assert "vbus_v" in result_df.columns

    def test_parsing_performance(self, sample_payload_data):
        """Test that parsing doesn't significantly slow down processing."""
        import time

        # Measure parsing time
        start_time = time.time()
        result_df = helpers.add_parsed_packet_data(sample_payload_data)
        parsing_time = time.time() - start_time

        # Should complete quickly for small datasets
        assert parsing_time < 1.0  # Less than 1 second
        assert len(result_df) == len(sample_payload_data)


class TestHelpersParsingIntegration:
    """Test integration of parsing with other helpers functions."""

    @pytest.fixture
    def sample_payload_data(self):
        """Create sample DataFrame with various payload types."""
        return pl.DataFrame(
            [
                {
                    "frame_number": 1,
                    "timestamp": 5.930,
                    "payload_hex": "410a82020100000b5c0f0000faffffffa00f0000f2ffffff04100000500000007e0d7b7ed40471014201837e0080780025002100",  # ADC response
                    "data_length": 52,
                },
                {
                    "frame_number": 2,
                    "timestamp": 5.991,
                    "payload_hex": "0c0a0200",  # ADC request
                    "data_length": 4,
                },
            ]
        )

    def test_parsing_with_real_dataset_subset(self):
        """Test parsing with a real dataset subset if available."""
        dataset_path = project_root / "usb_master_dataset.parquet"
        if not dataset_path.exists():
            pytest.skip("Dataset not available")

        # Load a small subset
        df = helpers.load_master_dataset(str(dataset_path))
        subset = df.filter(
            (pl.col("source_file") == "orig_open_close.16")
            & (pl.col("payload_hex") != "")
        ).head(20)

        if len(subset) == 0:
            pytest.skip("No payload data in dataset subset")

        # Apply parsing
        parsed_df = helpers.add_parsed_packet_data(subset)

        # Verify parsing worked
        assert "packet_type" in parsed_df.columns

        # Should have some recognizable packet types
        packet_types = set(parsed_df["packet_type"].to_list())
        expected_types = {
            "SimpleAdcData",
            "CmdGetSimpleAdcData",
            "Generic",
            "UNPARSEABLE",
        }
        assert len(packet_types.intersection(expected_types)) > 0

    def test_parsing_preserves_data_integrity(self, sample_payload_data):
        """Test that parsing preserves original data integrity."""
        original_df = sample_payload_data.clone()
        parsed_df = helpers.add_parsed_packet_data(sample_payload_data)

        # Original columns should be unchanged
        for col in original_df.columns:
            if col in parsed_df.columns:
                assert original_df[col].equals(parsed_df[col])

        # Row count should be the same
        assert len(original_df) == len(parsed_df)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
