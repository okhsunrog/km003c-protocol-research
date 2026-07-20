"""Regression tests for separating framed packets from MemoryRead ciphertext."""

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from parquet.analyze_with_km003c_lib import is_framed_protocol_packet  # noqa: E402

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    ("payload", "endpoint"),
    [
        (bytes.fromhex("02010000"), "0x01"),
        (bytes.fromhex("05010000"), "0x81"),
        (bytes.fromhex("44020101") + bytes(32), "0x01"),
        (bytes.fromhex("c4020101") + bytes(16), "0x81"),
        (bytes.fromhex("4c020002") + bytes(32), "0x01"),
        (bytes.fromhex("4c000302") + bytes(32), "0x81"),
        (bytes.fromhex("41000000"), "0x81"),
    ],
)
def test_accepts_known_framed_packets(payload: bytes, endpoint: str) -> None:
    assert is_framed_protocol_packet(payload, endpoint)


@pytest.mark.parametrize(
    "payload",
    [
        bytes.fromhex("1a") + bytes(63),
        bytes.fromhex("3a") + bytes(63),
        bytes.fromhex("40") + bytes(63),
        bytes.fromhex("75") + bytes(15),
    ],
)
def test_rejects_recorded_memory_ciphertext(payload: bytes) -> None:
    assert not is_framed_protocol_packet(payload, "0x81")
