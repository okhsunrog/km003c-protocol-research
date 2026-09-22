"""Hardware access for the KM003C research scripts.

`protocol` owns the authenticated command layout, `transport` owns the pyusb
plumbing. Scripts should import from here rather than re-deriving the AES keys
or the confirmation layout.
"""

from .protocol import (
    ADDR_CALIBRATION,
    ADDR_DEVICE_INFO,
    ADDR_FIRMWARE_INFO,
    ADDR_HARDWARE_ID,
    ADDR_OFFLINE_LOG,
    ADDR_PREFERRED_CALIBRATION,
    AES_BLOCK_SIZE,
    HARDWARE_ID_SIZE,
    INFO_BLOCK_SIZE,
    LOG_METADATA_SIZE,
    MEMORY_READ_KEY,
    OFFLINE_LOG_SAMPLE_SIZE,
    STREAMING_AUTH_KEY,
    aligned_response_size,
    build_memory_read_packet,
    build_streaming_auth_packet,
    crc32,
    decrypt_memory_payload,
    parse_memory_read_confirmation,
)
from .transport import INTERFACES, InterfaceConfig, Km003cUsb, MemoryReadError

__all__ = [
    "ADDR_CALIBRATION",
    "ADDR_DEVICE_INFO",
    "ADDR_FIRMWARE_INFO",
    "ADDR_HARDWARE_ID",
    "ADDR_OFFLINE_LOG",
    "ADDR_PREFERRED_CALIBRATION",
    "AES_BLOCK_SIZE",
    "HARDWARE_ID_SIZE",
    "INFO_BLOCK_SIZE",
    "INTERFACES",
    "InterfaceConfig",
    "Km003cUsb",
    "LOG_METADATA_SIZE",
    "MEMORY_READ_KEY",
    "MemoryReadError",
    "OFFLINE_LOG_SAMPLE_SIZE",
    "STREAMING_AUTH_KEY",
    "aligned_response_size",
    "build_memory_read_packet",
    "build_streaming_auth_packet",
    "crc32",
    "decrypt_memory_payload",
    "parse_memory_read_confirmation",
]
