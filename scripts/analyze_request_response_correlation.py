#!/usr/bin/env python3
"""
Comprehensive analysis of request-response correlations in KM003C protocol.

This script analyzes the USB master dataset to:
1. Process each source_file separately
2. Split into USB transactions
3. Correlate GetData requests (attribute_mask) with PutData responses (attributes)
4. Identify patterns and mappings between request masks and response attributes

Run: uv run python scripts/analyze_request_response_correlation.py
"""

from __future__ import annotations

import polars as pl
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from collections import defaultdict
import json

# Local package imports
from km003c_analysis.core import split_usb_transactions, tag_transactions

# Import the Rust library for KM003C packet parsing
try:
    from km003c_lib import parse_packet, parse_raw_packet
    KM003C_LIB_AVAILABLE = True
except ImportError:
    print("⚠️  km003c_lib not available - will parse headers manually")
    KM003C_LIB_AVAILABLE = False


@dataclass
class RequestHeader:
    """Parsed GetData request header"""
    packet_type: int  # Should be 0x0C for GetData
    reserved_flag: bool
    transaction_id: int
    attribute_mask: int  # 15-bit bitmask (wire: same values as extended header)
    raw_hex: str


@dataclass
class ResponseHeader:
    """Parsed PutData main header"""
    packet_type: int  # Should be 0x41 for PutData
    reserved_flag: bool
    transaction_id: int
    obj_count_words: int
    raw_hex: str


@dataclass
class LogicalPacket:
    """Parsed logical packet within PutData"""
    attribute: int  # 1=ADC, 2=AdcQueue, 8=Settings, 16=PdPacket
    next_flag: bool  # True if another logical packet follows
    chunk: int
    size_bytes: int
    payload_hex: str


@dataclass
class TransactionPair:
    """Request-Response transaction pair"""
    transaction_id: int
    request: RequestHeader
    response: ResponseHeader
    logical_packets: List[LogicalPacket]
    timestamp_request: float
    timestamp_response: float
    latency_us: float
    source_file: str


def parse_getdata_header(hex_data: str) -> Optional[RequestHeader]:
    """Parse GetData header using km003c_lib."""
    if not KM003C_LIB_AVAILABLE:
        return None
    if len(hex_data) < 8:
        return None

    try:
        data = bytes.fromhex(hex_data)
        raw = parse_raw_packet(data)
        pkt = parse_packet(data)
        if not (isinstance(raw, dict) and "Ctrl" in raw):
            return None
        header = raw["Ctrl"]["header"]
        if "GetData" not in pkt:
            return None
        attr_mask = pkt["GetData"].get("attribute_mask")
        return RequestHeader(
            packet_type=header.get("packet_type"),
            reserved_flag=header.get("reserved_flag"),
            transaction_id=header.get("id"),
            attribute_mask=attr_mask if attr_mask is not None else 0,
            raw_hex=hex_data[:8],
        )
    except Exception as e:
        print(f"Error parsing GetData header via km003c_lib: {e}")
        return None


def parse_putdata_header(hex_data: str) -> Optional[ResponseHeader]:
    """Parse PutData main header using km003c_lib."""
    if not KM003C_LIB_AVAILABLE:
        return None
    if len(hex_data) < 8:
        return None

    try:
        data = bytes.fromhex(hex_data)
        raw = parse_raw_packet(data)
        if not (isinstance(raw, dict) and "Data" in raw):
            return None
        header = raw["Data"]["header"]
        return ResponseHeader(
            packet_type=header.get("packet_type"),
            reserved_flag=header.get("reserved_flag"),
            transaction_id=header.get("id"),
            obj_count_words=header.get("obj_count_words"),
            raw_hex=hex_data[:8],
        )
    except Exception as e:
        print(f"Error parsing PutData header via km003c_lib: {e}")
        return None


