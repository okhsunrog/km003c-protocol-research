#!/usr/bin/env python3
"""Test PdStatus attribute with PD hardware connected."""

import usb.core
import usb.util
import time

VID = 0x5FC9
PID = 0x0063

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
