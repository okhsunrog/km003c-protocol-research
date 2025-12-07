#!/usr/bin/env python3
"""
Read MCU identification registers from KM003C device (v2).

Uses Unknown68 (0x44) memory download command with proper response parsing.
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

AES_KEY_0 = b"Lh2yfB7n6X7d9a5Z"


def build_unknown68_request(address: int, size: int, tid: int = 0x02) -> bytes:
    """Build Unknown68 memory download request packet."""
    plaintext = bytearray(32)
    struct.pack_into('<I', plaintext, 0, address)
    struct.pack_into('<I', plaintext, 4, size)
    struct.pack_into('<I', plaintext, 8, 0xFFFFFFFF)
    crc = binascii.crc32(bytes(plaintext[0:12])) & 0xFFFFFFFF
    struct.pack_into('<I', plaintext, 12, crc)
    for i in range(16, 32):
        plaintext[i] = 0xFF

    cipher = AES.new(AES_KEY_0, AES.MODE_ECB)
    ciphertext = cipher.encrypt(bytes(plaintext))
    header = bytes([0x44, tid, 0x01, 0x01])
    return header + ciphertext


def main():
    dev = usb.core.find(idVendor=VID, idProduct=PID)
    if dev is None:
        print("Device not found!")
        return 1

    print("Resetting device...")
    dev.reset()
    time.sleep(1.5)

    dev = usb.core.find(idVendor=VID, idProduct=PID)
    for cfg in dev:
        for intf in cfg:
            if dev.is_kernel_driver_active(intf.bInterfaceNumber):
                dev.detach_kernel_driver(intf.bInterfaceNumber)

    dev.set_configuration()
    usb.util.claim_interface(dev, INTERFACE_NUM)

    cipher = AES.new(AES_KEY_0, AES.MODE_ECB)

    def send_raw(data, timeout=2000):
        try:
            dev.write(ENDPOINT_OUT, data, timeout=timeout)
            time.sleep(0.05)
            return dev.read(ENDPOINT_IN, 2048, timeout=timeout)
        except usb.core.USBTimeoutError:
            return None

    def read_memory(address, size, tid, description):
        """Read memory and parse response."""
        print(f"\n{description}")
        print(f"  Address: 0x{address:08X}, Size: 0x{size:02X}")

        packet = build_unknown68_request(address, size, tid)
        dev.write(ENDPOINT_OUT, packet, timeout=2000)
        time.sleep(0.05)

        all_data = bytearray()
        for _ in range(10):
            try:
                resp = dev.read(ENDPOINT_IN, 2048, timeout=500)
                if resp:
                    resp_bytes = bytes(resp)
                    resp_type = resp_bytes[0] & 0x7F
                    print(f"  Response type: 0x{resp_type:02X}, len={len(resp_bytes)}")
                    print(f"    Raw: {resp_bytes.hex()}")

                    # Try AES decryption if response is 16+ bytes
                    if len(resp_bytes) >= 20:
                        # Try decrypting from offset 4
                        try:
                            decrypted = cipher.decrypt(resp_bytes[4:20])
                            print(f"    Decrypted[4:20]: {decrypted.hex()}")
                        except:
                            pass

                    # Check for data response types (0x1A, 0x2C, 0x3A, 0x75)
                    if resp_type in [0x1A, 0x2C, 0x3A, 0x75]:
                        # These are memory data responses
                        data_start = 4  # Skip header
                        all_data.extend(resp_bytes[data_start:])
            except usb.core.USBTimeoutError:
                break
            time.sleep(0.02)

        if all_data:
            print(f"  Collected data: {all_data.hex()}")
            # Decode as words
            for i in range(0, min(len(all_data), 64), 4):
                if i + 4 <= len(all_data):
                    word = struct.unpack_from('<I', all_data, i)[0]
                    print(f"    +{i:02X}: 0x{word:08X}")
        return all_data

    # Connect
    print("\nConnecting...")
    resp = send_raw(bytes([0x02, 0x01, 0x00, 0x00]))
    if resp and (resp[0] & 0x7F) == 0x05:
        print("  Connected!")
    else:
        print("  Connect failed")
        return 1

    # Test known working addresses first
    test_addresses = [
        # Known working from original script
        (0x420, 0x40, "Device info block 1 (known working)"),
        (0x4420, 0x40, "Device info block 2 (known working)"),

        # MCU identification
        (0x40048024, 0x04, "SIM_SDID (Kinetis device ID)"),
        (0x4004804C, 0x04, "SIM_FCFG1 (Flash config)"),
        (0x40048054, 0x10, "SIM_UIDH/M/L (Unique ID)"),

        # ARM CPUID (might need different access)
        (0xE000ED00, 0x04, "ARM CPUID register"),
    ]

    tid = 2
    for address, size, description in test_addresses:
        read_memory(address, size, tid, description)
        tid += 1
        time.sleep(0.15)

    usb.util.release_interface(dev, INTERFACE_NUM)
    print("\nDone!")
    return 0


if __name__ == "__main__":
    exit(main())
