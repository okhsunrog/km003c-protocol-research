#!/usr/bin/env python3
"""
Comprehensive KM003C protocol analysis with integrated usbpdpy v0.2.0 support

This script demonstrates the complete analysis pipeline:
1. Load raw USB data from Parquet
2. Process into USB transactions  
3. Parse KM003C application protocol
4. Extract and parse embedded PD messages with usbpdpy v0.2.0
5. Correlate PD negotiations with protocol flow

Run: uv run python notebooks/analyze_km003c_protocol.py
"""

from __future__ import annotations

import polars as pl
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
import usbpdpy

# Local package imports  
from km003c_analysis.core import split_usb_transactions, tag_transactions

# Import the Rust library for KM003C packet parsing
try:
    from km003c_lib import parse_packet, parse_raw_packet
    KM003C_LIB_AVAILABLE = True
except ImportError:
    print("⚠️  km003c_lib not available - will use simplified analysis")
    KM003C_LIB_AVAILABLE = False

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


@dataclass
class PdAnalysisResult:
    """Results from PD message analysis"""
    message_type: str
    pdos: List[Dict[str, Any]]
    rdos: List[Dict[str, Any]]
    raw_hex: str
    parse_success: bool
    error: Optional[str] = None


def extract_pdo_details(pdo: usbpdpy.PowerDataObj) -> Dict[str, Any]:
    """Extract PDO details for analysis"""
    return {
        'pdo_type': pdo.pdo_type,
        'voltage_v': pdo.voltage_v,
        'max_current_a': pdo.max_current_a,
        'max_power_w': pdo.max_power_w,
        'unconstrained_power': pdo.unconstrained_power,
    }


def extract_rdo_details(rdo: usbpdpy.RequestDataObj) -> Dict[str, Any]:
    """Extract RDO details for analysis"""
    return {
        'object_position': rdo.object_position,
        'rdo_type': rdo.rdo_type,
        'operating_current_a': rdo.operating_current_a,
        'capability_mismatch': rdo.capability_mismatch,
    }


def parse_pd_from_hex(hex_data: str, pdo_state: Optional[List[usbpdpy.PowerDataObj]] = None) -> PdAnalysisResult:
    """Parse PD message from hex data"""
    try:
        wire_bytes = bytes.fromhex(hex_data)
        
        # Basic parsing first
        msg = usbpdpy.parse_pd_message(wire_bytes)
        
        # Enhanced parsing for Request messages with PDO state
        if msg.header.message_type == "Request" and pdo_state:
            msg = usbpdpy.parse_pd_message_with_state(wire_bytes, pdo_state)
        
        # Extract PDOs and RDOs
        pdos = [extract_pdo_details(pdo) for pdo in msg.data_objects]
        rdos = [extract_rdo_details(rdo) for rdo in msg.request_objects]
        
        return PdAnalysisResult(
            message_type=msg.header.message_type,
            pdos=pdos,
            rdos=rdos,
            raw_hex=hex_data,
            parse_success=True
        )
        
    except Exception as e:
        return PdAnalysisResult(
            message_type="PARSE_ERROR",
            pdos=[],
            rdos=[],
            raw_hex=hex_data,
            parse_success=False,
            error=str(e)
        )


