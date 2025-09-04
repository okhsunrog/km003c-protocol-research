#!/usr/bin/env python3
"""
Helper functions for USB protocol analysis using the master dataset.
"""

import polars as pl
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np

def load_master_dataset(parquet_file: str = "usb_master_dataset.parquet") -> pl.DataFrame:
    """Load the master USB dataset from parquet file."""
    
    if not Path(parquet_file).exists():
        raise FileNotFoundError(f"Master dataset not found: {parquet_file}")
    
    df = pl.read_parquet(parquet_file)
    print(f"✅ Loaded {len(df):,} USB packets from {parquet_file}")
    return df

def get_session_stats(df: pl.DataFrame) -> pl.DataFrame:
    """Get comprehensive statistics for each capture session."""
    
    session_stats = df.group_by(['session_id', 'device_address']).agg([
        pl.len().alias('total_packets'),
        pl.col('payload_hex').map_elements(lambda x: len(x) > 0, return_dtype=pl.Boolean).sum().alias('payload_packets'),
        pl.col('transfer_type').n_unique().alias('transfer_types'),
        pl.col('endpoint_address').n_unique().alias('endpoints'),
        pl.col('data_length').mean().alias('avg_payload_size'),
        pl.col('data_length').max().alias('max_payload_size'),
        pl.col('timestamp').min().alias('start_time'),
        pl.col('timestamp').max().alias('end_time'),
        (pl.col('timestamp').max() - pl.col('timestamp').min()).alias('duration'),
        pl.col('urb_id').n_unique().alias('unique_urb_ids'),
    ]).with_columns([
        (pl.col('payload_packets') / pl.col('total_packets') * 100).alias('payload_percentage')
    ]).sort(['device_address', 'session_id'])
    
    return session_stats

def get_device_summary(df: pl.DataFrame) -> pl.DataFrame:
    """Get summary statistics for each device."""
    
    device_summary = df.group_by('device_address').agg([
        pl.len().alias('total_packets'),
        pl.col('session_id').n_unique().alias('sessions'),
        pl.col('payload_hex').map_elements(lambda x: len(x) > 0, return_dtype=pl.Boolean).sum().alias('payload_packets'),
        pl.col('transfer_type').n_unique().alias('transfer_types'),
        pl.col('endpoint_address').n_unique().alias('endpoints'),
        pl.col('data_length').mean().alias('avg_payload_size'),
        pl.col('timestamp').min().alias('earliest_time'),
        pl.col('timestamp').max().alias('latest_time'),
        pl.col('urb_id').n_unique().alias('unique_urb_ids'),
    ]).sort('device_address')
    
    return device_summary

def analyze_control_packets(df: pl.DataFrame) -> Dict[str, any]:
    """Analyze USB control packets and setup requests."""
    
    control_packets = df.filter(pl.col('transfer_type') == '0x02')
    
    if len(control_packets) == 0:
        return {"message": "No control packets found"}
    
    # Analyze setup requests
    setup_packets = control_packets.filter(pl.col('bmrequest_type').is_not_null())
    
    # Get unique setup requests
    unique_requests = setup_packets.group_by(['bmrequest_type', 'brequest', 'descriptor_type']).agg([
        pl.len().alias('count'),
        pl.col('wlength').unique().alias('wlength_values')
    ]).sort('count', descending=True)
    
    return {
        "total_control_packets": len(control_packets),
        "setup_packets": len(setup_packets),
        "unique_requests": unique_requests,
        "devices_with_control": control_packets['device_address'].unique().to_list()
    }

