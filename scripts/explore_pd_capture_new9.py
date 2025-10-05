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
from km003c_lib import parse_packet, parse_raw_packet
try:
    from scripts.km003c_helpers import (
        get_packet_type,
        get_adc_data,
        get_pd_status,
        get_pd_events,
    )
except Exception:
    from km003c_helpers import (
        get_packet_type,
        get_adc_data,
        get_pd_status,
        get_pd_events,
    )


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
        try:
            pkt = parse_packet(payload_bytes)
            if get_packet_type(pkt) != "DataResponse":
                continue
            raw = parse_raw_packet(payload_bytes)
            if not (isinstance(raw, dict) and "Data" in raw):
                continue
            lps = raw["Data"].get("logical_packets", []) or []
            if not lps:
                continue
            first = lps[0]
            entry = {
                "transaction_id": row["transaction_id"],
                "timestamp": row["timestamp"],
                "payload_hex": payload_hex,
                "payload_len": len(payload_bytes),
                "msg_type": 65,
                "msg_id": raw["Data"]["header"].get("id"),
                "attribute": first.get("attribute"),
                "next": first.get("next"),
                "chunk": first.get("chunk"),
                "size_bytes": first.get("size"),
                "obj_count": raw["Data"]["header"].get("obj_count_words"),
                "endpoint": row["endpoint_address"],
            }
            pd_candidates.append(entry)
            has_adc = any(lp.get("attribute") == 1 for lp in lps)
            has_pd = any(lp.get("attribute") == 16 for lp in lps)
            if has_adc and has_pd:
                adc_pd_combined.append(entry)
            elif has_pd and not has_adc:
                pd_lp = next((lp for lp in lps if lp.get("attribute") == 16), {})
                entry_pd = dict(entry)
                entry_pd["size_bytes"] = pd_lp.get("size")
                pd_only_responses.append(entry_pd)
        except Exception:
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
            try:
                pkt = parse_packet(payload_bytes)
                if get_packet_type(pkt) != "DataResponse":
                    continue
                pdev = get_pd_events(pkt)
                if pdev is None:
                    print("No PdEventStream present")
                    continue
                events = getattr(pdev, "events", [])
                for ev in events:
                    wd = getattr(ev, "wire_data", None)
                    if wd is None:
                        continue
                    wb = bytes(wd)
                    print(f"  PD wire ({len(wb)} bytes): {wb.hex()}")
                    try:
                        pd_msg = usbpdpy.parse_pd_message(wb)
                        print(f"  ✅ PD message parsed: {pd_msg.header.message_type}")
                    except Exception as e:
                        print(f"  ❌ PD parse failed: {e}")
            except Exception:
                continue

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
                try:
                    pkt = parse_packet(payload_bytes)
                    if get_packet_type(pkt) != "DataResponse":
                        continue
                    pdev = get_pd_events(pkt)
                    pdst = get_pd_status(pkt)
                    if pdst is not None:
                        print("  PD status present (12 bytes)")
                    if pdev is not None:
                        events = getattr(pdev, "events", [])
                        for ev in events:
                            wd = getattr(ev, "wire_data", None)
                            if wd is None:
                                continue
                            wb = bytes(wd)
                            print(f"  PD wire ({len(wb)} bytes): {wb.hex()}")
                            try:
                                pd_msg = usbpdpy.parse_pd_message(wb)
                                print(f"    ✅ {pd_msg.header.message_type}")
                            except Exception as e:
                                print(f"    ❌ Parse failed: {e}")
                except Exception:
                    continue

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
