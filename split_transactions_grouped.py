#!/usr/bin/env python3
"""
USB transaction splitter that groups complete bulk transfer sequences.

Groups bulk transfers into complete command-response cycles:
1. Command Submit (0x01 S) 
2. Command Complete/ACK (0x01 C)
3. Data Response (0x81 C) 
4. Setup for next (0x81 S)

This creates logical transactions that represent complete USB operations.
"""

import polars as pl
import json
import sys
from pathlib import Path
from typing import Set, Dict, Any, List


class USBTransactionSplitterGrouped:
    """USB transaction splitter that groups complete bulk transfer sequences"""
    
    def __init__(self):
        self.current_transaction = 1
        self.seen_urb_ids: Set[str] = set()
        self.completed_urb_ids: Set[str] = set()
        self.pending_bulk_sequence: List[Dict[str, Any]] = []  # Track bulk sequence frames
    
    def is_bulk_setup(self, frame: Dict[str, Any]) -> bool:
        """Check if frame is a bulk setup (EP 0x81 Submit with 0 data length)"""
        return (frame.get("transfer_type") == "0x03" and 
                frame.get("endpoint_address") == "0x81" and
                frame.get("urb_type") == "S" and
                frame.get("data_length", 0) == 0)
    
    def is_cancellation(self, frame: Dict[str, Any]) -> bool:
        """Check if frame is a cancellation (urb_status -2)"""
        return frame.get("urb_status") == "-2"
    
    def is_completion(self, frame: Dict[str, Any]) -> bool:
        """Check if frame is a completion (urb_type C)"""
        return frame.get("urb_type") == "C"
    
    def is_bulk_command_start(self, frame: Dict[str, Any]) -> bool:
        """Check if frame starts a bulk command sequence (0x01 S with data)"""
        return (frame.get("transfer_type") == "0x03" and 
                frame.get("endpoint_address") == "0x01" and
                frame.get("urb_type") == "S" and
                frame.get("data_length", 0) > 0)
    
    def is_bulk_command_ack(self, frame: Dict[str, Any]) -> bool:
        """Check if frame is bulk command ACK (0x01 C)"""
        return (frame.get("transfer_type") == "0x03" and 
                frame.get("endpoint_address") == "0x01" and
                frame.get("urb_type") == "C")
    
    def is_bulk_data_response(self, frame: Dict[str, Any]) -> bool:
        """Check if frame is bulk data response (0x81 C with data)"""
        return (frame.get("transfer_type") == "0x03" and 
                frame.get("endpoint_address") == "0x81" and
                frame.get("urb_type") == "C" and
                frame.get("data_length", 0) > 0)
    
    def should_start_new_transaction(self, frame: Dict[str, Any], frame_index: int) -> bool:
        """
        Determine if this frame should start a new transaction
        """
        urb_id = frame.get("urb_id", "")
        
        # First frame doesn't start a new transaction
        if frame_index == 0:
            return False
        
        # Check special cases that go to previous transaction
        if self.is_bulk_setup(frame) or self.is_cancellation(frame):
            return False
        
        # For bulk transfers, we want to group command sequences together
        if frame.get("transfer_type") == "0x03":
            # If this is a command start (0x01 S with data), start new transaction
            if self.is_bulk_command_start(frame):
                return True
            
            # If this is an ACK, data response, or setup - continue current transaction
            if (self.is_bulk_command_ack(frame) or 
                self.is_bulk_data_response(frame) or 
                self.is_bulk_setup(frame)):
                return False
        
        # For non-bulk transfers, use URB ID logic
        if not urb_id:
            return False
        
        # Check if this URB ID is truly new (not seen and not completed)
        is_truly_new_urb = urb_id not in self.seen_urb_ids and urb_id not in self.completed_urb_ids
        
        # OR if it was completed before, treat it as new (URB ID reuse)
        is_reused_urb = urb_id in self.completed_urb_ids and urb_id not in self.seen_urb_ids
        
        return is_truly_new_urb or is_reused_urb
    
    def process_frame(self, frame: Dict[str, Any], frame_index: int) -> int:
        """Process a frame and return its transaction ID"""
        urb_id = frame.get("urb_id", "")
        
        # Check if we should start a new transaction
        if self.should_start_new_transaction(frame, frame_index):
            self.current_transaction += 1
        
        # Handle URB ID tracking
        if urb_id:
            is_bulk_setup = self.is_bulk_setup(frame)
            is_cancellation = self.is_cancellation(frame)
            is_completion = self.is_completion(frame)
            
            if is_bulk_setup or is_cancellation:
                # Don't mark bulk setup or cancellation URB IDs as seen
                pass
            elif is_completion:
                # Mark completion URB IDs as completed (allows reuse)
                self.completed_urb_ids.add(urb_id)
                # Remove from seen so it can be reused
                self.seen_urb_ids.discard(urb_id)
            else:
                # Mark normal URB IDs as seen
                self.seen_urb_ids.add(urb_id)
            
        return self.current_transaction
    
    def split_transactions_dataframe(self, df: pl.DataFrame) -> pl.DataFrame:
        """Split DataFrame into proper transactions"""
        # Sort by frame_number to ensure proper order
        df = df.sort("frame_number")
        
        # Convert to list of dicts for processing
        rows = df.to_dicts()
        
        # Reset state
        self.current_transaction = 1
        self.seen_urb_ids = set()
        self.completed_urb_ids = set()
        
        # Process each frame
        for i, row in enumerate(rows):
            transaction_id = self.process_frame(row, i)
            row["transaction_id"] = transaction_id
        
        # Convert back to DataFrame
        return pl.DataFrame(rows)