def analyze_urb_transactions(df: pl.DataFrame, device_address: Optional[int] = None) -> Dict[str, any]:
    """Analyze URB transaction patterns (Submit/Complete pairs)."""
    
    if device_address:
        df_filtered = df.filter(pl.col('device_address') == device_address)
    else:
        df_filtered = df
    
    # Analyze URB reuse patterns
    urb_patterns = df_filtered.group_by('urb_id').agg([
        pl.len().alias('packet_count'),
        pl.col('urb_type').unique().alias('urb_types'),
        pl.col('frame_number').min().alias('first_frame'),
        pl.col('frame_number').max().alias('last_frame'),
        (pl.col('frame_number').max() - pl.col('frame_number').min()).alias('frame_span')
    ])
    
    # Find Submit/Complete pairs
    paired_urbs = urb_patterns.filter(pl.col('packet_count') == 2)
    
    # Calculate transaction timing for pairs
    transaction_times = []
    for urb_id in paired_urbs['urb_id'].to_list()[:10]:  # Sample first 10
        urb_packets = df_filtered.filter(pl.col('urb_id') == urb_id).sort('frame_number')
        if len(urb_packets) == 2:
            submit_time = urb_packets[0, 'timestamp']
            complete_time = urb_packets[1, 'timestamp']
            transaction_times.append(complete_time - submit_time)
    
    return {
        "total_urb_ids": len(urb_patterns),
        "submit_complete_pairs": len(paired_urbs),
        "avg_transaction_time": np.mean(transaction_times) if transaction_times else 0,
        "urb_reuse_stats": urb_patterns.sort('packet_count', descending=True).head(10)
    }

def get_payload_patterns(df: pl.DataFrame, device_address: Optional[int] = None, limit: int = 20) -> pl.DataFrame:
    """Find common payload patterns in the data."""
    
    if device_address:
        df_filtered = df.filter(pl.col('device_address') == device_address)
    else:
        df_filtered = df
    
    # Filter for packets with payload
    with_payload = df_filtered.filter(pl.col('payload_hex') != '')
    
    if len(with_payload) == 0:
        return pl.DataFrame()
    
    # Find most common payloads
    payload_patterns = with_payload.group_by(['payload_hex', 'data_length', 'direction']).agg([
        pl.len().alias('count'),
        pl.col('frame_number').min().alias('first_seen'),
        pl.col('timestamp').min().alias('first_time')
    ]).sort('count', descending=True).head(limit)
    
    return payload_patterns

def analyze_timing_patterns(df: pl.DataFrame, device_address: Optional[int] = None) -> Dict[str, any]:
    """Analyze timing patterns in USB communication."""
    
    if device_address:
        df_filtered = df.filter(pl.col('device_address') == device_address)
    else:
        df_filtered = df
    
    # Calculate intervals between packets
    df_sorted = df_filtered.sort(['device_address', 'timestamp'])
    
    # Group by device and calculate intervals
    intervals_by_device = {}
    for device in df_sorted['device_address'].unique():
        device_data = df_sorted.filter(pl.col('device_address') == device)
        timestamps = device_data['timestamp'].to_list()
        
        if len(timestamps) > 1:
            intervals = [timestamps[i] - timestamps[i-1] for i in range(1, len(timestamps))]
            intervals_by_device[device] = {
                'avg_interval': np.mean(intervals),
                'min_interval': np.min(intervals),
                'max_interval': np.max(intervals),
                'std_interval': np.std(intervals)
            }
    
    return intervals_by_device

def print_session_summary(session_stats: pl.DataFrame):
    """Print a formatted summary of all capture sessions."""
    
    print("📊 CAPTURE SESSION SUMMARY")
    print("=" * 80)
    
    for row in session_stats.iter_rows(named=True):
        session_id = row['session_id']
        device = row['device_address']
        total = row['total_packets']
        payload = row['payload_packets']
        payload_pct = row['payload_percentage']
        duration = row['duration']
        avg_size = row['avg_payload_size']
        max_size = row['max_payload_size']
        endpoints = row['endpoints']
        urb_ids = row['unique_urb_ids']
        
        print(f"📁 {session_id}")
        print(f"   🔌 Device: {device}")
        print(f"   📦 Packets: {total:,} total ({payload} with payload, {payload_pct:.1f}%)")
        print(f"   ⏱️  Duration: {duration:.1f}s")
        print(f"   📏 Payload: avg {avg_size:.1f}b, max {max_size}b")
        print(f"   🔗 Endpoints: {endpoints}, URB IDs: {urb_ids}")
        print()

def print_device_summary(device_summary: pl.DataFrame):
    """Print a formatted summary of all devices."""
    
    print("🔌 DEVICE SUMMARY")
    print("=" * 50)
    
    for row in device_summary.iter_rows(named=True):
        device = row['device_address']
        total = row['total_packets']
        sessions = row['sessions']
        payload = row['payload_packets']
        avg_size = row['avg_payload_size']
        time_span = row['latest_time'] - row['earliest_time']
        
        print(f"Device {device}:")
        print(f"  📊 {total:,} packets across {sessions} sessions")
        print(f"  💾 {payload} packets with payload data")
        print(f"  📏 Average payload: {avg_size:.1f} bytes")
        print(f"  ⏱️  Time span: {time_span:.1f}s")
        print()

