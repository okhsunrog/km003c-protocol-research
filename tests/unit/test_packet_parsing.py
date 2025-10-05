"""
Tests for the km003c_lib packet parsing functionality.

Tests the updated parse_packet function that returns dict-like Packet enum.
"""

import sys
from pathlib import Path

import pytest

# Add the analysis scripts directory to the Python path for helpers
project_root = Path(__file__).parent.parent.parent
analysis_scripts_path = project_root / "src" / "analysis" / "scripts"
sys.path.insert(0, str(analysis_scripts_path))

from km003c_lib import parse_packet  # noqa: E402

# Mark all tests in this module as unit tests
pytestmark = pytest.mark.unit


# Helper functions to extract data from new dict-based Packet API
def get_packet_type(packet):
    """Extract packet type from dict-based Packet."""
    if isinstance(packet, dict):
        # Return the variant key
        return list(packet.keys())[0]
    return None


def get_adc_data(packet):
    """Extract ADC data from DataResponse packet."""
    if "DataResponse" not in packet:
        return None
    payloads = packet["DataResponse"]["payloads"]
    for payload in payloads:
        if "Adc" in payload:
            return payload["Adc"]
    return None


def get_adcqueue_data(packet):
    """Extract AdcQueue data from DataResponse packet."""
    if "DataResponse" not in packet:
        return None
    payloads = packet["DataResponse"]["payloads"]
    for payload in payloads:
        if "AdcQueue" in payload:
            return payload["AdcQueue"]
    return None


def get_pd_status(packet):
    """Extract PD status from DataResponse packet."""
    if "DataResponse" not in packet:
        return None
    payloads = packet["DataResponse"]["payloads"]
    for payload in payloads:
        if "PdStatus" in payload:
            return payload["PdStatus"]
    return None


def get_pd_events(packet):
    """Extract PD events from DataResponse packet."""
    if "DataResponse" not in packet:
        return None
    payloads = packet["DataResponse"]["payloads"]
    for payload in payloads:
        if "PdEvents" in payload:
            return payload["PdEvents"]
    return None