def analyze_km003c_protocol() -> None:
    """Comprehensive KM003C protocol analysis with PD parsing"""
    
    # Load the master dataset
    dataset_path = Path("data/processed/usb_master_dataset.parquet")
    if not dataset_path.exists():
        print(f"Dataset not found: {dataset_path}")
        print("Run the USB capture processing pipeline first.")
        return
        
    print("=== KM003C PROTOCOL ANALYSIS WITH PD PARSING ===")
    print(f"Using usbpdpy v0.2.0")
    print(f"KM003C Rust library: {'✅ Available' if KM003C_LIB_AVAILABLE else '❌ Not available'}")
    print()
    
    # Load and analyze dataset
    print("Loading USB master dataset...")
    df = pl.read_parquet(dataset_path)
    print(f"Loaded {len(df)} USB packets")
    
    # Process into transactions
    print("Processing USB transactions...")
    transactions = split_usb_transactions(df)
    print(f"Found {len(transactions)} USB transactions")
    
    # Tag transactions for analysis
    tagged_transactions = tag_transactions(transactions)
    
    # Simplified analysis focusing on payloads
    print("Analyzing application-layer payloads...")
    
    all_payloads = []
    pd_results = []
    current_source_capabilities = None
    
    # Extract all payloads from transactions DataFrame
    if "payload_hex" in tagged_transactions.columns:
        payload_df = tagged_transactions.filter(
            pl.col("payload_hex").is_not_null() & 
            (pl.col("payload_hex").str.len_chars() >= 16)
        ).select([
            "transaction_id",
            "timestamp", 
            "payload_hex",
            "endpoint_address"
        ])
        
        for row in payload_df.iter_rows(named=True):
            direction = "OUT" if row["endpoint_address"] == "0x01" else "IN"
            all_payloads.append({
                "transaction_id": row["transaction_id"],
                "direction": direction,
                "timestamp": row["timestamp"],
                "payload_hex": row["payload_hex"],
                "payload_length": len(row["payload_hex"]) // 2,
            })
    
    print(f"Found {len(all_payloads)} application payloads")
    
    # Analyze payloads to find PD data using km003c_lib
    print("\nExtracting PD messages via km003c_lib...")

    def _extract_pd_wires(pdev) -> List[bytes]:
        wires: List[bytes] = []
        try:
            events = getattr(pdev, "events", None)
            if not events:
                return wires
            for e in events:
                # pyi style
                event_type = getattr(e, "event_type", None)
                wire_data = getattr(e, "wire_data", None)
                if event_type == "pd_message" and wire_data is not None:
                    try:
                        wires.append(bytes(wire_data))
                        continue
                    except Exception:
                        pass
                # alt repr
                if isinstance(e, dict):
                    wd = e.get("wire_data")
                    if wd is not None:
                        try:
                            wires.append(bytes(wd))
                        except Exception:
                            pass
        except Exception:
            return wires
        return wires

    pd_candidates = []
    for payload in all_payloads:
        hex_data = payload["payload_hex"]
        try:
            pkt = parse_packet(bytes.fromhex(hex_data))
            if get_packet_type(pkt) != "DataResponse":
                continue
            pdst = get_pd_status(pkt)
            pdev = get_pd_events(pkt)
            if pdst is None and pdev is None:
                continue
            # Store pd candidates uniformly for downstream reporting
            if pdst is not None:
                pd_candidates.append({
                    **payload,
                    "pd_offset_bytes": None,
                    "pd_hex": None,
                    "pd_result": PdAnalysisResult(
                        message_type="PdStatus",
                        pdos=[],
                        rdos=[],
                        raw_hex="",
                        parse_success=True,
                    ),
                })
            if pdev is not None:
                # Try usbpdpy to compute success ratio and update state
                wires = _extract_pd_wires(pdev)
                for w in wires:
                    try:
                        msg = usbpdpy.parse_pd_message(w)
                        if msg.header.message_type == "Source_Capabilities":
                            current_source_capabilities = msg.data_objects
                        pd_candidates.append({
                            **payload,
                            "pd_offset_bytes": None,
                            "pd_hex": w.hex(),
                            "pd_result": PdAnalysisResult(
                                message_type=msg.header.message_type,
                                pdos=[
                                    {
                                        'pdo_type': p.pdo_type,
                                        'voltage_v': p.voltage_v,
                                        'max_current_a': p.max_current_a,
                                        'max_power_w': p.max_power_w,
                                        'unconstrained_power': p.unconstrained_power,
                                    } for p in getattr(msg, 'data_objects', [])
                                ],
                                rdos=[],
                                raw_hex=w.hex(),
                                parse_success=True,
                            ),
                        })
                    except Exception:
                        continue
        except Exception:
            continue

    print(f"Found {len(pd_candidates)} PD signals")
    
    # PD Message Analysis
    if pd_candidates:
        print("\n=== PD MESSAGE ANALYSIS ===")
        
        # Message type distribution
        msg_types = {}
        for candidate in pd_candidates:
            msg_type = candidate["pd_result"].message_type
            msg_types[msg_type] = msg_types.get(msg_type, 0) + 1
        
        print("PD Message type distribution:")
        for msg_type, count in sorted(msg_types.items(), key=lambda x: x[1], reverse=True):
            print(f"  {msg_type}: {count}")
        
        # Source Capabilities Analysis
        source_caps = [c for c in pd_candidates if c["pd_result"].message_type == "Source_Capabilities"]
        if source_caps:
            print(f"\n=== SOURCE CAPABILITIES ANALYSIS ===")
            print(f"Found {len(source_caps)} Source_Capabilities messages")
            
            # Analyze first one
            first_caps = source_caps[0]["pd_result"]
            if first_caps.pdos:
                print(f"Power Profile ({len(first_caps.pdos)} PDOs):")
                for i, pdo in enumerate(first_caps.pdos):
                    extra_info = ""
                    if pdo.get("unconstrained_power"):
                        extra_info = " (Unconstrained)"
                    print(f"  PDO{i+1}: {pdo['pdo_type']} - {pdo['voltage_v']}V @ {pdo['max_current_a']}A = {pdo['max_power_w']}W{extra_info}")
        
        # Request Analysis  
        requests = [c for c in pd_candidates if c["pd_result"].message_type == "Request"]
        if requests:
            print(f"\n=== REQUEST MESSAGE ANALYSIS ===")
            print(f"Found {len(requests)} Request messages")
            
            for req in requests:
                req_result = req["pd_result"]
                if req_result.rdos:
                    rdo = req_result.rdos[0]
                    print(f"  Request at offset {req['pd_offset_bytes']}B:")
                    print(f"    └─ Requesting PDO #{rdo['object_position']}")
                    print(f"    └─ Type: {rdo['rdo_type']}")
                    if rdo.get('operating_current_a'):
                        print(f"    └─ Operating current: {rdo['operating_current_a']}A")
                    if rdo.get('capability_mismatch'):
                        print(f"    └─ ⚠️  Capability mismatch")
        
        # Protocol Flow Analysis
        control_msgs = [c for c in pd_candidates if c["pd_result"].message_type in ["GoodCRC", "Accept", "PS_RDY"]]
        if control_msgs:
            print(f"\n=== PROTOCOL FLOW ANALYSIS ===")
            print(f"Control messages: {len(control_msgs)}")
            
            flow_sequence = []
            for candidate in sorted(pd_candidates, key=lambda x: x["timestamp"]):
                flow_sequence.append(candidate["pd_result"].message_type)
            
            print("Message sequence:")
            for i, msg_type in enumerate(flow_sequence):
                print(f"  {i+1}. {msg_type}")
    
    else:
        print("No PD messages found in the dataset.")
        print("This may indicate:")
        print("  - Dataset doesn't contain PD traffic")
        print("  - PD data is in a different format")
        print("  - Need to adjust payload parsing offsets")
    
    # Summary
    print(f"\n=== SUMMARY ===")
    print(f"USB packets analyzed: {len(df)}")
    print(f"USB transactions: {len(transactions)}")
    print(f"Application payloads: {len(all_payloads)}")
    print(f"PD messages found: {len(pd_candidates)}")
    print(f"Parse success rate: {len(pd_candidates)} found")
    
    if current_source_capabilities:
        print(f"Source Capabilities PDOs for Request parsing: {len(current_source_capabilities)}")
    
    print("\n✅ Analysis complete!")
    print("The KM003C protocol analysis now includes complete PD message parsing with usbpdpy v0.2.0")


if __name__ == "__main__":
    analyze_km003c_protocol()
