import pytest
from km003c_lib import RawPacket, parse_raw_packet

# Mark all tests in this module as unit tests
pytestmark = pytest.mark.unit


def test_parse_raw_packet_basic():
    """Test that parse_raw_packet works with basic packet data."""
    # Simple packet data
    data = bytes([0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08])

    result = parse_raw_packet(data)

    assert isinstance(result, RawPacket)
    assert result.packet_type == "Sync"
    assert result.id == 2
    # New API: has_extended_header replaces old is_extended
    assert result.has_extended_header is False
    assert len(result.raw_bytes) == 8
    assert len(result.payload) == 4


def test_parse_raw_packet_extended():
    """Test that parse_raw_packet correctly parses extended header fields."""
    # Real ADC response packet (PutData with extended header)
    # From orig_open_close.16 dataset
    adc_response_hex = "410a82020100000b5c0f0000faffffffa00f0000f2ffffff04100000500000007e0d7b7ed40471014201837e0080780025002100"
    data = bytes.fromhex(adc_response_hex)

    result = parse_raw_packet(data)

    assert isinstance(result, RawPacket)
    assert result.packet_type == "PutData"
    assert result.packet_type_id == 0x41
    assert result.id == 0x0A
    assert result.has_extended_header is True
    
    # Check extended header fields are correctly parsed
    assert result.ext_attribute_id == 1  # ATT_ADC
    assert result.ext_next == False  # Last logical packet
    assert result.ext_chunk == 0
    assert result.ext_size == 44  # ADC payload size


def test_raw_packet_attributes():
    """Test that RawPacket has all expected attributes."""
    data = bytes([0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08])
    result = parse_raw_packet(data)

    # Check that all expected attributes exist
    assert hasattr(result, "packet_type")
    assert hasattr(result, "packet_type_id")
    assert hasattr(result, "id")
    assert hasattr(result, "has_extended_header")
    assert hasattr(result, "attribute")
    assert hasattr(result, "attribute_id")
    assert hasattr(result, "payload")
    assert hasattr(result, "raw_bytes")


def test_raw_packet_repr():
    """Test that RawPacket has a proper string representation."""
    data = bytes([0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08])
    result = parse_raw_packet(data)

    repr_str = repr(result)
    assert "RawPacket" in repr_str
    assert "Sync" in repr_str
    assert "2" in repr_str  # ID
    assert "8 bytes" in repr_str
