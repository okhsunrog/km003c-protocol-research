#!/usr/bin/env python3
"""
Memory scanner for POWER-Z KM003C.

Scans various memory addresses and reports response types.
This reproduces the Rust memory_scan binary functionality.

The MemoryRead framing, AES key and CRC layout live in
`km003c_analysis.device`; this script only decides what to probe and how to
classify the answers.

Usage:
    uv run --locked scripts/memory_scan.py
    uv run --locked scripts/memory_scan.py --quick   # Only known addresses
"""

import argparse
import time
from dataclasses import dataclass
from enum import Enum

import usb.core

from km003c_analysis.device import (
    ADDR_CALIBRATION,
    ADDR_DEVICE_INFO,
    ADDR_FIRMWARE_INFO,
    ADDR_HARDWARE_ID,
    ADDR_OFFLINE_LOG,
    HARDWARE_ID_SIZE,
    INFO_BLOCK_SIZE,
    Km003cUsb,
    MemoryReadError,
)

# Known memory addresses from protocol documentation
KNOWN_ADDRESSES = {
    ADDR_DEVICE_INFO: ("DeviceInfo1", INFO_BLOCK_SIZE),
    ADDR_FIRMWARE_INFO: ("FirmwareInfo", INFO_BLOCK_SIZE),
    ADDR_CALIBRATION: ("CalibrationData", INFO_BLOCK_SIZE),
    ADDR_HARDWARE_ID: ("HardwareID", HARDWARE_ID_SIZE),
    ADDR_OFFLINE_LOG: ("LogData", INFO_BLOCK_SIZE),
}

# Boundary addresses to scan
BOUNDARY_ADDRESSES = [
    0x00000000,
    0x00000100,
    0x00000200,
    0x00000400,
    0x00000800,
    0x00001000,
    0x00002000,
    0x00004000,
    0x00008000,
    0x00010000,
    0x00100000,
    0x01000000,
    0x02000000,
    0x03000000,
    0x04000000,
    0x08000000,
    0x10000000,
    0x20000000,
    0x40000000,
    0x40010000,
    0x40020000,
    0x80000000,
    0x90000000,
    0x98000000,
    0x9F000000,
    0xA0000000,
    0xE0000000,
    0xF0000000,
    0xFFFFFF00,
]

# Probing an unmapped address should fail fast rather than stall the scan.
PROBE_TIMEOUT_MS = 500


class ReadResult(Enum):
    DATA = "Data"
    REJECT = "Reject"
    NOT_READABLE = "NotReadable"
    TIMEOUT = "Timeout"
    ERROR = "Error"


@dataclass
class ScanResult:
    result: ReadResult
    size: int = 0
    error_msg: str = ""

    def __str__(self) -> str:
        if self.result == ReadResult.DATA:
            return f"Data({self.size}B)"
        if self.result == ReadResult.ERROR:
            return f"Error({self.error_msg})"
        return self.result.value


def classify(error: MemoryReadError) -> ScanResult:
    """Map a MemoryRead failure onto the scanner's result categories."""
    message = str(error)
    if "rejected" in message:
        return ScanResult(ReadResult.REJECT)
    if "not readable" in message:
        return ScanResult(ReadResult.NOT_READABLE)
    if "No confirmation" in message or "Truncated" in message:
        return ScanResult(ReadResult.TIMEOUT, error_msg=message)
    return ScanResult(ReadResult.ERROR, error_msg=message)


def probe(device: Km003cUsb, address: int, size: int) -> ScanResult:
    """Attempt one read and classify the outcome."""
    try:
        data = device.read_memory(address, size, timeout_ms=PROBE_TIMEOUT_MS)
    except MemoryReadError as error:
        return classify(error)
    except usb.core.USBTimeoutError:
        return ScanResult(ReadResult.TIMEOUT)
    except usb.core.USBError as error:
        return ScanResult(ReadResult.ERROR, error_msg=str(error))
    return ScanResult(ReadResult.DATA, size=len(data))


def scan(device: Km003cUsb, quick: bool) -> dict[int, ScanResult]:
    results: dict[int, ScanResult] = {}

    print("\n" + "=" * 60)
    print("SCANNING KNOWN ADDRESSES")
    print("=" * 60 + "\n")
    for address, (name, size) in KNOWN_ADDRESSES.items():
        results[address] = probe(device, address, size)
        print(f"  0x{address:08X} ({name:16}): {results[address]}")
        time.sleep(0.05)  # Delay to avoid overwhelming device

    if quick:
        return results

    print("\n" + "=" * 60)
    print("SCANNING BOUNDARY ADDRESSES")
    print("=" * 60 + "\n")
    for address in BOUNDARY_ADDRESSES:
        if address in results:
            continue
        result = probe(device, address, INFO_BLOCK_SIZE)
        results[address] = result
        print(f"  0x{address:08X}: {result}")
        time.sleep(0.05)

        if (
            result.result == ReadResult.ERROR
            and "disconnect" in result.error_msg.lower()
        ):
            print("\n  Device disconnected! Stopping scan.")
            break

    return results


def print_summary(results: dict[int, ScanResult]) -> None:
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60 + "\n")

    counts = dict.fromkeys(ReadResult, 0)
    for result in results.values():
        counts[result.result] += 1

    print(f"Total addresses scanned: {len(results)}")
    for kind in ReadResult:
        print(f"  {kind.value + ':':<13}{counts[kind]}")

    print("\nAddresses that returned data:\n")
    for address, result in sorted(results.items()):
        if result.result is not ReadResult.DATA:
            continue
        name = KNOWN_ADDRESSES.get(address, (None, None))[0]
        label = f" ({name})" if name else ""
        print(f"  0x{address:08X}{label}: {result}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Scan KM003C memory regions")
    parser.add_argument(
        "--quick", action="store_true", help="Only scan known addresses"
    )
    parser.add_argument("--no-reset", action="store_true", help="Skip USB reset")
    args = parser.parse_args()

    try:
        with Km003cUsb("vendor", skip_reset=args.no_reset) as device:
            device.connect()
            time.sleep(0.05)
            results = scan(device, args.quick)

        print_summary(results)
        return 0

    except Exception as error:  # noqa: BLE001 - top-level CLI reporting
        print(f"\nError: {error}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
