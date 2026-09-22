"""Capture-backed tests for the offline log catalog and sample layouts.

The MemoryRead and StreamingAuth framing these used to exercise now lives in
`km003c_analysis.device` and is covered by `test_device_transport.py`.
"""

import struct

import pytest

from km003c_analysis.device import protocol
from scripts.download_offline_log import (
    AdcSample,
    LogMetadata,
    parse_catalog,
    parse_samples,
)

pytestmark = pytest.mark.unit


def catalog_entry(name: bytes, count: int, duration: int, offset: int) -> bytes:
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


def test_streaming_auth_uses_the_connected_device_hardware_id() -> None:
    hardware_id = bytes.fromhex("00112233445566778899aabb")

    request = protocol.build_streaming_auth_packet(hardware_id, 6)

    assert request[:4] == bytes.fromhex("4c060002")
    assert len(request) == 36


def test_memory_response_size_uses_complete_aes_blocks() -> None:
    assert protocol.aligned_response_size(12) == 16
    assert protocol.aligned_response_size(16) == 16
    assert protocol.aligned_response_size(17) == 32


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
    payload = b"".join(
        [
            catalog_entry(b"A01.d", 521, 5_200, 0),
            catalog_entry(b"A02.d", 2, 10, 0x2200),
            catalog_entry(b"A03.d", 2_036, 20_350, 0x2400),
        ]
    )

    catalog = parse_catalog(b"\x41" + b"\x00" * 7 + payload)

    assert [metadata.name for metadata in catalog] == ["A01.d", "A02.d", "A03.d"]
    assert [metadata.data_offset for metadata in catalog] == [0, 0x2200, 0x2400]


def test_log_metadata_empty_payload_means_no_logs() -> None:
    assert parse_catalog(bytes.fromhex("4108c2ff00020000")) == []


def test_catalog_rejects_a_truncated_payload() -> None:
    with pytest.raises(ValueError, match="48-byte entries"):
        parse_catalog(b"\x41" + b"\x00" * 7 + b"\x00" * 47)


def test_samples_are_parsed_at_their_documented_offsets() -> None:
    # Source: reading_logs0.11, first sample of A01.d.
    samples = parse_samples(bytes.fromhex("81494c0021f0e2ff56ebffffb998ffff"))

    assert samples == [
        AdcSample(
            voltage_uv=4_999_553,
            current_ua=-1_904_607,
            charge_acc_uah=-5_290,
            energy_acc_uwh=-26_439,
        )
    ]
    assert samples[0].voltage_v == pytest.approx(4.999553)
    assert samples[0].charge_mah == pytest.approx(-5.29)


def test_samples_reject_a_truncated_log() -> None:
    with pytest.raises(ValueError, match="multiple of 16"):
        parse_samples(bytes(15))
