"""Authenticated KM003C commands and the device memory map.

`memory_scan.py`, `dump_device_info.py`, `download_offline_log.py`,
`run_adcqueue_single.py` and `decrypt_offline_adc.py` each used to carry their
own copy of the AES key, the CRC layout and the request framing. Since km003c
0.4.0 the Rust bindings expose all of it, so this module is a thin re-export
that gives scripts one import location and adds the few pieces the bindings do
not cover.
"""

from __future__ import annotations

import binascii

import km003c
from km003c import (
    ADDR_CALIBRATION,
    ADDR_DEVICE_INFO,
    ADDR_FIRMWARE_INFO,
    ADDR_HARDWARE_ID,
    ADDR_OFFLINE_LOG,
    ADDR_PREFERRED_CALIBRATION,
    CMD_MEMORY_READ,
    CMD_STREAMING_AUTH,
    ENDPOINT_IN_HID,
    ENDPOINT_IN_VENDOR,
    ENDPOINT_OUT_HID,
    ENDPOINT_OUT_VENDOR,
    HARDWARE_ID_SIZE,
    INFO_BLOCK_SIZE,
    INTERFACE_HID,
    INTERFACE_VENDOR,
    LOG_METADATA_SIZE,
    OFFLINE_LOG_SAMPLE_SIZE,
)

__all__ = [
    "AES_BLOCK_SIZE",
    "ADDR_CALIBRATION",
    "ADDR_DEVICE_INFO",
    "ADDR_FIRMWARE_INFO",
    "ADDR_HARDWARE_ID",
    "ADDR_OFFLINE_LOG",
    "ADDR_PREFERRED_CALIBRATION",
    "CMD_MEMORY_READ",
    "CMD_NOT_READABLE",
    "CMD_STREAMING_AUTH",
    "ENDPOINT_IN_HID",
    "ENDPOINT_IN_VENDOR",
    "ENDPOINT_OUT_HID",
    "ENDPOINT_OUT_VENDOR",
    "HARDWARE_ID_SIZE",
    "INFO_BLOCK_SIZE",
    "INTERFACE_HID",
    "INTERFACE_VENDOR",
    "LOG_METADATA_SIZE",
    "MEMORY_READ_KEY",
    "OFFLINE_LOG_SAMPLE_SIZE",
    "STREAMING_AUTH_KEY",
    "aligned_response_size",
    "build_memory_read_packet",
    "build_streaming_auth_packet",
    "crc32",
    "decrypt_memory_payload",
    "parse_memory_read_confirmation",
]

AES_BLOCK_SIZE = 16

# Response type the device returns for an address it will not read. The
# bindings parse it as Packet::NotReadable but do not export the raw code.
CMD_NOT_READABLE = 0x27

# The protocol keys, kept for firmware research (decrypt_firmware.py) and for
# building capture fixtures in tests. Live traffic goes through the bindings.
#: AES-128-ECB key for MemoryRead (0x44) requests and responses.
MEMORY_READ_KEY = b"Lh2yfB7n6X7d9a5Z"
#: AES-128-ECB key for host-to-device StreamingAuth (0x4C) requests.
STREAMING_AUTH_KEY = b"Fa0b4tA25f4R038a"


def crc32(data: bytes) -> int:
    """CRC-32 as the KM003C firmware computes it."""
    return binascii.crc32(data) & 0xFFFFFFFF


def aligned_response_size(requested_size: int) -> int:
    """Round a MemoryRead response up to whole AES blocks."""
    return -(-requested_size // AES_BLOCK_SIZE) * AES_BLOCK_SIZE


def build_memory_read_packet(address: int, size: int, transaction_id: int) -> bytes:
    """Build the 36-byte MemoryRead (0x44) request packet."""
    return bytes(km003c.build_memory_read_packet(address, size, transaction_id))


def decrypt_memory_payload(ciphertext: bytes) -> bytes:
    """Decrypt an unframed MemoryRead response body.

    Raises:
        ValueError: If the length is not a non-zero multiple of 16.
    """
    return bytes(km003c.decrypt_memory_payload(ciphertext))


def parse_memory_read_confirmation(packet: bytes) -> tuple[int, int] | None:
    """Validate a MemoryRead confirmation packet.

    Args:
        packet: The full 20-byte confirmation (4-byte header + 16-byte body).

    Returns:
        The echoed ``(address, size)``, or ``None`` when the magic word or the
        CRC-32 does not match.
    """
    result = km003c.parse_memory_read_confirmation(packet)
    return None if result is None else (int(result[0]), int(result[1]))


def build_streaming_auth_packet(credential: bytes, transaction_id: int) -> bytes:
    """Build the 36-byte StreamingAuth (0x4C) request packet.

    Raises:
        ValueError: If the credential is not exactly 12 bytes.
    """
    return bytes(km003c.build_streaming_auth_packet(credential, transaction_id))
