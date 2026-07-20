#!/usr/bin/env python3
"""
Download offline ADC logs from POWER-Z KM003C.

This script:
1. Connects to the device
2. Requests log metadata (name, sample count, interval)
3. Downloads the encrypted log data
4. Decrypts using AES-128 ECB
5. Parses and displays the ADC samples

Usage:
    uv run scripts/download_offline_log.py
    uv run scripts/download_offline_log.py --output log_data.csv
"""

import argparse
import os
import struct
import time
from dataclasses import dataclass

import usb.core
import usb.util
from Crypto.Cipher import AES
from km003c import PID, VID

# USB endpoints (vendor interface)
INTERFACE_NUM = 0
ENDPOINT_OUT = 0x01
ENDPOINT_IN = 0x81

# AES key for MemoryRead requests and responses
AES_KEY = b"Lh2yfB7n6X7d9a5Z"
STREAMING_AUTH_KEY = b"Fa0b4tA25f4R038a"
AES_BLOCK_SIZE = 16

# Initialization reads used by the official application.
INIT_MEMORY_READS = [
    (0x00000420, 64),
    (0x00004420, 64),
    (0x03000C00, 64),
    (0x40010450, 12),
]


@dataclass
class LogMetadata:
    """Offline log metadata from attribute 0x0200."""

    name: str
    sample_count: int
    interval_ms: int
    flags: int
    recorded_duration_seconds: int

    @property
    def duration_seconds(self) -> float:
        """Elapsed time between the first and last recorded samples."""
        return max(self.sample_count - 1, 0) * self.interval_ms / 1000

    @property
    def data_size(self) -> int:
        """Actual data size (16 bytes per sample)."""
        return self.sample_count * 16


@dataclass
class AdcSample:
    """Single ADC sample from offline log."""

    voltage_uv: int  # Microvolts
    current_ua: int  # Microamps (negative = discharge)
    charge_acc_uah: int  # Accumulated charge in µAh
    energy_acc_uwh: int  # Accumulated energy in µWh

    @property
    def voltage_v(self) -> float:
        return self.voltage_uv / 1_000_000

    @property
    def current_a(self) -> float:
        return self.current_ua / 1_000_000

    @property
    def charge_mah(self) -> float:
        return self.charge_acc_uah / 1000

    @property
    def energy_mwh(self) -> float:
        return self.energy_acc_uwh / 1000


def decrypt_ecb(data: bytes, key: bytes = AES_KEY) -> bytes:
    """Decrypt data using AES-128 ECB."""
    cipher = AES.new(key, AES.MODE_ECB)
    return cipher.decrypt(data)


def encrypt_ecb(data: bytes, key: bytes = AES_KEY) -> bytes:
    """Encrypt data using AES-128 ECB."""
    cipher = AES.new(key, AES.MODE_ECB)
    return cipher.encrypt(data)


def crc32(data: bytes) -> int:
    """Calculate CRC32 checksum."""
    import binascii

    return binascii.crc32(data) & 0xFFFFFFFF