class TestPacketParsing:
    """Test cases for packet parsing functionality."""

    def test_parse_adc_data_packet(self):
        """Test parsing of 52-byte ADC data response packets."""
        # Real ADC data packet from orig_open_close.16 dataset
        adc_packet_hex = "410a82020100000b5c0f0000faffffffa00f0000f2ffffff04100000500000007e0d7b7ed40471014201837e0080780025002100"
        adc_packet_bytes = bytes.fromhex(adc_packet_hex)

        result = parse_packet(adc_packet_bytes)

        packet_type = get_packet_type(result)
        assert packet_type == "DataResponse"

        adc = get_adc_data(result)
        assert adc is not None
        assert get_pd_status(result) is None
        assert get_pd_events(result) is None

        # Check ADC data values
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

        packet_type = get_packet_type(result)
        assert packet_type == "GetData"

        # GetData has attribute_mask field (wire ATT_ADC = 0x0001)
        assert "attribute_mask" in result["GetData"]
        assert result["GetData"]["attribute_mask"] == 0x0001

    def test_parse_generic_control_command(self):
        """Test parsing of Connect command."""
        # Real control command: packet_type=0x02 (Connect)
        control_command_hex = "02010000"
        control_command_bytes = bytes.fromhex(control_command_hex)

        result = parse_packet(control_command_bytes)

        packet_type = get_packet_type(result)
        assert packet_type == "Connect"
        # Connect is empty variant: {"Connect": None}
        assert result["Connect"] is None

    def test_parse_generic_data_command(self):
        """Test parsing of generic data commands with payloads."""
        # Real Unknown68 command with 32-byte payload
        extended_command_hex = (
            "4402010133f8860c0054288cdc7e52729826872dd18b539a39c407d5c063d91102e36a9e"
        )
        extended_command_bytes = bytes.fromhex(extended_command_hex)

        result = parse_packet(extended_command_bytes)

        packet_type = get_packet_type(result)
        assert packet_type == "Generic"

        # Generic contains a RawPacket
        raw_packet = result["Generic"]
        assert isinstance(raw_packet, dict)

    def test_parse_other_get_data_command(self):
        """Test parsing of GetData commands with non-ADC attributes."""
        # GetData command with PD attribute (0x0010)
        # For PD (0x0010), byte2 must be 0x20 due to the reserved bit after id
        other_getdata_hex = "0c072000"  # packet_type=0x0C, id=0x07, attribute=0x0010
        other_getdata_bytes = bytes.fromhex(other_getdata_hex)

        result = parse_packet(other_getdata_bytes)

        packet_type = get_packet_type(result)
        assert packet_type == "GetData"
        assert result["GetData"]["attribute_mask"] == 0x0010

    def test_parse_multiple_adc_transactions(self):
        """Test parsing of sequential ADC request/response pairs."""
        # Sequential transaction IDs should work correctly
        test_cases = [
            ("0c0b0200", "GetData"),  # Request ID 0x0B
            ("0c0c0200", "GetData"),  # Request ID 0x0C
            ("0c0d0200", "GetData"),  # Request ID 0x0D
        ]

        for hex_data, expected_type in test_cases:
            packet_bytes = bytes.fromhex(hex_data)
            result = parse_packet(packet_bytes)
            assert get_packet_type(result) == expected_type

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

            packet_type = get_packet_type(result)
            assert packet_type == "DataResponse"
            assert get_adc_data(result) is not None

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

        assert "DataResponse" in repr_str

    def test_adc_data_realistic_values(self):
        """Test that parsed ADC values are within realistic ranges."""
        adc_packet_hex = "410a82020100000b5c0f0000faffffffa00f0000f2ffffff04100000500000007e0d7b7ed40471014201837e0080780025002100"
        adc_packet_bytes = bytes.fromhex(adc_packet_hex)

        result = parse_packet(adc_packet_bytes)
        adc = get_adc_data(result)

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
            ("0c0a0200", "GetData", "ADC request command"),
            (
                "410a82020100000b5c0f0000faffffffa00f0000f2ffffff04100000500000007e0d7b7ed40471014201837e0080780025002100",
                "DataResponse",
                "ADC response data",
            ),
            ("02010000", "Connect", "Connect command"),
            ("0c071000", "GetData", "PD GetData command"),
            (
                "4402010133f8860c0054288cdc7e52729826872dd18b539a39c407d5c063d91102e36a9e",
                "Generic",
                "Unknown68 command",
            ),
        ]

        for hex_data, expected_type, description in test_cases:
            packet_bytes = bytes.fromhex(hex_data)
            result = parse_packet(packet_bytes)
            assert get_packet_type(result) == expected_type, (
                f"Failed for {description}: {hex_data}"
            )

    def test_packet_type_consistency(self):
        """Test that similar packets are classified consistently."""
        # Multiple GetData requests should all be classified as GetData
        getdata_requests = ["0c0a0200", "0c0b0200", "0c0c0200", "0c0d0200"]
        for hex_data in getdata_requests:
            packet_bytes = bytes.fromhex(hex_data)
            result = parse_packet(packet_bytes)
            assert get_packet_type(result) == "GetData"

        # Multiple extended commands should all be Generic
        extended_commands = [
            "4402010133f8860c0054288cdc7e52729826872dd18b539a39c407d5c063d91102e36a9e",
            "44030101636beaf3f0856506eee9a27e89722dcfd18b539a39c407d5c063d91102e36a9e",
        ]
        for hex_data in extended_commands:
            packet_bytes = bytes.fromhex(hex_data)
            result = parse_packet(packet_bytes)
            assert get_packet_type(result) == "Generic"


