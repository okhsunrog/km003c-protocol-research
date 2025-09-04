#!/usr/bin/env python3
"""
Script to explore the structure of packets in a pcap file to understand
what fields are available for conversion to Parquet format.
"""

import asyncio
import nest_asyncio
nest_asyncio.apply()

import pyshark
import json
from collections import defaultdict, Counter
from pprint import pprint
import sys
import os

def explore_packet_structure(pcap_file, max_packets=10):
    """Explore the structure of packets in a pcap file."""
    
    if not os.path.exists(pcap_file):
        print(f"Error: File {pcap_file} not found")
        return
    
    print(f"=== Exploring Packet Structure in {pcap_file} ===\n")
    
    # Open the capture file without raw data for better compatibility
    cap = pyshark.FileCapture(pcap_file)
    
    packet_info = []
    field_frequency = defaultdict(int)
    layer_frequency = Counter()
    
    try:
        for i, packet in enumerate(cap):
            if i >= max_packets:
                break
            
            print(f"--- Packet {i+1} ---")
            
            # Handle timestamp safely
            try:
                timestamp = str(packet.sniff_time)
            except:
                timestamp = str(packet.sniff_timestamp) if hasattr(packet, 'sniff_timestamp') else 'unknown'
            
            print(f"Timestamp: {timestamp}")
            print(f"Length: {len(packet)} bytes")
            print(f"Layers: {[layer.layer_name for layer in packet.layers]}")
            
            # Count layer frequency
            for layer in packet.layers:
                layer_frequency[layer.layer_name] += 1
            
            packet_data = {
                'packet_num': i+1,
                'timestamp': timestamp,
                'length': len(packet),
                'layers': [layer.layer_name for layer in packet.layers],
                'layer_details': {}
            }
            
            # Examine each layer
            for layer in packet.layers:
                layer_name = layer.layer_name
                print(f"\n  Layer: {layer_name}")
                
                layer_fields = {}
                try:
                    if hasattr(layer, 'field_names') and layer.field_names:
                        for field_name in layer.field_names:
                            try:
                                field_value = getattr(layer, field_name)
                                layer_fields[field_name] = str(field_value)
                                field_frequency[f"{layer_name}.{field_name}"] += 1
                            except Exception as e:
                                layer_fields[field_name] = f"<error: {e}>"
                    
                    # Alternative approach: try to get all attributes
                    elif hasattr(layer, '_all_fields'):
                        for field_name, field_value in layer._all_fields.items():
                            layer_fields[field_name] = str(field_value)
                            field_frequency[f"{layer_name}.{field_name}"] += 1
                            
                except Exception as e:
                    print(f"    Error accessing fields for {layer_name}: {e}")
                    layer_fields = {"error": str(e)}
                
                # Show first few fields for this layer
                field_items = list(layer_fields.items())
                for j, (key, value) in enumerate(field_items[:5]):
                    print(f"    {key}: {value}")
                
                if len(field_items) > 5:
                    print(f"    ... and {len(field_items) - 5} more fields")
                
                packet_data['layer_details'][layer_name] = layer_fields
            
            packet_info.append(packet_data)
            print("\n" + "="*50)
        
    finally:
        cap.close()
    
    # Summary statistics
    print(f"\n=== SUMMARY ===")
    print(f"Analyzed {len(packet_info)} packets")
    print(f"\nLayer frequency:")
    for layer, count in layer_frequency.most_common():
        print(f"  {layer}: {count}")
    
    print(f"\nMost common fields across all packets:")
    for field, count in sorted(field_frequency.items(), key=lambda x: x[1], reverse=True)[:20]:
        print(f"  {field}: {count}")
    
    return packet_info, field_frequency, layer_frequency

def suggest_parquet_schema(field_frequency, layer_frequency):
    """Suggest a schema for Parquet conversion based on field analysis."""
    
    print(f"\n=== SUGGESTED PARQUET SCHEMA ===")
    
    # Core fields that should always be included
    core_fields = [
        'timestamp',
        'packet_length',
        'frame_number'
    ]
    
    print("Core fields:")
    for field in core_fields:
        print(f"  {field}: timestamp/int64")
    
    # USB-specific fields (since this appears to be USB traffic)
    usb_fields = []
    for field, count in field_frequency.items():
        if field.startswith('usb.') and count > len(packet_info) * 0.1:  # Present in >10% of packets
            usb_fields.append(field)
    
    print(f"\nUSB fields (present in >10% of packets):")
    for field in sorted(usb_fields):
        print(f"  {field}: string")
    
    # Other important fields
    other_fields = []
    for field, count in field_frequency.items():
        if not field.startswith('usb.') and count > len(packet_info) * 0.5:  # Present in >50% of packets
            other_fields.append(field)
    
    print(f"\nOther common fields (present in >50% of packets):")
    for field in sorted(other_fields):
        print(f"  {field}: string")

if __name__ == "__main__":
    # Use the pcap file from the project
    pcap_file = "captures/wireshark/orig_with_pd.13.pcapng"
    
    if len(sys.argv) > 1:
        pcap_file = sys.argv[1]
    
    packet_info, field_freq, layer_freq = explore_packet_structure(pcap_file, max_packets=5)
    suggest_parquet_schema(field_freq, layer_freq)
