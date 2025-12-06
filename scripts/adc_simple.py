#!/usr/bin/env python3
"""
Simple ADC data reader for POWER-Z KM003C.

Demonstrates basic device communication using:
- pyusb for USB communication
- km003c_lib (Rust bindings) for protocol parsing

This is a minimal example showing how to request and parse single ADC samples.
For multi-sample streaming (AdcQueue), see test_adcqueue.py.

Usage:
    uv run scripts/adc_simple.py                  # Default: HID interface
    uv run scripts/adc_simple.py --interface hid  # HID interface (~3.8ms latency)
    uv run scripts/adc_simple.py --interface vendor  # Vendor interface (~0.6ms, 6x faster)
"""

import argparse
import usb.core
import usb.util
from km003c_lib import VID, PID, parse_packet, create_packet, CMD_GET_DATA, ATT_ADC
from km003c_helpers import get_adc_data


# USB Interface configurations
# Based on km003c-lib/src/device.rs documentation
INTERFACE_CONFIGS = {
    "vendor": {
        "interface": 0,
        "endpoint_out": 0x01,
        "endpoint_in": 0x81,
        "description": "Vendor (Bulk, ~0.6ms latency, fastest)",
    },
    "hid": {
        "interface": 3,
        "endpoint_out": 0x05,
        "endpoint_in": 0x85,
        "description": "HID (Interrupt, ~3.8ms latency, most compatible)",
    },
}


class KM003C:
    """Simple KM003C device interface using pyusb."""

    def __init__(self, interface: str = "hid"):
        if interface not in INTERFACE_CONFIGS:
            raise ValueError(f"Unknown interface: {interface}. Use 'vendor' or 'hid'")

        config = INTERFACE_CONFIGS[interface]
        self.interface_num = config["interface"]
        self.endpoint_out = config["endpoint_out"]
        self.endpoint_in = config["endpoint_in"]

        print(f"Using {config['description']}")

        # Find the device
        self.dev = usb.core.find(idVendor=VID, idProduct=PID)
        if self.dev is None:
            raise ValueError(f"POWER-Z KM003C not found (VID={VID:04x}, PID={PID:04x})")

        # Detach kernel driver from all interfaces
        for cfg in self.dev:
            for intf in cfg:
                if self.dev.is_kernel_driver_active(intf.bInterfaceNumber):
                    try:
                        self.dev.detach_kernel_driver(intf.bInterfaceNumber)
                    except usb.core.USBError as e:
                        raise RuntimeError(f"Could not detach kernel driver from interface {intf.bInterfaceNumber}: {e}")

        # Set configuration and claim interface
        self.dev.set_configuration()
        usb.util.claim_interface(self.dev, self.interface_num)

        self.transaction_id = 0
        print(f"Connected to POWER-Z KM003C")

    def _next_transaction_id(self):
        """Get next transaction ID (8-bit rollover)."""
        tid = self.transaction_id
        self.transaction_id = (self.transaction_id + 1) & 0xFF
        return tid

    def _create_getdata_packet(self, attribute_mask):
        """Create a GetData control packet using the Rust helper."""
        tid = self._next_transaction_id()
        return create_packet(CMD_GET_DATA, tid, attribute_mask)

    def _send(self, data):
        """Send data to the device via OUT endpoint."""
        self.dev.write(self.endpoint_out, data)

    def _receive(self, timeout=2000):
        """Receive data from the device via IN endpoint."""
        return self.dev.read(self.endpoint_in, 1024, timeout=timeout)

    def request_adc_data(self):
        """Request ADC data from the device."""
        # Create and send GetData packet requesting ADC attribute (single sample)
        packet = self._create_getdata_packet(ATT_ADC)
        self._send(packet)

        # Receive response
        response = self._receive()

        # Parse using the Rust library bindings
        parsed_packet = parse_packet(bytes(response))

        # Extract ADC data using helper function
        adc_data = get_adc_data(parsed_packet)
        if adc_data is None:
            raise ValueError("No ADC data in response")

        return adc_data

    def close(self):
        """Release the device interface."""
        usb.util.release_interface(self.dev, self.interface_num)
        try:
            self.dev.reset()
        except usb.core.USBError:
            pass
        usb.util.dispose_resources(self.dev)


def main():
    """Main function - read and display ADC data."""
    parser = argparse.ArgumentParser(
        description="Simple ADC data reader for POWER-Z KM003C"
    )
    parser.add_argument(
        "-i", "--interface",
        choices=["vendor", "hid"],
        default="hid",
        help="USB interface: 'vendor' (fast, ~0.6ms) or 'hid' (compatible, ~3.8ms)",
    )
    args = parser.parse_args()

    try:
        device = KM003C(interface=args.interface)

        print("\nRequesting ADC data...")
        adc_data = device.request_adc_data()

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

        device.close()

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
