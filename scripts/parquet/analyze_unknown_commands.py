#!/usr/bin/env python3
"""
Analyze Unknown Commands in USB Captures

This script explores unknown command types (0x1A, 0x2C, 0x3A, 0x44, 0x4C, 0x75)
in the context of the captured USB sessions, using the existing analysis patterns.

The parquet dataset contains multiple capture sessions (source_file column).
"""

import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import polars as pl
from collections import defaultdict
from typing import Dict, List, Any

from km003c_analysis.core import split_usb_transactions, tag_transactions

try:
    from km003c_lib import parse_raw_packet
    KM003C_LIB_AVAILABLE = True
except ImportError:
    KM003C_LIB_AVAILABLE = False
    print("⚠️  km003c_lib not available, using manual parsing")


# Known command types (fully documented)
KNOWN_TYPES = {
    0x02: "Connect",
    0x03: "Disconnect",
    0x05: "Accept",
    0x06: "Rejected",
    0x0C: "GetData",
    0x0E: "StartGraph",
    0x0F: "StopGraph",
    0x10: "EnablePdMonitor",
    0x11: "DisablePdMonitor",
    0x40: "Head",
    0x41: "PutData",
}

# Documented but not in km003c-lib
DOCUMENTED_TYPES = {
    0x1A: "MemoryResponse26 (addr 0x420)",
    0x2C: "MemoryResponse44 (attr 0x564D)",
    0x34: "LogDataChunk1 (2544B)",
    0x3A: "MemoryResponse58 (addr 0x4420)",
    0x44: "MemoryDownload (request)",
    0x4C: "StreamingAuth",
    0x4E: "LogDataChunk2 (2544B)",
    0x68: "LogDataChunk4 (704B)",
    0x75: "MemoryResponse117 (addr 0x40010450)",
    0x76: "LogDataChunk3 (2544B)",
}

# Truly unknown types (found in firmware update captures)
UNKNOWN_TYPES = {
    0x00: "Unknown0",
    0x01: "Unknown1 (Sync?)",
    0x04: "Unknown4 (Reset?)",
    0x07: "Unknown7 (Finished?)",
    0x08: "Unknown8 (JumpAprom?)",
    0x09: "Unknown9 (JumpDfu?)",
    0x0B: "Unknown11 (Error?)",
    0x0D: "Unknown13 (GetFile?)",
}


def parse_header(payload_hex: str) -> Dict[str, Any]:
    """Parse 4-byte packet header from hex string."""
    if not payload_hex or len(payload_hex) < 8:
        return {}

    header_bytes = bytes.fromhex(payload_hex[:8])
    pkt_type = header_bytes[0] & 0x7F
    reserved = (header_bytes[0] >> 7) & 1
    tid = header_bytes[1]
    attr = int.from_bytes(header_bytes[2:4], 'little')

    return {
        "type": pkt_type,
        "type_hex": f"0x{pkt_type:02X}",
        "reserved": reserved,
        "tid": tid,
        "attribute": attr,
        "attribute_hex": f"0x{attr:04X}",
    }


def analyze_source_file(df: pl.DataFrame, source_file: str) -> Dict[str, Any]:
    """Analyze unknown commands in a specific source file."""
    source_df = df.filter(pl.col("source_file") == source_file)

    # Split into transactions and tag
    tx_df = split_usb_transactions(source_df)
    tagged_df = tag_transactions(tx_df)

    # Filter for bulk traffic with payload
    bulk_with_payload = tagged_df.filter(
        (pl.col("transfer_type") == "0x03") &
        pl.col("payload_hex").is_not_null() &
        (pl.col("payload_hex").str.len_chars() >= 8)
    )

    # Analyze packet types
    type_counts = defaultdict(int)
    unknown_packets = []
    unknown68_requests = []
    unknown68_responses = []

    for row in bulk_with_payload.iter_rows(named=True):
        header = parse_header(row["payload_hex"])
        if not header:
            continue

        pkt_type = header["type"]
        type_counts[pkt_type] += 1

        # Track documented or unknown types (not in km003c-lib)
        if pkt_type in DOCUMENTED_TYPES or pkt_type in UNKNOWN_TYPES:
            packet_info = {
                "frame": row["frame_number"],
                "transaction_id": row["transaction_id"],
                "endpoint": row["endpoint_address"],
                "urb_type": row["urb_type"],
                "type": pkt_type,
                "type_name": DOCUMENTED_TYPES.get(pkt_type) or UNKNOWN_TYPES.get(pkt_type) or f"0x{pkt_type:02X}",
                "tid": header["tid"],
                "attribute": header["attribute_hex"],
                "payload_preview": row["payload_hex"][:80],
                "payload_len": len(row["payload_hex"]) // 2,
            }
            unknown_packets.append(packet_info)

            # Separate Unknown68 requests vs responses
            if pkt_type == 0x44:
                if row["endpoint_address"] == "0x01":
                    unknown68_requests.append(packet_info)
                else:
                    unknown68_responses.append(packet_info)

    return {
        "source_file": source_file,
        "total_bulk_packets": len(bulk_with_payload),
        "total_transactions": tagged_df["transaction_id"].max() or 0,
        "type_counts": dict(type_counts),
        "unknown_packets": unknown_packets,
        "unknown68_requests": unknown68_requests,
        "unknown68_responses": unknown68_responses,
    }