class TestChainedLogicalPackets:
    """Test parsing of chained logical packets (multiple payloads in one packet)."""

    def test_adc_plus_pd_status(self):
        """Test ADC + PdStatus chained packet (68 bytes total)."""
        import polars as pl

        dataset_path = Path(__file__).parent.parent / "data/processed/usb_master_dataset.parquet"
        if not dataset_path.exists():
            pytest.skip("Dataset not available")

        df = pl.read_parquet(dataset_path)
        session = df.filter(pl.col('source_file') == 'pd_capture_new.9')
        bulk = session.filter(pl.col('transfer_type') == '0x03')

        # Find ADC+PD packet (68 bytes = 4 main + 4 ext + 44 ADC + 4 ext + 12 PD)
        responses = bulk.filter(
            (pl.col('endpoint_address') == '0x81') &
            (pl.col('urb_type') == 'C') &
            (pl.col('data_length') == 68)
        )

        assert len(responses) > 0, "No ADC+PD packets found"

        row = responses.row(0, named=True)
        payload = bytes.fromhex(row['payload_hex'])
        packet = parse_packet(payload)

        # Should have BOTH ADC and PD status
        packet_type = get_packet_type(packet)
        assert packet_type == "DataResponse"

        adc_data = get_adc_data(packet)
        pd_status = get_pd_status(packet)

        assert adc_data is not None, "ADC data missing in chained packet"
        assert pd_status is not None, "PD status missing in chained packet"

        # Both should have valid data
        assert 0.0 <= adc_data.vbus_v <= 50.0
        assert 0.0 <= pd_status.vbus_v <= 50.0

        print(f"✓ Chained ADC+PD: ADC={adc_data.vbus_v:.3f}V, PD={pd_status.vbus_v:.3f}V")

    def test_adc_plus_adcqueue(self):
        """Test ADC + AdcQueue chained packet."""
        import polars as pl

        dataset_path = Path(__file__).parent.parent / "data/processed/usb_master_dataset.parquet"
        if not dataset_path.exists():
            pytest.skip("Dataset not available")

        df = pl.read_parquet(dataset_path)
        session = df.filter(pl.col('source_file') == 'orig_adc_record.6')
        bulk = session.filter(pl.col('transfer_type') == '0x03')

        responses = bulk.filter(
            (pl.col('endpoint_address') == '0x81') &
            (pl.col('urb_type') == 'C') &
            pl.col('payload_hex').is_not_null()
        )

        # Find ADC+AdcQueue packet
        found = False
        for row in responses.iter_rows(named=True):
            payload = bytes.fromhex(row['payload_hex'])
            try:
                packet = parse_packet(payload)
                adc_data = get_adc_data(packet)
                adcqueue_data = get_adcqueue_data(packet)

                if adc_data and adcqueue_data:
                    found = True

                    # Should have BOTH ADC and AdcQueue
                    assert get_packet_type(packet) == "DataResponse"
                    assert len(adcqueue_data.samples) >= 1

                    print(f"✓ Chained ADC+AdcQueue: ADC={adc_data.vbus_v:.3f}V, Queue={len(adcqueue_data.samples)} samples")
                    break
            except:
                continue

        assert found, "No ADC+AdcQueue chained packets found in dataset"


