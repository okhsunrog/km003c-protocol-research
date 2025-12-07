#!/usr/bin/env python3
"""
Read MCU identification registers from KM003C device.

Uses Unknown68 (0x44) memory download command to read specific
peripheral registers that can help identify the MCU.
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

    def send_and_collect(data, timeout=2000):
        """Send request and collect all response packets."""
        responses = []
        try:
            dev.write(ENDPOINT_OUT, data, timeout=timeout)
            time.sleep(0.05)
            # Collect all responses
            for _ in range(10):
                try:
                    resp = dev.read(ENDPOINT_IN, 2048, timeout=300)
                    if resp:
                        responses.append(bytes(resp))
                except usb.core.USBTimeoutError:
                    break
                time.sleep(0.02)
        except usb.core.USBTimeoutError:
            pass
        return responses

    # Connect first
    print("\nConnecting...")
    resp = send_and_collect(bytes([0x02, 0x01, 0x00, 0x00]))
    if resp and (resp[0][0] & 0x7F) == 0x05:
        print("  Connected!")
    else:
        print(f"  Connect failed")
        return 1

    # MCU identification registers to read
    mcu_registers = [
        # ARM Cortex-M standard
        (0xE000ED00, 0x04, "ARM CPUID"),
        (0xE000ED04, 0x04, "ARM ICSR"),
        (0xE000EDF0, 0x04, "ARM DHCSR"),

        # System/SIM registers (potential Kinetis)
        (0x40048000, 0x10, "SIM base (0x40048000-0x4004800F)"),
        (0x40048010, 0x10, "SIM 0x40048010-0x4004801F"),
        (0x40048020, 0x10, "SIM 0x40048020-0x4004802F (SDID area)"),
        (0x40048030, 0x10, "SIM 0x40048030-0x4004803F"),
        (0x40048040, 0x10, "SIM 0x40048040-0x4004804F (FCFG)"),
        (0x40048050, 0x10, "SIM 0x40048050-0x4004805F (UID)"),
        (0x40048060, 0x10, "SIM 0x40048060-0x4004806F"),

        # Clock generator
        (0x40054000, 0x10, "Clock 0x40054000-0x4005400F"),
        (0x40054020, 0x10, "Clock 0x40054020-0x4005402F"),
        (0x40054100, 0x10, "Clock 0x40054100-0x4005410F (PLL)"),

        # USB controller ID
        (0x40040000, 0x10, "USB 0x40040000-0x4004000F"),

        # Watchdog
        (0x40049000, 0x10, "WDOG 0x40049000-0x4004900F"),

        # I2C
        (0x4004e800, 0x10, "I2C 0x4004e800-0x4004e80F"),

        # DMA
        (0x40053000, 0x10, "DMA 0x40053000-0x4005300F"),

        # External memory / LCD controller
        (0x9c000000, 0x20, "External/LCD 0x9c000000-0x9c00001F"),

        # Flash config (if accessible)
        (0x00000400, 0x10, "Flash config area 0x400"),

        # Bootloader ROM area
        (0x1fff0000, 0x10, "ROM 0x1fff0000"),
        (0x1fff8000, 0x10, "ROM 0x1fff8000"),
    ]

    tid = 2
    results = {}

    print("\n" + "="*70)
    print("Reading MCU identification registers")
    print("="*70)

    for address, size, description in mcu_registers:
        print(f"\n{description}")
        print(f"  Address: 0x{address:08X}, Size: 0x{size:02X}")

        packet = build_unknown68_request(address, size, tid)
        responses = send_and_collect(packet, timeout=1000)

        if responses:
            for i, resp_bytes in enumerate(responses):
                resp_type = resp_bytes[0] & 0x7F

                if resp_type == 0x06:
                    print(f"  -> REJECTED (address may not be readable)")
                elif resp_type == 0x1A:  # Memory data response
                    print(f"  -> Data (type 0x1A, len={len(resp_bytes)})")
                    # Extract data after header
                    if len(resp_bytes) > 4:
                        data = resp_bytes[4:]
                        print(f"  Raw: {data[:min(32, len(data))].hex()}")
                        results[address] = data
                        # Try to decode as 32-bit words
                        if len(data) >= 4:
                            words = []
                            for j in range(0, min(len(data), size), 4):
                                if j + 4 <= len(data):
                                    word = struct.unpack_from('<I', data, j)[0]
                                    words.append(f"0x{word:08X}")
                            print(f"  Words: {' '.join(words)}")
                elif resp_type == 0x40:  # Head response
                    print(f"  -> Head (multi-part, len={len(resp_bytes)})")
                    if len(resp_bytes) > 4:
                        data = resp_bytes[4:]
                        print(f"  Raw: {data[:min(32, len(data))].hex()}")
                        results[address] = data
                else:
                    print(f"  -> Response type 0x{resp_type:02X}: {resp_bytes[:32].hex()}")
        else:
            print("  -> TIMEOUT")

        tid += 1
        time.sleep(0.1)

    # Analysis
    print("\n" + "="*70)
    print("MCU IDENTIFICATION ANALYSIS")
    print("="*70)

    # Check ARM CPUID
    if 0xE000ED00 in results and len(results[0xE000ED00]) >= 4:
        cpuid = struct.unpack('<I', results[0xE000ED00][:4])[0]
        implementer = (cpuid >> 24) & 0xFF
        variant = (cpuid >> 20) & 0xF
        architecture = (cpuid >> 16) & 0xF
        partno = (cpuid >> 4) & 0xFFF
        revision = cpuid & 0xF

        print(f"\nARM CPUID: 0x{cpuid:08X}")
        print(f"  Implementer: 0x{implementer:02X} ({'ARM' if implementer == 0x41 else 'Unknown'})")
        print(f"  Variant: {variant}")
        print(f"  Architecture: 0x{architecture:X} ({'ARMv7-M' if architecture == 0xF else 'ARMv6-M' if architecture == 0xC else 'Unknown'})")
        print(f"  Part number: 0x{partno:03X}", end="")
        if partno == 0xC23:
            print(" (Cortex-M3)")
        elif partno == 0xC24:
            print(" (Cortex-M4)")
        elif partno == 0xC20:
            print(" (Cortex-M0)")
        elif partno == 0xC60:
            print(" (Cortex-M0+)")
        else:
            print(" (Unknown)")
        print(f"  Revision: {revision}")

    # Check SIM SDID (Kinetis)
    if 0x40048024 in results or 0x40048020 in results:
        data = results.get(0x40048024) or results.get(0x40048020)
        if data and len(data) >= 4:
            sdid = struct.unpack('<I', data[:4])[0]
            print(f"\nSIM SDID: 0x{sdid:08X}")
            # Decode Kinetis SDID fields
            pinid = sdid & 0xF
            famid = (sdid >> 4) & 0x7
            dieid = (sdid >> 7) & 0x1F
            revid = (sdid >> 12) & 0xF
            seriesid = (sdid >> 20) & 0xF
            subfamid = (sdid >> 24) & 0xF
            familyid = (sdid >> 28) & 0xF
            print(f"  Family ID: {familyid}, SubFamily: {subfamid}, Series: {seriesid}")
            print(f"  Die ID: {dieid}, Revision: {revid}")

    # Cleanup
    usb.util.release_interface(dev, INTERFACE_NUM)
    print(f"\n{'='*70}")
    print("Done!")
    return 0


if __name__ == "__main__":
    exit(main())
