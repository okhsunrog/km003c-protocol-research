#!/usr/bin/env python3
"""
Test Refactored KM003C Library

Test the newly refactored RawPacket enum with SimpleData vs ExtendedData
to ensure everything works correctly with the Python bindings.
"""

import sys
from pathlib import Path
import polars as pl

# Setup paths
project_root = Path.cwd()
while not (project_root / 'pyproject.toml').exists():
    project_root = project_root.parent

analysis_scripts_path = project_root / 'analysis' / 'scripts'
sys.path.insert(0, str(analysis_scripts_path))

import helpers
from km003c_lib import parse_packet

def test_refactored_library():
    """Test the refactored library with real data."""
    
    print("🧪 TESTING REFACTORED KM003C LIBRARY")
    print("=" * 45)
    
    # Load dataset
    df = helpers.load_master_dataset(project_root / 'usb_master_dataset.parquet')
    transactions = helpers.get_transactions(df, filter_out_enumeration=True)
    
    # Get sample packets of different types
    test_cases = []
    
    # Find a PutData packet (should be ExtendedData)
    putdata_sample = transactions.filter(
        pl.col('payload_hex').str.starts_with('41') & 
        (pl.col('payload_length') >= 52)
    ).head(1)
    
    if len(putdata_sample) > 0:
        row = putdata_sample.iter_rows(named=True).__next__()
        test_cases.append({
            'name': 'PutData (should be ExtendedData)',
            'payload_hex': row['payload_hex'],
            'expected_type': 'ExtendedData',
            'length': row['payload_length']
        })
    
    # Find a control packet (should stay as parsed before)
    ctrl_sample = transactions.filter(
        pl.col('payload_hex').str.starts_with('0c') &
        (pl.col('payload_length') == 4)
    ).head(1)
    
    if len(ctrl_sample) > 0:
        row = ctrl_sample.iter_rows(named=True).__next__()
        test_cases.append({
            'name': 'Control (GetData)',
            'payload_hex': row['payload_hex'], 
            'expected_type': 'CmdGetSimpleAdcData',
            'length': row['payload_length']
        })
    
    # Find a Head packet (should be SimpleData) 
    head_sample = transactions.filter(
        pl.col('payload_hex').str.starts_with('40')
    ).head(1)
    
    if len(head_sample) > 0:
        row = head_sample.iter_rows(named=True).__next__()
        test_cases.append({
            'name': 'Head (should be SimpleData)',
            'payload_hex': row['payload_hex'],
            'expected_type': 'Generic',
            'length': row['payload_length']
        })
    
    # Find an Unknown packet
    unknown_sample = transactions.filter(
        pl.col('payload_hex').str.starts_with('44') |  # Type 68
        pl.col('payload_hex').str.starts_with('4c') |  # Type 76 
        pl.col('payload_hex').str.starts_with('75')    # Type 117
    ).head(1)
    
    if len(unknown_sample) > 0:
        row = unknown_sample.iter_rows(named=True).__next__()
        first_byte = int(row['payload_hex'][:2], 16)
        packet_type = first_byte & 0x7F
        test_cases.append({
            'name': f'Unknown Type {packet_type} (should be SimpleData)',
            'payload_hex': row['payload_hex'],
            'expected_type': 'Generic',
            'length': row['payload_length']
        })
    
    print(f"🔍 Testing {len(test_cases)} packet types:")
    print()
    
    # Test each case
    results = []
    for i, test_case in enumerate(test_cases):
        print(f"📋 Test {i+1}: {test_case['name']}")
        print(f"   Payload: {test_case['payload_hex'][:32]}...")
        print(f"   Length: {test_case['length']} bytes")
        
        try:
            # Parse with refactored library
            payload_bytes = bytes.fromhex(test_case['payload_hex'])
            parsed = parse_packet(payload_bytes)
            
            print(f"   ✅ Parsed successfully!")
            print(f"   📊 Result:")
            print(f"      packet_type: {parsed.packet_type}")
            
            # Check if we have ADC data
            if hasattr(parsed, 'adc_data') and parsed.adc_data:
                print(f"      adc_data: V={parsed.adc_data.vbus_v:.3f}V I={parsed.adc_data.ibus_a:.3f}A")
            
            # Check if we have PD data
            if hasattr(parsed, 'pd_data') and parsed.pd_data:
                pd_preview = ' '.join(f'{b:02x}' for b in parsed.pd_data[:8])
                print(f"      pd_data: {pd_preview}... ({len(parsed.pd_data)} bytes)")
            
            # Check if we have raw payload
            if hasattr(parsed, 'raw_payload') and parsed.raw_payload:
                raw_preview = ' '.join(f'{b:02x}' for b in parsed.raw_payload[:8])
                print(f"      raw_payload: {raw_preview}... ({len(parsed.raw_payload)} bytes)")
            
            results.append({
                'test_name': test_case['name'],
                'success': True,
                'packet_type': parsed.packet_type,
                'expected': test_case['expected_type'],
                'matches_expected': parsed.packet_type == test_case['expected_type']
            })
            
        except Exception as e:
            print(f"   ❌ Parse failed: {e}")
            results.append({
                'test_name': test_case['name'],
                'success': False,
                'error': str(e),
                'expected': test_case['expected_type'],
                'matches_expected': False
            })
        
        print()
    
    # Summary
    print("🎯 TEST SUMMARY:")
    print("-" * 20)
    
    successful_tests = sum(1 for r in results if r['success'])
    matching_expected = sum(1 for r in results if r.get('matches_expected', False))
    
    print(f"Total tests: {len(results)}")
    print(f"Successful parses: {successful_tests}/{len(results)}")
    print(f"Expected results: {matching_expected}/{len(results)}")
    
    if successful_tests == len(results):
        print("✅ All packets parsed successfully!")
    else:
        print("⚠️  Some packets failed to parse")
    
    # Detailed results
    print(f"\n📋 DETAILED RESULTS:")
    for result in results:
        status = "✅" if result['success'] else "❌"
        expected_match = "✅" if result.get('matches_expected', False) else "❌"
        
        print(f"  {status} {result['test_name']}")
        if result['success']:
            print(f"     → Parsed as: {result['packet_type']}")
            print(f"     → Expected: {result['expected']} {expected_match}")
        else:
            print(f"     → Error: {result.get('error', 'Unknown error')}")
    
    # Test some edge cases
    print(f"\n🔬 EDGE CASE TESTING:")
    print("-" * 25)
    
    edge_cases = [
        ('Empty packet', ''),
        ('Too short', '41'),
        ('Short PutData', '411f0200'),  # The 4-byte packet we found earlier
        ('Invalid packet', 'ff' * 10)
    ]
    
    for name, payload_hex in edge_cases:
        print(f"Testing {name}: {payload_hex}")
        try:
            if payload_hex:
                payload_bytes = bytes.fromhex(payload_hex)
                parsed = parse_packet(payload_bytes)
                print(f"  ✅ Parsed as: {parsed.packet_type}")
            else:
                print(f"  ⚠️  Skipped empty packet")
        except Exception as e:
            print(f"  ❌ Error (expected): {e}")
    
    print(f"\n🚀 REFACTORED LIBRARY TEST COMPLETE!")

if __name__ == "__main__":
    test_refactored_library()