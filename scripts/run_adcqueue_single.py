#!/usr/bin/env python3
"""
Simple single-shot AdcQueue test - get one batch of streaming samples.

This test demonstrates the minimal initialization sequence required for AdcQueue
(streaming ADC) mode on the POWER-Z KM003C.

Key findings:
- AdcQueue requires Connect + Unknown76 (unlike simple ADC which needs neither)
- Unknown68 commands are NOT required
- GetData PD/Settings and StopGraph cleanup are NOT required
- Attribute values must be shifted left by 1 for wire format
- Samples are 20 bytes each with sequence, marker, VBUS, IBUS, CC1, CC2, D+, D-
- AdcQueue only works on vendor interface (not HID)
"""

import usb.core
import usb.util
import time
from km003c_lib import VID, PID

INTERFACE_NUM = 0  # Vendor/Bulk interface
ENDPOINT_OUT = 0x01
ENDPOINT_IN = 0x81


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

    # Full initialization sequence (required for AdcQueue streaming)
    print("\nInitialization sequence:")

    # Connect (tid=1)
    print("  Connect...", end=" ")
    resp = send_raw(bytes([0x02, 0x01, 0x00, 0x00]))
    if resp and (resp[0] & 0x7F) == 0x05:
        print("OK (Accepted)")
    else:
        print("FAILED")
        return 1

    # # Unknown68 commands - NOT required for AdcQueue
    # print("  Unknown68 init...", end=" ")
    # cmds68 = [
    #     "4402010133f8860c0054288cdc7e52729826872dd18b539a39c407d5c063d91102e36a9e",
    #     "44030101636beaf3f0856506eee9a27e89722dcfd18b539a39c407d5c063d91102e36a9e",
    #     "44040101c51167ae613a6d46ec84a6bde8bd462ad18b539a39c407d5c063d91102e36a9e",
    #     "440501019c409debc8df53b83b066c315250d05cd18b539a39c407d5c063d91102e36a9e",
    # ]
    # ok_count = 0
    # for cmd_hex in cmds68:
    #     resp = send_raw(bytes.fromhex(cmd_hex), timeout=500)
    #     if resp:
    #         ok_count += 1
    # print(f"{ok_count}/4 OK")

    # Unknown76 (tid=2) - REQUIRED
    print("  Unknown76...", end=" ")
    resp = send_raw(bytes.fromhex("4c0200025538815b69a452c83e54ef1d70f3bc9ae6aac1b12a6ac07c20fde58c7bf517ca"))
    print("OK" if resp else "timeout")

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

    # StartGraph at 50 SPS (tid=3)
    # Rate encoding: RATE_50_SPS=2 -> wire=4 (shifted by 1)
    print("\nStarting graph mode (50 SPS)...", end=" ")
    resp = send_raw(bytes([0x0E, 0x03, 0x04, 0x00]))
    if resp and (resp[0] & 0x7F) == 0x05:
        print("ACCEPTED")
    else:
        print("REJECTED")
        usb.util.release_interface(dev, INTERFACE_NUM)
        return 1

    # Wait for samples to accumulate (at 50 SPS, 2 sec = ~100 samples)
    print("Waiting 2 seconds for buffer to fill...")
    time.sleep(2.0)

    # Request AdcQueue data (tid=4)
    # ATT_ADC_QUEUE=0x0002 -> wire=0x0004
    print("\nRequesting AdcQueue data...", end=" ")
    resp = send_raw(bytes([0x0C, 0x04, 0x04, 0x00]))

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
                print(f"  Payload: {len(payload)} bytes ({num_samples} samples, {remainder} remainder)")

                if num_samples > 0:
                    print(f"\n{'Seq':>6} {'VBUS (V)':>10} {'IBUS (A)':>10} {'Power (W)':>10}")
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

                        print(f"{seq:>6} {vbus_v:>10.3f} {ibus_a:>10.3f} {power_w:>10.3f}")

                    if num_samples > 10:
                        print(f"... ({num_samples - 10} more samples)")
        else:
            print("  Empty response (no samples buffered)")
    else:
        print("TIMEOUT")

    # Stop Graph (tid=5)
    print("\nStopping graph mode...", end=" ")
    resp = send_raw(bytes([0x0F, 0x05, 0x00, 0x00]), timeout=500)
    print("OK" if resp else "timeout")

    # Cleanup
    usb.util.release_interface(dev, INTERFACE_NUM)
    print("\nDone!")
    return 0


if __name__ == "__main__":
    exit(main())
