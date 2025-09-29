#!/usr/bin/env python3
"""
Extract PD messages from USB capture data - Deep dive analysis

The initial exploration found that:
- 12-byte PD payloads are KM003C status data (not PD wire messages)
- Larger payloads (18, 28, 88, 108 bytes) contain actual PD messages
- Patterns like 'a1612c91...' and '8210dc70...' match our SQLite findings

Let's parse these larger payloads using the wrapped event format.
"""

import polars as pl
import sys
from pathlib import Path
import usbpdpy

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from km003c_analysis.core import split_usb_transactions, tag_transactions


def parse_wrapped_pd_events(payload_bytes, offset=0):
    """Parse wrapped PD events from KM003C payload, similar to SQLite format."""
    events = []

    # Look for event patterns in the payload
    # Based on SQLite findings, events have size_flag + timestamp + sop + wire_bytes format
    i = offset

    while i < len(payload_bytes) - 6:
        # Look for potential event header patterns
        # Check if this could be a size flag (reasonable wire length)
        size_flag = payload_bytes[i]
        potential_wire_len = (size_flag & 0x3F) - 5

        # Valid wire lengths for PD messages are typically 4-32 bytes
        if potential_wire_len < 2 or potential_wire_len > 32:
            i += 1
            continue

        if i + 6 + potential_wire_len > len(payload_bytes):
            i += 1
            continue

        # Extract event header
        timestamp = int.from_bytes(payload_bytes[i+1:i+5], 'little')
        sop = payload_bytes[i+5]
        wire_bytes = payload_bytes[i+6:i+6+potential_wire_len]

        # Basic validation - check if this looks like a valid PD message
        if len(wire_bytes) >= 2:  # Minimum for header
            # Try to validate as PD message format
            try:
                # Basic header validation - first 2 bytes should form valid PD header
                header_word = int.from_bytes(wire_bytes[0:2], 'little')
                msg_type = (header_word >> 0) & 0x1F
                # Valid PD message types are 1-31
                if 1 <= msg_type <= 31:
                    events.append({
                        "timestamp": timestamp,
                        "sop": sop,
                        "wire_len": potential_wire_len,
                        "wire_bytes": wire_bytes,
                        "wire_hex": wire_bytes.hex()
                    })
                    i += 6 + potential_wire_len
                    continue
            except:
                pass

        i += 1

    return events


