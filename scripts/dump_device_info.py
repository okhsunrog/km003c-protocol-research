#!/usr/bin/env python3
"""
Dump and decode device information from POWER-Z KM003C.

This script reads encrypted memory blocks from the device and decrypts them
to extract device information including:
- Model name, hardware version, manufacturing date
- Firmware version and build date
- Device serial number and UUID
- Calibration data

Usage:
    uv run scripts/dump_device_info.py
    uv run scripts/dump_device_info.py --raw  # Also save raw decrypted data
"""

import argparse
import binascii
import struct
import time
import usb.core
import usb.util
from Crypto.Cipher import AES
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

# Device identifiers
VID = 0x5FC9
PID = 0x0063

# USB endpoints (vendor interface)
INTERFACE_NUM = 0
ENDPOINT_OUT = 0x01
ENDPOINT_IN = 0x81

# AES key for memory block encryption (key index 0)
AES_KEY = b"Lh2yfB7n6X7d9a5Z"

# Known memory addresses and their purposes
MEMORY_BLOCKS = {
    0x00000420: ("DeviceInfo1", 64, "Device info block 1: model, HW version, mfg date"),
    0x00004420: ("FirmwareInfo", 64, "Firmware info: model, FW version, FW date"),
    0x03000C00: ("Calibration", 64, "Calibration data: serial, UUID, timestamp"),
    0x40010450: ("DeviceSerial", 12, "Device serial number and ID"),
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


def extract_string(data: bytes, start: int, end: int) -> str:
    """Extract null-terminated string from bytes."""
    return data[start:end].split(b'\x00')[0].decode('ascii', errors='replace')


class KM003C:
    """KM003C device interface for memory dump."""

    def __init__(self):
        dev = usb.core.find(idVendor=VID, idProduct=PID)
        if dev is None:
            raise ValueError(f"Device not found (VID={VID:04x}, PID={PID:04x})")

        # Reset device
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

    def _recv(self, timeout: int = 2000) -> bytes:
        return bytes(self.dev.read(ENDPOINT_IN, 4096, timeout=timeout))

    def _send_cmd(self, cmd_type: int, data_word: int) -> bytes | None:
        """Send 4-byte command and return response."""
        tid = self._next_tid()
        packet = bytes([cmd_type & 0x7F, tid, data_word & 0xFF, (data_word >> 8) & 0xFF])
        self._send(packet)
        try:
            return self._recv()
        except usb.core.USBTimeoutError:
            return None

    def _build_download_request(self, address: int, size: int) -> bytes:
        """Build encrypted Unknown68 download request."""
        # Build plaintext payload
        payload = struct.pack('<III', address, size, 0xFFFFFFFF)
        # Add padding for CRC calculation
        padded = payload + b'\xFF' * 4
        checksum = crc32(padded)

        # Full 32-byte payload
        full_payload = payload + struct.pack('<I', checksum) + (b'\xFF' * 16)

        # Encrypt
        encrypted = encrypt_ecb(full_payload)

        # Build packet header
        tid = self._next_tid()
        header = bytes([0x44, tid, 0x01, 0x01])

        return header + encrypted

    def download_memory(self, address: int, size: int) -> bytes:
        """Download memory from device at specified address."""
        request = self._build_download_request(address, size)
        self._send(request)

        # Read Unknown68 response (20 bytes)
        response = self._recv()
        if len(response) < 20:
            raise ValueError(f"Invalid Unknown68 response: {len(response)} bytes")

        # Check for error (type 0x06 = Rejected)
        if (response[0] & 0x7F) == 0x06:
            raise ValueError(f"Request rejected by device")

        # Check encryption flag (bit 16)
        data_encrypted = (response[2] & 0x01) == 1

        # Read data packet
        data_packet = self._recv(timeout=3000)

        if data_encrypted and len(data_packet) % 16 == 0:
            return decrypt_ecb(data_packet)
        return data_packet

    def initialize(self):
        """Run minimal initialization sequence."""
        print("Connecting...")
        self._send_cmd(0x02, 0x0000)
        time.sleep(0.05)

    def close(self):
        usb.util.release_interface(self.dev, INTERFACE_NUM)
        try:
            self.dev.reset()
        except:
            pass
        usb.util.dispose_resources(self.dev)


def parse_device_info(blocks: dict[int, bytes]) -> DeviceInfo:
    """Parse all memory blocks into DeviceInfo structure."""

    # Parse DeviceInfo1 (0x420)
    if 0x420 in blocks:
        data = blocks[0x420]
        model = extract_string(data, 0x10, 0x1C)
        hw_version = extract_string(data, 0x1C, 0x28)
        mfg_date = extract_string(data, 0x28, 0x40)
    else:
        model = hw_version = mfg_date = "N/A"

    # Parse FirmwareInfo (0x4420)
    if 0x4420 in blocks:
        data = blocks[0x4420]
        # Check if valid (first 4 bytes not 0xFFFFFFFF)
        if struct.unpack('<I', data[0:4])[0] != 0xFFFFFFFF:
            fw_version = extract_string(data, 0x1C, 0x28)
            fw_date = extract_string(data, 0x28, 0x38)
        else:
            fw_version = fw_date = "none"
    else:
        fw_version = fw_date = "N/A"

    # Parse Calibration (0x3000C00)
    if 0x3000C00 in blocks:
        data = blocks[0x3000C00]
        serial_id = data[0:7].decode('ascii', errors='replace').strip()
        uuid = data[7:39].decode('ascii', errors='replace').strip()
        ts_str = extract_string(data, 39, 51)
        calibration_timestamp = int(ts_str) if ts_str.isdigit() else None
    else:
        serial_id = uuid = "N/A"
        calibration_timestamp = None

    # Parse HardwareID (0x40010450) - authentication blob, NOT a serial number
    if 0x40010450 in blocks:
        data = blocks[0x40010450]
        hardware_id_prefix = data[0:6].decode('ascii', errors='replace')
        hardware_id_suffix = data[6:12]
    else:
        hardware_id_prefix = "N/A"
        hardware_id_suffix = b''

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


def main():
    parser = argparse.ArgumentParser(description="Dump device info from POWER-Z KM003C")
    parser.add_argument("--raw", action="store_true", help="Save raw decrypted data to files")
    args = parser.parse_args()

    try:
        device = KM003C()
        device.initialize()

        print("\n" + "=" * 60)
        print("READING DEVICE MEMORY BLOCKS")
        print("=" * 60)

        blocks = {}
        for address, (name, size, desc) in MEMORY_BLOCKS.items():
            print(f"\nReading {name} (0x{address:08X}, {size} bytes)...")
            try:
                data = device.download_memory(address, size)
                blocks[address] = data
                print(f"  OK: {len(data)} bytes")

                if args.raw:
                    raw_file = Path(f"device_{name.lower()}_0x{address:08x}.bin")
                    raw_file.write_bytes(data)
                    print(f"  Saved to {raw_file}")
            except Exception as e:
                print(f"  ERROR: {e}")

        device.close()

        # Parse and display info
        info = parse_device_info(blocks)

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
            dt = datetime.utcfromtimestamp(info.calibration_timestamp)
            print(f"Calibration Time:   {info.calibration_timestamp} ({dt.isoformat()} UTC)")
        print()
        print(f"HardwareID Prefix:  {info.hardware_id_prefix} (NOT a serial)")
        print(f"HardwareID Suffix:  {info.hardware_id_suffix.hex()}")

        # Print raw hex dumps
        print("\n" + "=" * 60)
        print("RAW MEMORY DUMPS (decrypted)")
        print("=" * 60)
        for address, data in blocks.items():
            name = MEMORY_BLOCKS[address][0]
            print(f"\n{name} (0x{address:08X}):")
            for i in range(0, len(data), 16):
                chunk = data[i:i+16]
                hex_part = ' '.join(f'{b:02x}' for b in chunk)
                ascii_part = ''.join(chr(b) if 32 <= b < 127 else '.' for b in chunk)
                print(f"  {i:04x}: {hex_part:<48} {ascii_part}")

        return 0

    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(main())
