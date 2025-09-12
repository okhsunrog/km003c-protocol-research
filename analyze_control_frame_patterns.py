#!/usr/bin/env python3
"""
Analyzes control and bulk frame patterns in USB transaction data.

This script addresses two specific questions:
1. Verifies if it's true that there are never more than 6 consecutive bulk
   frames immediately preceding a control frame.
2. For each source file, calculates how far from the start of the capture
   the last control frame appears.
"""

import polars as pl
from pathlib import Path

def analyze_file(file_path: Path) -> dict:
    """
    Performs both analyses on a single JSONL file.

    Args:
        file_path: Path to the JSONL file.

    Returns:
        A dictionary containing the analysis results.
    """
    try:
        df = pl.read_ndjson(file_path).sort("frame_number")
    except Exception as e:
        return {"file": file_path.name, "error": f"Failed to read file: {e}"}

    # Analysis 1: Check for > 6 consecutive bulk frames before a control frame
    violation_found = False
    violation_detail = ""
    control_transfer_type = "0x02"
    bulk_transfer_type = "0x03"
    
    control_frame_indices = [i for i, t in enumerate(df["transfer_type"]) if t == control_transfer_type]

    for idx in control_frame_indices:
        if idx == 0:
            continue
        
        bulk_count = 0
        # Look backwards from the frame before the control frame
        for i in range(idx - 1, -1, -1):
            if df["transfer_type"][i] == bulk_transfer_type:
                bulk_count += 1
            else:
                break # Stop counting if a non-bulk frame is found
        
        if bulk_count > 6:
            violation_found = True
            control_frame_num = df["frame_number"][idx]
            violation_detail = (
                f"Rule violated: Found {bulk_count} bulk frames before control "
                f"frame {control_frame_num}."
            )
            break # Stop after first violation

    bulk_rule_result = "FAIL" if violation_found else "PASS"

    # Analysis 2: Find the position of the last control frame
    
    # Add a row number column to represent the chronological position
    df_with_pos = df.with_row_count("position")
    control_frames = df_with_pos.filter(pl.col("transfer_type") == control_transfer_type)
    
    last_control_frame_info = "No control frames found."
    if control_frames.height > 0:
        # Get the maximum position (i.e., the last chronological occurrence)
        last_pos_row = control_frames.select(pl.max("position")).item()
        
        # Find the frame number at that last position
        last_control_frame_num = df_with_pos.filter(pl.col("position") == last_pos_row).select("frame_number").item()
        
        total_frames = df_with_pos.height
        # Correct percentage calculation using position (0-indexed)
        percentage = ((last_pos_row + 1) / total_frames) * 100
        
        last_control_frame_info = (
            f"Last control frame is at frame_number {last_control_frame_num} "
            f"({percentage:.1f}% through the capture)."
        )

    return {
        "file": file_path.name,
        "bulk_rule_result": bulk_rule_result,
        "violation_detail": violation_detail,
        "last_control_frame_info": last_control_frame_info
    }

def main():
    """Main script execution."""
    source_dir = Path("transactions_per_source")
    if not source_dir.exists():
        print(f"Error: Directory not found: {source_dir}")
        return

    jsonl_files = sorted(list(source_dir.glob("*.jsonl")))
    if not jsonl_files:
        print(f"No JSONL files found in {source_dir}")
        return

    print("🔍 Analyzing control and bulk frame patterns...")
    
    for file_path in jsonl_files:
        result = analyze_file(file_path)
        
        print("\n" + "="*50)
        print(f"📄 Analysis for: {result['file']}")
        print("="*50)
        
        if "error" in result:
            print(f"⚠️ ERROR: {result['error']}")
            continue
            
        # Report on Rule 1
        print("Rule: Max 6 consecutive bulk frames before a control frame?")
        if result["bulk_rule_result"] == "PASS":
            print("  └─ ✅ PASS: The rule holds true for this file.")
        else:
            print(f"  └─ ❌ FAIL: {result['violation_detail']}")
            
        # Report on Question 2
        print("\nPosition of the last control frame:")
        print(f"  └─ {result['last_control_frame_info']}")

    print("\n" + "="*50)
    print("✅ Analysis complete for all files.")

if __name__ == "__main__":
    main()
