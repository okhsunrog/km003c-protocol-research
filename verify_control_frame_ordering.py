#!/usr/bin/env python3
"""
Verifies that control frames only appear at the beginning of a session.

This script inspects all JSONL files in the transactions_per_source directory
to check if the following hypothesis is true: "control frames are always only in
the beginning of the transfer".

It iterates through each frame in a capture session chronologically. If it
encounters a control frame after a non-control frame has already been seen,
it reports a violation for that session.
"""

import polars as pl
from pathlib import Path
import json

def verify_control_frame_ordering(file_path: Path) -> dict:
    """
    Verifies that control frames only appear at the start of a capture.

    Args:
        file_path: Path to the JSONL file for a single capture session.

    Returns:
        A dictionary containing the verification result.
    """
    try:
        # read_ndjson can handle the blank lines between transactions
        df = pl.read_ndjson(file_path)
    except Exception as e:
        return {"file": file_path.name, "result": "error", "details": f"Failed to read file: {e}"}

    if "frame_number" not in df.columns:
        return {"file": file_path.name, "result": "error", "details": "Missing 'frame_number' column"}
        
    df = df.sort("frame_number")

    non_control_seen = False
    control_transfer_type = "0x02"

    for frame in df.to_dicts():
        transfer_type = frame.get("transfer_type")

        if transfer_type != control_transfer_type:
            non_control_seen = True
        elif non_control_seen:
            # Violation: Control frame found after a non-control frame
            return {
                "file": file_path.name,
                "result": "fail",
                "details": f"Control frame found at frame_number {frame.get('frame_number')} after non-control frames."
            }
            
    return {"file": file_path.name, "result": "pass"}

def main():
    """Main script execution."""
    source_dir = Path("transactions_per_source")
    if not source_dir.exists():
        print(f"Error: Directory not found: {source_dir}")
        return

    results = []
    jsonl_files = sorted(list(source_dir.glob("*.jsonl")))

    if not jsonl_files:
        print(f"No JSONL files found in {source_dir}")
        return

    print(f"🔍 Verifying control frame ordering for {len(jsonl_files)} source files...")
    print("-" * 50)

    for file_path in jsonl_files:
        result = verify_control_frame_ordering(file_path)
        results.append(result)

    all_passed = True
    for res in results:
        if res["result"] == "pass":
            print(f"✅ PASS: {res['file']}")
        elif res["result"] == "fail":
            all_passed = False
            print(f"❌ FAIL: {res['file']}")
            print(f"   └─ {res['details']}")
        else:
            all_passed = False
            print(f"⚠️ ERROR: {res['file']}")
            print(f"   └─ {res['details']}")

    print("-" * 50)
    if all_passed:
        print("🎉 Hypothesis confirmed: Control frames only appear at the beginning of all sessions.")
    else:
        print("Hypothesis rejected: Some sessions have control frames after non-control frames.")

if __name__ == "__main__":
    main()
