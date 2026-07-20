#!/usr/bin/env python3
"""
Memory scanner for POWER-Z KM003C.

Scans various memory addresses and reports response types.
This reproduces the Rust memory_scan binary functionality.

Usage:
    uv run scripts/memory_scan.py
    uv run scripts/memory_scan.py --quick   # Only known addresses
"""

import argparse
import binascii
import struct
import time
from dataclasses import dataclass
from enum import Enum

import usb.core
import usb.util
from Crypto.Cipher import AES

# Device identifiers
VID = 0x5FC9
PID = 0x0063

# USB endpoints (vendor interface)
INTERFACE_NUM = 0
ENDPOINT_OUT = 0x01
ENDPOINT_IN = 0x81

# AES key for memory block encryption (key index 0)
AES_KEY = b"Lh2yfB7n6X7d9a5Z"

# Known memory addresses from protocol documentation
KNOWN_ADDRESSES = {
    0x00000420: ("DeviceInfo1", 64),
    0x00004420: ("FirmwareInfo", 64),
    0x03000C00: ("CalibrationData", 64),
    0x40010450: ("HardwareID", 12),
    0x98100000: ("LogData", 64),
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

    def __str__(self):
        if self.result == ReadResult.DATA:
            return f"Data({self.size}B)"
        elif self.result == ReadResult.ERROR:
            return f"Error({self.error_msg})"
        else:
            return self.result.value


def encrypt_ecb(data: bytes) -> bytes:
    """Encrypt data using AES-128 ECB."""
    cipher = AES.new(AES_KEY, AES.MODE_ECB)
    return cipher.encrypt(data)


def decrypt_ecb(data: bytes) -> bytes:
    """Decrypt data using AES-128 ECB."""
    cipher = AES.new(AES_KEY, AES.MODE_ECB)
    return cipher.decrypt(data)


def crc32(data: bytes) -> int:
    """Calculate CRC32 checksum."""
    return binascii.crc32(data) & 0xFFFFFFFF


class KM003C:
    """KM003C device interface for memory scanning."""

    def __init__(self, skip_reset: bool = False):
        dev = usb.core.find(idVendor=VID, idProduct=PID)
        if dev is None:
            raise ValueError(f"Device not found (VID={VID:04x}, PID={PID:04x})")

        if not skip_reset:
            print("Resetting device...")
            try:
                dev.reset()
                time.sleep(1.5)
            except Exception as e:
                print(f"Warning: {e}")
                time.sleep(0.5)

            # Reconnect after reset
            self.dev = usb.core.find(idVendor=VID, idProduct=PID)
            if self.dev is None:
                raise ValueError("Device not found after reset")
        else:
            self.dev = dev

        # Detach kernel drivers
        for cfg in self.dev:
            for intf in cfg:
                if self.dev.is_kernel_driver_active(intf.bInterfaceNumber):
                    self.dev.detach_kernel_driver(intf.bInterfaceNumber)

        self.dev.set_configuration()
        usb.util.claim_interface(self.dev, INTERFACE_NUM)

        self.tid = 0
        print("Device connected")

    def _next_tid(self) -> int:
        self.tid = (self.tid + 1) & 0xFF
        return self.tid

    def _send(self, data: bytes):
        self.dev.write(ENDPOINT_OUT, data)

    def _recv(self, timeout: int = 500) -> bytes:
        return bytes(self.dev.read(ENDPOINT_IN, 4096, timeout=timeout))

    def _send_cmd(self, cmd_type: int, data_word: int) -> bytes | None:
        """Send 4-byte command and return response."""
        tid = self._next_tid()
        packet = bytes(
            [cmd_type & 0x7F, tid, data_word & 0xFF, (data_word >> 8) & 0xFF]
        )
        self._send(packet)
        try:
            return self._recv()
        except usb.core.USBTimeoutError:
            return None

    def _build_memory_read_request(self, address: int, size: int) -> bytes:
        """Build encrypted MemoryRead (0x44) request."""
        # Build plaintext: address + size + magic + CRC + padding
        payload = struct.pack("<III", address, size, 0xFFFFFFFF)
        checksum = crc32(payload)
        full_payload = payload + struct.pack("<I", checksum) + (b"\xff" * 16)

        # Encrypt
        encrypted = encrypt_ecb(full_payload)

        # Build packet header
        tid = self._next_tid()
        header = bytes([0x44, tid, 0x01, 0x01])

        return header + encrypted

    def try_read_memory(self, address: int, size: int) -> ScanResult:
        """Attempt to read memory and return result type."""
        try:
            request = self._build_memory_read_request(address, size)
            self._send(request)

            # First response: confirmation (0xC4) or error (0x06/0x27)
            try:
                response = self._recv(timeout=500)
            except usb.core.USBTimeoutError:
                return ScanResult(ReadResult.TIMEOUT)

            if len(response) < 4:
                return ScanResult(
                    ReadResult.ERROR, error_msg=f"short response: {len(response)}B"
                )

            resp_type = response[0] & 0x7F

            # Check for error responses
            if resp_type == 0x06:  # Reject
                return ScanResult(ReadResult.REJECT)
            elif resp_type == 0x27:  # NotReadable
                return ScanResult(ReadResult.NOT_READABLE)
            elif resp_type == 0x44:  # Confirmation (0xC4 with bit 7 set)
                # Read encrypted data packet
                try:
                    data_packet = self._recv(timeout=500)
                except usb.core.USBTimeoutError:
                    return ScanResult(ReadResult.TIMEOUT, error_msg="data timeout")

                # Decrypt if valid AES block
                if len(data_packet) > 0 and len(data_packet) % 16 == 0:
                    decrypted = decrypt_ecb(data_packet)
                    return ScanResult(ReadResult.DATA, size=len(decrypted))
                else:
                    return ScanResult(ReadResult.DATA, size=len(data_packet))
            else:
                return ScanResult(
                    ReadResult.ERROR, error_msg=f"unexpected type 0x{resp_type:02X}"
                )

        except usb.core.USBError as e:
            return ScanResult(ReadResult.ERROR, error_msg=str(e))
        except Exception as e:
            return ScanResult(ReadResult.ERROR, error_msg=str(e))

    def initialize(self):
        """Run minimal initialization sequence."""
        print("Connecting...")
        self._send_cmd(0x02, 0x0000)
        time.sleep(0.05)

    def close(self):
        try:
            usb.util.release_interface(self.dev, INTERFACE_NUM)
        except usb.core.USBError:
            pass
        try:
            usb.util.dispose_resources(self.dev)
        except usb.core.USBError:
            pass


def main():
    parser = argparse.ArgumentParser(description="Scan KM003C memory regions")
    parser.add_argument(
        "--quick", action="store_true", help="Only scan known addresses"
    )
    parser.add_argument("--no-reset", action="store_true", help="Skip USB reset")
    args = parser.parse_args()

    try:
        device = KM003C(skip_reset=args.no_reset)
        device.initialize()

        results = {}

        print("\n" + "=" * 60)
        print("SCANNING KNOWN ADDRESSES")
        print("=" * 60 + "\n")

        for address, (name, size) in KNOWN_ADDRESSES.items():
            result = device.try_read_memory(address, size)
            results[address] = result
            print(f"  0x{address:08X} ({name:16}): {result}")
            time.sleep(0.05)  # Delay to avoid overwhelming device

        if not args.quick:
            print("\n" + "=" * 60)
            print("SCANNING BOUNDARY ADDRESSES")
            print("=" * 60 + "\n")

            for address in BOUNDARY_ADDRESSES:
                if address in results:
                    continue
                result = device.try_read_memory(address, 64)
                results[address] = result
                print(f"  0x{address:08X}: {result}")
                time.sleep(0.05)

                # Stop if device disconnected
                if (
                    result.result == ReadResult.ERROR
                    and "disconnect" in result.error_msg.lower()
                ):
                    print("\n  Device disconnected! Stopping scan.")
                    break

        device.close()

        # Summary
        print("\n" + "=" * 60)
        print("SUMMARY")
        print("=" * 60 + "\n")

        counts = {r: 0 for r in ReadResult}
        for result in results.values():
            counts[result.result] += 1

        print(f"Total addresses scanned: {len(results)}")
        print(f"  Data:        {counts[ReadResult.DATA]}")
        print(f"  NotReadable: {counts[ReadResult.NOT_READABLE]}")
        print(f"  Reject:      {counts[ReadResult.REJECT]}")
        print(f"  Timeout:     {counts[ReadResult.TIMEOUT]}")
        print(f"  Error:       {counts[ReadResult.ERROR]}")

        print("\nAddresses that returned data:\n")
        for address, result in sorted(results.items()):
            if result.result == ReadResult.DATA:
                name = KNOWN_ADDRESSES.get(address, (None, None))[0]
                if name:
                    print(f"  0x{address:08X} ({name}): {result}")
                else:
                    print(f"  0x{address:08X}: {result}")

        return 0

    except Exception as e:
        print(f"\nError: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(main())
