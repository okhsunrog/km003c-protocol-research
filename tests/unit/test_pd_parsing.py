"""
Tests for USB PD (Power Delivery) message parsing using offline dataset.

Uses the parquet dataset to validate PD parsing with usbpdpy library.
No hardware required - runs in CI.
"""

import pytest
import polars as pl
from pathlib import Path

# Try to import usbpdpy - skip tests if not available
try:
    import usbpdpy
    USBPDPY_AVAILABLE = True
except ImportError:
    USBPDPY_AVAILABLE = False

from km003c import parse_packet, PdEventStream

# Mark all tests in this module as unit tests
pytestmark = pytest.mark.unit

DATASET = Path(__file__).parent.parent.parent / "data/processed/usb_master_dataset.parquet"


def get_pd_events(packet):
    """Extract PD events from DataResponse packet."""
    if "DataResponse" not in packet:
        return None
    for payload in packet["DataResponse"]["payloads"]:
        if isinstance(payload, PdEventStream):
            return payload
    return None


@pytest.fixture(scope="module")
def pd_capture_data():
    """Load PD capture data from parquet dataset."""
    if not DATASET.exists():
        pytest.skip("Dataset not available")

    df = pl.read_parquet(DATASET)

    # Filter for PD capture file with larger payloads (actual events)
    pd_capture = df.filter(
        (pl.col("source_file").str.contains("pd_capture_new.9"))
        & (pl.col("endpoint_address") == "0x81")
        & (pl.col("urb_type") == "C")
        & (pl.col("data_length") > 12)  # Larger than just PdStatus
    )

    return pd_capture


@pytest.mark.skipif(not USBPDPY_AVAILABLE, reason="usbpdpy not installed")
class TestPdMessageParsing:
    """Test USB PD message parsing with usbpdpy."""

    def test_can_parse_pd_events(self, pd_capture_data):
        """Test that we can parse PD events from the dataset."""
        events_found = 0

        for row in pd_capture_data.iter_rows(named=True):
            payload_hex = row.get("payload_hex")
            if not payload_hex:
                continue

            try:
                raw_bytes = bytes.fromhex(payload_hex)
                packet = parse_packet(raw_bytes)
            except Exception:
                continue

            pd_events = get_pd_events(packet)
            if pd_events:
                events_found += len(pd_events.events)

        assert events_found > 0, "Should find PD events in dataset"

    def test_source_capabilities_parsing(self, pd_capture_data):
        """Test parsing Source_Capabilities messages."""
        source_caps_found = 0
        pdos_found = 0

        for row in pd_capture_data.iter_rows(named=True):
            payload_hex = row.get("payload_hex")
            if not payload_hex:
                continue

            try:
                raw_bytes = bytes.fromhex(payload_hex)
                packet = parse_packet(raw_bytes)
            except Exception:
                continue

            pd_events = get_pd_events(packet)
            if not pd_events:
                continue

            for event in pd_events.events:
                data = event.data

                if not isinstance(data, dict) or "wire_data" not in data:
                    continue

                wire = bytes(data["wire_data"])
                if len(wire) < 2:
                    continue

                try:
                    msg = usbpdpy.parse_pd_message(wire)
                    if msg.is_source_capabilities():
                        source_caps_found += 1
                        pdos_found += len(list(msg.data_objects))
                except Exception:
                    continue

        assert source_caps_found > 0, "Should find Source_Capabilities messages"
        assert pdos_found > 0, "Should find PDOs in Source_Capabilities"

    def test_request_parsing_with_state(self, pd_capture_data):
        """Test parsing Request messages with PDO state for proper RDO decoding."""
        source_caps = None
        request_found = False
        rdo_current_decoded = False

        for row in pd_capture_data.iter_rows(named=True):
            payload_hex = row.get("payload_hex")
            if not payload_hex:
                continue

            try:
                raw_bytes = bytes.fromhex(payload_hex)
                packet = parse_packet(raw_bytes)
            except Exception:
                continue

            pd_events = get_pd_events(packet)
            if not pd_events:
                continue

            for event in pd_events.events:
                data = event.data

                if not isinstance(data, dict) or "wire_data" not in data:
                    continue

                wire = bytes(data["wire_data"])
                if len(wire) < 2:
                    continue

                try:
                    # Parse with or without state
                    if source_caps:
                        msg = usbpdpy.parse_pd_message_with_state(wire, source_caps)
                    else:
                        msg = usbpdpy.parse_pd_message(wire)

                    msg_type = msg.header.message_type

                    # Track Source_Capabilities
                    if msg.is_source_capabilities():
                        source_caps = list(msg.data_objects)

                    # Check Request messages
                    if msg_type == "Request" and msg.request_objects:
                        request_found = True
                        for rdo in msg.request_objects:
                            if rdo.operating_current_a is not None:
                                rdo_current_decoded = True
                                # Verify current is reasonable (0-10A for USB PD)
                                assert 0.0 <= rdo.operating_current_a <= 10.0, (
                                    f"RDO current out of range: {rdo.operating_current_a}A"
                                )

                except Exception:
                    continue

        assert request_found, "Should find Request messages in dataset"
        assert rdo_current_decoded, (
            "Should decode operating_current_a in Request messages "
            "(requires usbpdpy >= 0.2.1 with header fix)"
        )

    def test_connection_events(self, pd_capture_data):
        """Test detecting connect/disconnect events."""
        connect_found = False
        disconnect_found = False

        for row in pd_capture_data.iter_rows(named=True):
            payload_hex = row.get("payload_hex")
            if not payload_hex:
                continue

            try:
                raw_bytes = bytes.fromhex(payload_hex)
                packet = parse_packet(raw_bytes)
            except Exception:
                continue

            pd_events = get_pd_events(packet)
            if not pd_events:
                continue

            for event in pd_events.events:
                data = event.data

                if not isinstance(data, dict) or "wire_data" not in data:
                    continue

                sop = data.get("sop")
                wire = bytes(data["wire_data"])

                # Empty wire with special SOP = connection event
                if len(wire) == 0:
                    if sop == 0x11:
                        connect_found = True
                    elif sop == 0x12:
                        disconnect_found = True

        assert connect_found, "Should find CONNECT events"
        assert disconnect_found, "Should find DISCONNECT events"

    def test_pd_negotiation_sequence(self, pd_capture_data):
        """Test that we can follow a complete PD negotiation sequence."""
        source_caps = None
        seen_types = set()
        seen_events = set()

        for row in pd_capture_data.iter_rows(named=True):
            payload_hex = row.get("payload_hex")
            if not payload_hex:
                continue

            try:
                raw_bytes = bytes.fromhex(payload_hex)
                packet = parse_packet(raw_bytes)
            except Exception:
                continue

            pd_events = get_pd_events(packet)
            if not pd_events:
                continue

            for event in pd_events.events:
                ts = event.timestamp
                data = event.data

                if not isinstance(data, dict) or "wire_data" not in data:
                    continue

                wire = bytes(data["wire_data"])

                # Skip connection events
                if len(wire) == 0:
                    continue

                if len(wire) < 2:
                    continue

                # Deduplicate
                event_key = (ts, wire.hex())
                if event_key in seen_events:
                    continue
                seen_events.add(event_key)

                try:
                    if source_caps:
                        msg = usbpdpy.parse_pd_message_with_state(wire, source_caps)
                    else:
                        msg = usbpdpy.parse_pd_message(wire)

                    msg_type = msg.header.message_type
                    seen_types.add(msg_type)

                    if msg.is_source_capabilities():
                        source_caps = list(msg.data_objects)

                except Exception:
                    continue

        # A complete negotiation should have these message types
        assert "Source_Capabilities" in seen_types, "Missing Source_Capabilities"
        assert "Request" in seen_types, "Missing Request"
        assert "Accept" in seen_types, "Missing Accept"
        assert "PS_RDY" in seen_types, "Missing PS_RDY"
        assert "GoodCRC" in seen_types, "Missing GoodCRC"


