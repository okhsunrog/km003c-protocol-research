"""
Integration tests for packet parsing with the helpers module.

Tests how the updated parse_packet function integrates with the existing
transaction analysis workflow.
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
from km003c_lib import parse_packet


class TestParsingIntegration:
    """Test integration of packet parsing with transaction analysis."""

    @pytest.fixture
    def sample_transaction_data(self):
        """Create sample transaction data for testing."""
        # Real transaction data from orig_open_close.16
        return pl.DataFrame(
            [
                {
                    "start_time": 5.991,
                    "duration_ms": 0.2,
                    "type": "Host Command",
                    "submit_direction": "H->D",
                    "submit_data_length": 4,
                    "submit_payload_hex": "0c0a0200",  # ADC request
                    "complete_data_length": 0,
                    "complete_payload_hex": "",
                },
                {
                    "start_time": 5.930,
                    "duration_ms": 61.0,
                    "type": "Device Response",
                    "submit_direction": "D->H",
                    "submit_data_length": 0,
                    "submit_payload_hex": "",
                    "complete_data_length": 52,
                    "complete_payload_hex": "410a82020100000b5c0f0000faffffffa00f0000f2ffffff04100000500000007e0d7b7ed40471014201837e0080780025002100",  # ADC response
                },
                {
                    "start_time": 5.372,
                    "duration_ms": 0.1,
                    "type": "Host Command",
                    "submit_direction": "H->D",
                    "submit_data_length": 4,
                    "submit_payload_hex": "02010000",  # Control command
                    "complete_data_length": 0,
                    "complete_payload_hex": "",
                },
            ]
        )

    def test_parse_transaction_payloads(self, sample_transaction_data):
        """Test parsing all payloads in transaction data."""
        results = []

        for row in sample_transaction_data.iter_rows(named=True):
            # Parse submit payload if present
            if row["submit_payload_hex"]:
                submit_bytes = bytes.fromhex(row["submit_payload_hex"])
                submit_result = parse_packet(submit_bytes)
                results.append(
                    {
                        "direction": "submit",
                        "packet_type": submit_result.packet_type,
                        "has_adc_data": submit_result.adc_data is not None,
                        "payload_length": len(submit_bytes),
                    }
                )

            # Parse complete payload if present
            if row["complete_payload_hex"]:
                complete_bytes = bytes.fromhex(row["complete_payload_hex"])
                complete_result = parse_packet(complete_bytes)
                results.append(
                    {
                        "direction": "complete",
                        "packet_type": complete_result.packet_type,
                        "has_adc_data": complete_result.adc_data is not None,
                        "payload_length": len(complete_bytes),
                    }
                )

        # Verify we get the expected packet types
        packet_types = [r["packet_type"] for r in results]
        assert "CmdGetSimpleAdcData" in packet_types
        assert "SimpleAdcData" in packet_types
        assert "Generic" in packet_types

        # Verify ADC data is only in SimpleAdcData packets
        adc_data_packets = [r for r in results if r["has_adc_data"]]
        assert len(adc_data_packets) == 1
        assert adc_data_packets[0]["packet_type"] == "SimpleAdcData"

    def test_adc_request_response_correlation(self, sample_transaction_data):
        """Test that ADC requests can be correlated with responses."""
        adc_requests = []
        adc_responses = []

        for row in sample_transaction_data.iter_rows(named=True):
            # Check submit payloads for ADC requests
            if row["submit_payload_hex"]:
                submit_bytes = bytes.fromhex(row["submit_payload_hex"])
                submit_result = parse_packet(submit_bytes)
                if submit_result.packet_type == "CmdGetSimpleAdcData":
                    # Extract transaction ID from packet
                    transaction_id = submit_bytes[1]  # Second byte is transaction ID
                    adc_requests.append(
                        {
                            "transaction_id": transaction_id,
                            "timestamp": row["start_time"],
                        }
                    )

            # Check complete payloads for ADC responses
            if row["complete_payload_hex"]:
                complete_bytes = bytes.fromhex(row["complete_payload_hex"])
                complete_result = parse_packet(complete_bytes)
                if complete_result.packet_type == "SimpleAdcData":
                    # Extract transaction ID from packet
                    transaction_id = complete_bytes[1]  # Second byte is transaction ID
                    adc_responses.append(
                        {
                            "transaction_id": transaction_id,
                            "timestamp": row["start_time"],
                            "adc_data": complete_result.adc_data,
                        }
                    )

        # Verify we have matching request/response pairs
        assert len(adc_requests) == 1
        assert len(adc_responses) == 1
        assert adc_requests[0]["transaction_id"] == adc_responses[0]["transaction_id"]
        assert adc_requests[0]["transaction_id"] == 0x0A  # Expected transaction ID

    def test_packet_parsing_with_real_dataset(self):
        """Test packet parsing with a small subset of real dataset."""
        # Skip if dataset not available
        dataset_path = project_root / "usb_master_dataset.parquet"
        if not dataset_path.exists():
            pytest.skip("Dataset not available")

        # Load a small subset of the dataset
        df = helpers.load_master_dataset(str(dataset_path))
        filtered_df = df.filter(pl.col("source_file") == "orig_open_close.16").head(50)

        # Get transactions
        transactions = helpers.get_transactions(
            filtered_df, filter_out_enumeration=True
        )

        # Test parsing some transactions
        parsed_packets = []
        for row in transactions.head(10).iter_rows(named=True):
            if row["payload_hex"]:
                try:
                    payload_bytes = bytes.fromhex(row["payload_hex"])
                    result = parse_packet(payload_bytes)
                    parsed_packets.append(result.packet_type)
                except Exception:
                    pass  # Skip invalid packets

        # Verify we can parse packets from real data
        assert len(parsed_packets) > 0

        # Should have at least some recognized packet types
        packet_types = set(parsed_packets)
        expected_types = {"CmdGetSimpleAdcData", "SimpleAdcData", "Generic"}
        assert len(packet_types.intersection(expected_types)) > 0

    def test_transaction_type_classification(self, sample_transaction_data):
        """Test that transaction types are correctly classified with packet parsing."""
        classification_results = []

        for row in sample_transaction_data.iter_rows(named=True):
            transaction_info = {
                "transaction_type": row["type"],
                "parsed_submit": None,
                "parsed_complete": None,
            }

            # Parse submit payload
            if row["submit_payload_hex"]:
                submit_bytes = bytes.fromhex(row["submit_payload_hex"])
                submit_result = parse_packet(submit_bytes)
                transaction_info["parsed_submit"] = submit_result.packet_type

            # Parse complete payload
            if row["complete_payload_hex"]:
                complete_bytes = bytes.fromhex(row["complete_payload_hex"])
                complete_result = parse_packet(complete_bytes)
                transaction_info["parsed_complete"] = complete_result.packet_type

            classification_results.append(transaction_info)

        # Verify transaction type vs parsed type alignment
        for result in classification_results:
            if result["transaction_type"] == "Host Command":
                # Host commands should have parsed submit payload
                assert result["parsed_submit"] is not None
                assert result["parsed_complete"] is None
            elif result["transaction_type"] == "Device Response":
                # Device responses should have parsed complete payload
                assert result["parsed_submit"] is None
                assert result["parsed_complete"] is not None

    def test_adc_data_extraction_workflow(self, sample_transaction_data):
        """Test the complete workflow of extracting ADC data from transactions."""
        adc_measurements = []

        for row in sample_transaction_data.iter_rows(named=True):
            # Only look at complete payloads (device responses)
            if row["complete_payload_hex"]:
                complete_bytes = bytes.fromhex(row["complete_payload_hex"])
                result = parse_packet(complete_bytes)

                if result.packet_type == "SimpleAdcData" and result.adc_data:
                    adc = result.adc_data
                    adc_measurements.append(
                        {
                            "timestamp": row["start_time"],
                            "vbus_v": adc.vbus_v,
                            "ibus_a": adc.ibus_a,
                            "power_w": adc.power_w,
                            "temp_c": adc.temp_c,
                        }
                    )

        # Verify we extracted ADC data
        assert len(adc_measurements) == 1

        measurement = adc_measurements[0]
        assert "timestamp" in measurement
        assert "vbus_v" in measurement
        assert "ibus_a" in measurement
        assert "power_w" in measurement
        assert "temp_c" in measurement

        # Verify values are reasonable
        assert -1.0 <= measurement["vbus_v"] <= 30.0
        assert -10.0 <= measurement["ibus_a"] <= 10.0
        assert -40.0 <= measurement["temp_c"] <= 85.0


class TestPacketAnalysisHelpers:
    """Test helper functions for packet analysis."""

    def test_extract_transaction_id(self):
        """Test extracting transaction IDs from packets."""
        test_cases = [
            ("0c0a0200", 0x0A),  # ADC request
            (
                "410a82020100000b5c0f0000faffffffa00f0000f2ffffff04100000500000007e0d7b7ed40471014201837e0080780025002100",
                0x0A,
            ),  # ADC response
            ("0c0b0200", 0x0B),  # Different transaction ID
        ]

        for hex_data, expected_id in test_cases:
            packet_bytes = bytes.fromhex(hex_data)
            # Transaction ID is always in the second byte for our protocol
            actual_id = packet_bytes[1]
            assert actual_id == expected_id

    def test_packet_size_analysis(self):
        """Test analysis of packet sizes for different types."""
        test_cases = [
            ("0c0a0200", 4, "ADC request"),
            (
                "410a82020100000b5c0f0000faffffffa00f0000f2ffffff04100000500000007e0d7b7ed40471014201837e0080780025002100",
                52,
                "ADC response",
            ),
            ("02010000", 4, "Control command"),
            (
                "4402010133f8860c0054288cdc7e52729826872dd18b539a39c407d5c063d91102e36a9e",
                36,
                "Extended command",
            ),
        ]

        for hex_data, expected_size, description in test_cases:
            packet_bytes = bytes.fromhex(hex_data)
            assert len(packet_bytes) == expected_size, (
                f"Size mismatch for {description}"
            )

            # Parse and verify packet type makes sense for size
            result = parse_packet(packet_bytes)
            if expected_size == 52:
                assert result.packet_type == "SimpleAdcData"
            elif (
                expected_size == 4
                and hex_data.startswith("0c")
                and hex_data.endswith("0200")
            ):
                assert result.packet_type == "CmdGetSimpleAdcData"
            else:
                assert result.packet_type == "Generic"


if __name__ == "__main__":
    # Allow running tests directly
    pytest.main([__file__, "-v"])
