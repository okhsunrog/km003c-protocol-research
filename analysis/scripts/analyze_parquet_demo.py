#!/usr/bin/env python3
"""
Demo script showing how to analyze the converted Parquet data.
This demonstrates the advantages of having the data in Parquet format.
"""

import polars as pl
import argparse
import sys
from pathlib import Path

def analyze_usb_traffic(parquet_file):
    """Analyze USB traffic from the Parquet file."""
    
    print(f"=== Analyzing USB Traffic from {parquet_file} ===\n")
    
    # Load the data
    df = pl.read_parquet(parquet_file)
    print(f"Loaded {len(df)} packets from {parquet_file}")
    print(f"Data covers time range: {df['timestamp'].min()} to {df['timestamp'].max()}")
    print(f"File size: {Path(parquet_file).stat().st_size} bytes\n")
    
    # Basic statistics
    print("=== Basic Statistics ===")
    print(f"Total packets: {len(df)}")
    print(f"Unique URB IDs: {df['usb_urb_id'].n_unique()}")
    print(f"Unique device addresses: {df['usb_device_address'].n_unique()}")
    print(f"Average packet length: {df['packet_length'].mean():.2f} bytes")
    print(f"Packet length range: {df['packet_length'].min()} - {df['packet_length'].max()} bytes\n")
    
    # URB types analysis
    print("=== URB Types ===")
    urb_types = df.group_by('usb_urb_type').agg([
        pl.count().alias('count'),
        pl.col('packet_length').mean().alias('avg_length')
    ]).sort('count', descending=True)
    print(urb_types)
    print()
    
    # Transfer types analysis
    print("=== Transfer Types ===")
    transfer_types = df.group_by('usb_transfer_type').agg([
        pl.count().alias('count'),
        pl.col('packet_length').mean().alias('avg_length')
    ]).sort('count', descending=True)
    print(transfer_types)
    print()
    
    # Data direction analysis
    print("=== Data Direction (src -> dst) ===")
    direction = df.group_by(['usb_src', 'usb_dst']).agg([
        pl.count().alias('count')
    ]).sort('count', descending=True)
    print(direction)
    print()
    
    # Descriptor types analysis (from DATA layer)
    print("=== USB Descriptor Types ===")
    descriptors = df.filter(
        pl.col('data_descriptor_type').is_not_null()
    ).group_by('data_descriptor_type').agg([
        pl.count().alias('count')
    ]).sort('count', descending=True)
    print(descriptors)
    print()
    
    # Device information (from device descriptors)
    print("=== Device Information ===")
    device_info = df.filter(
        pl.col('data_usb_idvendor').is_not_null() & 
        pl.col('data_usb_idproduct').is_not_null()
    ).select([
        'data_usb_idvendor', 'data_usb_idproduct', 'data_usb_bcdusb',
        'data_usb_bdeviceclass', 'data_usb_bdevicesubclass'
    ]).unique()
    print(device_info)
    print()
    
    # Endpoint analysis
    print("=== Endpoint Usage ===")
    endpoints = df.filter(
        pl.col('usb_endpoint_address').is_not_null()
    ).group_by(['usb_endpoint_address', 'usb_endpoint_address_direction']).agg([
        pl.count().alias('count')
    ]).sort('count', descending=True)
    print(endpoints)
    print()
    
    # Timeline analysis (packets per second)
    print("=== Traffic Timeline (packets per second) ===")
    timeline = df.with_columns([
        pl.col('timestamp_parsed').dt.truncate('1s').alias('second')
    ]).group_by('second').agg([
        pl.count().alias('packets_per_second')
    ]).sort('second')
    
    print(f"Peak traffic: {timeline['packets_per_second'].max()} packets/second")
    print(f"Average traffic: {timeline['packets_per_second'].mean():.2f} packets/second")
    print("\nFirst 10 seconds of traffic:")
    print(timeline.head(10))
    print()
    
    return df

def filter_examples(df):
    """Show examples of filtering the data."""
    
    print("=== Filtering Examples ===\n")
    
    # Example 1: Find all setup packets
    setup_packets = df.filter(
        pl.col('data_descriptor_type') == 'Setup Data'
    )
    print(f"Setup packets: {len(setup_packets)} out of {len(df)} total")
    
    # Example 2: Find packets with actual data payload
    data_packets = df.filter(
        (pl.col('usb_data_len').is_not_null()) & 
        (pl.col('usb_data_len') != '0')
    )
    print(f"Packets with data payload: {len(data_packets)}")
    
    # Example 3: Find device descriptor responses
    device_descriptors = df.filter(
        pl.col('data_descriptor_type') == 'DEVICE DESCRIPTOR'
    )
    print(f"Device descriptor packets: {len(device_descriptors)}")
    
    # Example 4: Find packets from host to device
    host_to_device = df.filter(
        pl.col('usb_src') == 'host'
    )
    print(f"Host to device packets: {len(host_to_device)}")
    
    print()

def main():
    parser = argparse.ArgumentParser(description='Analyze USB traffic from Parquet file')
    parser.add_argument('parquet_file', help='Input parquet file')
    parser.add_argument('--filter-examples', action='store_true', 
                       help='Show filtering examples')
    
    args = parser.parse_args()
    
    if not Path(args.parquet_file).exists():
        print(f"Error: File {args.parquet_file} not found")
        return 1
    
    try:
        df = analyze_usb_traffic(args.parquet_file)
        
        if args.filter_examples:
            filter_examples(df)
        
        print("=== Analysis Complete ===")
        print("The Parquet format allows for fast filtering and analysis!")
        print("You can now easily query this data using Polars, Pandas, or other tools.")
        
        return 0
        
    except Exception as e:
        print(f"Error analyzing file: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
