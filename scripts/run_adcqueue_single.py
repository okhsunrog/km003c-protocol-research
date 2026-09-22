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

The MemoryRead and StreamingAuth framing lives in `km003c_analysis.device`, and
the response is decoded by the Rust bindings rather than by hand.
"""

import time

import km003c

from km003c_analysis.device import Km003cUsb
from km003c_analysis.helpers import get_adcqueue_raw_data

# StartGraph and GetData carry the attribute shifted left by one unused bit.
WIRE_ATT_ADC_QUEUE = km003c.ATT_ADC_QUEUE << 1
WIRE_RATE_50_SPS = km003c.RATE_50_SPS << 1

BUFFER_FILL_SECONDS = 2.0


def main() -> int:
    with Km003cUsb("vendor") as device:
        print("\nInitialization sequence:")

        print("  Connect...", end=" ")
        response = device.connect()
        if not response or (response[0] & 0x7F) != km003c.CMD_ACCEPT:
            print("FAILED")
            return 1
        print("OK (Accepted)")

        print("  Read HardwareID...", end=" ")
        hardware_id = device.hardware_id()
        print("OK")

        print("  StreamingAuth...", end=" ")
        response = device.streaming_auth(hardware_id)
        if response is None or bytes(response)[:4] != bytes.fromhex("4c000302"):
            print(
                f"FAILED ({'timeout' if response is None else bytes(response).hex()})"
            )
            return 1
        print("OK")

        print("\nInit complete!")

        print("\nStarting graph mode (50 SPS)...", end=" ")
        response = device.command(km003c.CMD_START_GRAPH, WIRE_RATE_50_SPS)
        if not response or (response[0] & 0x7F) != km003c.CMD_ACCEPT:
            print("REJECTED")
            return 1
        print("ACCEPTED")

        print(f"Waiting {BUFFER_FILL_SECONDS} seconds for buffer to fill...")
        time.sleep(BUFFER_FILL_SECONDS)

        print("\nRequesting AdcQueue data...", end=" ")
        response = device.command(km003c.CMD_GET_DATA, WIRE_ATT_ADC_QUEUE)
        if response is None:
            print("TIMEOUT")
        else:
            print(f"Got {len(response)} bytes")
            report_samples(bytes(response))

        print("\nStopping graph mode...", end=" ")
        stopped = device.command(km003c.CMD_STOP_GRAPH, 0, timeout_ms=500)
        print("OK" if stopped else "timeout")

    print("\nDone!")
    return 0


def report_samples(response: bytes) -> None:
    """Decode and print an AdcQueue response with the library parser."""
    packet = km003c.parse_packet(response)
    queue = get_adcqueue_raw_data(packet)
    if queue is None or not queue.samples:
        print("  Empty response (no samples buffered)")
        return

    print(f"  {len(queue.samples)} samples")
    print(f"\n{'Seq':>6} {'VBUS (V)':>10} {'IBUS (A)':>10} {'Power (W)':>10}")
    print("=" * 42)
    for sample in queue.samples[:10]:
        vbus_v = sample.vbus_uv / 1e6
        ibus_a = sample.ibus_ua / 1e6
        print(
            f"{sample.sequence:>6} {vbus_v:>10.3f} {ibus_a:>10.3f} {vbus_v * ibus_a:>10.3f}"
        )

    if len(queue.samples) > 10:
        print(f"... ({len(queue.samples) - 10} more samples)")


if __name__ == "__main__":
    raise SystemExit(main())
