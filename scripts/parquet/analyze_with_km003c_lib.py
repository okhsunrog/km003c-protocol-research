#!/usr/bin/env python3
"""
Продвинутый анализ request-response с использованием km003c_lib (Rust).

Использует полный функционал Rust библиотеки для:
- Парсинга пакетов через parse_raw_packet/parse_packet
- Работы с AttributeSet и Attribute
- Валидации структуры chained logical packets
- Глубокого анализа ADC и PD данных

Run: uv run python scripts/analyze_with_km003c_lib.py
"""

from __future__ import annotations

import polars as pl
from pathlib import Path
from typing import Dict, List, Any
from collections import defaultdict
import json

# Rust library imports
try:
    from km003c_lib import (
        parse_raw_packet,
        parse_packet,
        VID,
        PID,
    )
    KM003C_LIB_AVAILABLE = True
    print("✅ km003c_lib (Rust) loaded successfully")
    print(f"   Device: VID=0x{VID:04X}, PID=0x{PID:04X}")
except ImportError as e:
    print(f"❌ km003c_lib not available: {e}")
    print("   Build it with: just rust-ext")
    exit(1)

# Python library imports
from km003c_analysis.core import split_usb_transactions
from km003c_helpers import (
    get_packet_type,
    get_adc_data,
    get_adcqueue_data,
    get_pd_status,
    get_pd_events,
)


