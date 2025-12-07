#!/usr/bin/env python3
"""
Test Unknown68 (0x44) - Memory Download Command

This script tests reading device memory using the Unknown68 command.
Based on Ghidra analysis of Mtools.exe.

Packet structure:
  Header: 44 TID 01 01 (type=0x44, attr=0x0101)
  Payload: 32 bytes AES-128 ECB encrypted:
    - Address (4 bytes, little-endian)
    - Size (4 bytes, little-endian)
    - CRC32 (4 bytes)
    - Padding (20 bytes, 0xFF)

AES Key (index 0): Lh2yfB7n6X7d9a5Z
"""

import usb.core
import usb.util
import time
import struct
from Crypto.Cipher import AES
from km003c_lib import VID, PID

INTERFACE_NUM = 0
ENDPOINT_OUT = 0x01
ENDPOINT_IN = 0x81

# AES key for Unknown68 (crypto key index 0)
AES_KEY_0 = b"Lh2yfB7n6X7d9a5Z"

# CRC32 table at 0x140183b10 - standard CRC32 polynomial
def crc32(data: bytes) -> int:
    """Calculate CRC32 matching Mtools implementation."""
    import binascii
    # The Mtools code does inverted CRC32
    return binascii.crc32(data) ^ 0xFFFFFFFF


def build_unknown68_request(address: int, size: int, tid: int = 0x02) -> bytes:
    """Build Unknown68 memory download request packet."""
    # Build plaintext payload
    plaintext = bytearray(32)

    # Address (bytes 0-3)
    struct.pack_into('<I', plaintext, 0, address)

    # Size (bytes 4-7)
    struct.pack_into('<I', plaintext, 4, size)

    # CRC32 of address+size (bytes 8-11)
    crc_data = struct.pack('<II', address, size)
    crc = crc32(crc_data)
    struct.pack_into('<I', plaintext, 8, crc)

    # Padding with 0xFF (bytes 12-31)
    for i in range(12, 32):
        plaintext[i] = 0xFF

    print(f"  Plaintext: {plaintext.hex()}")

    # AES encrypt
    cipher = AES.new(AES_KEY_0, AES.MODE_ECB)
    ciphertext = cipher.encrypt(bytes(plaintext))

    # Build header: type=0x44, tid, attr=0x0101 (little-endian: 01 01)
    header = bytes([0x44, tid, 0x01, 0x01])

    return header + ciphertext


def main():
    # Find device
    dev = usb.core.find(idVendor=VID, idProduct=PID)
    if dev is None:
        print("Device not found!")
        return 1

    print("Resetting device...")
    dev.reset()
    time.sleep(1.5)

    dev = usb.core.find(idVendor=VID, idProduct=PID)

    # Detach kernel drivers
    for cfg in dev:
        for intf in cfg:
            if dev.is_kernel_driver_active(intf.bInterfaceNumber):
                dev.detach_kernel_driver(intf.bInterfaceNumber)

    dev.set_configuration()
    usb.util.claim_interface(dev, INTERFACE_NUM)

    def send_raw(data, timeout=2000):
        try:
            dev.write(ENDPOINT_OUT, data, timeout=timeout)
            time.sleep(0.05)
            return dev.read(ENDPOINT_IN, 2048, timeout=timeout)
        except usb.core.USBTimeoutError:
            return None

    # Connect first (required for most operations)
    print("\nConnecting...")
    resp = send_raw(bytes([0x02, 0x01, 0x00, 0x00]))
    if resp and (resp[0] & 0x7F) == 0x05:
        print("  Connected!")
    else:
        print(f"  Connect failed: {bytes(resp).hex() if resp else 'timeout'}")
        return 1

    # Test memory addresses from Mtools.exe analysis
    test_addresses = [
        (0x420, 0x40, "Device info block 1"),
        (0x4420, 0x40, "Device info block 2"),
        (0x3000c00, 0x40, "Calibration/config data"),
        (0x40010450, 0x0C, "Unknown 12-byte block"),
        (0x0, 0x40, "Address 0 (test)"),
        (0x100, 0x40, "Address 0x100 (test)"),
    ]

    tid = 2
    for address, size, description in test_addresses:
        print(f"\n--- Reading {description} ---")
        print(f"  Address: 0x{address:08X}, Size: 0x{size:02X}")

        packet = build_unknown68_request(address, size, tid)
        print(f"  Request: {packet.hex()}")

        resp = send_raw(packet, timeout=1000)

        if resp:
            resp_bytes = bytes(resp)
            resp_type = resp_bytes[0] & 0x7F
            print(f"  Response type: 0x{resp_type:02X}, Length: {len(resp_bytes)}")
            print(f"  Response hex: {resp_bytes[:64].hex()}")

            if resp_type == 0x06:
                print("  -> REJECTED")
            elif resp_type == 0x44:
                print("  -> Unknown68 response (may have data)")
                # Check if encrypted (bit 16 of header)
                if len(resp_bytes) > 4:
                    encrypted = (resp_bytes[2] & 0x01) != 0
                    print(f"  -> Encrypted: {encrypted}")
            else:
                print(f"  -> Unexpected response type")

            # Try reading follow-up data
            for i in range(3):
                time.sleep(0.05)
                try:
                    more = dev.read(ENDPOINT_IN, 2048, timeout=200)
                    if more:
                        print(f"  Follow-up {i+1}: {bytes(more).hex()}")
                except usb.core.USBTimeoutError:
                    break
        else:
            print("  -> TIMEOUT")

        tid += 1
        time.sleep(0.1)

    # Cleanup
    usb.util.release_interface(dev, INTERFACE_NUM)
    print("\nDone!")
    return 0


if __name__ == "__main__":
    exit(main())
