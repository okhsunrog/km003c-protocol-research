"""Capture-backed tests for the shared MemoryRead transport.

These used to be duplicated across the tests for `dump_device_info.py`,
`memory_scan.py` and `download_offline_log.py`, because each script carried its
own copy of the request framing.
"""

from collections.abc import Iterator

import pytest

from km003c_analysis.device import protocol
from km003c_analysis.device.transport import Km003cUsb, MemoryReadError

pytestmark = pytest.mark.unit

# Source: usb_master_dataset.parquet, orig_adc_1000hz.6 - a MemoryRead of the
# HardwareID block, and the confirmation for an 8336-byte offline log read.
RECORDED_HARDWARE_ID_REQUEST = (
    "4402010133f8860c0054288cdc7e52729826872dd18b539a39c407d5c063d91102e36a9e"
)
RECORDED_LOG_CONFIRMATION = bytes.fromhex("c40201010000109890200000ffffffff2f0ab013")


def fake_device(responses: Iterator[bytes]) -> Km003cUsb:
    """A Km003cUsb whose USB endpoints are replaced by a canned script."""
    device = object.__new__(Km003cUsb)
    device.tid = 1
    device.send = lambda _request: None  # type: ignore[method-assign]
    device.receive = lambda timeout_ms=1000: next(responses)  # type: ignore[method-assign]
    return device


def test_memory_read_request_matches_recorded_packet() -> None:
    request = protocol.build_memory_read_packet(0x420, 64, 2)

    assert request.hex() == RECORDED_HARDWARE_ID_REQUEST


def test_confirmation_round_trips_its_echoed_fields() -> None:
    assert protocol.parse_memory_read_confirmation(RECORDED_LOG_CONFIRMATION) == (
        0x98100000,
        8336,
    )


def test_corrupted_confirmation_is_rejected() -> None:
    corrupted = bytearray(RECORDED_LOG_CONFIRMATION)
    corrupted[8] ^= 1

    assert protocol.parse_memory_read_confirmation(bytes(corrupted)) is None


def test_read_memory_collects_all_raw_transfers() -> None:
    # Source: reading_logs0.11 - an 8336-byte read arrived as three 2544-byte
    # transfers followed by one 704-byte transfer.
    plaintext = bytes(range(256)) * 32 + bytes(range(144))
    ciphertext = _encrypt(plaintext)
    device = fake_device(
        iter(
            [
                RECORDED_LOG_CONFIRMATION,
                ciphertext[:2544],
                ciphertext[2544:5088],
                ciphertext[5088:7632],
                ciphertext[7632:],
            ]
        )
    )

    assert device.read_memory(0x98100000, len(plaintext)) == plaintext


def test_read_memory_reports_a_rejected_request() -> None:
    device = fake_device(iter([bytes.fromhex("06020000")]))

    with pytest.raises(MemoryReadError, match="rejected"):
        device.read_memory(0x420, 64)


def test_read_memory_reports_an_unreadable_address() -> None:
    device = fake_device(iter([bytes.fromhex("27020000")]))

    with pytest.raises(MemoryReadError, match="not readable"):
        device.read_memory(0x420, 64)


def test_read_memory_rejects_a_confirmation_for_another_request() -> None:
    device = fake_device(iter([RECORDED_LOG_CONFIRMATION]))

    with pytest.raises(MemoryReadError, match="echoed"):
        device.read_memory(0x420, 64)


def _encrypt(plaintext: bytes) -> bytes:
    """Encrypt with the MemoryRead key, as the device would."""
    from Crypto.Cipher import AES

    return AES.new(protocol.MEMORY_READ_KEY, AES.MODE_ECB).encrypt(plaintext)