def memory_response_size(requested_size: int) -> int:
    """Round a MemoryRead response up to complete AES blocks."""
    return ((requested_size + AES_BLOCK_SIZE - 1) // AES_BLOCK_SIZE) * AES_BLOCK_SIZE


def validate_memory_read_confirmation(
    response: bytes, tid: int, address: int, size: int
) -> None:
    """Validate the 20-byte plaintext confirmation preceding MemoryRead data."""
    if len(response) != 20:
        raise ValueError(
            f"MemoryRead confirmation must be 20 bytes, got {len(response)}"
        )
    if response[0] & 0x7F != 0x44 or response[1] != tid:
        raise ValueError("MemoryRead confirmation type or transaction ID mismatch")
    if response[2:4] != b"\x01\x01":
        raise ValueError(f"Unexpected MemoryRead header word: {response[2:4].hex()}")

    echoed_address, echoed_size, magic, checksum = struct.unpack(
        "<IIII", response[4:20]
    )
    expected_crc = crc32(response[4:16])
    if echoed_address != address or echoed_size != size:
        raise ValueError(
            "MemoryRead confirmation echo mismatch: "
            f"got address=0x{echoed_address:08X}, size={echoed_size}"
        )
    if magic != 0xFFFFFFFF:
        raise ValueError(f"Unexpected MemoryRead magic: 0x{magic:08X}")
    if checksum != expected_crc:
        raise ValueError(
            f"MemoryRead confirmation CRC mismatch: expected 0x{expected_crc:08X}, "
            f"got 0x{checksum:08X}"
        )


class KM003C:
    """KM003C device interface for offline log download."""

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

    def _recv_memory_data(self, requested_size: int) -> bytes:
        """Collect an unframed encrypted MemoryRead response across USB transfers."""
        expected_size = memory_response_size(requested_size)
        encrypted = bytearray()
        while len(encrypted) < expected_size:
            chunk = self._recv(timeout=5000)
            if not chunk:
                raise ValueError("Received an empty MemoryRead data transfer")
            if len(encrypted) + len(chunk) > expected_size:
                raise ValueError(
                    "MemoryRead data exceeded expected size: "
                    f"expected {expected_size}, got at least {len(encrypted) + len(chunk)}"
                )
            encrypted.extend(chunk)
            print(
                f"  Raw encrypted chunk: size={len(chunk)}, "
                f"total={len(encrypted)}/{expected_size}"
            )
        return bytes(encrypted)

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

    def initialize(self):
        """Run initialization sequence."""
        print("Running initialization sequence...")

        # Connect
        self._send_cmd(0x02, 0x0000)
        time.sleep(0.05)

        # Read the same device-information blocks as the official application.
        hardware_id = None
        for address, size in INIT_MEMORY_READS:
            request = self._build_memory_read_request(address, size)
            self._send(request)
            confirmation = self._recv()
            validate_memory_read_confirmation(confirmation, request[1], address, size)
            data = decrypt_ecb(self._recv_memory_data(size))[:size]
            if address == 0x40010450:
                hardware_id = data
            time.sleep(0.05)

        if hardware_id is None or len(hardware_id) != 12:
            raise ValueError("Failed to read the 12-byte HardwareID")

        # Authenticate with this device's HardwareID rather than replaying a
        # device-specific packet from a capture.
        auth_request = self._build_streaming_auth_request(hardware_id)
        self._send(auth_request)
        auth_response = self._recv()
        if len(auth_response) < 4 or auth_response[0] & 0x7F != 0x4C:
            raise ValueError("Invalid StreamingAuth response")
        auth_result = struct.unpack("<H", auth_response[2:4])[0]
        if auth_result & 0x03 != 0x03:
            raise ValueError(f"StreamingAuth failed with result 0x{auth_result:04X}")
        time.sleep(0.05)

        # GetData commands
        self._send_cmd(0x0C, 0x0020)  # PD
        time.sleep(0.05)
        self._send_cmd(0x0C, 0x0010)  # Settings
        time.sleep(0.05)

        print("Initialization complete")

    def get_log_metadata(self) -> LogMetadata | None:
        """Request log metadata (attribute 0x0200)."""
        # GetData with attribute 0x0200 (encoded as 0x0400 in wire format)
        response = self._send_cmd(0x0C, 0x0400)

        if response is None or len(response) < 56:
            return None

        # Check for PutData response with attribute 0x0200
        pkt_type = response[0] & 0x7F
        if pkt_type != 0x41:
            return None

        # Parse metadata (starts at byte 8)
        metadata = response[8:]

        name_bytes = metadata[0:16]
        name = name_bytes.split(b"\x00")[0].decode("ascii", errors="replace")

        sample_count = struct.unpack("<H", metadata[18:20])[0]
        interval_ms = struct.unpack("<H", metadata[20:22])[0]
        flags = struct.unpack("<H", metadata[22:24])[0]
        recorded_duration_seconds = struct.unpack("<I", metadata[24:28])[0]

        return LogMetadata(
            name=name,
            sample_count=sample_count,
            interval_ms=interval_ms,
            flags=flags,
            recorded_duration_seconds=recorded_duration_seconds,
        )

    def _build_memory_read_request(self, address: int, size: int) -> bytes:
        """Build an encrypted MemoryRead request."""
        # Build plaintext payload
        payload = struct.pack("<III", address, size, 0xFFFFFFFF)
        checksum = crc32(payload)

        # Full 32-byte payload
        full_payload = payload + struct.pack("<I", checksum) + (b"\xff" * 16)

        # Encrypt
        encrypted = encrypt_ecb(full_payload)

        # Build packet header
        tid = self._next_tid()
        header = bytes([0x44, tid, 0x01, 0x01])

        return header + encrypted

    def _build_streaming_auth_request(self, hardware_id: bytes) -> bytes:
        """Build a fresh StreamingAuth request for the connected device."""
        if len(hardware_id) != 12:
            raise ValueError(f"HardwareID must be 12 bytes, got {len(hardware_id)}")

        timestamp_ms = time.time_ns() // 1_000_000
        plaintext = struct.pack("<Q", timestamp_ms) + hardware_id + os.urandom(12)
        encrypted = encrypt_ecb(plaintext, STREAMING_AUTH_KEY)
        tid = self._next_tid()
        return bytes([0x4C, tid, 0x00, 0x02]) + encrypted

    def download_log_data(self, size: int) -> bytes:
        """Download and decrypt raw offline log data with MemoryRead."""
        # Address 0x98100000 is the special marker for offline logs
        address = 0x98100000
        request = self._build_memory_read_request(address, size)

        print(f"Sending download request for {size} bytes...")
        self._send(request)

        # Read and validate the plaintext MemoryRead confirmation.
        response = self._recv()
        validate_memory_read_confirmation(response, request[1], address, size)
        print(f"Response confirmed address=0x{address:08X}, size={size}")

        # The following transfers are raw ciphertext. Their first bytes are
        # encrypted data, not packet types or headers.
        encrypted = self._recv_memory_data(size)
        print(f"Total received: {len(encrypted)} bytes")
        return decrypt_ecb(encrypted)[:size]

    def close(self):
        usb.util.release_interface(self.dev, INTERFACE_NUM)
        try:
            self.dev.reset()
        except usb.core.USBError:
            pass
        usb.util.dispose_resources(self.dev)


def parse_samples(data: bytes) -> list[AdcSample]:
    """Parse decrypted data into ADC samples."""
    samples = []
    for i in range(len(data) // 16):
        sample_data = data[i * 16 : (i + 1) * 16]
        v, i_val, q, e = struct.unpack("<iiii", sample_data)
        samples.append(
            AdcSample(
                voltage_uv=v, current_ua=i_val, charge_acc_uah=q, energy_acc_uwh=e
            )
        )
    return samples


def main():
    parser = argparse.ArgumentParser(
        description="Download offline logs from POWER-Z KM003C"
    )
    parser.add_argument("-o", "--output", help="Output CSV file")
    parser.add_argument("-r", "--raw", help="Output raw decrypted data to file")
    args = parser.parse_args()

    try:
        device = KM003C()
        device.initialize()

        # Get log metadata
        print("\nRequesting log metadata...")
        metadata = device.get_log_metadata()

        if metadata is None:
            print("No log found on device")
            device.close()
            return 1

        print("\n=== Log Information ===")
        print(f"Name: {metadata.name}")
        print(f"Samples: {metadata.sample_count}")
        print(f"Interval: {metadata.interval_ms}ms ({metadata.interval_ms / 1000}s)")
        duration = metadata.duration_seconds
        print(
            f"Duration: {int(duration // 3600)}:{int((duration % 3600) // 60):02d}:{int(duration % 60):02d}"
        )
        if metadata.recorded_duration_seconds != duration:
            print(
                "Warning: metadata duration differs from sample count: "
                f"{metadata.recorded_duration_seconds}s"
            )
        print(f"Data size: {metadata.data_size} bytes")

        # Download log data
        print("\n=== Downloading Log Data ===")
        data = device.download_log_data(metadata.data_size)

        # Parse samples
        samples = parse_samples(data)
        print(f"\nParsed {len(samples)} samples")

        # Show summary
        print("\n=== Data Summary ===")
        voltages = [s.voltage_v for s in samples]
        currents = [s.current_a for s in samples]
        print(f"Voltage: {min(voltages):.3f}V - {max(voltages):.3f}V")
        print(f"Current: {min(currents):.3f}A - {max(currents):.3f}A")
        print(f"Final charge: {samples[-1].charge_mah:.3f} mAh")
        print(f"Final energy: {samples[-1].energy_mwh:.3f} mWh")

        # Show first/last samples
        print("\n=== First 5 Samples ===")
        print(f"{'#':>4} {'Voltage':>10} {'Current':>10} {'Charge':>12} {'Energy':>12}")
        for i, s in enumerate(samples[:5]):
            print(
                f"{i:4} {s.voltage_v:10.3f}V {s.current_a:10.3f}A {s.charge_mah:10.3f}mAh {s.energy_mwh:10.3f}mWh"
            )

        print("\n=== Last 5 Samples ===")
        for i, s in enumerate(samples[-5:], start=len(samples) - 5):
            print(
                f"{i:4} {s.voltage_v:10.3f}V {s.current_a:10.3f}A {s.charge_mah:10.3f}mAh {s.energy_mwh:10.3f}mWh"
            )

        # Save to CSV if requested
        if args.output:
            with open(args.output, "w") as f:
                f.write("sample,voltage_v,current_a,charge_mah,energy_mwh\n")
                for i, s in enumerate(samples):
                    f.write(
                        f"{i},{s.voltage_v:.6f},{s.current_a:.6f},{s.charge_mah:.6f},{s.energy_mwh:.6f}\n"
                    )
            print(f"\nSaved to {args.output}")

        # Save raw data if requested
        if args.raw:
            with open(args.raw, "wb") as f:
                f.write(data)
            print(f"Raw data saved to {args.raw}")

        device.close()
        return 0

    except Exception as e:
        print(f"\nError: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(main())