def extract_pd_messages_from_capture():
    """Extract actual PD messages from pd_capture_new.9 USB data."""

    print("=== EXTRACTING PD MESSAGES FROM USB CAPTURE ===")
    print()

    # Load and filter data
    dataset_path = Path("data/processed/usb_master_dataset.parquet")
    df = pl.read_parquet(dataset_path)
    pd_capture = df.filter(pl.col("source_file") == "pd_capture_new.9")

    # Process transactions
    transactions = split_usb_transactions(pd_capture)
    tagged_transactions = tag_transactions(transactions)

    # Focus on larger PD payloads that should contain actual PD messages
    payload_df = tagged_transactions.filter(
        pl.col("payload_hex").is_not_null() &
        (pl.col("payload_hex").str.len_chars() >= 40)  # At least 20 bytes
    ).select([
        "transaction_id",
        "timestamp",
        "payload_hex",
        "endpoint_address"
    ])

    pd_messages_found = []
    source_capabilities_found = []

    for row in payload_df.iter_rows(named=True):
        payload_hex = row["payload_hex"]
        payload_bytes = bytes.fromhex(payload_hex)
        payload_len = len(payload_bytes)

        # Try parsing KM003C headers
        try:
            if payload_len >= 8:
                main_header = int.from_bytes(payload_bytes[0:4], 'little')
                ext_header = int.from_bytes(payload_bytes[4:8], 'little')

                msg_type = main_header & 0x7F
                attribute = ext_header & 0x7FFF
                size_bytes = (ext_header >> 22) & 0x3FF

                # Focus on PutData with PD attribute (16) and larger sizes
                if msg_type == 65 and attribute == 16 and size_bytes > 12:
                    print(f"--- Transaction {row['transaction_id']} at {row['timestamp']:.6f}s ---")
                    print(f"Payload length: {payload_len} bytes, PD size: {size_bytes} bytes")

                    # Extract the PD portion (after 8-byte headers)
                    pd_section = payload_bytes[8:8+size_bytes]
                    print(f"PD section ({len(pd_section)} bytes): {pd_section.hex()}")

                    # Try wrapped event parsing
                    events = parse_wrapped_pd_events(pd_section)
                    print(f"Parsed {len(events)} wrapped events")

                    # Also look for known patterns directly in the payload
                    known_patterns = [
                        "a1612c9101082cd102002cc103002cb10400454106003c21dcc0",  # Source_Capabilities
                        "a1632c9101082cd102002cc103002cb10400454106003c21dcc0",  # Source_Capabilities (variant)
                        "8210dc700323",  # Request
                        "4102", "2101", "a305", "4104", "a607", "4106"  # GoodCRC, Accept, PS_RDY
                    ]

                    pd_hex = pd_section.hex()
                    found_direct_patterns = []
                    for pattern in known_patterns:
                        if pattern in pd_hex:
                            start_idx = pd_hex.find(pattern)
                            found_direct_patterns.append({
                                "pattern": pattern,
                                "offset": start_idx // 2
                            })

                    if found_direct_patterns:
                        print(f"  Found {len(found_direct_patterns)} known PD patterns:")
                        for p in found_direct_patterns:
                            pattern_bytes = bytes.fromhex(p["pattern"])
                            try:
                                pd_msg = usbpdpy.parse_pd_message(pattern_bytes)
                                print(f"    ✅ {pd_msg.header.message_type} at offset {p['offset']}: {p['pattern']}")

                                # Track message details
                                msg_info = {
                                    "transaction_id": row['transaction_id'],
                                    "timestamp": row['timestamp'],
                                    "message_type": pd_msg.header.message_type,
                                    "wire_hex": p['pattern'],
                                    "wire_len": len(pattern_bytes),
                                    "message": pd_msg,
                                    "offset": p['offset']
                                }
                                pd_messages_found.append(msg_info)

                                # Special handling for Source_Capabilities
                                if pd_msg.header.message_type == "Source_Capabilities":
                                    source_capabilities_found.append(msg_info)
                                    print(f"      📋 Found Source_Capabilities with {len(pd_msg.data_objects)} PDOs")

                            except Exception as e:
                                print(f"    ❓ Pattern at offset {p['offset']}: {p['pattern']} ({e})")

                    for i, event in enumerate(events):
                        print(f"  Event {i+1}: {event['wire_len']} bytes - {event['wire_hex']}")

                        # Try to parse as PD message
                        try:
                            pd_msg = usbpdpy.parse_pd_message(event['wire_bytes'])
                            print(f"    ✅ {pd_msg.header.message_type}")

                            # Track message details (if not already found via direct pattern matching)
                            wire_hex = event['wire_hex']
                            if not any(p['pattern'] == wire_hex for p in found_direct_patterns):
                                msg_info = {
                                    "transaction_id": row['transaction_id'],
                                    "timestamp": row['timestamp'],
                                    "event_timestamp": event['timestamp'],
                                    "message_type": pd_msg.header.message_type,
                                    "wire_hex": wire_hex,
                                    "wire_len": event['wire_len'],
                                    "message": pd_msg
                                }
                                pd_messages_found.append(msg_info)

                                # Special handling for Source_Capabilities
                                if pd_msg.header.message_type == "Source_Capabilities":
                                    source_capabilities_found.append(msg_info)
                                    print(f"    📋 Found Source_Capabilities with {len(pd_msg.data_objects)} PDOs")

                        except Exception as e:
                            print(f"    ❌ Parse failed: {e}")

                    print()

        except Exception as e:
            continue

    print("=== EXTRACTION RESULTS ===")
    print(f"Total PD messages extracted: {len(pd_messages_found)}")

    # Message type summary
    if pd_messages_found:
        msg_types = {}
        for msg in pd_messages_found:
            msg_type = msg["message_type"]
            msg_types[msg_type] = msg_types.get(msg_type, 0) + 1

        print("Message types found:", msg_types)
        print()

        # Show chronological order
        sorted_messages = sorted(pd_messages_found, key=lambda x: x["timestamp"])
        print("=== CHRONOLOGICAL PD MESSAGE SEQUENCE ===")
        for msg in sorted_messages:
            print(f"{msg['timestamp']:.3f}s: {msg['message_type']} (tx {msg['transaction_id']})")
        print()

    # Analyze Source_Capabilities if found
    if source_capabilities_found:
        print("=== SOURCE_CAPABILITIES ANALYSIS ===")
        for i, sc in enumerate(source_capabilities_found):
            print(f"Source_Capabilities #{i+1} at {sc['timestamp']:.3f}s:")
            print(f"  Wire hex: {sc['wire_hex']}")
            print(f"  PDOs: {len(sc['message'].data_objects)}")

            # Compare with SQLite findings
            expected_hex = "a1612c9101082cd102002cc103002cb10400454106003c21dcc0"
            if sc['wire_hex'] == expected_hex:
                print("  ✅ MATCHES SQLite export data!")
            else:
                print("  ⚠️  Different from SQLite export")
                print(f"  Expected: {expected_hex}")
            print()

    return {
        "pd_messages": pd_messages_found,
        "source_capabilities": source_capabilities_found
    }


if __name__ == "__main__":
    results = extract_pd_messages_from_capture()