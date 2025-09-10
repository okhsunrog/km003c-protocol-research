import pytest
from km003c_lib import parse_raw_packet, RawPacket

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
    """Test that parse_raw_packet correctly identifies extended packets."""
    # Extended packet data (PutData 0x41 always carries an extended header)
    data = bytes([
        0x41, 0x00, 0x00, 0x00,  # DataHeader (0x41 = PutData)
        0x01, 0x00, 0x08, 0x00,  # Extended header (attribute=1/ADC, size=8)
        0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07,  # Payload data (16 bytes total)
        0x08, 0x09, 0x0A, 0x0B, 0x0C, 0x0D, 0x0E, 0x0F
    ])
    
    result = parse_raw_packet(data)
    
    assert isinstance(result, RawPacket)
    assert result.has_extended_header is True
    assert len(result.raw_bytes) == 24
    # Payload excludes the 4-byte extended header; 24 total - 8 header = 16
    assert len(result.payload) == 16

def test_raw_packet_attributes():
    """Test that RawPacket has all expected attributes."""
    data = bytes([0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08])
    result = parse_raw_packet(data)
    
    # Check that all expected attributes exist
    assert hasattr(result, 'packet_type')
    assert hasattr(result, 'packet_type_id')
    assert hasattr(result, 'id')
    assert hasattr(result, 'has_extended_header')
    assert hasattr(result, 'attribute')
    assert hasattr(result, 'attribute_id')
    assert hasattr(result, 'payload')
    assert hasattr(result, 'raw_bytes')

def test_raw_packet_repr():
    """Test that RawPacket has a proper string representation."""
    data = bytes([0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08])
    result = parse_raw_packet(data)
    
    repr_str = repr(result)
    assert "RawPacket" in repr_str
    assert "Sync" in repr_str
    assert "2" in repr_str  # ID
    assert "8 bytes" in repr_str
