#!/usr/bin/env python3
"""
Example script demonstrating the new RawPacket functionality for debugging.
"""

from km003c_lib import parse_raw_packet, parse_packet

def main():
    print("KM003C Raw Packet Debugging Example")
    print("=" * 40)
    
    # Example 1: Simple control packet
    print("\nExample 1: Simple Control Packet")
    simple_data = bytes([0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08])
    raw_packet = parse_raw_packet(simple_data)
    
    print(f"Raw packet type: {raw_packet.packet_type}")
    print(f"Packet ID: {raw_packet.id}")
    print(f"Is extended: {raw_packet.is_extended}")
    print(f"Raw bytes length: {len(raw_packet.raw_bytes)}")
    print(f"Payload length: {len(raw_packet.payload)}")
    print(f"Raw bytes: {raw_packet.raw_bytes}")
    
    # Example 2: Extended data packet
    print("\nExample 2: Extended Data Packet")
    extended_data = bytes([
        0x81, 0x00, 0x00, 0x00,  # Header (0x81 = PutData with extended bit set)
        0x01, 0x00, 0x08, 0x00,  # Extended header (8 words of ADC data)
        0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07,  # ADC data
        0x08, 0x09, 0x0A, 0x0B, 0x0C, 0x0D, 0x0E, 0x0F
    ])
    raw_packet = parse_raw_packet(extended_data)
    
    print(f"Raw packet type: {raw_packet.packet_type}")
    print(f"Packet ID: {raw_packet.id}")
    print(f"Is extended: {raw_packet.is_extended}")
    print(f"Attribute: {raw_packet.attribute}")
    print(f"Raw bytes length: {len(raw_packet.raw_bytes)}")
    print(f"Payload length: {len(raw_packet.payload)}")
    print(f"First 8 payload bytes: {raw_packet.payload[:8]}")
    
    # Show the difference between raw and parsed packets
    print("\nExample 3: Comparing Raw vs Parsed Packets")
    try:
        # This will likely fail for our test data, but show the difference
        parsed_packet = parse_packet(extended_data)
        print(f"Parsed packet type: {parsed_packet.packet_type}")
    except Exception as e:
        print(f"Error parsing as regular packet: {e}")
        print("This is expected for our test data - RawPacket is useful for debugging!")

if __name__ == "__main__":
    main()
