#!/usr/bin/env python3
"""
JSONL USB Transaction Splitter

Command-line tool for splitting USB transaction data from JSONL files.
Uses the modular usb_transaction_splitter library for the core logic.

This script handles:
- Reading JSONL files into Polars DataFrames
- Calling the transaction splitter library
- Writing results back to JSONL format
- Validation and reporting
"""

import polars as pl
import json
import sys
import argparse
from pathlib import Path
from typing import Dict, Any

# Import the core library
from usb_transaction_splitter import (
    USBTransactionSplitter, 
    TransactionSplitterConfig,
    split_usb_transactions
)


def load_jsonl_to_dataframe(jsonl_file: Path) -> pl.DataFrame:
    """
    Load JSONL file into a Polars DataFrame.
    
    Args:
        jsonl_file: Path to the JSONL file
        
    Returns:
        Polars DataFrame containing the USB frame data
        
    Raises:
        FileNotFoundError: If the input file doesn't exist
        ValueError: If no valid JSON records found
    """
    if not jsonl_file.exists():
        raise FileNotFoundError(f"Input file not found: {jsonl_file}")
    
    rows = []
    with open(jsonl_file, "r") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
                
            try:
                frame = json.loads(line)
                rows.append(frame)
            except json.JSONDecodeError as e:
                print(f"Warning: Skipping invalid JSON on line {line_num}: {str(e)}")
                continue
    
    if not rows:
        raise ValueError("No valid JSON records found in input file")
    
    return pl.DataFrame(rows)


def save_dataframe_to_jsonl(df: pl.DataFrame, output_file: Path) -> None:
    """
    Save Polars DataFrame to JSONL format.
    
    Args:
        df: DataFrame to save
        output_file: Path for the output file
    """
    with open(output_file, "w") as f:
        for row in df.to_dicts():
            f.write(json.dumps(row) + "\n")


def print_validation_results(validation: Dict[str, bool]) -> None:
    """Print validation results in a formatted way"""
    print("\n=== Validation Results ===")
    print(f"1. Frame numbers in ascending order: {'✓ PASS' if validation['frame_order'] else '✗ FAIL'}")
    print(f"2. Timestamps in ascending order: {'✓ PASS' if validation['timestamp_order'] else '✗ FAIL'}")
    print(f"3. Transaction IDs in ascending order: {'✓ PASS' if validation['transaction_order'] else '✗ FAIL'}")
    
    if validation['valid']:
        print("\n🎉 All validation tests PASSED!")
    else:
        print("\n❌ Some validation tests FAILED!")


def print_transaction_stats(stats: Dict[str, Any]) -> None:
    """Print transaction statistics in a formatted way"""
    print("\n=== Transaction Statistics ===")
    print(f"Total transactions: {stats['total_transactions']}")
    print(f"Total frames: {stats['total_frames']}")
    print(f"Average frames per transaction: {stats['avg_frames_per_transaction']:.1f}")
    
    dist = stats['size_distribution']
    print(f"\nSize distribution:")
    print(f"  1 frame: {dist['1_frame']} transactions")
    print(f"  2-4 frames: {dist['2_4_frames']} transactions")
    print(f"  5+ frames: {dist['5_plus_frames']} transactions")
    
    if dist['5_plus_frames'] > 0:
        print(f"  Largest transaction: {stats['largest_transaction_size']} frames")


def analyze_bulk_sequences(df: pl.DataFrame) -> None:
    """Analyze and display bulk transfer sequence patterns"""
    print("\n=== Bulk Transfer Analysis ===")
    
    # Filter to bulk transfers only
    bulk_frames = df.filter(pl.col("transfer_type") == "0x03")
    
    if bulk_frames.height == 0:
        print("No bulk transfer frames found")
        return
    
    # Group by transaction
    bulk_transactions = (bulk_frames
                        .group_by("transaction_id")
                        .len()
                        .sort("transaction_id")
                        .filter(pl.col("len") >= 2))  # Multi-frame transactions
    
    print(f"Bulk transactions with multiple frames: {bulk_transactions.height}")
    
    # Show a few examples
    sample_count = 0
    for row in bulk_transactions.to_dicts()[:3]:  # Show first 3
        tid = row['transaction_id']
        tx_frames = bulk_frames.filter(pl.col("transaction_id") == tid).sort("frame_number")
        
        print(f"\nTransaction {tid} ({tx_frames.height} frames):")
        for frame in tx_frames.to_dicts():
            frame_num = frame['frame_number']
            ep = frame['endpoint_address']
            urb_type = frame['urb_type']
            data_len = frame['data_length']
            direction = frame['direction']
            timestamp = frame['timestamp']
            
            # Classify frame
            if ep == "0x01" and urb_type == "S" and data_len > 0:
                desc = "Command"
            elif ep == "0x01" and urb_type == "C":
                desc = "ACK"
            elif ep == "0x81" and urb_type == "C" and data_len > 0:
                desc = "Data Response"
            elif ep == "0x81" and urb_type == "S" and data_len == 0:
                desc = "Setup"
            else:
                desc = "Other"
            
            print(f"  Frame {frame_num}: {timestamp:.6f} - {urb_type} ({ep}) {direction} Len={data_len} [{desc}]")
        
        sample_count += 1


def main():
    """Main entry point for the JSONL USB transaction splitter"""
    parser = argparse.ArgumentParser(
        description="Split USB frames from JSONL into logical transactions",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s input.jsonl output.jsonl
  %(prog)s usb_data.jsonl usb_transactions.jsonl --verbose
  %(prog)s data.jsonl result.jsonl --no-validate
        """
    )
    
    parser.add_argument("input", type=Path, 
                       help="Input JSONL file containing USB frame data")
    parser.add_argument("output", type=Path,
                       help="Output JSONL file with transaction IDs")
    parser.add_argument("--verbose", "-v", action="store_true",
                       help="Show detailed analysis and bulk sequence examples")
    parser.add_argument("--no-validate", action="store_true",
                       help="Skip validation checks (faster processing)")
    parser.add_argument("--config", type=Path,
                       help="JSON configuration file for custom column names")
    
    args = parser.parse_args()
    
    try:
        # Load configuration if provided
        config = None
        if args.config:
            with open(args.config) as f:
                config_data = json.load(f)
                config = TransactionSplitterConfig(**config_data)
        
        # Load input data
        print(f"Reading {args.input}...")
        df = load_jsonl_to_dataframe(args.input)
        print(f"Loaded {df.height:,} frames")
        
        # Split transactions
        print("Splitting transactions...")
        df_split = split_usb_transactions(df, config)
        
        # Create splitter instance for detailed analysis
        splitter = USBTransactionSplitter(config)
        
        # Validation
        if not args.no_validate:
            validation = splitter.validate_output(df_split)
            print_validation_results(validation)
            
            if not validation['valid']:
                print("Warning: Output failed validation checks!")
        
        # Statistics
        stats = splitter.get_transaction_stats(df_split)
        print_transaction_stats(stats)
        
        # Detailed analysis
        if args.verbose:
            analyze_bulk_sequences(df_split)
        
        # Save output
        print(f"\nWriting to {args.output}...")
        save_dataframe_to_jsonl(df_split, args.output)
        print(f"✅ Successfully wrote {df_split.height:,} frames to {args.output}")
        
        # Summary
        print(f"\n🎯 Summary: Split {df.height} frames into {stats['total_transactions']} transactions")
        
        return 0
        
    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())