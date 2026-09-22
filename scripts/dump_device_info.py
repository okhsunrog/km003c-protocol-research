#!/usr/bin/env python3
"""
Dump and decode device information from POWER-Z KM003C.

This script reads encrypted memory blocks from the device and decrypts them
to extract device information including:
- Model name, hardware version, manufacturing date
- Firmware version and build date
- Device serial number and UUID
- Calibration data

The MemoryRead framing, AES key and CRC layout live in
`km003c_analysis.device`, which delegates to the Rust bindings; this script
only decodes the block contents.

Usage:
    uv run --locked scripts/dump_device_info.py
    uv run --locked scripts/dump_device_info.py --raw  # Also save raw decrypted data
"""

import argparse
import struct
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from km003c_analysis.device import (
    ADDR_CALIBRATION,
    ADDR_DEVICE_INFO,
    ADDR_FIRMWARE_INFO,
    ADDR_HARDWARE_ID,
    HARDWARE_ID_SIZE,
    INFO_BLOCK_SIZE,
    Km003cUsb,
)

# Known memory addresses and their purposes
MEMORY_BLOCKS = {
    ADDR_DEVICE_INFO: (
        "DeviceInfo1",
        INFO_BLOCK_SIZE,
        "Device info block 1: model, HW version, mfg date",
    ),
    ADDR_FIRMWARE_INFO: (
        "FirmwareInfo",
        INFO_BLOCK_SIZE,
        "Firmware info: model, FW version, FW date",
    ),
    ADDR_CALIBRATION: (
        "Calibration",
        INFO_BLOCK_SIZE,
        "Calibration data: serial, UUID, timestamp",
    ),
    ADDR_HARDWARE_ID: (
        "DeviceSerial",
        HARDWARE_ID_SIZE,
        "Device serial number and ID",
    ),
}


@dataclass
class DeviceInfo:
    """Parsed device information."""

    model: str
    hw_version: str
    mfg_date: str
    fw_version: str
    fw_date: str
    serial_id: str
    uuid: str
    calibration_timestamp: int | None
    hardware_id_prefix: str  # First 6 bytes of HardwareID (NOT a serial number)
    hardware_id_suffix: bytes  # Remaining 6 bytes of HardwareID


def extract_string(data: bytes, start: int, end: int) -> str:
    """Extract null-terminated string from bytes."""
    return data[start:end].split(b"\x00")[0].decode("ascii", errors="replace")


def parse_device_info(blocks: dict[int, bytes]) -> DeviceInfo:
    """Parse all memory blocks into DeviceInfo structure."""

    # Parse DeviceInfo1 (0x420)
    if ADDR_DEVICE_INFO in blocks:
        data = blocks[ADDR_DEVICE_INFO]
        model = extract_string(data, 0x10, 0x1C)
        hw_version = extract_string(data, 0x1C, 0x28)
        mfg_date = extract_string(data, 0x28, 0x40)
    else:
        model = hw_version = mfg_date = "N/A"

    # Parse FirmwareInfo (0x4420)
    if ADDR_FIRMWARE_INFO in blocks:
        data = blocks[ADDR_FIRMWARE_INFO]
        # Check if valid (first 4 bytes not 0xFFFFFFFF)
        if struct.unpack("<I", data[0:4])[0] != 0xFFFFFFFF:
            fw_version = extract_string(data, 0x1C, 0x28)
            fw_date = extract_string(data, 0x28, 0x38)
        else:
            fw_version = fw_date = "none"
    else:
        fw_version = fw_date = "N/A"

    # Parse Calibration (0x3000C00)
    if ADDR_CALIBRATION in blocks:
        data = blocks[ADDR_CALIBRATION]
        serial_id = data[0:7].decode("ascii", errors="replace").strip()
        uuid = data[7:39].decode("ascii", errors="replace").strip()
        ts_str = extract_string(data, 39, 51)
        calibration_timestamp = int(ts_str) if ts_str.isdigit() else None
    else:
        serial_id = uuid = "N/A"
        calibration_timestamp = None

    # Parse HardwareID (0x40010450) - authentication blob, NOT a serial number
    if ADDR_HARDWARE_ID in blocks:
        data = blocks[ADDR_HARDWARE_ID]
        hardware_id_prefix = data[0:6].decode("ascii", errors="replace")
        hardware_id_suffix = data[6:HARDWARE_ID_SIZE]
    else:
        hardware_id_prefix = "N/A"
        hardware_id_suffix = b""

    return DeviceInfo(
        model=model,
        hw_version=hw_version,
        mfg_date=mfg_date,
        fw_version=fw_version,
        fw_date=fw_date,
        serial_id=serial_id,
        uuid=uuid,
        calibration_timestamp=calibration_timestamp,
        hardware_id_prefix=hardware_id_prefix,
        hardware_id_suffix=hardware_id_suffix,
    )


