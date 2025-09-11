"""
Tests for the km003c_lib packet parsing functionality.

Tests the updated parse_packet function that returns the complete Packet enum
instead of just ADC data.
"""

import sys
from pathlib import Path

import pytest

# Add the analysis scripts directory to the Python path for helpers
project_root = Path(__file__).parent.parent
analysis_scripts_path = project_root / "src" / "analysis" / "scripts"
sys.path.insert(0, str(analysis_scripts_path))

from km003c_lib import parse_packet

# Import the updated parse_packet function and related classes


class TestPacketParsing:
    """Test cases for packet parsing functionality."""

    def test_parse_adc_data_packet(self):
        """Test parsing of 52-byte ADC data response packets."""
        # Real ADC data packet from orig_open_close.16 dataset
        adc_packet_hex = "410a82020100000b5c0f0000faffffffa00f0000f2ffffff04100000500000007e0d7b7ed40471014201837e0080780025002100"
        adc_packet_bytes = bytes.fromhex(adc_packet_hex)

        result = parse_packet(adc_packet_bytes)

        assert result.packet_type == "SimpleAdcData"
        assert result.adc_data is not None
        assert result.pd_data is None
        assert result.raw_payload is None

        # Check ADC data values
        adc = result.adc_data
        assert adc.vbus_v == pytest.approx(0.004, abs=0.001)  # ~0.004V
        assert adc.ibus_a == pytest.approx(-0.000, abs=0.001)  # ~0A
        assert adc.power_w == pytest.approx(-0.000, abs=0.001)  # ~0W
        assert adc.temp_c == pytest.approx(26.0, abs=1.0)  # ~26°C

    def test_parse_adc_request_command(self):
        """Test parsing of ADC request commands (CmdGetSimpleAdcData)."""
        # Real ADC request command: packet_type=0x0C, id=0x0A, attribute=0x0002 (Adc)
        adc_request_hex = "0c0a0200"
        adc_request_bytes = bytes.fromhex(adc_request_hex)

        result = parse_packet(adc_request_bytes)

        assert result.packet_type == "CmdGetSimpleAdcData"
        assert result.adc_data is None
        assert result.pd_data is None
        assert result.raw_payload is None

    def test_parse_generic_control_command(self):
        """Test parsing of generic control commands."""
        # Real control command: packet_type=0x02, different from GetData
        control_command_hex = "02010000"
        control_command_bytes = bytes.fromhex(control_command_hex)

        result = parse_packet(control_command_bytes)

        assert result.packet_type == "Generic"
        assert result.adc_data is None
        assert result.pd_data is None
        assert result.raw_payload is not None
        assert len(result.raw_payload) == 0  # No payload after 4-byte header

    def test_parse_generic_data_command(self):
        """Test parsing of generic data commands with payloads."""
        # Real extended command with 32-byte payload
        extended_command_hex = (
            "4402010133f8860c0054288cdc7e52729826872dd18b539a39c407d5c063d91102e36a9e"
        )
        extended_command_bytes = bytes.fromhex(extended_command_hex)

        result = parse_packet(extended_command_bytes)

        assert result.packet_type == "Generic"
        assert result.adc_data is None
        assert result.pd_data is None
        assert result.raw_payload is not None
        assert len(result.raw_payload) == 32  # 32-byte payload

    def test_parse_other_get_data_command(self):
        """Test parsing of GetData commands with non-ADC attributes."""
        # GetData command with different attribute (not ADC)
        other_getdata_hex = "0c071000"  # packet_type=0x0C, id=0x07, attribute=0x0010
        other_getdata_bytes = bytes.fromhex(other_getdata_hex)

        result = parse_packet(other_getdata_bytes)

        assert result.packet_type == "Generic"  # Not recognized as ADC request
        assert result.adc_data is None
        assert result.pd_data is None
        assert result.raw_payload is not None
        assert len(result.raw_payload) == 0

    def test_parse_multiple_adc_transactions(self):
        """Test parsing of sequential ADC request/response pairs."""
        # Sequential transaction IDs should work correctly
        test_cases = [
            ("0c0b0200", "CmdGetSimpleAdcData"),  # Request ID 0x0B
            ("0c0c0200", "CmdGetSimpleAdcData"),  # Request ID 0x0C
            ("0c0d0200", "CmdGetSimpleAdcData"),  # Request ID 0x0D
        ]

        for hex_data, expected_type in test_cases:
            packet_bytes = bytes.fromhex(hex_data)
            result = parse_packet(packet_bytes)
            assert result.packet_type == expected_type

    def test_parse_invalid_packet_too_short(self):
        """Test parsing of invalid packets (too short)."""
        # Packet too short (less than 4 bytes for header)
        short_packet = b"\x0c\x0a\x02"

        with pytest.raises(Exception):  # Should raise ValueError from Rust
            parse_packet(short_packet)

    def test_parse_empty_packet(self):
        """Test parsing of empty packet."""
        empty_packet = b""

        with pytest.raises(Exception):  # Should raise ValueError from Rust
            parse_packet(empty_packet)

    def test_adc_response_transaction_ids(self):
        """Test that ADC responses contain matching transaction IDs."""
        # Real ADC responses with different transaction IDs
        test_cases = [
            (
                "410a82020100000b5c0f0000faffffffa00f0000f2ffffff04100000500000007e0d7b7ed40471014201837e0080780025002100",
                0x0A,
            ),
            (
                "410b82020100000ba70f0000f6ffffff810f0000f8ffffffe50f0000560000007f0d7b7ed40471014201837e0080780024002000",
                0x0B,
            ),
            (
                "410c82020100000ba70f0000f6ffffff810f0000f8ffffffe50f0000560000007f0d7b7ed30475014701837e0080780024001f00",
                0x0C,
            ),
        ]

        for hex_data, expected_id in test_cases:
            packet_bytes = bytes.fromhex(hex_data)
            result = parse_packet(packet_bytes)

            assert result.packet_type == "SimpleAdcData"
            assert result.adc_data is not None

            # Transaction ID should be in the second byte of the packet
            actual_id = packet_bytes[1]
            assert actual_id == expected_id

    def test_packet_repr_formatting(self):
        """Test that packet objects have proper string representations."""
        # Test ADC data packet representation
        adc_packet_hex = "410a82020100000b5c0f0000faffffffa00f0000f2ffffff04100000500000007e0d7b7ed40471014201837e0080780025002100"
        adc_packet_bytes = bytes.fromhex(adc_packet_hex)

        result = parse_packet(adc_packet_bytes)
        repr_str = str(result)

        assert "Packet::SimpleAdcData" in repr_str
        assert "AdcData" in repr_str
        assert "vbus=" in repr_str
        assert "temp=" in repr_str

    def test_adc_data_realistic_values(self):
        """Test that parsed ADC values are within realistic ranges."""
        adc_packet_hex = "410a82020100000b5c0f0000faffffffa00f0000f2ffffff04100000500000007e0d7b7ed40471014201837e0080780025002100"
        adc_packet_bytes = bytes.fromhex(adc_packet_hex)

        result = parse_packet(adc_packet_bytes)
        adc = result.adc_data

        # Test realistic ranges for USB power measurements
        assert -1.0 <= adc.vbus_v <= 30.0  # USB voltage range
        assert -10.0 <= adc.ibus_a <= 10.0  # USB current range
        assert -100.0 <= adc.power_w <= 100.0  # USB power range
        assert -40.0 <= adc.temp_c <= 85.0  # Operating temperature range
        assert 0.0 <= adc.vdp_v <= 5.0  # D+ voltage range
        assert 0.0 <= adc.vdm_v <= 5.0  # D- voltage range
        assert 0.0 <= adc.cc1_v <= 5.0  # CC1 voltage range
        assert 0.0 <= adc.cc2_v <= 5.0  # CC2 voltage range


