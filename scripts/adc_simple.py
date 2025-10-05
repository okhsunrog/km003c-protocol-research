#!/usr/bin/env python3
"""
Simple ADC data reader for POWER-Z KM003C.

Demonstrates basic device communication using:
- pyusb for USB communication
- km003c_lib (Rust bindings) for protocol parsing

This is a minimal example showing how to request and parse single ADC samples.
For multi-sample streaming (AdcQueue), see test_adcqueue.py.
"""

import usb.core
import usb.util
from km003c_lib import VID, PID, parse_packet, create_packet, CMD_GET_DATA, ATT_ADC, ATT_ADC_QUEUE
from km003c_helpers import get_adc_data


# USB Interface Selection
# Based on km003c-lib/src/device.rs documentation:
# - Interface 0: Bulk 0x01/0x81 (Vendor-specific, fastest ~0.6ms latency)
# - Interface 3: Interrupt 0x05/0x85 (HID, most compatible ~3.8ms latency)
# Using Interface 3 (HID) for compatibility (no kernel driver conflicts)
INTERFACE_NUM = 3
ENDPOINT_OUT = 0x05
ENDPOINT_IN = 0x85

# Packet header constants
PACKET_TYPE_GETDATA = CMD_GET_DATA
ATTRIBUTE_ADC = ATT_ADC
ATTRIBUTE_ADCQUEUE = ATT_ADC_QUEUE  # AdcQueue attribute - used in the example code


class KM003C:
    """Simple KM003C device interface using pyusb."""

    def __init__(self):
        # Find the device
        self.dev = usb.core.find(idVendor=VID, idProduct=PID)
        if self.dev is None:
            raise ValueError(f"POWER-Z KM003C not found (VID={VID:04x}, PID={PID:04x})")

        # Track which interfaces had kernel drivers, so we can reattach them
        self.detached_interfaces = []

        # Detach kernel driver from all interfaces (hid-generic binds to this device)
        for cfg in self.dev:
            for intf in cfg:
                if self.dev.is_kernel_driver_active(intf.bInterfaceNumber):
                    try:
                        print(f"Detaching kernel driver from interface {intf.bInterfaceNumber}")
                        self.dev.detach_kernel_driver(intf.bInterfaceNumber)
                        self.detached_interfaces.append(intf.bInterfaceNumber)
                    except usb.core.USBError as e:
                        raise RuntimeError(f"Could not detach kernel driver from interface {intf.bInterfaceNumber}: {e}")

        # Set configuration and claim interface (bulk endpoints)
        self.dev.set_configuration()
        usb.util.claim_interface(self.dev, INTERFACE_NUM)

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
        """Send data to the device via bulk OUT endpoint."""
        self.dev.write(ENDPOINT_OUT, data)

    def _receive(self, timeout=2000):
        """Receive data from the device via bulk IN endpoint."""
        return self.dev.read(ENDPOINT_IN, 1024, timeout=timeout)

    def request_adc_data(self):
        """Request ADC data from the device."""
        # Create and send GetData packet requesting AdcQueue attribute
        # Note: Using AdcQueue (0x0002) on interface 1 works, while ADC (0x0001)
        # on interface 0 doesn't respond. This matches the example code.
        packet = self._create_getdata_packet(ATTRIBUTE_ADCQUEUE)
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
        """Release the device interface and reattach kernel drivers."""
        # Release the interface
        usb.util.release_interface(self.dev, INTERFACE_NUM)

        # Reset the device to clean state (like the example code does)
        try:
            self.dev.reset()
        except usb.core.USBError:
            pass  # Ignore errors during reset

        # Dispose of resources
        usb.util.dispose_resources(self.dev)


def main():
    """Main function - read and display ADC data."""
    try:
        # Connect to device
        device = KM003C()

        # Request ADC data
        print("\nRequesting ADC data...")
        adc_data = device.request_adc_data()

        # Display the ADC data
        print("\nADC Data:")
        print(f"  Voltage: {adc_data.vbus_v:.3f} V")
        print(f"  Current: {adc_data.ibus_a:.3f} A")
        print(f"  Power: {adc_data.power_w:.3f} W")
        print(f"  Temperature: {adc_data.temp_c:.1f} °C")

        # Display USB data lines
        print("\nUSB Data Lines:")
        print(f"  D+: {adc_data.vdp_v:.3f} V")
        print(f"  D-: {adc_data.vdm_v:.3f} V")

        # Display USB CC lines
        print("\nUSB CC Lines:")
        print(f"  CC1: {adc_data.cc1_v:.3f} V")
        print(f"  CC2: {adc_data.cc2_v:.3f} V")

        # Cleanup
        device.close()

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
