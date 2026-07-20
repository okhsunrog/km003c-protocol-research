"""Tests for the standalone device-information MemoryRead tool."""

import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.dump_device_info import KM003C, encrypt_ecb

pytestmark = pytest.mark.unit


def test_memory_read_request_matches_recorded_packet() -> None:
    device = object.__new__(KM003C)
    device.tid = 1

    request = device._build_memory_read_request(0x420, 64)

    assert request.hex() == (
        "4402010133f8860c0054288cdc7e52729826872dd18b539a39c407d5c063d91102e36a9e"
    )


def test_download_memory_collects_all_raw_transfers() -> None:
    plaintext = bytes(range(256)) * 32 + bytes(range(144))
    encrypted = encrypt_ecb(plaintext)
    confirmation = bytes.fromhex("c40201010000109890200000ffffffff2f0ab013")
    responses: Iterator[bytes] = iter(
        [
            confirmation,
            encrypted[:2544],
            encrypted[2544:5088],
            encrypted[5088:7632],
            encrypted[7632:],
        ]
    )
    device = object.__new__(KM003C)
    device.tid = 1
    device._send = lambda _request: None
    device._recv = lambda timeout=2000: next(responses)

    assert device.download_memory(0x98100000, len(plaintext)) == plaintext


def test_download_memory_reports_rejected_response() -> None:
    device = object.__new__(KM003C)
    device.tid = 1
    device._send = lambda _request: None
    device._recv = lambda timeout=2000: bytes.fromhex("06020000")

    with pytest.raises(ValueError, match="rejected"):
        device.download_memory(0x420, 64)
