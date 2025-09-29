#!/usr/bin/env python3
"""
Explore pd_capture_new.9 from USB master dataset for PD message extraction

Focus on correlating USB capture data with SQLite export findings. The SQLite export
contained 11 PD messages including Source_Capabilities, Request, Accept, PS_RDY.
Let's see if we can extract the same messages from the USB capture.

From previous research: pd_capture_new.9 contains PD-related activity between
transactions, including ADC+PD combined packets and PD-only responses.
"""

import polars as pl
import sys
from pathlib import Path
import usbpdpy

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from km003c_analysis.core import split_usb_transactions, tag_transactions


def explore_pd_capture_new9():
    """Explore pd_capture_new.9 for PD message extraction."""

    print("=== EXPLORING PD_CAPTURE_NEW.9 FOR PD MESSAGE EXTRACTION ===")
    print()

    # Load the master dataset
    dataset_path = Path("data/processed/usb_master_dataset.parquet")
    if not dataset_path.exists():
        print(f"❌ Dataset not found: {dataset_path}")
        return

    # Filter for pd_capture_new.9
    df = pl.read_parquet(dataset_path)
    pd_capture = df.filter(pl.col("source_file") == "pd_capture_new.9")

    print(f"Total USB packets in pd_capture_new.9: {len(pd_capture)}")

    # Process into transactions
    print("Processing USB transactions...")
    transactions = split_usb_transactions(pd_capture)
    tagged_transactions = tag_transactions(transactions)

    print(f"Total transactions: {len(tagged_transactions)}")
    print()

    # From previous research findings, look for:
    # 1. ADC+PD combined packets (attribute=1, next=1, total_len=68)
    # 2. PD-only responses (attribute=16, various sizes including 12, 18, 28, 88, 108)

    # Analyze payload patterns focusing on PD extraction
    print("=== ANALYZING PAYLOAD PATTERNS FOR PD EXTRACTION ===")

    pd_candidates = []
    adc_pd_combined = []
    pd_only_responses = []

    # Extract payloads with sufficient length
    payload_df = tagged_transactions.filter(
        pl.col("payload_hex").is_not_null() &
        (pl.col("payload_hex").str.len_chars() >= 16)  # At least 8 bytes
    ).select([
        "transaction_id",
        "timestamp",
        "payload_hex",
        "endpoint_address",
        "transfer_type",
        "urb_type"
    ])

    print(f"Payloads to analyze: {len(payload_df)}")

    for row in payload_df.iter_rows(named=True):
        payload_hex = row["payload_hex"]
        payload_bytes = bytes.fromhex(payload_hex)
        payload_len = len(payload_bytes)

        # Skip very short payloads
        if payload_len < 8:
            continue

        # Parse KM003C headers if possible
        try:
            # Try to parse main header (first 4 bytes) and extended header (next 4 bytes)
            if payload_len >= 8:
                main_header = int.from_bytes(payload_bytes[0:4], 'little')
                ext_header = int.from_bytes(payload_bytes[4:8], 'little')

                # Extract fields from headers
                msg_type = main_header & 0x7F
                extend = (main_header >> 7) & 1
                msg_id = (main_header >> 8) & 0xFF
                obj_count = (main_header >> 22) & 0x3FF

                attribute = ext_header & 0x7FFF
                next_bit = (ext_header >> 15) & 1
                chunk = (ext_header >> 16) & 0x3F
                size_bytes = (ext_header >> 22) & 0x3FF

                # Focus on PutData responses (type 65 / 0x41)
                if msg_type == 65:  # PutData
                    entry = {
                        "transaction_id": row["transaction_id"],
                        "timestamp": row["timestamp"],
                        "payload_hex": payload_hex,
                        "payload_len": payload_len,
                        "msg_type": msg_type,
                        "msg_id": msg_id,
                        "attribute": attribute,
                        "next": next_bit,
                        "chunk": chunk,
                        "size_bytes": size_bytes,
                        "obj_count": obj_count,
                        "endpoint": row["endpoint_address"],
                    }

                    # Categorize based on previous findings
                    if attribute == 1 and next_bit == 1:
                        # ADC+PD combined (should be 68 bytes total)
                        adc_pd_combined.append(entry)
                    elif attribute == 16:
                        # PD-only response
                        pd_only_responses.append(entry)

                    pd_candidates.append(entry)

        except Exception as e:
            continue

    print(f"PutData packets found: {len(pd_candidates)}")
    print(f"ADC+PD combined packets: {len(adc_pd_combined)}")
    print(f"PD-only responses: {len(pd_only_responses)}")
    print()

    # Analyze ADC+PD combined packets
    if adc_pd_combined:
        print("=== ADC+PD COMBINED PACKET ANALYSIS ===")
        print(f"Found {len(adc_pd_combined)} ADC+PD combined packets")

        for i, packet in enumerate(adc_pd_combined[:3]):  # Show first 3
            print(f"--- ADC+PD #{i+1} (tx {packet['transaction_id']}) ---")
            print(f"Timestamp: {packet['timestamp']:.6f}s")
            print(f"Total length: {packet['payload_len']} bytes")
            print(f"Size field: {packet['size_bytes']} bytes")

            # According to chained payload model:
            # - First 8 bytes: main + extended headers
            # - Next 44 bytes: ADC payload (attribute=1, size=44)
            # - Then should be another 4-byte extended header for PD
            # - Followed by PD payload (12 bytes typical)

            payload_bytes = bytes.fromhex(packet["payload_hex"])

            if len(payload_bytes) >= 52:  # 8 headers + 44 ADC
                # Look for nested PD header at offset 52
                if len(payload_bytes) >= 56:  # Room for PD extended header
                    pd_ext_header = int.from_bytes(payload_bytes[52:56], 'little')
                    pd_attribute = pd_ext_header & 0x7FFF
                    pd_next = (pd_ext_header >> 15) & 1
                    pd_size = (pd_ext_header >> 22) & 0x3FF

                    print(f"Nested PD header found:")
                    print(f"  PD attribute: {pd_attribute}")
                    print(f"  PD next: {pd_next}")
                    print(f"  PD size: {pd_size}")

                    # Extract PD payload
                    if len(payload_bytes) >= 56 + pd_size:
                        pd_payload = payload_bytes[56:56+pd_size]
                        print(f"  PD payload ({len(pd_payload)} bytes): {pd_payload.hex()}")

                        # Try to parse as PD message
                        try:
                            pd_msg = usbpdpy.parse_pd_message(pd_payload)
                            print(f"  ✅ PD message parsed: {pd_msg.header.message_type}")
                        except Exception as e:
                            print(f"  ❌ PD parse failed: {e}")

            print()

    # Analyze PD-only responses
    if pd_only_responses:
        print("=== PD-ONLY RESPONSE ANALYSIS ===")
        print(f"Found {len(pd_only_responses)} PD-only responses")

        # Group by size
        by_size = {}
        for packet in pd_only_responses:
            size = packet['size_bytes']
            if size not in by_size:
                by_size[size] = []
            by_size[size].append(packet)

        print("Size distribution:", {k: len(v) for k, v in by_size.items()})

        for size, packets in sorted(by_size.items()):
            print(f"\n--- PD-only responses with size={size} bytes ---")

            for i, packet in enumerate(packets[:2]):  # Show first 2 of each size
                print(f"Packet #{i+1} (tx {packet['transaction_id']}):")
                print(f"  Timestamp: {packet['timestamp']:.6f}s")
                print(f"  Total length: {packet['payload_len']} bytes")

                payload_bytes = bytes.fromhex(packet["payload_hex"])

                # PD payload should start after headers (8 bytes)
                if len(payload_bytes) > 8:
                    pd_payload_candidate = payload_bytes[8:8+size]
                    print(f"  PD candidate ({len(pd_payload_candidate)} bytes): {pd_payload_candidate.hex()}")

                    # Try different parsing approaches for larger payloads
                    if size > 12:
                        print(f"  Large payload - trying wrapped event parsing...")
                        # Try the wrapped event format parsing like SQLite
                        # Skip preamble and look for event headers

                    else:
                        # Simple PD status format (12 bytes)
                        try:
                            pd_msg = usbpdpy.parse_pd_message(pd_payload_candidate)
                            print(f"  ✅ PD message parsed: {pd_msg.header.message_type}")
                        except Exception as e:
                            print(f"  ❌ PD parse failed: {e}")

    print()
    print("=== SUMMARY ===")
    print(f"Total PD-related packets found: {len(pd_candidates)}")
    print(f"ADC+PD combined: {len(adc_pd_combined)}")
    print(f"PD-only responses: {len(pd_only_responses)}")

    return {
        "pd_candidates": pd_candidates,
        "adc_pd_combined": adc_pd_combined,
        "pd_only_responses": pd_only_responses
    }


if __name__ == "__main__":
    results = explore_pd_capture_new9()