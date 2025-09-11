#!/usr/bin/env python3
"""
Final corrected USB transaction splitter.

Key insights:
1. Bulk setup frames go to previous transaction
2. Cancellation frames go to previous transaction  
3. Don't mark bulk setup/cancellation URB IDs as "seen" so completions can start new transactions
4. Handle URB ID reuse: mark URB IDs as "seen" after their completion frames
"""

import polars as pl
import json
import sys
from pathlib import Path
from typing import Set, Dict, Any


class USBTransactionSplitterFinal:
    """Final corrected USB transaction splitter"""
    
    def __init__(self):
        self.current_transaction = 1
        self.seen_urb_ids: Set[str] = set()
        self.completed_urb_ids: Set[str] = set()  # Track completed URB IDs
    
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
    
    def should_start_new_transaction(self, frame: Dict[str, Any], frame_index: int) -> bool:
        """
        Determine if this frame should start a new transaction
        """
        urb_id = frame.get("urb_id", "")
        
        # Must have URB ID
        if not urb_id:
            return False
        
        # Check if this URB ID is truly new (not seen and not completed)
        is_truly_new_urb = urb_id not in self.seen_urb_ids and urb_id not in self.completed_urb_ids
        
        # OR if it was completed before, treat it as new (URB ID reuse)
        is_reused_urb = urb_id in self.completed_urb_ids and urb_id not in self.seen_urb_ids
        
        is_new_urb = is_truly_new_urb or is_reused_urb
        
        if not is_new_urb:
            return False
            
        # First frame doesn't start a new transaction (it starts transaction 1)
        if frame_index == 0:
            return False
        
        # Check special cases
        is_bulk_setup = self.is_bulk_setup(frame)
        is_cancellation = self.is_cancellation(frame)
        
        # Don't start new transaction for bulk setup frames  
        if is_bulk_setup:
            return False
            
        # Don't start new transaction for cancellations
        if is_cancellation:
            return False
        
        return True
    
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
                # This allows their completion/related frames to start new transactions
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


def print_transaction_summary(df: pl.DataFrame) -> None:
    """Print summary of transactions"""
    print("\n=== Transaction Summary ===")
    
    transaction_stats = df.group_by("transaction_id").len().sort("transaction_id") 
    print(f"Total transactions: {transaction_stats.height}")
    print(f"Total frames: {df.height}")
    
    # Show transactions with concerning sizes
    large_transactions = transaction_stats.filter(pl.col("len") > 10).to_dicts()
    if large_transactions:
        print(f"\nTransactions with >10 frames:")
        for row in large_transactions:
            tid = row['transaction_id']
            count = row['len']
            
            # Get frame range for this transaction
            tx_frames = df.filter(pl.col("transaction_id") == tid).sort("frame_number")
            first_frame = tx_frames.head(1).to_dicts()[0]['frame_number']
            last_frame = tx_frames.tail(1).to_dicts()[0]['frame_number']
            
            size_indicator = " ⚠️" if count > 20 else ""
            print(f"  Transaction {tid:2d}: {count:3d} frames (#{first_frame:3d}-{last_frame:3d}){size_indicator}")
    else:
        print("\n✅ All transactions have ≤10 frames (good distribution)")


def main():
    input_file = "usb_dataset.jsonl"
    output_file = "usb_dataset_split_final.jsonl"
    
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
    splitter = USBTransactionSplitterFinal()
    print("\nSplitting transactions (final corrected algorithm)...")
    df_split = splitter.split_transactions_dataframe(df)
    
    # Validate ordering
    all_tests_pass = validate_ordering(df_split)
    
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