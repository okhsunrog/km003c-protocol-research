#!/usr/bin/env python3
"""
Read and decrypt device info blocks from KM003C device.
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
        print(f"\n{'='*60}")
        print(f"{description}")
        print(f"Address: 0x{address:08X}, Size: 0x{size:02X}")
        print("="*60)

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

                    # Data responses: 0x1A, 0x2C, 0x3A, 0x75
                    if resp_type in [0x1A, 0x2C, 0x3A, 0x75]:
                        data = resp_bytes[4:]  # Skip 4-byte header
                        all_data.extend(data)
                        print(f"Data packet (type 0x{resp_type:02X}): {len(data)} bytes")
                    elif resp_type == 0x44:
                        print(f"Confirmation (0x44)")
                    elif resp_type == 0x06:
                        print(f"REJECTED (0x06)")
                        return None
                    elif resp_type == 0x27:
                        print(f"Not readable (0x27)")
                        return None
            except usb.core.USBTimeoutError:
                break
            time.sleep(0.02)

        if all_data:
            print(f"\nRaw data ({len(all_data)} bytes):")
            print(f"  {all_data.hex()}")

            # Try decrypting with AES-ECB
            print(f"\nDecrypted (AES-ECB):")
            decrypted = bytearray()
            for i in range(0, len(all_data), 16):
                block = all_data[i:i+16]
                if len(block) == 16:
                    dec_block = cipher.decrypt(bytes(block))
                    decrypted.extend(dec_block)
                    print(f"  Block {i//16}: {dec_block.hex()}")
                    # Try to decode as ASCII
                    try:
                        ascii_str = dec_block.decode('ascii', errors='replace')
                        printable = ''.join(c if c.isprintable() else '.' for c in ascii_str)
                        print(f"         ASCII: {printable}")
                    except:
                        pass

            # Also show as raw ASCII
            print(f"\nRaw as ASCII:")
            try:
                ascii_str = all_data.decode('ascii', errors='replace')
                printable = ''.join(c if c.isprintable() else '.' for c in ascii_str)
                print(f"  {printable}")
            except:
                pass

        return all_data

    # Connect
    print("\nConnecting...")
    resp = send_raw(bytes([0x02, 0x01, 0x00, 0x00]))
    if resp and (resp[0] & 0x7F) == 0x05:
        print("  Connected!")
    else:
        print("  Connect failed")
        return 1

    # Read device info blocks
    test_addresses = [
        (0x420, 0x40, "Device info block 1"),
        (0x4420, 0x40, "Device info block 2"),
        (0x3000C00, 0x40, "Calibration/config data"),
        (0x40010450, 0x0C, "Unknown 12-byte block"),
        # Also try firmware version area
        (0x43C, 0x10, "Firmware version area?"),
        # Try reading from flash start
        (0x0, 0x40, "Flash start (vector table)"),
    ]

    tid = 2
    for address, size, description in test_addresses:
        read_memory(address, size, tid, description)
        tid += 1
        time.sleep(0.15)

    usb.util.release_interface(dev, INTERFACE_NUM)
    print("\n" + "="*60)
    print("Done!")
    return 0


if __name__ == "__main__":
    exit(main())