def parse_logical_packets(hex_data: str) -> List[LogicalPacket]:
    """Extract chained logical packets from km003c_lib RawPacket."""
    if not KM003C_LIB_AVAILABLE:
        return []
    logical_packets: List[LogicalPacket] = []
    try:
        data = bytes.fromhex(hex_data)
        raw = parse_raw_packet(data)
        if not (isinstance(raw, dict) and "Data" in raw):
            return []
        for lp in raw["Data"].get("logical_packets", []) or []:
            # lp can be a dict or a PyO3 class with attributes
            if isinstance(lp, dict):
                attr = lp.get("attribute")
                nxt = lp.get("next")
                chk = lp.get("chunk")
                sz = lp.get("size")
                payload = lp.get("payload", b"")
            else:
                # Fallback to attribute access
                attr = getattr(lp, "attribute", None)
                nxt = getattr(lp, "next", None)
                chk = getattr(lp, "chunk", None)
                sz = getattr(lp, "size", None)
                payload = getattr(lp, "payload", b"")
            payload_hex = payload.hex() if isinstance(payload, (bytes, bytearray)) else ""
            logical_packets.append(
                LogicalPacket(
                    attribute=int(attr) if attr is not None else 0,
                    next_flag=bool(nxt) if nxt is not None else False,
                    chunk=int(chk) if chk is not None else 0,
                    size_bytes=int(sz) if sz is not None else 0,
                    payload_hex=payload_hex,
                )
            )
    except Exception as e:
        print(f"Error extracting logical packets via km003c_lib: {e}")
    return logical_packets


def extract_transaction_pairs(df: pl.DataFrame, source_file: str) -> List[TransactionPair]:
    """Extract request-response pairs from a DataFrame of transactions"""
    pairs = []
    
    # Filter for bulk transfers on the primary protocol endpoints
    bulk_df = df.filter(
        (pl.col("transfer_type") == "0x03") &  # Bulk transfers
        (pl.col("endpoint_address").is_in(["0x01", "0x81"]))  # Protocol endpoints
    )
    
    if len(bulk_df) == 0:
        return pairs
    
    # Split into transactions
    transactions = split_usb_transactions(bulk_df)
    
    # Group by transaction_id and process pairs
    for txn_id in transactions["transaction_id"].unique().to_list():
        txn_packets = transactions.filter(pl.col("transaction_id") == txn_id)
        
        # Find request (OUT endpoint, Submit)
        request_packets = txn_packets.filter(
            (pl.col("endpoint_address") == "0x01") &
            (pl.col("urb_type") == "S") &
            pl.col("payload_hex").is_not_null()
        )
        
        # Find response (IN endpoint, Complete)
        response_packets = txn_packets.filter(
            (pl.col("endpoint_address") == "0x81") &
            (pl.col("urb_type") == "C") &
            pl.col("payload_hex").is_not_null()
        )
        
        if len(request_packets) > 0 and len(response_packets) > 0:
            req_row = request_packets.row(0, named=True)
            resp_row = response_packets.row(0, named=True)
            
            # Parse headers
            req_header = parse_getdata_header(req_row["payload_hex"])
            resp_header = parse_putdata_header(resp_row["payload_hex"])
            
            if req_header and resp_header:
                # Verify transaction IDs match
                if req_header.transaction_id == resp_header.transaction_id:
                    # Parse logical packets from response
                    logical_packets = parse_logical_packets(resp_row["payload_hex"])
                    
                    # Calculate latency
                    latency_us = (resp_row["timestamp"] - req_row["timestamp"]) * 1_000_000
                    
                    pairs.append(TransactionPair(
                        transaction_id=req_header.transaction_id,
                        request=req_header,
                        response=resp_header,
                        logical_packets=logical_packets,
                        timestamp_request=req_row["timestamp"],
                        timestamp_response=resp_row["timestamp"],
                        latency_us=latency_us,
                        source_file=source_file
                    ))
    
    return pairs


