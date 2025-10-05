import pytest
from km003c_lib import parse_raw_packet

# Mark all tests in this module as unit tests
pytestmark = pytest.mark.unit


def test_parse_raw_packet_basic():
    """Test that parse_raw_packet works with basic packet data."""
    # Simple packet data (Sync command)
    data = bytes([0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08])

    result = parse_raw_packet(data)

    # RawPacket is now a dict-like enum with "Ctrl", "SimpleData", or "Data" keys
    assert isinstance(result, dict)
    assert "Ctrl" in result  # Sync is a control packet

    ctrl = result["Ctrl"]
    assert ctrl["header"]["packet_type"] == 1  # Sync = 0x01
    assert ctrl["header"]["id"] == 2
    assert ctrl["header"]["reserved_flag"] is False
    assert len(ctrl["payload"]) == 4


def test_parse_raw_packet_extended():
    """Test that parse_raw_packet correctly parses extended header fields."""
    # Real ADC response packet (PutData with extended header)
    # From orig_open_close.16 dataset
    adc_response_hex = "410a82020100000b5c0f0000faffffffa00f0000f2ffffff04100000500000007e0d7b7ed40471014201837e0080780025002100"
    data = bytes.fromhex(adc_response_hex)

    result = parse_raw_packet(data)

    assert isinstance(result, dict)
    assert "Data" in result  # PutData with logical packets

    data_pkt = result["Data"]
    assert data_pkt["header"]["packet_type"] == 0x41  # PutData
    assert data_pkt["header"]["id"] == 0x0A
    # Per wire format, extend/reserved bit here is 0 in this sample
    assert data_pkt["header"]["reserved_flag"] is False

    # Check logical packets (extended headers)
    logical_packets = data_pkt["logical_packets"]
    assert len(logical_packets) >= 1

    first_lp = logical_packets[0]
    # logical_packets may contain dicts or PyO3 LogicalPacket objects
    def lp_get(obj, key, default=None):
        if isinstance(obj, dict):
            return obj.get(key, default)
        return getattr(obj, key, default)

    assert lp_get(first_lp, "attribute") == 1  # ATT_ADC
    assert lp_get(first_lp, "next") is False  # Last logical packet
    assert lp_get(first_lp, "chunk") == 0
    assert lp_get(first_lp, "size") == 44  # ADC payload size
    payload = lp_get(first_lp, "payload") or b""
    assert isinstance(payload, (bytes, bytearray))
    assert len(payload) == 44


def test_raw_packet_attributes():
    """Test that RawPacket has all expected structure."""
    data = bytes([0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08])
    result = parse_raw_packet(data)

    # RawPacket is a dict with variant keys
    assert isinstance(result, dict)
    assert "Ctrl" in result

    ctrl = result["Ctrl"]
    # Check that header and payload exist
    assert "header" in ctrl
    assert "payload" in ctrl

    header = ctrl["header"]
    assert "packet_type" in header
    assert "id" in header
    assert "reserved_flag" in header
    assert "attribute" in header


def test_raw_packet_repr():
    """Test that RawPacket has a proper string representation."""
    data = bytes([0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08])
    result = parse_raw_packet(data)

    # RawPacket dict should have string representation
    repr_str = repr(result)
    assert "Ctrl" in repr_str
    assert "header" in repr_str