def filter_by_device(df: pl.DataFrame, device_address: int) -> pl.DataFrame:
    """Filter dataset for specific device."""
    return df.filter(pl.col('device_address') == device_address)

def filter_by_session(df: pl.DataFrame, session_id: str) -> pl.DataFrame:
    """Filter dataset for specific session."""
    return df.filter(pl.col('session_id') == session_id)

def get_payload_data(df: pl.DataFrame) -> pl.DataFrame:
    """Get only packets with payload data."""
    return df.filter(pl.col('payload_hex') != '')

def get_control_data(df: pl.DataFrame) -> pl.DataFrame:
    """Get only control packets."""
    return df.filter(pl.col('transfer_type') == '0x02')

def decode_hex_payload(hex_string: str) -> bytes:
    """Convert hex string to bytes."""
    if not hex_string:
        return b''
    return bytes.fromhex(hex_string)

def hex_to_ascii(hex_string: str) -> str:
    """Convert hex string to ASCII representation (printable chars only)."""
    if not hex_string:
        return ''
    try:
        data = bytes.fromhex(hex_string)
        return ''.join(chr(b) if 32 <= b <= 126 else '.' for b in data)
    except ValueError:
        return '<invalid hex>'

# -- Rust-backed Parser Integration --
from km003c_lib import parse_packet, AdcData

def add_parsed_adc_data(df: pl.DataFrame) -> pl.DataFrame:
    """
    Applies the Rust-based parser to a DataFrame, returning a new DataFrame
    with a 'packet_type' column and columns for the parsed ADC data.
    """

    def parse_hex_payload(payload_hex: str) -> Optional[dict]:
        """Wrapper to handle hex decoding and call the Rust parser."""
        NULL_ADC_DICT = {
            'vbus_v': None, 'ibus_a': None, 'power_w': None, 'vbus_avg_v': None,
            'ibus_avg_a': None, 'temp_c': None, 'vdp_v': None, 'vdm_v': None,
            'vdp_avg_v': None, 'vdm_avg_v': None, 'cc1_v': None, 'cc2_v': None,
        }
        if not payload_hex:
            return NULL_ADC_DICT
        try:
            payload_bytes = bytes.fromhex(payload_hex)
            adc_data = parse_packet(payload_bytes)
            if adc_data:
                return {
                    'vbus_v': adc_data.vbus_v, 'ibus_a': adc_data.ibus_a,
                    'power_w': adc_data.power_w, 'vbus_avg_v': adc_data.vbus_avg_v,
                    'ibus_avg_a': adc_data.ibus_avg_a, 'temp_c': adc_data.temp_c,
                    'vdp_v': adc_data.vdp_v, 'vdm_v': adc_data.vdm_v,
                    'vdp_avg_v': adc_data.vdp_avg_v, 'vdm_avg_v': adc_data.vdm_avg_v,
                    'cc1_v': adc_data.cc1_v, 'cc2_v': adc_data.cc2_v,
                }
            return NULL_ADC_DICT
        except (ValueError, TypeError):
            return NULL_ADC_DICT

    adc_struct_type = pl.Struct([
        pl.Field('vbus_v', pl.Float64), pl.Field('ibus_a', pl.Float64),
        pl.Field('power_w', pl.Float64), pl.Field('vbus_avg_v', pl.Float64),
        pl.Field('ibus_avg_a', pl.Float64), pl.Field('temp_c', pl.Float64),
        pl.Field('vdp_v', pl.Float64), pl.Field('vdm_v', pl.Float64),
        pl.Field('vdp_avg_v', pl.Float64), pl.Field('vdm_avg_v', pl.Float64),
        pl.Field('cc1_v', pl.Float64), pl.Field('cc2_v', pl.Float64),
    ])

    parsed_series = df["payload_hex"].map_elements(
        parse_hex_payload,
        return_dtype=adc_struct_type
    )

    return df.with_columns(
        pl.when(parsed_series.is_not_null())
          .then(pl.lit("ADC_DATA"))
          .otherwise(pl.lit("OTHER"))
          .alias("packet_type"),
        parsed_series.alias("adc_data")
    ).unnest("adc_data")