def analyze_attribute_mapping(pairs: List[TransactionPair]) -> Dict[str, Any]:
    """Analyze the mapping between request attribute_mask and response attributes"""
    
    # Mapping: attribute_mask -> [list of response attribute combinations]
    mask_to_attributes = defaultdict(list)
    
    # Detailed mapping with counts
    detailed_mapping = defaultdict(lambda: defaultdict(int))
    
    for pair in pairs:
        mask = pair.request.attribute_mask
        
        # Get list of attributes in response
        response_attrs = tuple(sorted([lp.attribute for lp in pair.logical_packets]))
        
        mask_to_attributes[mask].append(response_attrs)
        detailed_mapping[mask][response_attrs] += 1
    
    # Convert to regular dicts for JSON serialization
    result = {
        "summary": {},
        "detailed_mapping": {},
        "bit_analysis": {}
    }
    
    # Analyze each mask
    for mask in sorted(detailed_mapping.keys()):
        mask_hex = f"0x{mask:04X}"
        
        # Get most common response pattern
        responses = detailed_mapping[mask]
        most_common = max(responses.items(), key=lambda x: x[1])
        
        result["summary"][mask_hex] = {
            "mask_decimal": mask,
            "mask_binary": f"0b{mask:015b}",
            "total_occurrences": sum(responses.values()),
            "unique_response_patterns": len(responses),
            "most_common_response": list(most_common[0]),
            "most_common_count": most_common[1]
        }
        
        # Detailed breakdown
        result["detailed_mapping"][mask_hex] = {
            str(list(attrs)): count 
            for attrs, count in sorted(responses.items(), key=lambda x: x[1], reverse=True)
        }
        
        # Bit analysis - which bits are set
        result["bit_analysis"][mask_hex] = {
            "bit_0_adc": bool(mask & 0x0001),
            "bit_1_adcqueue": bool(mask & 0x0002),
            "bit_3_settings": bool(mask & 0x0008),
            "bit_4_pdpacket": bool(mask & 0x0010),
            "bit_9_unknown512": bool(mask & 0x0200)
        }
    
    return result