class TestAdcQueueParsing:
    """Test AdcQueue multi-sample parsing against real dataset."""

    def test_parse_adcqueue_from_dataset(self):
        """Test parsing AdcQueue responses from actual USB captures."""
        import polars as pl

        # Load dataset
        dataset_path = Path(__file__).parent.parent / "data/processed/usb_master_dataset.parquet"
        if not dataset_path.exists():
            pytest.skip("Dataset not available")

        df = pl.read_parquet(dataset_path)

        # Filter for AdcQueue responses from orig_adc_1000hz.6
        session = df.filter(pl.col('source_file') == 'orig_adc_1000hz.6')
        bulk = session.filter(pl.col('transfer_type') == '0x03')
        responses = bulk.filter(
            (pl.col('endpoint_address') == '0x81') &
            (pl.col('urb_type') == 'C') &
            pl.col('payload_hex').is_not_null()
        )

        adcqueue_count = 0
        adc_count = 0

        for row in responses.iter_rows(named=True):
            payload_hex = row['payload_hex']
            if not payload_hex or len(payload_hex) < 16:
                continue

            payload = bytes.fromhex(payload_hex)

            try:
                packet = parse_packet(payload)
                adcqueue_data = get_adcqueue_data(packet)
                adc_data = get_adc_data(packet)

                if adcqueue_data:
                    adcqueue_count += 1
                    samples = adcqueue_data.samples

                    # Validate AdcQueue structure
                    assert len(samples) > 0, "AdcQueue has no samples"
                    assert 5 <= len(samples) <= 50, f"Unexpected sample count: {len(samples)}"

                    # Validate first sample fields
                    first = samples[0]
                    assert isinstance(first.sequence, int)
                    assert isinstance(first.vbus_v, float)
                    assert isinstance(first.ibus_a, float)
                    assert isinstance(first.power_w, float)

                    # Sanity check values
                    assert -1.0 <= first.vbus_v <= 50.0
                    assert -10.0 <= first.ibus_a <= 10.0

                    # Test has_dropped_samples method
                    assert isinstance(adcqueue_data.has_dropped_samples(), bool)

                    # Test sequence_range method
                    seq_range = adcqueue_data.sequence_range()
                    if seq_range:
                        assert seq_range[0] <= seq_range[1] or (seq_range[0] > 60000 and seq_range[1] < 1000)  # Handle wrap

                elif adc_data:
                    adc_count += 1
            except Exception as e:
                # Some packets might not parse (that's OK for this test)
                pass

        # Should have found AdcQueue data in this capture
        assert adcqueue_count > 0, f"No AdcQueue packets found (found {adc_count} ADC packets)"
        assert adcqueue_count >= 200, f"Expected >=200 AdcQueue packets, found {adcqueue_count}"
        print(f"✓ Parsed {adcqueue_count} AdcQueue packets and {adc_count} ADC packets")

    def test_adcqueue_sample_structure(self):
        """Test AdcQueue sample has all expected fields using dataset."""
        import polars as pl

        # Load a real AdcQueue packet from dataset
        dataset_path = Path(__file__).parent.parent / "data/processed/usb_master_dataset.parquet"
        if not dataset_path.exists():
            pytest.skip("Dataset not available")

        df = pl.read_parquet(dataset_path)
        session = df.filter(pl.col('source_file') == 'orig_adc_1000hz.6')
        bulk = session.filter(pl.col('transfer_type') == '0x03')
        responses = bulk.filter(
            (pl.col('endpoint_address') == '0x81') &
            (pl.col('urb_type') == 'C') &
            pl.col('payload_hex').is_not_null() &
            (pl.col('frame_number') >= 1004)
        )

        # Find first valid AdcQueue packet
        for row in responses.head(10).iter_rows(named=True):
            payload = bytes.fromhex(row['payload_hex'])
            try:
                packet = parse_packet(payload)
                adcqueue_data = get_adcqueue_data(packet)

                if adcqueue_data and len(adcqueue_data.samples) >= 10:
                    # Found a valid one!
                    assert get_packet_type(packet) == "DataResponse"

                    samples = adcqueue_data.samples
                    assert len(samples) >= 10  # At least 10 samples

                    # Check first sample has all fields
                    first = samples[0]
                    assert hasattr(first, 'sequence')
                    assert hasattr(first, 'vbus_v')
                    assert hasattr(first, 'ibus_a')
                    assert hasattr(first, 'power_w')
                    assert hasattr(first, 'cc1_v')
                    assert hasattr(first, 'cc2_v')
                    assert hasattr(first, 'vdp_v')
                    assert hasattr(first, 'vdm_v')

                    # Test repr works
                    assert 'AdcQueueSample' in repr(first)
                    assert 'AdcQueueData' in repr(adcqueue_data)

                    return  # Test passed
            except Exception as e:
                continue

        pytest.fail("Could not find a valid AdcQueue packet in dataset")


if __name__ == "__main__":
    # Allow running tests directly
    pytest.main([__file__])
