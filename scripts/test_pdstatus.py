#!/usr/bin/env python3
"""Test PD packet parsing with PD hardware connected."""

import usb.core
import usb.util
import time

VID = 0x5FC9
PID = 0x0063

# USB PD Control Message Types (no data objects)
PD_CTRL_MSGS = {
    0x01: "GoodCRC",
    0x02: "GotoMin",
    0x03: "Accept",
    0x04: "Reject",
    0x05: "Ping",
    0x06: "PS_RDY",
    0x07: "Get_Source_Cap",
    0x08: "Get_Sink_Cap",
    0x09: "DR_Swap",
    0x0A: "PR_Swap",
    0x0B: "VCONN_Swap",
    0x0C: "Wait",
    0x0D: "Soft_Reset",
    0x0E: "Data_Reset",
    0x0F: "Data_Reset_Complete",
    0x10: "Not_Supported",
    0x11: "Get_Source_Cap_Extended",
    0x12: "Get_Status",
    0x13: "FR_Swap",
    0x14: "Get_PPS_Status",
    0x15: "Get_Country_Codes",
    0x16: "Get_Sink_Cap_Extended",
}

# USB PD Data Message Types (have data objects)
PD_DATA_MSGS = {
    0x01: "Source_Capabilities",
    0x02: "Request",
    0x03: "BIST",
    0x04: "Sink_Capabilities",
    0x05: "Battery_Status",
    0x06: "Alert",
    0x07: "Get_Country_Info",
    0x08: "Enter_USB",
    0x0F: "Vendor_Defined",
}

def decode_pd_header(wire_data):
    """Decode PD message header from wire bytes."""
    if len(wire_data) < 2:
        return None

    header = int.from_bytes(wire_data[:2], 'little')
    msg_type = header & 0x1F
    data_role = (header >> 5) & 1  # 0=UFP, 1=DFP
    spec_rev = (header >> 6) & 3   # PD spec revision
    power_role = (header >> 8) & 1  # 0=Sink, 1=Source
    msg_id = (header >> 9) & 7     # Message ID (0-7)
    num_data_obj = (header >> 12) & 7  # Number of 4-byte data objects
    extended = (header >> 15) & 1   # Extended message flag

    if num_data_obj == 0:
        # Control message
        msg_name = PD_CTRL_MSGS.get(msg_type, f"Ctrl_{msg_type}")
    else:
        # Data message
        msg_name = PD_DATA_MSGS.get(msg_type, f"Data_{msg_type}")

    return {
        "msg_type": msg_type,
        "msg_name": msg_name,
        "data_role": "DFP" if data_role else "UFP",
        "power_role": "Source" if power_role else "Sink",
        "spec_rev": f"PD{spec_rev+1}.0",
        "msg_id": msg_id,
        "num_data_obj": num_data_obj,
        "extended": extended,
        "data_objects": wire_data[2:] if len(wire_data) > 2 else b"",
    }

def find_device():
    dev = usb.core.find(idVendor=VID, idProduct=PID)
    if dev is None:
        raise ValueError("Device not found")
    return dev

def send_recv(dev, ep_out, ep_in, data: bytes, timeout_ms: int = 1000) -> bytes:
    """Send data and receive response."""
    dev.write(ep_out, data, timeout=timeout_ms)
    time.sleep(0.1)
    try:
        resp = dev.read(ep_in, 512, timeout=timeout_ms)
        return bytes(resp)
    except usb.core.USBTimeoutError:
        return b""

def drain(dev, ep_in, timeout_ms=100):
    """Drain any pending data."""
    count = 0
    while True:
        try:
            data = dev.read(ep_in, 512, timeout=timeout_ms)
            count += 1
            print(f"   Drained: {len(data)} bytes")
        except usb.core.USBTimeoutError:
            break
    return count