class TestPacketClassification:
    """Test cases for proper packet type classification."""

    def test_all_packet_types_covered(self):
        """Test that we can parse all major packet types we expect to see."""
        test_cases = [
            # (hex_data, expected_type, description)
            ("0c0a0200", "CmdGetSimpleAdcData", "ADC request command"),
            (
                "410a82020100000b5c0f0000faffffffa00f0000f2ffffff04100000500000007e0d7b7ed40471014201837e0080780025002100",
                "SimpleAdcData",
                "ADC response data",
            ),
            ("02010000", "Generic", "Control command"),
            ("0c071000", "Generic", "Non-ADC GetData command"),
            (
                "4402010133f8860c0054288cdc7e52729826872dd18b539a39c407d5c063d91102e36a9e",
                "Generic",
                "Extended data command",
            ),
        ]

        for hex_data, expected_type, description in test_cases:
            packet_bytes = bytes.fromhex(hex_data)
            result = parse_packet(packet_bytes)
            assert result.packet_type == expected_type, (
                f"Failed for {description}: {hex_data}"
            )

    def test_packet_type_consistency(self):
        """Test that similar packets are classified consistently."""
        # Multiple ADC requests should all be CmdGetSimpleAdcData
        adc_requests = ["0c0a0200", "0c0b0200", "0c0c0200", "0c0d0200"]
        for hex_data in adc_requests:
            packet_bytes = bytes.fromhex(hex_data)
            result = parse_packet(packet_bytes)
            assert result.packet_type == "CmdGetSimpleAdcData"

        # Multiple extended commands should all be Generic
        extended_commands = [
            "4402010133f8860c0054288cdc7e52729826872dd18b539a39c407d5c063d91102e36a9e",
            "44030101636beaf3f0856506eee9a27e89722dcfd18b539a39c407d5c063d91102e36a9e",
        ]
        for hex_data in extended_commands:
            packet_bytes = bytes.fromhex(hex_data)
            result = parse_packet(packet_bytes)
            assert result.packet_type == "Generic"


if __name__ == "__main__":
    # Allow running tests directly
    pytest.main([__file__])