def print_analysis(analysis: Dict[str, Any]):
    """Print analysis results."""
    print(f"\n{'='*70}")
    print(f"Source: {analysis['source_file']}")
    print(f"{'='*70}")
    print(f"Total bulk packets: {analysis['total_bulk_packets']:,}")
    print(f"Total transactions: {analysis['total_transactions']}")

    # Type distribution
    print(f"\nPacket Type Distribution:")
    for pkt_type, count in sorted(analysis["type_counts"].items()):
        name = KNOWN_TYPES.get(pkt_type) or DOCUMENTED_TYPES.get(pkt_type) or UNKNOWN_TYPES.get(pkt_type) or "?"
        if pkt_type in KNOWN_TYPES:
            marker = "  "  # Implemented in km003c-lib
        elif pkt_type in DOCUMENTED_TYPES:
            marker = "📄"  # Documented but not implemented
        else:
            marker = "❓"  # Truly unknown
        print(f"  {marker} 0x{pkt_type:02X} ({name:<30}): {count:>5}")

    # Unknown command details
    unknown = analysis["unknown_packets"]
    if unknown:
        print(f"\nUnknown Command Details ({len(unknown)} packets):")

        # Group by type
        by_type = defaultdict(list)
        for pkt in unknown:
            by_type[pkt["type"]].append(pkt)

        for pkt_type in sorted(by_type.keys()):
            packets = by_type[pkt_type]
            type_name = DOCUMENTED_TYPES.get(pkt_type) or UNKNOWN_TYPES.get(pkt_type) or f"Unknown"
            print(f"\n  --- {type_name} (0x{pkt_type:02X}) ---")
            print(f"  Count: {len(packets)}")

            # Show first few examples
            for i, pkt in enumerate(packets[:3]):
                direction = "OUT" if pkt["endpoint"] == "0x01" else "IN"
                print(f"    [{i+1}] Frame {pkt['frame']}, TX#{pkt['transaction_id']}, "
                      f"{direction}, TID=0x{pkt['tid']:02X}, attr={pkt['attribute']}")
                print(f"        Payload ({pkt['payload_len']}B): {pkt['payload_preview']}...")

            if len(packets) > 3:
                print(f"    ... and {len(packets) - 3} more")

    # Unknown68 request-response correlation
    if analysis["unknown68_requests"]:
        print(f"\n  --- Unknown68 Request/Response Flow ---")
        print(f"  Requests (OUT): {len(analysis['unknown68_requests'])}")
        print(f"  Responses (IN): {len(analysis['unknown68_responses'])}")

        # Show the flow
        all_68 = sorted(
            analysis["unknown68_requests"] + analysis["unknown68_responses"],
            key=lambda x: x["frame"]
        )
        print(f"\n  Sequence:")
        for pkt in all_68[:10]:
            direction = "→ OUT" if pkt["endpoint"] == "0x01" else "← IN "
            print(f"    Frame {pkt['frame']:>5}: {direction} TID=0x{pkt['tid']:02X} "
                  f"attr={pkt['attribute']} ({pkt['payload_len']}B)")


def main():
    dataset_path = Path("data/processed/usb_master_dataset.parquet")
    if not dataset_path.exists():
        print(f"❌ Dataset not found: {dataset_path}")
        return 1

    print("=" * 70)
    print("UNKNOWN COMMANDS ANALYSIS")
    print("=" * 70)

    df = pl.read_parquet(dataset_path)
    print(f"Loaded {len(df):,} packets from {df['source_file'].n_unique()} captures")

    # Find captures with unknown commands
    source_files = df["source_file"].unique().sort().to_list()

    captures_with_unknown = []

    for source_file in source_files:
        # Quick check for unknown types
        source_df = df.filter(pl.col("source_file") == source_file)
        bulk_payloads = source_df.filter(
            (pl.col("transfer_type") == "0x03") &
            pl.col("payload_hex").is_not_null()
        )

        has_unknown = False
        for payload in bulk_payloads["payload_hex"].head(500):
            if payload and len(payload) >= 2:
                pkt_type = int(payload[:2], 16) & 0x7F
                if pkt_type in DOCUMENTED_TYPES or pkt_type in UNKNOWN_TYPES:
                    has_unknown = True
                    break

        if has_unknown:
            captures_with_unknown.append(source_file)

    print(f"\nCaptures with unknown commands: {len(captures_with_unknown)}")
    for sf in captures_with_unknown:
        print(f"  • {sf}")

    # Analyze each capture with unknown commands
    for source_file in captures_with_unknown:
        analysis = analyze_source_file(df, source_file)
        print_analysis(analysis)

    # Summary
    print(f"\n{'='*70}")
    print("SUMMARY")
    print("="*70)
    print("""
Command Type Categories:

  IMPLEMENTED (in km003c-lib):
    0x02 Connect, 0x03 Disconnect, 0x05 Accept, 0x06 Rejected
    0x0C GetData, 0x0E StartGraph, 0x0F StopGraph, 0x41 PutData

  DOCUMENTED (reversed, not yet in library):
    0x10 EnablePdMonitor  - Enable PD sniffer mode
    0x11 DisablePdMonitor - Disable PD sniffer mode
    0x44 MemoryDownload   - AES-128 ECB encrypted requests
    0x4C StreamingAuth    - Required for AdcQueue (vestigial DRM)
    0x1A/0x2C/0x3A/0x75   - Memory response types for 0x44
    0x34/0x4E/0x68/0x76   - Offline log data chunks (encrypted)

  TRULY UNKNOWN (seen in firmware updates):
    0x00, 0x01, 0x04, 0x07, 0x08, 0x09, 0x0B, 0x0D, etc.
    - Likely bootloader/DFU commands
    - Need further analysis of firmware update captures

See docs/unknown_commands_tracker.md for full status.
""")

    return 0


if __name__ == "__main__":
    exit(main())
