#!/usr/bin/env python3
"""
Live PD packet capture and decoding using km003c_lib and usbpdpy.

Captures PD events from connected hardware and decodes the USB PD wire messages.
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

def get_packet_type(packet):
    """Extract packet type from dict-based Packet."""
    if isinstance(packet, dict) and len(packet) > 0:
        return list(packet.keys())[0]
    return None

def get_pd_status(packet):
    """Extract PD status from DataResponse packet."""
    if "DataResponse" not in packet:
        return None
    for payload in packet["DataResponse"]["payloads"]:
        if isinstance(payload, PdStatus):
            return payload
    return None

def get_pd_events(packet):
    """Extract PD events from DataResponse packet."""
    if "DataResponse" not in packet:
        return None
    for payload in packet["DataResponse"]["payloads"]:
        if isinstance(payload, PdEventStream):
            return payload
    return None


class KM003CDevice:
    """Simple device wrapper for PD capture."""

    def __init__(self):
        self.dev = usb.core.find(idVendor=VID, idProduct=PID)
        if self.dev is None:
            raise ValueError(f"Device not found (VID={VID:04x}, PID={PID:04x})")

        # Detach kernel driver
        for cfg in self.dev:
            for intf in cfg:
                if self.dev.is_kernel_driver_active(intf.bInterfaceNumber):
                    self.dev.detach_kernel_driver(intf.bInterfaceNumber)

        # Reset and reconfigure
        self.dev.reset()
        time.sleep(0.5)

        self.dev = usb.core.find(idVendor=VID, idProduct=PID)
        for cfg in self.dev:
            for intf in cfg:
                if self.dev.is_kernel_driver_active(intf.bInterfaceNumber):
                    self.dev.detach_kernel_driver(intf.bInterfaceNumber)

        self.dev.set_configuration()
        usb.util.claim_interface(self.dev, 0)

        self.ep_out = 0x01
        self.ep_in = 0x81
        self.tid = 0

    def _next_tid(self):
        self.tid = (self.tid + 1) & 0xFF
        return self.tid

    def send(self, data: bytes):
        self.dev.write(self.ep_out, data, timeout=1000)

    def recv(self, timeout_ms: int = 1000) -> bytes:
        try:
            return bytes(self.dev.read(self.ep_in, 512, timeout=timeout_ms))
        except usb.core.USBTimeoutError:
            return b""

    def connect(self) -> bool:
        """Send connect command."""
        tid = self._next_tid()
        self.send(create_packet(CMD_CONNECT, tid, 0))
        time.sleep(0.1)
        resp = self.recv()
        return len(resp) >= 1 and (resp[0] & 0x7F) == 0x05

    def disconnect(self):
        """Send disconnect command."""
        tid = self._next_tid()
        self.send(create_packet(CMD_DISCONNECT, tid, 0))

    def request_pd(self):
        """Request PD packet data."""
        tid = self._next_tid()
        self.send(create_packet(CMD_GET_DATA, tid, ATT_PD_PACKET))
        time.sleep(0.05)
        return self.recv()

    def drain(self):
        """Drain any pending data."""
        while True:
            try:
                self.dev.read(self.ep_in, 512, timeout=50)
            except usb.core.USBTimeoutError:
                break


def decode_pd_wire(wire_data: bytes, source_caps=None) -> dict | None:
    """Decode PD wire bytes using usbpdpy.

    Args:
        wire_data: Raw PD wire bytes
        source_caps: Optional list of PowerDataObj from previous Source_Capabilities
    """
    if len(wire_data) < 2:
        return None

    try:
        if source_caps:
            msg = usbpdpy.parse_pd_message_with_state(wire_data, source_caps)
        else:
            msg = usbpdpy.parse_pd_message(wire_data)

        result = {
            "type": msg.header.message_type,  # Already a string
            "msg_id": msg.header.message_id,
            "num_data_obj": msg.header.num_data_objects,
            "power_role": msg.header.port_power_role,
            "data_role": msg.header.port_data_role,
            "spec_rev": msg.header.spec_revision,
            "is_source_caps": msg.is_source_capabilities(),
        }

        # If Source Capabilities, include PDOs
        if msg.data_objects:
            result["data_objects"] = []
            for pdo in msg.data_objects:
                result["data_objects"].append(str(pdo))

        # If Request, include RDOs
        if msg.request_objects:
            result["request_objects"] = []
            for rdo in msg.request_objects:
                if rdo.operating_current_a is not None:
                    result["request_objects"].append(f"PDO#{rdo.object_position} @ {rdo.operating_current_a:.2f}A")
                else:
                    result["request_objects"].append(f"PDO#{rdo.object_position}")

        return result
    except Exception as e:
        return {"error": str(e), "raw": wire_data.hex()}


def main():
    print("Connecting to POWER-Z KM003C...")
    dev = KM003CDevice()

    # Drain pending data
    dev.drain()

    if not dev.connect():
        print("Failed to connect!")
        return
    print("Connected\n")

    print("Capturing PD events (Ctrl+C to stop)...")
    print("=" * 80)

    # Track Source Capabilities for Request decoding
    source_caps = None

    try:
        while True:
            resp = dev.request_pd()

            if len(resp) < 8:
                time.sleep(0.1)
                continue

            # Parse with km003c_lib
            try:
                packet = parse_packet(resp)
            except Exception as e:
                print(f"Parse error: {e}")
                continue

            pkt_type = get_packet_type(packet)

            if pkt_type != "DataResponse":
                continue

            # Check for PD status (12-byte measurement snapshot)
            pd_status = get_pd_status(packet)
            if pd_status:
                print(f"PdStatus: type={pd_status.type_id}, ts={pd_status.timestamp}, "
                      f"vbus={pd_status.vbus_v:.2f}V, ibus={pd_status.ibus_a:.3f}A")

            # Check for PD events (preamble + wire messages)
            pd_events = get_pd_events(packet)
            if pd_events:
                preamble = pd_events.preamble
                print(f"\nPdEventStream: ts={preamble.timestamp}ms, "
                      f"vbus={preamble.vbus_v:.2f}V, ibus={preamble.ibus_a:.3f}A")

                for event in pd_events.events:
                    ts = event.timestamp
                    data = event.data

                    # PdEventData is an enum: Connect(()), Disconnect(()), or PdMessage{sop, wire_data}
                    # In Python it comes as dict with keys 'sop' and 'wire_data' for messages
                    if isinstance(data, dict) and "sop" in data and "wire_data" in data:
                        sop = data["sop"]
                        wire = bytes(data["wire_data"])

                        # Empty wire_data with special sop = connection event
                        if len(wire) == 0:
                            if sop == 0x11:
                                print(f"  [{ts:8d}ms] ** CONNECT **")
                                source_caps = None  # Reset on new connection
                            elif sop == 0x12:
                                print(f"  [{ts:8d}ms] ** DISCONNECT **")
                        elif len(wire) >= 2:
                            decoded = decode_pd_wire(wire, source_caps)

                            if decoded and "type" in decoded:
                                # Update source caps if this is Source_Capabilities
                                if decoded.get("is_source_caps"):
                                    # Re-parse to get the PowerDataObj list
                                    msg = usbpdpy.parse_pd_message(wire)
                                    source_caps = list(msg.data_objects)

                                role = f"{decoded['power_role']}/{decoded['data_role']}"
                                obj_info = ""
                                if decoded.get("data_objects"):
                                    obj_info = f"\n             PDOs: {decoded['data_objects']}"
                                if decoded.get("request_objects"):
                                    obj_info = f"\n             RDOs: {decoded['request_objects']}"
                                print(f"  [{ts:8d}ms] SOP{sop}: {decoded['type']:20s} "
                                      f"(ID={decoded['msg_id']}, {role}){obj_info}")
                            else:
                                print(f"  [{ts:8d}ms] SOP{sop}: raw={wire.hex()}")
                    # Handle Connect/Disconnect enum variants (tuple form)
                    elif data == ():
                        # This shouldn't happen with current structure, but just in case
                        print(f"  [{ts:8d}ms] Event: {data}")

                print()

            time.sleep(0.05)

    except KeyboardInterrupt:
        print("\n\nStopping...")
    finally:
        dev.disconnect()
        print("Disconnected")


if __name__ == "__main__":
    main()
