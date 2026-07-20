import struct
import zlib

import pytest

# GetData(Settings) payload from orig_adc_1000hz.6, frame 392. The outer and
# extended packet headers are intentionally omitted.
SETTINGS_PAYLOAD = bytes.fromhex(
    "610150f800000000102741ff00000000"
    "fffffffffffffffffffffffffaffffff"
    "fafffffffafffffffafffffffaffffff"
    "ed4a0f00ed4a0f00ed4a0f00ed4a0f00"
    "ed4a0f00ed4a0f00ed4a0f00ed4a0f00"
    "ed4a0f00ed4a0f005e000000268bb83a"
    "43000000000000000000000000000000"
    "504f5745522d5a000000000000000000"
    "00000000000000000000000000000000"
    "00000000000000000000000000000000"
    "00000000000000000000000000000000"
    "207d05d2"
)


@pytest.mark.unit
def test_settings_payload_is_two_independently_checksummed_blocks() -> None:
    assert len(SETTINGS_PAYLOAD) == 180

    settings_a = SETTINGS_PAYLOAD[:0x60]
    settings_b = SETTINGS_PAYLOAD[0x60:]
    assert len(settings_a) == 96
    assert len(settings_b) == 84

    (settings_a_checksum,) = struct.unpack_from("<I", settings_a, 0x5C)
    (settings_b_checksum,) = struct.unpack_from("<I", settings_b, 0x50)
    assert zlib.crc32(settings_a[:0x5C]) == settings_a_checksum
    assert zlib.crc32(settings_b[:0x50]) == settings_b_checksum


@pytest.mark.unit
def test_settings_capture_matches_documented_offsets() -> None:
    assert struct.unpack_from("<H", SETTINGS_PAYLOAD, 0x08) == (10_000,)
    assert struct.unpack_from("<3i", SETTINGS_PAYLOAD, 0x10) == (-1, -1, -1)
    assert struct.unpack_from("<5i", SETTINGS_PAYLOAD, 0x1C) == (-6,) * 5
    assert struct.unpack_from("<10I", SETTINGS_PAYLOAD, 0x30) == (1_002_221,) * 10
    assert struct.unpack_from("<i", SETTINGS_PAYLOAD, 0x58) == (94,)
    assert SETTINGS_PAYLOAD[0x70:0xB0].split(b"\0", 1)[0] == b"POWER-Z"
