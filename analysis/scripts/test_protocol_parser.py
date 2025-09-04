import pytest
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# The native Rust extension is now the source of truth
from km003c_lib import parse_packet, AdcData

def hex_to_bytes(hex_str: str) -> bytes:
    """Helper to convert a hex string to bytes."""
    return bytes.fromhex(hex_str)

# From common/mod.rs in the Rust tests
REAL_ADC_RESPONSE = bytes([
    0x41, 0x00, 0x80, 0x02, 0x01, 0x00, 0x00, 0x0b, 0x45, 0x1c, 0x4d, 0x00, 0xae, 0x9e, 0xfe, 0xff, 0xdb, 0x1c, 0x4d,
    0x00, 0x23, 0x9f, 0xfe, 0xff, 0xe1, 0x1c, 0x4d, 0x00, 0x81, 0x9f, 0xfe, 0xff, 0xc9, 0x0c, 0x8a, 0x10, 0x0e, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x78, 0x7e, 0x00, 0x80, 0x02, 0x00, 0x00, 0x00, 0x00, 0x00,
])

def test_adc_response_parsing_with_rust():
    """
    Tests the Rust-backed parser with the real ADC response.
    This test should now pass perfectly, including the temperature.
    """
    adc_data = parse_packet(REAL_ADC_RESPONSE)

    assert adc_data is not None
    assert isinstance(adc_data, AdcData)

    # Assertions with tolerance, matching the Rust test
    assert abs(adc_data.vbus_v - 5.054) < 0.001
    assert abs(adc_data.ibus_a - (-0.090)) < 0.001
    assert abs(adc_data.power_w - (-0.457)) < 0.001
    assert abs(adc_data.temp_c - 25.0) < 0.1
    assert abs(adc_data.cc1_v - 0.423) < 0.001
    assert abs(adc_data.cc2_v - 0.001) < 0.001

def test_non_adc_packet_with_rust():
    """
    Tests that a non-ADC packet returns None, as expected.
    """
    hex_data = "02010000" # A CONNECT packet
    payload_bytes = hex_to_bytes(hex_data)
    
    result = parse_packet(payload_bytes)
    assert result is None