def read_blocks(device: Km003cUsb, save_raw: bool) -> dict[int, bytes]:
    """Read every documented info block, reporting per-block failures."""
    blocks: dict[int, bytes] = {}
    for address, (name, size, _description) in MEMORY_BLOCKS.items():
        print(f"\nReading {name} (0x{address:08X}, {size} bytes)...")
        try:
            data = device.read_memory(address, size)
        except Exception as error:  # noqa: BLE001 - one bad block must not stop the dump
            print(f"  ERROR: {error}")
            continue

        blocks[address] = data
        print(f"  OK: {len(data)} bytes")
        if save_raw:
            raw_file = Path(f"device_{name.lower()}_0x{address:08x}.bin")
            raw_file.write_bytes(data)
            print(f"  Saved to {raw_file}")
    return blocks


def print_report(info: DeviceInfo, blocks: dict[int, bytes]) -> None:
    print("\n" + "=" * 60)
    print("DEVICE INFORMATION")
    print("=" * 60)
    print(f"Model:              {info.model}")
    print(f"Hardware Version:   {info.hw_version}")
    print(f"Manufacturing Date: {info.mfg_date}")
    print()
    print(f"Firmware Version:   {info.fw_version}")
    print(f"Firmware Date:      {info.fw_date}")
    print()
    print(f"Serial ID:          {info.serial_id}")
    print(f"UUID:               {info.uuid}")
    if info.calibration_timestamp:
        moment = datetime.fromtimestamp(info.calibration_timestamp, tz=UTC)
        print(
            f"Calibration Time:   {info.calibration_timestamp} ({moment.isoformat()})"
        )
    print()
    print(f"HardwareID Prefix:  {info.hardware_id_prefix} (NOT a serial)")
    print(f"HardwareID Suffix:  {info.hardware_id_suffix.hex()}")

    print("\n" + "=" * 60)
    print("RAW MEMORY DUMPS (decrypted)")
    print("=" * 60)
    for address, data in blocks.items():
        print(f"\n{MEMORY_BLOCKS[address][0]} (0x{address:08X}):")
        for offset in range(0, len(data), 16):
            chunk = data[offset : offset + 16]
            hex_part = " ".join(f"{byte:02x}" for byte in chunk)
            ascii_part = "".join(
                chr(byte) if 32 <= byte < 127 else "." for byte in chunk
            )
            print(f"  {offset:04x}: {hex_part:<48} {ascii_part}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Dump device info from POWER-Z KM003C")
    parser.add_argument(
        "--raw", action="store_true", help="Save raw decrypted data to files"
    )
    args = parser.parse_args()

    try:
        with Km003cUsb("vendor") as device:
            device.connect()

            print("\n" + "=" * 60)
            print("READING DEVICE MEMORY BLOCKS")
            print("=" * 60)
            blocks = read_blocks(device, args.raw)

        print_report(parse_device_info(blocks), blocks)
        return 0

    except Exception as error:  # noqa: BLE001 - top-level CLI reporting
        print(f"\nError: {error}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
