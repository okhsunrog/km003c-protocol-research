#!/usr/bin/env python3
"""
Simple script to parse USB PD messages using usbpdpy

Usage:
    python analysis/scripts/parse_messages.py "1161" "0143" "0744"
"""

import sys
import usbpdpy


def main():
    if len(sys.argv) < 2:
        print("Usage: python parse_messages.py <hex_message1> [hex_message2] ...")
        print("Example: python parse_messages.py '1161' '0143' '0744'")
        return

    messages = sys.argv[1:]
    
    print(f"Parsing {len(messages)} USB PD messages...")
    print("=" * 50)
    
    for i, hex_msg in enumerate(messages, 1):
        try:
            msg_bytes = usbpdpy.hex_to_bytes(hex_msg)
            message = usbpdpy.parse_pd_message(msg_bytes)
            
            print(f"Message {i}: {hex_msg}")
            print(f"  Type: {message.header.message_type} ({usbpdpy.get_message_type_name(message.header.message_type)})")
            print(f"  Data Role: {message.header.port_data_role}")
            print(f"  Power Role: {message.header.port_power_role}")
            print(f"  Message ID: {message.header.message_id}")
            print(f"  Data Objects: {message.header.number_of_data_objects}")
            print()
            
        except Exception as e:
            print(f"Message {i}: {hex_msg}")
            print(f"  ❌ Error: {e}")
            print()


if __name__ == "__main__":
    main()
