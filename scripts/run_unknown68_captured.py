#!/usr/bin/env python3
"""
Test Unknown68 (0x44) using exact captured packets from Mtools.exe

These are the 4 packets Mtools sends during startup.
"""

import usb.core
import usb.util
import time
from km003c_lib import VID, PID

INTERFACE_NUM = 0
ENDPOINT_OUT = 0x01
ENDPOINT_IN = 0x81


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

    # Connect first
    print("\nConnecting...")
    resp = send_raw(bytes([0x02, 0x01, 0x00, 0x00]))
    if resp and (resp[0] & 0x7F) == 0x05:
        print("  Connected!")
    else:
        print(f"  Failed: {bytes(resp).hex() if resp else 'timeout'}")
        return 1

    # Exact Unknown68 packets captured from Mtools.exe
    # Note: last 16 bytes are the same in all 4: d18b539a39c407d5c063d91102e36a9e
    cmds68 = [
        ("4402010133f8860c0054288cdc7e52729826872dd18b539a39c407d5c063d91102e36a9e", "Packet 1"),
        ("44030101636beaf3f0856506eee9a27e89722dcfd18b539a39c407d5c063d91102e36a9e", "Packet 2"),
        ("44040101c51167ae613a6d46ec84a6bde8bd462ad18b539a39c407d5c063d91102e36a9e", "Packet 3"),
        ("440501019c409debc8df53b83b066c315250d05cd18b539a39c407d5c063d91102e36a9e", "Packet 4"),
    ]

    print("\nSending captured Unknown68 packets:")
    for cmd_hex, name in cmds68:
        print(f"\n  {name}:")
        print(f"    Sending: {cmd_hex}")

        resp = send_raw(bytes.fromhex(cmd_hex), timeout=1000)

        if resp:
            resp_bytes = bytes(resp)
            resp_type = resp_bytes[0] & 0x7F
            print(f"    Response type: 0x{resp_type:02X}, len={len(resp_bytes)}")
            print(f"    Response: {resp_bytes.hex()}")

            if resp_type == 0x44:
                # Parse Unknown68 response
                print(f"    -> Unknown68 response!")
                if len(resp_bytes) >= 36:
                    first_16 = resp_bytes[4:20].hex()
                    last_16 = resp_bytes[20:36].hex()
                    print(f"    First 16B:  {first_16}")
                    print(f"    Last 16B:   {last_16}")
            elif resp_type == 0x06:
                print(f"    -> REJECTED")
            elif resp_type == 0x05:
                print(f"    -> ACCEPTED")
        else:
            print(f"    -> TIMEOUT")

        time.sleep(0.1)

    # Also try Unknown76 for comparison
    print("\n\nTrying Unknown76 (for reference):")
    resp = send_raw(bytes.fromhex("4c0600025538815b69a452c83e54ef1d70f3bc9ae6aac1b12a6ac07c20fde58c7bf517ca"))
    if resp:
        resp_bytes = bytes(resp)
        print(f"  Response type: 0x{resp_bytes[0] & 0x7F:02X}")
        print(f"  Response: {resp_bytes.hex()}")
    else:
        print("  TIMEOUT")

    usb.util.release_interface(dev, INTERFACE_NUM)
    print("\nDone!")
    return 0


if __name__ == "__main__":
    exit(main())
