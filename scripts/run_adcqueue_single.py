#!/usr/bin/env python3
"""
Simple single-shot AdcQueue test - get one batch of streaming samples.

This test demonstrates the minimal initialization sequence required for AdcQueue
(streaming ADC) mode on the POWER-Z KM003C.

Key findings:
- AdcQueue requires Connect + StreamingAuth (unlike simple ADC)
- StreamingAuth must contain the HardwareID read from the connected device
- GetData PD/Settings and StopGraph cleanup are NOT required
- Attribute values must be shifted left by 1 for wire format
- Samples are 20 bytes each with sequence, marker, VBUS, IBUS, CC1, CC2, D+, D-
- AdcQueue only works on vendor interface (not HID)
"""

import binascii
import os
import struct
import time

import usb.core
import usb.util
from Crypto.Cipher import AES
from km003c import PID, VID

INTERFACE_NUM = 0  # Vendor/Bulk interface
ENDPOINT_OUT = 0x01
ENDPOINT_IN = 0x81
MEMORY_KEY = b"Lh2yfB7n6X7d9a5Z"
STREAMING_AUTH_KEY = b"Fa0b4tA25f4R038a"
HARDWARE_ID_ADDRESS = 0x40010450


def build_memory_read_request(address: int, size: int, tid: int) -> bytes:
    """Build an encrypted MemoryRead request."""
    payload = struct.pack("<III", address, size, 0xFFFFFFFF)
    checksum = binascii.crc32(payload) & 0xFFFFFFFF
    plaintext = payload + struct.pack("<I", checksum) + b"\xff" * 16
    encrypted = AES.new(MEMORY_KEY, AES.MODE_ECB).encrypt(plaintext)
    return bytes([0x44, tid, 0x01, 0x01]) + encrypted


def validate_memory_read_confirmation(
    response: bytes, tid: int, address: int, size: int
) -> None:
    """Validate the plaintext confirmation preceding raw memory ciphertext."""
    if len(response) != 20 or response[:4] != bytes([0xC4, tid, 0x01, 0x01]):
        raise ValueError(f"Invalid MemoryRead confirmation: {response.hex()}")
    echoed_address, echoed_size, magic, checksum = struct.unpack(
        "<IIII", response[4:20]
    )
    expected_crc = binascii.crc32(response[4:16]) & 0xFFFFFFFF
    if (echoed_address, echoed_size, magic, checksum) != (
        address,
        size,
        0xFFFFFFFF,
        expected_crc,
    ):
        raise ValueError("MemoryRead confirmation payload mismatch")


def build_streaming_auth_request(hardware_id: bytes, tid: int) -> bytes:
    """Build a fresh StreamingAuth request for this device."""
    if len(hardware_id) != 12:
        raise ValueError(f"HardwareID must be 12 bytes, got {len(hardware_id)}")
    timestamp_ms = time.time_ns() // 1_000_000
    plaintext = struct.pack("<Q", timestamp_ms) + hardware_id + os.urandom(12)
    encrypted = AES.new(STREAMING_AUTH_KEY, AES.MODE_ECB).encrypt(plaintext)
    return bytes([0x4C, tid, 0x00, 0x02]) + encrypted


def decrypt_hardware_id(ciphertext: bytes) -> bytes:
    """Decrypt the AES-aligned response to the 12-byte HardwareID read."""
    if len(ciphertext) != AES.block_size:
        raise ValueError(
            f"Expected 16 HardwareID ciphertext bytes, got {len(ciphertext)}"
        )
    return AES.new(MEMORY_KEY, AES.MODE_ECB).decrypt(ciphertext)[:12]


