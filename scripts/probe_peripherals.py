#!/usr/bin/env python3
"""
Probe peripheral address ranges to find readable areas.
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

    def send_raw(data, timeout=2000):
        try:
            dev.write(ENDPOINT_OUT, data, timeout=timeout)
            time.sleep(0.05)
            return dev.read(ENDPOINT_IN, 2048, timeout=timeout)
        except usb.core.USBTimeoutError:
            return None

    def probe_address(address, size, tid):
        """Probe an address and return result type."""
        packet = build_unknown68_request(address, size, tid)
        dev.write(ENDPOINT_OUT, packet, timeout=2000)
        time.sleep(0.03)

        data_bytes = bytearray()
        result_type = None

        for _ in range(5):
            try:
                resp = dev.read(ENDPOINT_IN, 2048, timeout=200)
                if resp:
                    resp_bytes = bytes(resp)
                    resp_type = resp_bytes[0] & 0x7F

                    if resp_type in [0x1A, 0x2C, 0x3A, 0x75]:
                        data_bytes.extend(resp_bytes[4:])
                        result_type = "DATA"
                    elif resp_type == 0x06:
                        result_type = "REJECT"
                    elif resp_type == 0x27:
                        result_type = "NOREAD"
                    elif resp_type == 0x44:
                        if result_type is None:
                            result_type = "CONFIRM"
            except usb.core.USBTimeoutError:
                break
            time.sleep(0.01)

        return result_type, data_bytes

    # Connect
    print("\nConnecting...")
    resp = send_raw(bytes([0x02, 0x01, 0x00, 0x00]))
    if resp and (resp[0] & 0x7F) == 0x05:
        print("Connected!\n")
    else:
        print("Connect failed")
        return 1

    # Addresses to probe - focusing on MCU identification areas
    probe_list = [
        # Peripheral ranges that might work
        (0x40010000, "Unknown 0x40010000"),
        (0x40010400, "Unknown 0x40010400"),
        (0x40010450, "Unknown 0x40010450 (known working)"),
        (0x40010800, "Unknown 0x40010800"),

        # USB controller area (might have ID)
        (0x40040000, "USB controller base"),
        (0x400401FC, "USB controller ID?"),

        # Try some potential device ID locations
        (0x0FFF0000, "Device ID area 1?"),
        (0x1FFF0000, "Device ID area 2?"),
        (0x1FFFF000, "Device ID area 3?"),

        # Kinetis-style SIM device ID
        (0x40048024, "SIM_SDID"),

        # Alternative peripheral ID registers
        (0x400FF000, "GPIO peripheral ID?"),
        (0x40000FF0, "Peripheral ID 0?"),
        (0x400FFFF0, "Peripheral ID 1?"),

        # Info flash areas
        (0x00000400, "Flash config 0x400"),
        (0x00000410, "Flash config 0x410"),
        (0x00000420, "Flash config 0x420 (known working)"),
        (0x00000430, "Flash config 0x430"),
        (0x00000440, "Flash config 0x440"),

        # Extended flash info
        (0x00004400, "Flash 0x4400"),
        (0x00004410, "Flash 0x4410"),
        (0x00004420, "Flash 0x4420 (known working)"),
        (0x00004430, "Flash 0x4430"),
    ]

    readable_addresses = []
    tid = 2

    print("Probing addresses...")
    print("-" * 70)

    for address, description in probe_list:
        result, data = probe_address(address, 0x10, tid)
        status = {
            "DATA": f"✓ DATA ({len(data)} bytes)",
            "REJECT": "✗ REJECTED",
            "NOREAD": "✗ NOT READABLE",
            "CONFIRM": "? CONFIRM ONLY",
            None: "? NO RESPONSE"
        }.get(result, f"? {result}")

        print(f"0x{address:08X}  {status:25s}  {description}")

        if result == "DATA" and data:
            print(f"             Data: {data[:32].hex()}")
            readable_addresses.append((address, description, data))

        tid += 1
        time.sleep(0.08)

    print("\n" + "="*70)
    print("READABLE ADDRESSES SUMMARY")
    print("="*70)
    for addr, desc, data in readable_addresses:
        print(f"\n0x{addr:08X}: {desc}")
        print(f"  Data ({len(data)} bytes): {data.hex()}")

        # Try to interpret as words
        for i in range(0, min(len(data), 32), 4):
            if i + 4 <= len(data):
                word = struct.unpack_from('<I', data, i)[0]
                print(f"    +{i:02X}: 0x{word:08X}")

    usb.util.release_interface(dev, INTERFACE_NUM)
    print("\nDone!")
    return 0


if __name__ == "__main__":
    exit(main())
