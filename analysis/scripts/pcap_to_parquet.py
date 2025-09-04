#!/usr/bin/env python3
"""
Script to convert pcap files to Parquet format for easier analysis.
Based on the packet structure analysis of USB traffic captures.
"""

import asyncio
import nest_asyncio
nest_asyncio.apply()

import pyshark
import polars as pl
import argparse
import os
from datetime import datetime
from pathlib import Path
import sys

def extract_packet_data(packet):
    """Extract relevant data from a packet into a dictionary."""
    
    # Handle timestamp safely
    try:
        timestamp = str(packet.sniff_time)
    except:
        timestamp = str(packet.sniff_timestamp) if hasattr(packet, 'sniff_timestamp') else 'unknown'
    
    # Base packet information
    packet_data = {
        'timestamp': timestamp,
        'packet_length': len(packet),
        'layers': ','.join([layer.layer_name for layer in packet.layers])
    }
    
    # Extract USB layer fields
    if hasattr(packet, 'usb'):
        usb = packet.usb
        usb_fields = [
            'src', 'dst', 'addr', 'urb_id', 'urb_type', 'transfer_type',
            'endpoint_address', 'endpoint_address_direction', 'endpoint_address_number',
            'device_address', 'bus_id', 'setup_flag', 'data_flag',
            'urb_ts_sec', 'urb_ts_usec', 'urb_status', 'urb_len', 'data_len',
            'interval', 'start_frame', 'time'
        ]
        
        for field in usb_fields:
            try:
                value = getattr(usb, field, None)
                packet_data[f'usb_{field}'] = str(value) if value is not None else None
            except:
                packet_data[f'usb_{field}'] = None
    
    # Extract DATA layer fields (USB descriptors and setup data)
    data_layer = None
    for layer in packet.layers:
        if layer.layer_name == 'DATA':
            data_layer = layer
            break
    
    if data_layer:
        # Common DATA fields
        data_fields = [
            'usb_bmrequesttype', 'usb_bmrequesttype_direction', 'usb_bmrequesttype_type',
            'usb_bmrequesttype_recipient', 'usb_setup_brequest', 'usb_descriptorindex',
            'usb_languageid', 'usb_setup_wlength', 'usb_bdescriptortype', 'usb_blength',
            'usb_bcdusb', 'usb_bdeviceclass', 'usb_bdevicesubclass', 'usb_bdeviceprotocol',
            'usb_bmaxpacketsize0', 'usb_idvendor', 'usb_idproduct', 'usb_bcddevice',
            'usb_wtotallength', 'usb_bnuminterfaces'
        ]
        
        for field in data_fields:
            try:
                value = getattr(data_layer, field, None)
                packet_data[f'data_{field}'] = str(value) if value is not None else None
            except:
                packet_data[f'data_{field}'] = None
        
        # Get the descriptor type description if available
        try:
            desc_type = getattr(data_layer, '', None)  # The unnamed field contains descriptor type
            packet_data['data_descriptor_type'] = str(desc_type) if desc_type else None
        except:
            packet_data['data_descriptor_type'] = None
    
    return packet_data

def convert_pcap_to_parquet(pcap_file, output_file=None, max_packets=None):
    """Convert a pcap file to Parquet format."""
    
    if not os.path.exists(pcap_file):
        print(f"Error: File {pcap_file} not found")
        return False
    
    if output_file is None:
        # Generate output filename
        pcap_path = Path(pcap_file)
        output_file = pcap_path.parent / f"{pcap_path.stem}.parquet"
    
    print(f"Converting {pcap_file} to {output_file}")
    
    # Open the capture file
    cap = pyshark.FileCapture(pcap_file)
    
    packets_data = []
    packet_count = 0
    
    try:
        for packet in cap:
            packet_count += 1
            
            if packet_count % 100 == 0:
                print(f"Processed {packet_count} packets...")
            
            if max_packets and packet_count > max_packets:
                break
            
            packet_data = extract_packet_data(packet)
            packets_data.append(packet_data)
        
    except Exception as e:
        print(f"Error processing packet {packet_count}: {e}")
        return False
    finally:
        cap.close()
    
    if not packets_data:
        print("No packets found in the capture file")
        return False
    
    print(f"Processed {packet_count} packets total")
    
    # Convert to Polars DataFrame
    try:
        df = pl.DataFrame(packets_data)
        
        # Convert timestamp to proper datetime if possible
        try:
            df = df.with_columns([
                pl.col('timestamp').str.to_datetime().alias('timestamp_parsed')
            ])
        except:
            print("Warning: Could not parse timestamps")
        
        # Write to Parquet
        df.write_parquet(output_file)
        print(f"Successfully wrote {len(df)} rows to {output_file}")
        
        # Print schema info
        print(f"\nDataFrame shape: {df.shape}")
        print(f"Columns: {df.columns}")
        
        return True
        
    except Exception as e:
        print(f"Error creating DataFrame or writing Parquet: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description='Convert pcap files to Parquet format')
    parser.add_argument('input_file', help='Input pcap/pcapng file')
    parser.add_argument('-o', '--output', help='Output parquet file (default: input_file.parquet)')
    parser.add_argument('-n', '--max-packets', type=int, help='Maximum number of packets to process')
    parser.add_argument('--info', action='store_true', help='Show info about the resulting Parquet file')
    
    args = parser.parse_args()
    
    success = convert_pcap_to_parquet(args.input_file, args.output, args.max_packets)
    
    if success and args.info:
        output_file = args.output
        if output_file is None:
            pcap_path = Path(args.input_file)
            output_file = pcap_path.parent / f"{pcap_path.stem}.parquet"
        
        # Show info about the created file
        try:
            df = pl.read_parquet(output_file)
            print(f"\n=== Parquet File Info ===")
            print(f"Shape: {df.shape}")
            print(f"File size: {os.path.getsize(output_file)} bytes")
            print(f"\nFirst few rows:")
            print(df.head())
            print(f"\nColumn types:")
            for col, dtype in zip(df.columns, df.dtypes):
                print(f"  {col}: {dtype}")
        except Exception as e:
            print(f"Error reading created Parquet file: {e}")
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())