def jsonl_to_dataframe(jsonl_file: str) -> pl.DataFrame:
    """Load JSONL file into DataFrame"""
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
    
    return pl.DataFrame(rows)


def dataframe_to_jsonl(df: pl.DataFrame, output_file: str) -> None:
    """Convert DataFrame back to JSONL format"""
    with open(output_file, "w") as f:
        for row in df.to_dicts():
            f.write(json.dumps(row) + "\n")
    
    print(f"Wrote {df.height:,} frames to {output_file}")


def validate_ordering(df: pl.DataFrame) -> bool:
    """Validate that all ordering requirements are met"""
    print("\n=== Validation Tests ===")
    
    frame_nums = df.select('frame_number').to_series().to_list()
    timestamps = df.select('timestamp').to_series().to_list() 
    tx_ids = df.select('transaction_id').to_series().to_list()
    
    # Test 1: Frame numbers ascending
    is_frame_ascending = all(frame_nums[i] <= frame_nums[i+1] for i in range(len(frame_nums)-1))
    print(f"1. Frame numbers in ascending order: {'✓ PASS' if is_frame_ascending else '✗ FAIL'}")
    
    # Test 2: Timestamps ascending  
    is_time_ascending = all(timestamps[i] <= timestamps[i+1] for i in range(len(timestamps)-1))
    print(f"2. Timestamps in ascending order: {'✓ PASS' if is_time_ascending else '✗ FAIL'}")
    
    # Test 3: Transaction IDs ascending
    is_tx_ascending = all(tx_ids[i] <= tx_ids[i+1] for i in range(len(tx_ids)-1))
    print(f"3. Transaction IDs in ascending order: {'✓ PASS' if is_tx_ascending else '✗ FAIL'}")
    
    return is_frame_ascending and is_time_ascending and is_tx_ascending


def analyze_bulk_sequences(df: pl.DataFrame) -> None:
    """Analyze bulk transfer sequences to verify grouping"""
    print("\n=== Bulk Transfer Sequence Analysis ===")
    
    # Look for bulk transfer transactions  
    bulk_frames = df.filter(pl.col("transfer_type") == "0x03")
    
    if bulk_frames.height == 0:
        print("No bulk transfer frames found")
        return
        
    # Group by transaction and analyze patterns
    bulk_transactions = bulk_frames.group_by("transaction_id").len().sort("transaction_id")
    
    print(f"Bulk transfer transactions: {bulk_transactions.height}")
    print("\nSample bulk sequences:")
    
    sample_count = 0
    for row in bulk_transactions.to_dicts():
        if sample_count >= 3:  # Show first 3 examples
            break
            
        tid = row['transaction_id']
        tx_frames = bulk_frames.filter(pl.col("transaction_id") == tid).sort("frame_number")
        
        if tx_frames.height >= 2:  # Multi-frame transactions
            print(f"\nTransaction {tid} ({tx_frames.height} frames):")
            for frame in tx_frames.to_dicts():
                frame_num = frame['frame_number']
                ep = frame['endpoint_address'] 
                urb_type = frame['urb_type']
                data_len = frame['data_length']
                direction = frame['direction']
                timestamp = frame['timestamp']
                
                print(f"  Frame {frame_num}: {timestamp:.6f} - {urb_type} ({ep}) {direction} Len={data_len}")
            
            sample_count += 1


def print_transaction_summary(df: pl.DataFrame) -> None:
    """Print summary of transactions"""
    print("\n=== Transaction Summary ===")
    
    transaction_stats = df.group_by("transaction_id").len().sort("transaction_id") 
    print(f"Total transactions: {transaction_stats.height}")
    print(f"Total frames: {df.height}")
    
    # Analyze transaction sizes
    avg_frames = df.height / transaction_stats.height
    print(f"Average frames per transaction: {avg_frames:.1f}")
    
    # Show size distribution
    size_1 = transaction_stats.filter(pl.col("len") == 1).height
    size_2_4 = transaction_stats.filter((pl.col("len") >= 2) & (pl.col("len") <= 4)).height  
    size_5_plus = transaction_stats.filter(pl.col("len") >= 5).height
    
    print(f"\nSize distribution:")
    print(f"  1 frame: {size_1} transactions")
    print(f"  2-4 frames: {size_2_4} transactions") 
    print(f"  5+ frames: {size_5_plus} transactions")


def main():
    input_file = "usb_dataset.jsonl"
    output_file = "usb_dataset_split_grouped.jsonl"
    
    if not Path(input_file).exists():
        print(f"ERROR: Input file {input_file} not found")
        return 1
    
    print(f"Reading {input_file}...")
    df = jsonl_to_dataframe(input_file)
    
    if df.height == 0:
        print("ERROR: No valid frames found")
        return 1
    
    print(f"Loaded {df.height:,} frames")
    
    # Create splitter and process
    splitter = USBTransactionSplitterGrouped()
    print("\nSplitting transactions (grouped bulk sequences)...")
    df_split = splitter.split_transactions_dataframe(df)
    
    # Validate ordering
    all_tests_pass = validate_ordering(df_split)
    
    # Analyze bulk sequences
    analyze_bulk_sequences(df_split)
    
    # Print summary
    print_transaction_summary(df_split)
    
    # Write result
    print(f"\nWriting to {output_file}...")
    dataframe_to_jsonl(df_split, output_file)
    
    if all_tests_pass:
        print("🎉 All tests PASSED! Transaction splitting complete.")
        return 0
    else:
        print("❌ Some tests FAILED. Please review the algorithm.")
        return 1


if __name__ == "__main__":
    sys.exit(main())