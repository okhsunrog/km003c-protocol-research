"""Tests for the block decoding in the device-information tool.

The MemoryRead transport it used to own is covered by
`tests/unit/test_device_transport.py`.
"""

import pytest

from scripts.dump_device_info import (
    ADDR_CALIBRATION,
    ADDR_DEVICE_INFO,
    ADDR_HARDWARE_ID,
    extract_string,
    parse_device_info,
)

pytestmark = pytest.mark.unit


def _padded(text: bytes, length: int) -> bytes:
    return text + b"\x00" * (length - len(text))


def test_extract_string_stops_at_the_nul_terminator() -> None:
    block = b"\x00" * 16 + _padded(b"KM003C", 12)

    assert extract_string(block, 0x10, 0x1C) == "KM003C"


def test_device_info_block_fields_are_decoded_at_their_documented_offsets() -> None:
    block = bytearray(64)
    block[0x10:0x1C] = _padded(b"KM003C", 12)
    block[0x1C:0x28] = _padded(b"2.1", 12)
    block[0x28:0x40] = _padded(b"2022.11.7", 24)

    info = parse_device_info({ADDR_DEVICE_INFO: bytes(block)})

    assert (info.model, info.hw_version, info.mfg_date) == (
        "KM003C",
        "2.1",
        "2022.11.7",
    )
    # Blocks that were not read stay explicitly unavailable.
    assert info.fw_version == "N/A"
    assert info.serial_id == "N/A"


def test_calibration_block_yields_serial_uuid_and_timestamp() -> None:
    block = bytearray(64)
    block[0:7] = b"007965 "
    block[7:39] = b"a" * 32
    block[39:51] = _padded(b"1667779200", 12)

    info = parse_device_info({ADDR_CALIBRATION: bytes(block)})

    assert info.serial_id == "007965"
    assert info.uuid == "a" * 32
    assert info.calibration_timestamp == 1667779200


def test_hardware_id_is_reported_as_an_opaque_blob_not_a_serial() -> None:
    info = parse_device_info({ADDR_HARDWARE_ID: b"071KBP\x0d\xff\x11\x0a\xff\xff"})

    assert info.hardware_id_prefix == "071KBP"
    assert info.hardware_id_suffix.hex() == "0dff110affff"