def main():
    # Find device
    dev = usb.core.find(idVendor=VID, idProduct=PID)
    if dev is None:
        print("Device not found!")
        return 1

    # Reset and wait (1.5s is critical for device to be ready)
    print("Resetting device...")
    dev.reset()
    time.sleep(1.5)

    # Reconnect after reset
    dev = usb.core.find(idVendor=VID, idProduct=PID)

    # Detach kernel drivers from all interfaces
    for cfg in dev:
        for intf in cfg:
            if dev.is_kernel_driver_active(intf.bInterfaceNumber):
                dev.detach_kernel_driver(intf.bInterfaceNumber)

    dev.set_configuration()
    usb.util.claim_interface(dev, INTERFACE_NUM)

    def send_raw(data, timeout=2000):
        """Send raw packet and read response, with timeout handling."""
        try:
            dev.write(ENDPOINT_OUT, data, timeout=timeout)
            time.sleep(0.05)
            return dev.read(ENDPOINT_IN, 2048, timeout=timeout)
        except usb.core.USBTimeoutError:
            return None

    # Initialization sequence required for AdcQueue streaming.
    print("\nInitialization sequence:")

    # Connect (tid=1)
    print("  Connect...", end=" ")
    resp = send_raw(bytes([0x02, 0x01, 0x00, 0x00]))
    if resp and (resp[0] & 0x7F) == 0x05:
        print("OK (Accepted)")
    else:
        print("FAILED")
        return 1

    # Read this device's HardwareID (tid=2). The data transfer after the
    # confirmation is raw AES ciphertext, not a framed protocol packet.
    print("  Read HardwareID...", end=" ")
    memory_request = build_memory_read_request(HARDWARE_ID_ADDRESS, 12, tid=2)
    dev.write(ENDPOINT_OUT, memory_request, timeout=2000)
    confirmation = bytes(dev.read(ENDPOINT_IN, 2048, timeout=2000))
    validate_memory_read_confirmation(
        confirmation, tid=2, address=HARDWARE_ID_ADDRESS, size=12
    )
    encrypted_hardware_id = bytes(dev.read(ENDPOINT_IN, 2048, timeout=2000))
    hardware_id = decrypt_hardware_id(encrypted_hardware_id)
    print("OK")

    # Authenticate using the connected device's HardwareID (tid=3).
    print("  StreamingAuth...", end=" ")
    resp = send_raw(build_streaming_auth_request(hardware_id, tid=3))
    if resp is None or bytes(resp)[:4] != bytes.fromhex("4c000302"):
        actual = "timeout" if resp is None else bytes(resp).hex()
        print(f"FAILED ({actual})")
        usb.util.release_interface(dev, INTERFACE_NUM)
        return 1
    print("OK")

    # # GetData PD status - NOT required for AdcQueue
    # print("  GetData PD status...", end=" ")
    # resp = send_raw(bytes([0x0C, 0x07, 0x40, 0x00]))
    # print(f"{len(resp)} bytes" if resp else "timeout")

    # # GetData Settings - NOT required for AdcQueue
    # print("  GetData Settings...", end=" ")
    # resp = send_raw(bytes([0x0C, 0x08, 0x10, 0x00]))
    # print(f"{len(resp)} bytes" if resp else "timeout")

    # # StopGraph to ensure clean state - NOT required for AdcQueue
    # print("  StopGraph cleanup...", end=" ")
    # resp = send_raw(bytes([0x0F, 0x09, 0x00, 0x00]), timeout=500)
    # print("OK" if resp else "timeout")
    # time.sleep(0.1)

    print("\nInit complete!")

    # StartGraph at 50 SPS (tid=4)
    # Rate encoding: RATE_50_SPS=2 -> wire=4 (shifted by 1)
    print("\nStarting graph mode (50 SPS)...", end=" ")
    resp = send_raw(bytes([0x0E, 0x04, 0x04, 0x00]))
    if resp and (resp[0] & 0x7F) == 0x05:
        print("ACCEPTED")
    else:
        print("REJECTED")
        usb.util.release_interface(dev, INTERFACE_NUM)
        return 1

    # Wait for samples to accumulate (at 50 SPS, 2 sec = ~100 samples)
    print("Waiting 2 seconds for buffer to fill...")
    time.sleep(2.0)

    # Request AdcQueue data (tid=5)
    # ATT_ADC_QUEUE=0x0002 -> wire=0x0004
    print("\nRequesting AdcQueue data...", end=" ")
    resp = send_raw(bytes([0x0C, 0x05, 0x04, 0x00]))

    if resp:
        data = bytes(resp)
        print(f"Got {len(data)} bytes")

        if len(data) > 8:
            # Parse header
            pkt_type = data[0] & 0x7F
            pkt_tid = data[1]
            print(f"  Packet type: 0x{pkt_type:02x}, TID: {pkt_tid}")

            if pkt_type == 0x41:  # PutData
                # Payload starts at byte 8, 20 bytes per sample
                payload = data[8:]
                num_samples = len(payload) // 20
                remainder = len(payload) % 20
                print(
                    f"  Payload: {len(payload)} bytes ({num_samples} samples, {remainder} remainder)"
                )

                if num_samples > 0:
                    print(
                        f"\n{'Seq':>6} {'VBUS (V)':>10} {'IBUS (A)':>10} {'Power (W)':>10}"
                    )
                    print("=" * 42)

                    for i in range(min(10, num_samples)):  # Show up to 10 samples
                        offset = i * 20
                        sample = payload[offset : offset + 20]

                        seq = int.from_bytes(sample[0:2], "little")
                        vbus_uv = int.from_bytes(sample[4:8], "little", signed=True)
                        ibus_ua = int.from_bytes(sample[8:12], "little", signed=True)

                        vbus_v = vbus_uv / 1e6
                        ibus_a = ibus_ua / 1e6
                        power_w = vbus_v * ibus_a

                        print(
                            f"{seq:>6} {vbus_v:>10.3f} {ibus_a:>10.3f} {power_w:>10.3f}"
                        )

                    if num_samples > 10:
                        print(f"... ({num_samples - 10} more samples)")
        else:
            print("  Empty response (no samples buffered)")
    else:
        print("TIMEOUT")

    # Stop Graph (tid=6)
    print("\nStopping graph mode...", end=" ")
    resp = send_raw(bytes([0x0F, 0x06, 0x00, 0x00]), timeout=500)
    print("OK" if resp else "timeout")

    # Cleanup
    usb.util.release_interface(dev, INTERFACE_NUM)
    print("\nDone!")
    return 0


if __name__ == "__main__":
    exit(main())
