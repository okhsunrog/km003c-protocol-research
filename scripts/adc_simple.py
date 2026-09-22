#!/usr/bin/env python3
"""
Simple ADC data reader for POWER-Z KM003C.

Demonstrates basic device communication using:
- `km003c_analysis.device` for the shared pyusb transport
- `km003c` (Rust bindings) for protocol parsing

This is a minimal example showing how to request and parse single ADC samples.
For multi-sample streaming (AdcQueue), see run_adcqueue_single.py.

Usage:
    uv run --locked scripts/adc_simple.py                     # Default: HID interface
    uv run --locked scripts/adc_simple.py --interface hid     # HID interface (~3.8ms latency)
    uv run --locked scripts/adc_simple.py --interface vendor  # Vendor interface (~0.6ms, 6x faster)
"""

import argparse

import km003c

from km003c_analysis.device import INTERFACES, Km003cUsb
from km003c_analysis.helpers import get_adc_data

# GetData carries the attribute shifted left by one unused bit.
WIRE_ATT_ADC = km003c.ATT_ADC << 1


def request_adc_data(device: Km003cUsb) -> km003c.AdcData:
    """Request a single ADC sample and parse it with the Rust bindings."""
    response = device.command(km003c.CMD_GET_DATA, WIRE_ATT_ADC)
    if response is None:
        raise TimeoutError("No response to the ADC request")

    adc_data = get_adc_data(km003c.parse_packet(response))
    if adc_data is None:
        raise ValueError("No ADC data in response")
    return adc_data


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Simple ADC data reader for POWER-Z KM003C"
    )
    parser.add_argument(
        "-i",
        "--interface",
        choices=sorted(INTERFACES),
        default="hid",
        help="USB interface: 'vendor' (fast, ~0.6ms) or 'hid' (compatible, ~3.8ms)",
    )
    args = parser.parse_args()

    try:
        with Km003cUsb(args.interface, skip_reset=True) as device:
            print(f"Using {device.config.description}")
            print("\nRequesting ADC data...")
            adc_data = request_adc_data(device)

        print("\nADC Data:")
        print(f"  Voltage: {adc_data.vbus_v:.3f} V")
        print(f"  Current: {adc_data.ibus_a:.3f} A")
        print(f"  Power: {adc_data.power_w:.3f} W")
        print(f"  Temperature: {adc_data.temp_c:.1f} °C")

        print("\nUSB Data Lines:")
        print(f"  D+: {adc_data.vdp_v:.3f} V")
        print(f"  D-: {adc_data.vdm_v:.3f} V")

        print("\nUSB CC Lines:")
        print(f"  CC1: {adc_data.cc1_v:.3f} V")
        print(f"  CC2: {adc_data.cc2_v:.3f} V")

    except Exception as error:  # noqa: BLE001 - top-level CLI reporting
        print(f"Error: {error}")
        import traceback

        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
