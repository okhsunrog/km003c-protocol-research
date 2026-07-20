"""Capture-backed tests for the offline log download protocol."""

import struct
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.download_offline_log import (
    KM003C,
    STREAMING_AUTH_KEY,
    LogMetadata,
    decrypt_ecb,
    encrypt_ecb,
    memory_response_size,
    validate_memory_read_confirmation,
)

pytestmark = pytest.mark.unit


def test_memory_read_request_matches_recorded_packet() -> None:
    device = object.__new__(KM003C)
    device.tid = 1

    request = device._build_memory_read_request(0x420, 64)

    assert request.hex() == (
        "4402010133f8860c0054288cdc7e52729826872dd18b539a39c407d5c063d91102e36a9e"
    )


def test_recorded_memory_read_confirmation_is_valid() -> None:
    confirmation = bytes.fromhex("c40201012004000040000000ffffffff1b8c1b24")

    validate_memory_read_confirmation(confirmation, 2, 0x420, 64)


def test_memory_read_confirmation_rejects_bad_crc() -> None:
    confirmation = bytearray.fromhex("c40201012004000040000000ffffffff1b8c1b24")
    confirmation[-1] ^= 1

    with pytest.raises(ValueError, match="CRC mismatch"):
        validate_memory_read_confirmation(bytes(confirmation), 2, 0x420, 64)


def test_raw_memory_chunks_are_concatenated_without_header_stripping() -> None:
    plaintext = bytes(range(256)) * 32 + bytes(range(144))
    assert len(plaintext) == 8336

    encrypted = encrypt_ecb(plaintext)
    chunks: Iterator[bytes] = iter(
        [encrypted[:2544], encrypted[2544:5088], encrypted[5088:7632], encrypted[7632:]]
    )
    device = object.__new__(KM003C)
    device._recv = lambda timeout=2000: next(chunks)

    received = device._recv_memory_data(len(plaintext))

    assert received == encrypted
    assert decrypt_ecb(received) == plaintext


def test_streaming_auth_uses_connected_device_hardware_id() -> None:
    device = object.__new__(KM003C)
    device.tid = 5
    hardware_id = bytes.fromhex("00112233445566778899aabb")

    request = device._build_streaming_auth_request(hardware_id)
    plaintext = decrypt_ecb(request[4:], STREAMING_AUTH_KEY)

    assert request[:4] == bytes.fromhex("4c060002")
    assert plaintext[8:20] == hardware_id
    assert len(plaintext) == 32


def test_memory_response_size_uses_complete_aes_blocks() -> None:
    assert memory_response_size(12) == 16
    assert memory_response_size(16) == 16
    assert memory_response_size(17) == 32


def test_log_duration_counts_intervals_between_samples() -> None:
    metadata = LogMetadata(
        name="A01.d",
        sample_count=521,
        interval_ms=10_000,
        flags=0,
        recorded_duration_seconds=5200,
        unknown_0x10=0x0A45,
        final_charge_uah=-810_335,
        final_energy_uwh=-5_747_232,
        data_offset=0,
        reserved_tail=b"\x00" * 8,
    )

    assert metadata.duration_seconds == 5200
    assert metadata.recorded_duration_seconds == metadata.duration_seconds
    assert metadata.data_size == 8336
    assert metadata.data_address == 0x98100000


def test_log_catalog_offsets_select_distinct_memory_regions() -> None:
    metadata = LogMetadata(
        name="A03.d",
        sample_count=2036,
        interval_ms=10_000,
        flags=0,
        recorded_duration_seconds=20_350,
        unknown_0x10=0x0A45,
        final_charge_uah=-2_171_866,
        final_energy_uwh=-11_092_025,
        data_offset=0x2400,
        reserved_tail=b"\x00" * 8,
    )

    assert metadata.data_address == 0x98102400
    assert metadata.data_size == 32_576


def test_log_metadata_parses_multiple_catalog_entries() -> None:
    def entry(name: bytes, count: int, duration: int, offset: int) -> bytes:
        return struct.pack(
            "<16sHHHHIiiI8s",
            name,
            0x0A45,
            count,
            10_000,
            0,
            duration,
            0,
            0,
            offset,
            b"\x00" * 8,
        )

    payload = b"".join(
        [
            entry(b"A01.d", 521, 5_200, 0),
            entry(b"A02.d", 2, 10, 0x2200),
            entry(b"A03.d", 2_036, 20_350, 0x2400),
        ]
    )
    device = object.__new__(KM003C)
    device._send_cmd = lambda _command, _attribute: b"\x41" + b"\x00" * 7 + payload

    catalog = device.get_log_metadata()

    assert [metadata.name for metadata in catalog] == ["A01.d", "A02.d", "A03.d"]
    assert [metadata.data_offset for metadata in catalog] == [0, 0x2200, 0x2400]


def test_log_metadata_empty_payload_means_no_logs() -> None:
    device = object.__new__(KM003C)
    device._send_cmd = lambda _command, _attribute: bytes.fromhex("4108c2ff00020000")

    assert device.get_log_metadata() == []
