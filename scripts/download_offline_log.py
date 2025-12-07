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
import struct
import time
import usb.core
import usb.util
from Crypto.Cipher import AES
from dataclasses import dataclass
from km003c_lib import VID, PID

# USB endpoints (vendor interface)
INTERFACE_NUM = 0
ENDPOINT_OUT = 0x01
ENDPOINT_IN = 0x81

# AES key for Unknown68 and data chunks
AES_KEY = b"Lh2yfB7n6X7d9a5Z"

# Initialization packets (from captured traffic)
INIT_UNKNOWN68_PACKETS = [
    bytes.fromhex("4402010133f8860c0054288cdc7e52729826872dd18b539a39c407d5c063d91102e36a9e"),
    bytes.fromhex("44030101636beaf3f0856506eee9a27e89722dcfd18b539a39c407d5c063d91102e36a9e"),
    bytes.fromhex("44040101c51167ae613a6d46ec84a6bde8bd462ad18b539a39c407d5c063d91102e36a9e"),
    bytes.fromhex("440501019c409debc8df53b83b066c315250d05cd18b539a39c407d5c063d91102e36a9e"),
]

INIT_UNKNOWN76_PACKET = bytes.fromhex(
    "4c0600025538815b69a452c83e54ef1d70f3bc9ae6aac1b12a6ac07c20fde58c7bf517ca"
)


@dataclass
class LogMetadata:
    """Offline log metadata from attribute 0x0200."""
    name: str
    sample_count: int
    interval_ms: int
    flags: int
    estimated_size: int

    @property
    def duration_seconds(self) -> float:
        return self.sample_count * self.interval_ms / 1000

    @property
    def data_size(self) -> int:
        """Actual data size (16 bytes per sample)."""
        return self.sample_count * 16


@dataclass
class AdcSample:
    """Single ADC sample from offline log."""
    voltage_uv: int      # Microvolts
    current_ua: int      # Microamps (negative = discharge)
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


def decrypt_ecb(data: bytes) -> bytes:
    """Decrypt data using AES-128 ECB."""
    cipher = AES.new(AES_KEY, AES.MODE_ECB)
    return cipher.decrypt(data)


def encrypt_ecb(data: bytes) -> bytes:
    """Encrypt data using AES-128 ECB."""
    cipher = AES.new(AES_KEY, AES.MODE_ECB)
    return cipher.encrypt(data)


def crc32(data: bytes) -> int:
    """Calculate CRC32 checksum."""
    import binascii
    return binascii.crc32(data) & 0xFFFFFFFF


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

    def _send_cmd(self, cmd_type: int, data_word: int) -> bytes | None:
        """Send 4-byte command and return response."""
        tid = self._next_tid()
        packet = bytes([cmd_type & 0x7F, tid, data_word & 0xFF, (data_word >> 8) & 0xFF])
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

        # Unknown68 commands (authentication/handshake)
        for pkt in INIT_UNKNOWN68_PACKETS:
            self._send(pkt)
            self._recv()
            time.sleep(0.05)

        # Unknown76
        self._send(INIT_UNKNOWN76_PACKET)
        self._recv()
        time.sleep(0.05)

        # GetData commands
        self._send_cmd(0x0C, 0x0020)  # PD
        time.sleep(0.05)
        self._send_cmd(0x0C, 0x0008)  # Settings
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
        name = name_bytes.split(b'\x00')[0].decode('ascii', errors='replace')

        sample_count = struct.unpack('<H', metadata[18:20])[0]
        interval_ms = struct.unpack('<H', metadata[20:22])[0]
        flags = struct.unpack('<H', metadata[22:24])[0]
        estimated_size = struct.unpack('<I', metadata[24:28])[0]

        return LogMetadata(
            name=name,
            sample_count=sample_count,
            interval_ms=interval_ms,
            flags=flags,
            estimated_size=estimated_size
        )

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

    def download_log_data(self, size: int) -> bytes:
        """Download log data using Unknown68 command."""
        # Address 0x98100000 is the special marker for offline logs
        request = self._build_download_request(0x98100000, size)

        print(f"Sending download request for {size} bytes...")
        self._send(request)

        # Read Unknown68 response (20 bytes)
        response = self._recv()
        if len(response) < 20:
            raise ValueError(f"Invalid Unknown68 response: {len(response)} bytes")

        # Response payload (16 bytes after 4-byte header)
        resp_payload = response[4:20]

        # Try parsing as plaintext first (check if values make sense)
        resp_addr, resp_size, resp_const, resp_crc = struct.unpack('<IIII', resp_payload)

        # If constant isn't 0xFFFFFFFF, try decrypting
        if resp_const != 0xFFFFFFFF:
            decrypted_resp = decrypt_ecb(resp_payload)
            resp_addr, resp_size, resp_const, resp_crc = struct.unpack('<IIII', decrypted_resp)

        print(f"Response: addr=0x{resp_addr:08X}, size={resp_size}, crc=0x{resp_crc:08X}")

        # Read data chunks
        all_data = b''
        chunk_types = [0x34, 0x4E, 0x76, 0x68]  # Sequential chunk types

        while len(all_data) < size:
            chunk = self._recv(timeout=5000)
            chunk_type = chunk[0] & 0x7F

            if chunk_type in chunk_types:
                all_data += chunk
                print(f"  Chunk type=0x{chunk_type:02X}, size={len(chunk)}, total={len(all_data)}")
            else:
                print(f"  Unexpected packet type=0x{chunk_type:02X}, size={len(chunk)}")
                break

        print(f"Total received: {len(all_data)} bytes")

        # Decrypt all data
        if len(all_data) % 16 != 0:
            padding = 16 - (len(all_data) % 16)
            all_data += b'\x00' * padding

        decrypted = decrypt_ecb(all_data)
        return decrypted[:size]

    def close(self):
        usb.util.release_interface(self.dev, INTERFACE_NUM)
        try:
            self.dev.reset()
        except:
            pass
        usb.util.dispose_resources(self.dev)


