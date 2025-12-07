#!/usr/bin/env python3
"""
Capture USB PD negotiation by polling for PD events.

Usage:
1. Run this script
2. When prompted, disconnect and reconnect the USB-C load
3. The script will capture and decode the PD negotiation messages
"""

import usb.core
import usb.util
import time
import usbpdpy
from km003c import (
    VID, PID, parse_packet, create_packet,
    CMD_CONNECT, CMD_DISCONNECT, CMD_GET_DATA, ATT_PD_PACKET,
    PdStatus, PdEventStream
)


class PdDecoder:
    """Decode PD messages with state tracking for Request decoding."""

    def __init__(self):
        self.source_caps = None  # List of PowerDataObj from last Source_Capabilities

    def decode(self, wire: bytes) -> tuple[str, list[str]]:
        """Decode a PD message, returning (summary, detail_lines)."""
        if len(wire) < 2:
            return (f"Too short: {wire.hex()}", [])

        try:
            # Try parsing with state if we have source caps
            if self.source_caps:
                msg = usbpdpy.parse_pd_message_with_state(wire, self.source_caps)
            else:
                msg = usbpdpy.parse_pd_message(wire)

            msg_type = msg.header.message_type  # Already a string
            msg_id = msg.header.message_id
            role = f"{msg.header.port_power_role}/{msg.header.port_data_role}"

            summary = f"{msg_type:20s} (ID={msg_id}, {role})"
            details = []

            # Handle Source_Capabilities - save for later Request decoding
            if msg.is_source_capabilities():
                self.source_caps = list(msg.data_objects)  # list[PowerDataObj]
                for i, pdo in enumerate(msg.data_objects):
                    # PowerDataObj has nice repr: "PowerDataObj(FixedSupply: 5.0V @ 3.0A = 15.0W)"
                    details.append(f"PDO[{i+1}]: {pdo}")

            # Handle Request - decode with saved source caps
            elif msg_type == "Request" and msg.request_objects:
                for rdo in msg.request_objects:
                    obj_pos = rdo.object_position
                    # Look up the requested PDO
                    if self.source_caps and 1 <= obj_pos <= len(self.source_caps):
                        pdo = self.source_caps[obj_pos - 1]  # 1-based to 0-based
                        # Format based on RDO type
                        if rdo.operating_voltage_v is not None and rdo.operating_current_a is not None:
                            # PPS/AVS request
                            details.append(f"RDO: Requesting PDO#{obj_pos} ({pdo}) @ {rdo.operating_voltage_v:.2f}V/{rdo.operating_current_a:.2f}A")
                        elif rdo.operating_current_a is not None:
                            # Fixed/Variable supply request
                            details.append(f"RDO: Requesting PDO#{obj_pos} ({pdo}) @ {rdo.operating_current_a:.2f}A")
                        elif rdo.operating_power_w is not None:
                            details.append(f"RDO: Requesting PDO#{obj_pos} ({pdo}) @ {rdo.operating_power_w:.1f}W")
                        else:
                            details.append(f"RDO: Requesting PDO#{obj_pos} ({pdo})")
                    else:
                        details.append(f"RDO: Requesting PDO#{obj_pos} (raw=0x{rdo.raw:08X})")

                    if rdo.capability_mismatch:
                        details.append("      [CAPABILITY MISMATCH]")

            return (summary, details)

        except Exception as e:
            return (f"{wire.hex()} (error: {e})", [])


def main():
    print("=" * 60)
    print("USB PD Negotiation Capture")
    print("=" * 60)

    # Setup device
    dev = usb.core.find(idVendor=VID, idProduct=PID)
    if dev is None:
        print(f"Device not found (VID={VID:04x}, PID={PID:04x})")
        return

    for cfg in dev:
        for intf in cfg:
            if dev.is_kernel_driver_active(intf.bInterfaceNumber):
                dev.detach_kernel_driver(intf.bInterfaceNumber)
    dev.reset()
    time.sleep(0.5)

    dev = usb.core.find(idVendor=VID, idProduct=PID)
    for cfg in dev:
        for intf in cfg:
            if dev.is_kernel_driver_active(intf.bInterfaceNumber):
                dev.detach_kernel_driver(intf.bInterfaceNumber)
    dev.set_configuration()
    usb.util.claim_interface(dev, 0)

    # Drain
    while True:
        try:
            dev.read(0x81, 512, timeout=50)
        except usb.core.USBTimeoutError:
            break

    # Connect
    dev.write(0x01, create_packet(CMD_CONNECT, 1, 0), timeout=1000)
    time.sleep(0.1)
    dev.read(0x81, 512, timeout=1000)
    print("\nConnected to KM003C")

    print("\n" + "=" * 60)
    print("NOW: Disconnect and reconnect your USB-C load!")
    print("Capturing for 20 seconds...")
    print("=" * 60 + "\n")

    decoder = PdDecoder()
    tid = 2
    start_time = time.time()
    capture_duration = 20.0
    seen_events = set()  # Track seen events to avoid duplicates

    try:
        while time.time() - start_time < capture_duration:
            # Request PD events
            dev.write(0x01, create_packet(CMD_GET_DATA, tid, ATT_PD_PACKET), timeout=1000)
            tid = (tid + 1) & 0xFF

            time.sleep(0.03)  # ~30ms polling for PD events

            try:
                resp = bytes(dev.read(0x81, 512, timeout=200))
            except usb.core.USBTimeoutError:
                continue

            if len(resp) < 8:
                continue

            try:
                pkt = parse_packet(resp)
            except Exception:
                continue

            if "DataResponse" not in pkt:
                continue

            for payload in pkt["DataResponse"]["payloads"]:
                if isinstance(payload, PdEventStream):
                    for ev in payload.events:
                        data = ev.data

                        # Create unique key for this event
                        event_key = (ev.timestamp, str(data))
                        if event_key in seen_events:
                            continue
                        seen_events.add(event_key)

                        if isinstance(data, dict) and "sop" in data and "wire_data" in data:
                            sop = data["sop"]
                            wire = bytes(data["wire_data"])

                            # Connection events: sop=0x11 (Connect) or 0x12 (Disconnect)
                            if len(wire) == 0:
                                if sop == 0x11:
                                    print(f"[{ev.timestamp}ms] ** CONNECT **")
                                    decoder.source_caps = None  # Reset state on new connection
                                elif sop == 0x12:
                                    print(f"[{ev.timestamp}ms] ** DISCONNECT **")
                            elif len(wire) >= 2:
                                summary, details = decoder.decode(wire)
                                print(f"[{ev.timestamp}ms] SOP{sop}: {summary}")
                                for detail in details:
                                    print(f"             {detail}")

    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
    finally:
        # Disconnect
        dev.write(0x01, create_packet(CMD_DISCONNECT, tid, 0), timeout=1000)
        print("\n" + "=" * 60)
        print("Capture complete. Disconnected from KM003C.")
        print("=" * 60)


if __name__ == "__main__":
    main()
