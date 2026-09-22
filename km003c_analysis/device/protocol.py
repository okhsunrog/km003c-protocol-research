"""Single implementation of the authenticated KM003C commands.

`memory_scan.py`, `dump_device_info.py`, `download_offline_log.py`,
`run_adcqueue_single.py` and `decrypt_offline_adc.py` each used to carry their
own copy of the AES key, the CRC layout and the request framing. A change to
any of those in the firmware, or a correction in the Rust library, silently
left five Python copies behind.

Everything here delegates to the Rust `km003c` bindings when the installed
version exposes them, and otherwise falls back to an equivalent local
implementation. Once the pinned `km003c` release ships the helpers, the
fallback becomes dead weight and this module collapses to a re-export.
"""

from __future__ import annotations

import binascii
import os
import struct
import time
from collections.abc import Callable
from typing import Any

import km003c

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


def _const(name: str, documented: int) -> int:
    """Prefer the value the bindings expose, else the documented literal.

    The pinned `km003c` release does not export the whole memory map yet. Going
    through here means each constant has exactly one definition today and
    disappears from this file once the bindings catch up.
    """
    value = getattr(km003c, name, None)
    return documented if value is None else int(value)


# USB interfaces and endpoints, see docs/usb_transport.md.
INTERFACE_VENDOR = _const("INTERFACE_VENDOR", 0)
ENDPOINT_OUT_VENDOR = _const("ENDPOINT_OUT_VENDOR", 0x01)
ENDPOINT_IN_VENDOR = _const("ENDPOINT_IN_VENDOR", 0x81)
INTERFACE_HID = _const("INTERFACE_HID", 3)
ENDPOINT_OUT_HID = _const("ENDPOINT_OUT_HID", 0x05)
ENDPOINT_IN_HID = _const("ENDPOINT_IN_HID", 0x85)

# Command codes not yet exported by the pinned release.
CMD_MEMORY_READ = _const("CMD_MEMORY_READ", 0x44)
CMD_STREAMING_AUTH = _const("CMD_STREAMING_AUTH", 0x4C)
CMD_NOT_READABLE = _const("CMD_NOT_READABLE", 0x27)

# Device memory map, see docs/protocol_reference.md.
ADDR_DEVICE_INFO = _const("ADDR_DEVICE_INFO", 0x00000420)
ADDR_FIRMWARE_INFO = _const("ADDR_FIRMWARE_INFO", 0x00004420)
ADDR_CALIBRATION = _const("ADDR_CALIBRATION", 0x03000C00)
ADDR_PREFERRED_CALIBRATION = _const("ADDR_PREFERRED_CALIBRATION", 0x03000D80)
ADDR_HARDWARE_ID = _const("ADDR_HARDWARE_ID", 0x40010450)
ADDR_OFFLINE_LOG = _const("ADDR_OFFLINE_LOG", 0x98100000)
INFO_BLOCK_SIZE = _const("INFO_BLOCK_SIZE", 64)
HARDWARE_ID_SIZE = _const("HARDWARE_ID_SIZE", 12)
LOG_METADATA_SIZE = _const("LOG_METADATA_SIZE", 48)
OFFLINE_LOG_SAMPLE_SIZE = _const("OFFLINE_LOG_SAMPLE_SIZE", 16)

AES_BLOCK_SIZE = 16

#: AES-128-ECB key for MemoryRead (0x44) requests and responses.
MEMORY_READ_KEY = b"Lh2yfB7n6X7d9a5Z"
#: AES-128-ECB key for host-to-device StreamingAuth (0x4C) requests.
STREAMING_AUTH_KEY = b"Fa0b4tA25f4R038a"

_MEMORY_READ_MAGIC = 0xFFFFFFFF
_CONFIRMATION_BODY_SIZE = 16
_STREAMING_AUTH_CREDENTIAL_SIZE = 12


def crc32(data: bytes) -> int:
    """CRC-32 as the KM003C firmware computes it."""
    return binascii.crc32(data) & 0xFFFFFFFF


def aligned_response_size(requested_size: int) -> int:
    """Round a MemoryRead response up to whole AES blocks."""
    return -(-requested_size // AES_BLOCK_SIZE) * AES_BLOCK_SIZE


def _native(name: str) -> Callable[..., Any] | None:
    """The binding's own implementation of `name`, when it has one."""
    return getattr(km003c, name, None)


def _encrypt(key: bytes, plaintext: bytes) -> bytes:
    from Crypto.Cipher import AES

    ciphertext: bytes = AES.new(key, AES.MODE_ECB).encrypt(plaintext)
    return ciphertext


def _decrypt(key: bytes, ciphertext: bytes) -> bytes:
    from Crypto.Cipher import AES

    plaintext: bytes = AES.new(key, AES.MODE_ECB).decrypt(ciphertext)
    return plaintext


def build_memory_read_packet(address: int, size: int, transaction_id: int) -> bytes:
    """Build the 36-byte MemoryRead (0x44) request packet."""
    native = _native("build_memory_read_packet")
    if native is not None:
        return bytes(native(address, size, transaction_id))

    body = struct.pack("<III", address, size, _MEMORY_READ_MAGIC)
    plaintext = body + struct.pack("<I", crc32(body)) + b"\xff" * 16
    header = bytes([0x44, transaction_id & 0xFF, 0x01, 0x01])
    return header + _encrypt(MEMORY_READ_KEY, plaintext)


def decrypt_memory_payload(ciphertext: bytes) -> bytes:
    """Decrypt an unframed MemoryRead response body."""
    if not ciphertext or len(ciphertext) % AES_BLOCK_SIZE:
        raise ValueError(
            f"Ciphertext length must be a non-zero multiple of {AES_BLOCK_SIZE}, "
            f"got {len(ciphertext)}"
        )
    native = _native("decrypt_memory_payload")
    if native is not None:
        return bytes(native(ciphertext))
    return _decrypt(MEMORY_READ_KEY, ciphertext)


def parse_memory_read_confirmation(packet: bytes) -> tuple[int, int] | None:
    """Validate a MemoryRead confirmation packet.

    Args:
        packet: The full 20-byte confirmation (4-byte header + 16-byte body).

    Returns:
        The echoed ``(address, size)``, or ``None`` when the magic word or the
        CRC-32 does not match.
    """
    native = _native("parse_memory_read_confirmation")
    if native is not None:
        result = native(packet)
        return None if result is None else (int(result[0]), int(result[1]))

    body = packet[4 : 4 + _CONFIRMATION_BODY_SIZE]
    if len(body) != _CONFIRMATION_BODY_SIZE:
        return None
    address, size, magic, checksum = struct.unpack("<IIII", body)
    if magic != _MEMORY_READ_MAGIC or checksum != crc32(body[:12]):
        return None
    return int(address), int(size)


def build_streaming_auth_packet(credential: bytes, transaction_id: int) -> bytes:
    """Build the 36-byte StreamingAuth (0x4C) request packet."""
    if len(credential) != _STREAMING_AUTH_CREDENTIAL_SIZE:
        raise ValueError(
            f"Credential must be exactly {_STREAMING_AUTH_CREDENTIAL_SIZE} bytes, "
            f"got {len(credential)}"
        )
    native = _native("build_streaming_auth_packet")
    if native is not None:
        return bytes(native(credential, transaction_id))

    timestamp_ms = int(time.time() * 1000)
    plaintext = struct.pack("<Q", timestamp_ms) + credential + os.urandom(12)
    header = bytes([0x4C, transaction_id & 0xFF, 0x00, 0x02])
    return header + _encrypt(STREAMING_AUTH_KEY, plaintext)