def parse_samples(data: bytes) -> list[AdcSample]:
    """Parse decrypted data into ADC samples."""
    samples = []
    for i in range(len(data) // 16):
        sample_data = data[i*16:(i+1)*16]
        v, i_val, q, e = struct.unpack('<iiii', sample_data)
        samples.append(AdcSample(
            voltage_uv=v,
            current_ua=i_val,
            charge_acc_uah=q,
            energy_acc_uwh=e
        ))
    return samples


def main():
    parser = argparse.ArgumentParser(description="Download offline logs from POWER-Z KM003C")
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

        print(f"\n=== Log Information ===")
        print(f"Name: {metadata.name}")
        print(f"Samples: {metadata.sample_count}")
        print(f"Interval: {metadata.interval_ms}ms ({metadata.interval_ms/1000}s)")
        duration = metadata.duration_seconds
        print(f"Duration: {int(duration//3600)}:{int((duration%3600)//60):02d}:{int(duration%60):02d}")
        print(f"Data size: {metadata.data_size} bytes")

        # Download log data
        print("\n=== Downloading Log Data ===")
        data = device.download_log_data(metadata.data_size)

        # Parse samples
        samples = parse_samples(data)
        print(f"\nParsed {len(samples)} samples")

        # Show summary
        print(f"\n=== Data Summary ===")
        voltages = [s.voltage_v for s in samples]
        currents = [s.current_a for s in samples]
        print(f"Voltage: {min(voltages):.3f}V - {max(voltages):.3f}V")
        print(f"Current: {min(currents):.3f}A - {max(currents):.3f}A")
        print(f"Final charge: {samples[-1].charge_mah:.3f} mAh")
        print(f"Final energy: {samples[-1].energy_mwh:.3f} mWh")

        # Show first/last samples
        print(f"\n=== First 5 Samples ===")
        print(f"{'#':>4} {'Voltage':>10} {'Current':>10} {'Charge':>12} {'Energy':>12}")
        for i, s in enumerate(samples[:5]):
            print(f"{i:4} {s.voltage_v:10.3f}V {s.current_a:10.3f}A {s.charge_mah:10.3f}mAh {s.energy_mwh:10.3f}mWh")

        print(f"\n=== Last 5 Samples ===")
        for i, s in enumerate(samples[-5:], start=len(samples)-5):
            print(f"{i:4} {s.voltage_v:10.3f}V {s.current_a:10.3f}A {s.charge_mah:10.3f}mAh {s.energy_mwh:10.3f}mWh")

        # Save to CSV if requested
        if args.output:
            with open(args.output, 'w') as f:
                f.write("sample,voltage_v,current_a,charge_mah,energy_mwh\n")
                for i, s in enumerate(samples):
                    f.write(f"{i},{s.voltage_v:.6f},{s.current_a:.6f},{s.charge_mah:.6f},{s.energy_mwh:.6f}\n")
            print(f"\nSaved to {args.output}")

        # Save raw data if requested
        if args.raw:
            with open(args.raw, 'wb') as f:
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