def main():
    dev = find_device()
    print(f"Found device: {dev.manufacturer} {dev.product}")

    # Detach kernel driver if needed
    for cfg in dev:
        for intf in cfg:
            if dev.is_kernel_driver_active(intf.bInterfaceNumber):
                dev.detach_kernel_driver(intf.bInterfaceNumber)

    dev.set_configuration()

    # Reset device first
    print("\n0. Resetting device...")
    try:
        dev.reset()
        time.sleep(0.5)
    except usb.core.USBError as e:
        print(f"   Reset error (may be ok): {e}")

    # Re-find device after reset
    dev = find_device()
    for cfg in dev:
        for intf in cfg:
            if dev.is_kernel_driver_active(intf.bInterfaceNumber):
                dev.detach_kernel_driver(intf.bInterfaceNumber)
    dev.set_configuration()

    # Use vendor interface (interface 0, endpoints 0x01/0x81)
    interface_num = 0
    ep_out = 0x01
    ep_in = 0x81
    usb.util.claim_interface(dev, interface_num)

    # Drain any pending data
    print("   Draining pending data...")
    drain(dev, ep_in)

    tid = 1

    # 1. Connect
    print("\n1. Connect...")
    resp = send_recv(dev, ep_out, ep_in, bytes([0x02, tid, 0x00, 0x00]), timeout_ms=2000)
    pkt_type = resp[0] & 0x7F if resp else 0
    print(f"   Response: {len(resp)} bytes, type=0x{pkt_type:02x}")
    if pkt_type != 0x05:
        print("   FAILED - not Accept")
        return
    print("   OK")
    tid += 1

    # 2. Request PdPacket (attr 0x10, wire 0x20)
    print("\n2. Request PdPacket (attr=0x10, wire=0x0020)...")
    resp = send_recv(dev, ep_out, ep_in, bytes([0x0C, tid, 0x20, 0x00]))
    print(f"   Response: {len(resp)} bytes")
    if len(resp) > 4:
        print(f"   Header: {resp[:8].hex()}")
        print(f"   Payload: {resp[8:].hex()}")
    else:
        print(f"   Raw: {resp.hex()}")
    tid += 1

    # 3. Request PdStatus (attr 0x20, wire 0x40)
    print("\n3. Request PdStatus (attr=0x20, wire=0x0040)...")
    resp = send_recv(dev, ep_out, ep_in, bytes([0x0C, tid, 0x40, 0x00]))
    print(f"   Response: {len(resp)} bytes")
    if len(resp) > 4:
        print(f"   Header: {resp[:8].hex()}")
        print(f"   Payload: {resp[8:].hex()}")
    else:
        print(f"   Raw: {resp.hex()}")
    tid += 1

    def parse_logical_packets(data):
        """Parse response with logical packets. Data includes 4-byte header."""
        if len(data) < 4:
            return
        print(f"   Header: {data[:4].hex()}")
        # Payload starts at byte 4
        payload = data[4:]
        offset = 0
        pkt_num = 0
        while offset < len(payload):
            if offset + 4 > len(payload):
                break
            ext_hdr = int.from_bytes(payload[offset:offset+4], 'little')
            attr = ext_hdr & 0x7FFF
            has_next = bool((ext_hdr >> 15) & 1)
            chunk = (ext_hdr >> 16) & 0x3F
            size = (ext_hdr >> 22) & 0x3FF
            pkt_num += 1
            print(f"   LogicalPacket {pkt_num}: attr={attr}, next={has_next}, chunk={chunk}, size={size}")
            pkt_data = payload[offset+4:offset+4+size]
            print(f"      Data ({len(pkt_data)} bytes): {pkt_data[:32].hex()}{'...' if len(pkt_data) > 32 else ''}")
            offset += 4 + size
            if not has_next:
                break

    # 4. Request ADC+PdPacket (attr 0x11, wire 0x22)
    print("\n4. Request ADC+PdPacket (attr=0x11, wire=0x0022)...")
    resp = send_recv(dev, ep_out, ep_in, bytes([0x0C, tid, 0x22, 0x00]))
    print(f"   Response: {len(resp)} bytes")
    if len(resp) > 4:
        parse_logical_packets(resp)
    else:
        print(f"   Raw: {resp.hex()}")
    tid += 1

    # 5. Request ADC+PdStatus (attr 0x21, wire 0x42)
    print("\n5. Request ADC+PdStatus (attr=0x21, wire=0x0042)...")
    resp = send_recv(dev, ep_out, ep_in, bytes([0x0C, tid, 0x42, 0x00]))
    print(f"   Response: {len(resp)} bytes")
    if len(resp) > 4:
        parse_logical_packets(resp)
    else:
        print(f"   Raw: {resp.hex()}")
    tid += 1

    # 6. Disconnect
    print("\n6. Disconnect...")
    resp = send_recv(dev, ep_out, ep_in, bytes([0x03, tid, 0x00, 0x00]))
    print("   Done")

if __name__ == "__main__":
    main()