@pytest.mark.skipif(not USBPDPY_AVAILABLE, reason="usbpdpy not installed")
class TestPdoDecoding:
    """Test PDO (Power Data Object) decoding."""

    def test_fixed_supply_pdo(self, pd_capture_data):
        """Test parsing Fixed Supply PDOs."""
        fixed_pdos = []

        for row in pd_capture_data.iter_rows(named=True):
            payload_hex = row.get("payload_hex")
            if not payload_hex:
                continue

            try:
                raw_bytes = bytes.fromhex(payload_hex)
                packet = parse_packet(raw_bytes)
            except Exception:
                continue

            pd_events = get_pd_events(packet)
            if not pd_events:
                continue

            for event in pd_events.events:
                data = event.data
                if not isinstance(data, dict) or "wire_data" not in data:
                    continue

                wire = bytes(data["wire_data"])
                if len(wire) < 2:
                    continue

                try:
                    msg = usbpdpy.parse_pd_message(wire)
                    if msg.is_source_capabilities():
                        for pdo in msg.data_objects:
                            pdo_str = str(pdo)
                            if "FixedSupply" in pdo_str:
                                fixed_pdos.append(pdo_str)
                except Exception:
                    continue

        assert len(fixed_pdos) > 0, "Should find Fixed Supply PDOs"

        # Check that common voltages are present
        all_pdos = " ".join(fixed_pdos)
        assert "5V" in all_pdos or "5.0V" in all_pdos, "Should have 5V PDO"

    def test_pps_pdo(self, pd_capture_data):
        """Test parsing PPS (Programmable Power Supply) PDOs if present."""
        pps_pdos = []

        for row in pd_capture_data.iter_rows(named=True):
            payload_hex = row.get("payload_hex")
            if not payload_hex:
                continue

            try:
                raw_bytes = bytes.fromhex(payload_hex)
                packet = parse_packet(raw_bytes)
            except Exception:
                continue

            pd_events = get_pd_events(packet)
            if not pd_events:
                continue

            for event in pd_events.events:
                data = event.data
                if not isinstance(data, dict) or "wire_data" not in data:
                    continue

                wire = bytes(data["wire_data"])
                if len(wire) < 2:
                    continue

                try:
                    msg = usbpdpy.parse_pd_message(wire)
                    if msg.is_source_capabilities():
                        for pdo in msg.data_objects:
                            pdo_str = str(pdo)
                            if "PPS" in pdo_str:
                                pps_pdos.append(pdo_str)
                except Exception:
                    continue

        # PPS may or may not be present depending on the charger
        # Just verify we can parse them if they exist
        if pps_pdos:
            for pps in pps_pdos:
                assert "PPS" in pps
                # PPS should have voltage range
                assert "V" in pps


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