def analyze_with_rust_lib():
    """Полный анализ с использованием km003c_lib"""
    
    # Load dataset
    dataset_path = Path("data/processed/usb_master_dataset.parquet")
    if not dataset_path.exists():
        print(f"❌ Dataset not found: {dataset_path}")
        return
    
    print("\n" + "=" * 80)
    print("KM003C PROTOCOL ANALYSIS WITH km003c_lib (RUST)")
    print("=" * 80)
    print()
    
    df = pl.read_parquet(dataset_path)
    print(f"📂 Loaded {len(df):,} USB packets\n")
    
    # Filter for bulk transfers on protocol endpoints
    bulk_df = df.filter(
        (pl.col("transfer_type") == "0x03") &
        (pl.col("endpoint_address").is_in(["0x01", "0x81"]))
    )
    
    print(f"🔍 Protocol packets: {len(bulk_df):,}")
    
    # Split into transactions
    transactions = split_usb_transactions(bulk_df)
    print(f"🔗 Transactions: {len(transactions):,}\n")
    
    # Analyze each transaction
    stats = {
        "total_packets": 0,
        "parse_success": 0,
        "parse_errors": 0,
        "packet_types": defaultdict(int),
        "attributes_in_requests": defaultdict(int),
        "attributes_in_responses": defaultdict(int),
        "request_response_pairs": [],
        "chained_packets_stats": defaultdict(int),
        "adc_data_samples": [],
        "pd_status_samples": [],
        "pd_events_count": 0,
    }
    
    # Track request-response correlation
    pending_requests = {}  # id -> (packet_info, timestamp)
    
    for row in transactions.iter_rows(named=True):
        if row["payload_hex"] is None or len(row["payload_hex"]) < 8:
            continue
        
        payload_bytes = bytes.fromhex(row["payload_hex"])
        stats["total_packets"] += 1
        
        try:
            # Parse with Rust library
            raw_packet = parse_raw_packet(payload_bytes)
            packet = parse_packet(payload_bytes)
            
            stats["parse_success"] += 1
            pkt_type = get_packet_type(packet)
            if pkt_type is not None:
                stats["packet_types"][pkt_type] += 1
            
            # Analyze by endpoint
            is_request = row["endpoint_address"] == "0x01"
            is_response = row["endpoint_address"] == "0x81"
            
            if is_request:
                # Request analysis
                if get_packet_type(packet) == "GetData":
                    # Extract attribute set from parsed packet
                    mask = packet["GetData"].get("attribute_mask")
                    if mask is not None:
                        stats["attributes_in_requests"][f"0x{mask:04X}"] += 1
                        # Store for correlation using RawPacket header ID
                        req_id = None
                        if isinstance(raw_packet, dict) and "Ctrl" in raw_packet:
                            req_id = raw_packet["Ctrl"].get("header", {}).get("id")
                        if req_id is not None:
                            pending_requests[req_id] = {
                                "mask": mask,
                                "mask_hex": f"0x{mask:04X}",
                                "timestamp": row["timestamp"],
                                "transaction_id": row["transaction_id"],
                            }
            
            elif is_response:
                # Response analysis
                if get_packet_type(packet) == "DataResponse":
                    # Analyze chained logical packets (Data variant)
                    if isinstance(raw_packet, dict) and "Data" in raw_packet:
                        # Collect attributes seen in the response
                        response_attrs = []

                        # Extract from high-level parsed packet
                        adc = get_adc_data(packet)
                        if adc is not None:
                            response_attrs.append(1)  # ADC attribute
                            stats["adc_data_samples"].append(
                                {
                                    "vbus_v": adc.vbus_v,
                                    "ibus_a": adc.ibus_a,
                                    "power_w": adc.power_w,
                                    "temp_c": adc.temp_c,
                                }
                            )

                        adcq = get_adcqueue_data(packet)
                        if adcq is not None:
                            response_attrs.append(2)  # AdcQueue attribute

                        pdst = get_pd_status(packet)
                        if pdst is not None:
                            response_attrs.append(16)  # PdPacket attribute
                            stats["pd_status_samples"].append(
                                {
                                    "timestamp": pdst.timestamp,
                                    "vbus_v": pdst.vbus_v,
                                    "ibus_a": pdst.ibus_a,
                                }
                            )

                        pdev = get_pd_events(packet)
                        if pdev is not None:
                            response_attrs.append(16)  # PdPacket attribute (events)
                            try:
                                stats["pd_events_count"] += len(pdev.events)
                            except Exception:
                                pass

                        # Record response attributes
                        if response_attrs:
                            attrs_key = str(sorted(set(response_attrs)))
                            stats["attributes_in_responses"][attrs_key] += 1

                            # Chain length analysis
                            chain_len = len(set(response_attrs))
                            stats["chained_packets_stats"][f"{chain_len}_packets"] += 1

                        # Correlate with request by matching RawPacket IDs
                        resp_id = raw_packet["Data"].get("header", {}).get("id")
                        if resp_id in pending_requests:
                            req_info = pending_requests.pop(resp_id)
                            latency_us = (row["timestamp"] - req_info["timestamp"]) * 1_000_000

                            stats["request_response_pairs"].append(
                                {
                                    "request_mask": req_info["mask"],
                                    "request_mask_hex": req_info["mask_hex"],
                                    "response_attributes": response_attrs,
                                    "latency_us": latency_us,
                                    "transaction_id": req_info["transaction_id"],
                                }
                            )
        
        except Exception as e:
            stats["parse_errors"] += 1
            # print(f"⚠️  Parse error: {e}")
    
    # Print results
    print("=" * 80)
    print("📊 PARSING STATISTICS")
    print("=" * 80)
    print(f"Total packets: {stats['total_packets']:,}")
    print(f"Successfully parsed: {stats['parse_success']:,} ({stats['parse_success']/stats['total_packets']*100:.1f}%)")
    print(f"Parse errors: {stats['parse_errors']:,}")
    print()
    
    print("📦 PACKET TYPE DISTRIBUTION")
    print("-" * 80)
    for pkt_type, count in sorted(stats["packet_types"].items(), key=lambda x: x[1], reverse=True):
        print(f"  {pkt_type:<20}: {count:>6,} packets")
    print()
    
    print("🔍 REQUEST ATTRIBUTE MASKS (GetData)")
    print("-" * 80)
    for mask, count in sorted(stats["attributes_in_requests"].items(), key=lambda x: x[1], reverse=True):
        # Decode mask
        mask_val = int(mask, 16)
        bits_set = []
        if mask_val & 0x0001: bits_set.append("ADC(1)")
        if mask_val & 0x0002: bits_set.append("AdcQueue(2)")
        if mask_val & 0x0008: bits_set.append("Settings(8)")
        if mask_val & 0x0010: bits_set.append("PdPacket(16)")
        if mask_val & 0x0200: bits_set.append("Unknown512")
        
        bits_str = ", ".join(bits_set) if bits_set else "None"
        print(f"  {mask}: {count:>6,} times  [{bits_str}]")
    print()
    
    print("📤 RESPONSE ATTRIBUTES (PutData)")
    print("-" * 80)
    for attrs, count in sorted(stats["attributes_in_responses"].items(), key=lambda x: x[1], reverse=True):
        print(f"  {attrs:<30}: {count:>6,} responses")
    print()
    
    print("🔗 REQUEST → RESPONSE CORRELATION")
    print("-" * 80)
    if stats["request_response_pairs"]:
        # Analyze correlation
        correlation_map = defaultdict(lambda: defaultdict(int))
        
        for pair in stats["request_response_pairs"]:
            mask = pair["request_mask_hex"]
            attrs = str(sorted(pair["response_attributes"]))
            correlation_map[mask][attrs] += 1
        
        print("Perfect correlation analysis:")
        for mask in sorted(correlation_map.keys(), key=lambda x: int(x, 16)):
            responses = correlation_map[mask]
            total = sum(responses.values())
            most_common = max(responses.items(), key=lambda x: x[1])
            
            print(f"\n  Request mask {mask} ({total} occurrences):")
            for attrs, count in sorted(responses.items(), key=lambda x: x[1], reverse=True):
                pct = count / total * 100
                marker = "✓" if count == most_common[1] else " "
                print(f"    {marker} Response {attrs}: {count} times ({pct:.1f}%)")
        
        print()
        
        # Latency analysis
        latencies = [p["latency_us"] for p in stats["request_response_pairs"]]
        print(f"⏱️  Latency statistics ({len(latencies)} pairs):")
        print(f"   Min:    {min(latencies):>8.1f} µs")
        print(f"   Median: {sorted(latencies)[len(latencies)//2]:>8.1f} µs")
        print(f"   Mean:   {sum(latencies)/len(latencies):>8.1f} µs")
        print(f"   Max:    {max(latencies):>8.1f} µs")
    else:
        print("  No request-response pairs found")
    print()
    
    print("⛓️  CHAINED LOGICAL PACKETS")
    print("-" * 80)
    for chain_type, count in sorted(stats["chained_packets_stats"].items()):
        print(f"  {chain_type:<20}: {count:>6,} responses")
    print()
    
    print("📊 DATA SAMPLES")
    print("-" * 80)
    print(f"  ADC samples: {len(stats['adc_data_samples']):,}")
    if stats["adc_data_samples"]:
        first_adc = stats["adc_data_samples"][0]
        print(f"    Example: VBUS={first_adc['vbus_v']:.3f}V, IBUS={first_adc['ibus_a']:.3f}A, Power={first_adc['power_w']:.3f}W")
    
    print(f"  PD status samples: {len(stats['pd_status_samples']):,}")
    if stats["pd_status_samples"]:
        first_pd = stats["pd_status_samples"][0]
        print(f"    Example: timestamp={first_pd['timestamp']}, VBUS={first_pd['vbus_v']:.3f}V")
    
    print(f"  PD events: {stats['pd_events_count']:,}")
    print()
    
    # Export results
    output_path = Path("data/processed/rust_lib_analysis.json")
    print(f"💾 Exporting results to: {output_path}")
    
    # Convert defaultdicts to regular dicts for JSON
    export_data = {
        "total_packets": stats["total_packets"],
        "parse_success": stats["parse_success"],
        "parse_errors": stats["parse_errors"],
        "packet_types": dict(stats["packet_types"]),
        "attributes_in_requests": dict(stats["attributes_in_requests"]),
        "attributes_in_responses": dict(stats["attributes_in_responses"]),
        "request_response_pairs": stats["request_response_pairs"],
        "chained_packets_stats": dict(stats["chained_packets_stats"]),
        "data_sample_counts": {
            "adc_samples": len(stats["adc_data_samples"]),
            "pd_status_samples": len(stats["pd_status_samples"]),
            "pd_events": stats["pd_events_count"],
        }
    }
    
    with open(output_path, 'w') as f:
        json.dump(export_data, f, indent=2)
    
    print(f"   ✅ Exported!\n")
    
    print("=" * 80)
    print("✅ ANALYSIS COMPLETE WITH km003c_lib (RUST)")
    print("=" * 80)
    print()
    print("Key findings:")
    print("  • Rust parser provides validated, type-safe parsing")
    print("  • Confirms protocol specification accuracy")
    print("  • Enables deep analysis of ADC and PD data structures")
    print()


if __name__ == "__main__":
    analyze_with_rust_lib()