def analyze_per_source_file() -> None:
    """Main analysis function - process each source_file separately"""
    
    # Load the master dataset
    dataset_path = Path("data/processed/usb_master_dataset.parquet")
    if not dataset_path.exists():
        print(f"❌ Dataset not found: {dataset_path}")
        print("Run the USB capture processing pipeline first.")
        return
    
    print("=" * 80)
    print("KM003C REQUEST-RESPONSE CORRELATION ANALYSIS")
    print("=" * 80)
    print(f"KM003C Rust library: {'✅ Available' if KM003C_LIB_AVAILABLE else '❌ Not available (using manual parsing)'}")
    print()
    
    # Load dataset
    print("📂 Loading USB master dataset...")
    df = pl.read_parquet(dataset_path)
    print(f"   Loaded {len(df):,} USB packets\n")
    
    # Get unique source files
    source_files = df["source_file"].unique().sort().to_list()
    print(f"📁 Found {len(source_files)} source files:\n")
    for sf in source_files:
        print(f"   - {sf}")
    print()
    
    # Process each source file
    all_results = {}
    all_pairs = []
    
    for source_file in source_files:
        print("=" * 80)
        print(f"🔍 Analyzing: {source_file}")
        print("=" * 80)
        
        # Filter for this source file
        sf_df = df.filter(pl.col("source_file") == source_file)
        print(f"   Packets: {len(sf_df):,}")
        
        # Extract transaction pairs
        print("   Extracting request-response pairs...")
        pairs = extract_transaction_pairs(sf_df, source_file)
        print(f"   ✅ Found {len(pairs)} valid transaction pairs\n")
        
        if len(pairs) == 0:
            print("   ⚠️  No valid pairs found, skipping\n")
            continue
        
        all_pairs.extend(pairs)
        
        # Analyze attribute mapping
        print("   📊 Analyzing attribute mapping...")
        mapping_analysis = analyze_attribute_mapping(pairs)
        
        # Store results
        all_results[source_file] = {
            "total_packets": len(sf_df),
            "transaction_pairs": len(pairs),
            "mapping_analysis": mapping_analysis
        }
        
        # Print summary for this file
        print(f"\n   Request masks found: {len(mapping_analysis['summary'])}")
        for mask_hex, summary in mapping_analysis['summary'].items():
            print(f"      {mask_hex}: {summary['total_occurrences']} occurrences → {summary['most_common_response']}")
        
        print()
    
    # Global analysis across all files
    print("=" * 80)
    print("🌐 GLOBAL ANALYSIS (All Source Files)")
    print("=" * 80)
    print(f"Total transaction pairs: {len(all_pairs)}\n")
    
    if len(all_pairs) > 0:
        global_mapping = analyze_attribute_mapping(all_pairs)
        all_results["_global"] = {
            "total_pairs": len(all_pairs),
            "mapping_analysis": global_mapping
        }
        
        print("📋 Complete Request → Response Mapping:\n")
        for mask_hex, summary in sorted(global_mapping['summary'].items()):
            bits = global_mapping['bit_analysis'][mask_hex]
            bits_set = [k.split('_')[1].upper() for k, v in bits.items() if v]
            
            print(f"  {mask_hex} ({summary['mask_decimal']:5d}) | {summary['mask_binary']}")
            print(f"    Bits set: {', '.join(bits_set) if bits_set else 'NONE'}")
            print(f"    Occurrences: {summary['total_occurrences']}")
            print(f"    Response: {summary['most_common_response']}")
            
            # Show all response patterns if multiple exist
            if summary['unique_response_patterns'] > 1:
                print(f"    Alternate patterns:")
                for pattern, count in global_mapping['detailed_mapping'][mask_hex].items():
                    if count != summary['most_common_count']:
                        print(f"      → {pattern}: {count} times")
            print()
        
        # Latency statistics
        print("⏱️  Transaction Latency Statistics:")
        latencies = [p.latency_us for p in all_pairs]
        print(f"   Min:    {min(latencies):8.1f} µs")
        print(f"   Median: {sorted(latencies)[len(latencies)//2]:8.1f} µs")
        print(f"   Mean:   {sum(latencies)/len(latencies):8.1f} µs")
        print(f"   Max:    {max(latencies):8.1f} µs")
        print()
    
    # Export results
    output_path = Path("data/processed/request_response_analysis.json")
    print(f"💾 Exporting results to: {output_path}")
    
    with open(output_path, 'w') as f:
        json.dump(all_results, f, indent=2)
    
    print(f"✅ Exported!\n")
    
    # Create summary Parquet file
    if len(all_pairs) > 0:
        print("💾 Creating Parquet summary...")
        pairs_data = []
        for pair in all_pairs:
            pairs_data.append({
                "source_file": pair.source_file,
                "transaction_id": pair.transaction_id,
                "request_mask": pair.request.attribute_mask,
                "request_mask_hex": f"0x{pair.request.attribute_mask:04X}",
                "response_attributes": str([lp.attribute for lp in pair.logical_packets]),
                "num_logical_packets": len(pair.logical_packets),
                "timestamp_request": pair.timestamp_request,
                "timestamp_response": pair.timestamp_response,
                "latency_us": pair.latency_us,
                "request_hex": pair.request.raw_hex,
                "response_hex": pair.response.raw_hex,
            })
        
        pairs_df = pl.DataFrame(pairs_data)
        parquet_path = Path("data/processed/transaction_pairs.parquet")
        pairs_df.write_parquet(parquet_path)
        print(f"   ✅ Saved {len(pairs_df)} transaction pairs to: {parquet_path}\n")
    
    print("=" * 80)
    print("✅ ANALYSIS COMPLETE!")
    print("=" * 80)


if __name__ == "__main__":
    analyze_per_source_file()
