#!/usr/bin/env python3
"""
Test Unknown68 (0x44) - Memory Download Command (WORKING VERSION)

This script successfully reads device memory using the Unknown68 command.
Based on complete reverse engineering of Mtools.exe.

Payload structure (32 bytes, before AES-128 ECB encryption):
  Bytes 0-3:   Address (little-endian uint32)
  Bytes 4-7:   Size (little-endian uint32)
  Bytes 8-11:  Padding (0xFFFFFFFF, included in CRC)
  Bytes 12-15: CRC32 of bytes 0-11
  Bytes 16-31: Padding (0xFFFFFFFF * 4)

AES Key (index 0): Lh2yfB7n6X7d9a5Z
"""

import usb.core
import usb.util
import time
import struct
import binascii
from Crypto.Cipher import AES
from km003c_lib import VID, PID

INTERFACE_NUM = 0
ENDPOINT_OUT = 0x01
ENDPOINT_IN = 0x81

# AES key for Unknown68 (crypto key index 0)
AES_KEY_0 = b"Lh2yfB7n6X7d9a5Z"


def build_unknown68_request(address: int, size: int, tid: int = 0x02) -> bytes:
    """Build Unknown68 memory download request packet."""
    # Build plaintext payload (32 bytes)
    plaintext = bytearray(32)

    # Bytes 0-3: Address
    struct.pack_into('<I', plaintext, 0, address)

    # Bytes 4-7: Size
    struct.pack_into('<I', plaintext, 4, size)

    # Bytes 8-11: Padding (0xFFFFFFFF)
    struct.pack_into('<I', plaintext, 8, 0xFFFFFFFF)

    # Bytes 12-15: CRC32 of bytes 0-11
    crc = binascii.crc32(bytes(plaintext[0:12])) & 0xFFFFFFFF
    struct.pack_into('<I', plaintext, 12, crc)

    # Bytes 16-31: Padding (0xFF)
    for i in range(16, 32):
        plaintext[i] = 0xFF

    # AES encrypt
    cipher = AES.new(AES_KEY_0, AES.MODE_ECB)
    ciphertext = cipher.encrypt(bytes(plaintext))

    # Build header: type=0x44, tid, attr=0x0101 (little-endian)
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

    # Connect first
    print("\nConnecting...")
    resp = send_raw(bytes([0x02, 0x01, 0x00, 0x00]))
    if resp and (resp[0] & 0x7F) == 0x05:
        print("  Connected!")
    else:
        print(f"  Connect failed: {bytes(resp).hex() if resp else 'timeout'}")
        return 1

    # Test memory addresses from Mtools.exe
    test_addresses = [
        (0x420, 0x40, "Device info block 1"),
        (0x4420, 0x40, "Device info block 2"),
        (0x3000C00, 0x40, "Calibration/config data"),
        (0x40010450, 0x0C, "Unknown 12-byte block"),
    ]

    tid = 2
    for address, size, description in test_addresses:
        print(f"\n{'='*60}")
        print(f"Reading {description}")
        print(f"  Address: 0x{address:08X}, Size: 0x{size:02X}")

        packet = build_unknown68_request(address, size, tid)
        print(f"  Request: {packet.hex()}")

        resp = send_raw(packet, timeout=1000)

        if resp:
            resp_bytes = bytes(resp)
            resp_type = resp_bytes[0] & 0x7F
            print(f"  Response type: 0x{resp_type:02X}, Length: {len(resp_bytes)}")

            if resp_type == 0x06:
                print("  -> REJECTED")
            elif resp_type == 0x44:
                print("  -> Unknown68 response (confirmation)")
                if len(resp_bytes) >= 36:
                    # Try to decrypt response
                    cipher = AES.new(AES_KEY_0, AES.MODE_ECB)
                    decrypted = cipher.decrypt(resp_bytes[4:36])
                    print(f"  Decrypted: {decrypted.hex()}")
            elif resp_type == 0x1A:
                print(f"  -> Unknown26 response (data transfer)")
                print(f"  Data: {resp_bytes.hex()}")
            elif resp_type == 0x40:
                print(f"  -> Head response (multi-part)")
                print(f"  Data: {resp_bytes.hex()}")
            else:
                print(f"  -> Response: {resp_bytes.hex()}")

            # Check for follow-up packets
            for i in range(5):
                time.sleep(0.05)
                try:
                    more = dev.read(ENDPOINT_IN, 2048, timeout=200)
                    if more:
                        more_bytes = bytes(more)
                        more_type = more_bytes[0] & 0x7F
                        print(f"  Follow-up {i+1} (type 0x{more_type:02X}): {more_bytes.hex()}")
                except usb.core.USBTimeoutError:
                    break
        else:
            print("  -> TIMEOUT")

        tid += 1
        time.sleep(0.1)

    # Cleanup
    usb.util.release_interface(dev, INTERFACE_NUM)
    print(f"\n{'='*60}")
    print("Done!")
    return 0


if __name__ == "__main__":
    exit(main())
