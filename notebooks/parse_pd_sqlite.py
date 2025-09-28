#!/usr/bin/env python3
"""
Parse PD events from KM003C SQLite exports using usbpdpy v0.2.0

Analyzes PD messages stored in data/sqlite/pd_new.sqlite with complete PDO/RDO parsing,
power negotiation tracking, and protocol flow validation.

The SQLite Raw BLOB format uses wrapped events:
  - 0x45: 6-byte Connection/Status event
  - 0x80..0x9F: PD message event (size_flag, timestamp, sop, wire_bytes)

Run:
  uv run python notebooks/parse_pd_sqlite.py
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from collections import Counter
from dataclasses import dataclass
from typing import Optional
import usbpdpy


@dataclass
class PowerNegotiation:
    """Represents a complete power negotiation sequence"""
    source_capabilities: Optional[usbpdpy.PdMessage] = None
    request: Optional[usbpdpy.PdMessage] = None
    accept: Optional[usbpdpy.PdMessage] = None
    ps_rdy: Optional[usbpdpy.PdMessage] = None
    timestamp_start: float = 0.0
    timestamp_end: float = 0.0
    voltage_before: float = 0.0
    voltage_after: float = 0.0


def parse_pd_blob(blob: bytes) -> list[dict]:
    """Parse KM003C PD event BLOB into individual PD messages"""
    events = []
    if not blob:
        return events
        
    b = blob
    i = 0
    
    while i < len(b):
        t0 = b[i]
        
        if t0 == 0x45:
            # Connection/Status event (6 bytes)
            if i + 6 <= len(b):
                ts = int.from_bytes(b[i + 1 : i + 4], "little")
                reserved = b[i + 4]
                event_data = b[i + 5]
                events.append({
                    "kind": "connection",
                    "timestamp": ts,
                    "reserved": reserved,
                    "event_data": event_data,
                })
                i += 6
            else:
                break
                
        elif 0x80 <= t0 <= 0x9F:
            # PD message event
            if i + 6 > len(b):
                break
                
            size_flag = b[i]
            ts = int.from_bytes(b[i + 1 : i + 5], "little")
            sop = b[i + 5]
            i += 6
            
            size = size_flag & 0x3F
            wire_len = max(0, size - 5)
            
            if wire_len == 0 or i + wire_len > len(b):
                break
                
            wire = b[i : i + wire_len]
            i += wire_len
            
            events.append({
                "kind": "pd_message",
                "timestamp": ts,
                "sop": sop,
                "wire_len": wire_len,
                "wire_bytes": wire,
            })
        else:
            break
            
    return events


def analyze_power_negotiation(db_path: Path) -> None:
    """Perform comprehensive power negotiation analysis"""
    
    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()
    cur.execute("SELECT Time, Vbus, Ibus, Raw FROM pd_table ORDER BY Time")
    rows = cur.fetchall()
    
    print("=== PD SQLITE ANALYSIS ===")
    print(f"Using usbpdpy v0.2.0")
    print()
    
    # Track PD messages and negotiations
    pd_messages = []
    negotiations = []
    current_negotiation = PowerNegotiation()
    last_source_capabilities = None
    
    # Parse all events
    for time_s, vbus_v, ibus_a, raw in rows:
        events = parse_pd_blob(raw)
        
        for event in events:
            if event["kind"] == "pd_message":
                # Parse PD message
                wire_bytes = event["wire_bytes"]
                
                try:
                    # Basic parsing first
                    msg = usbpdpy.parse_pd_message(wire_bytes)
                    
                    # Enhanced parsing for Request messages (with PDO state)
                    if msg.header.message_type == "Request" and last_source_capabilities:
                        msg = usbpdpy.parse_pd_message_with_state(
                            wire_bytes, 
                            last_source_capabilities.data_objects
                        )
                    
                    # Store message with context
                    pd_msg_info = {
                        "time_s": time_s,
                        "vbus_v": vbus_v,
                        "ibus_a": ibus_a,
                        "message": msg,
                        "raw_hex": wire_bytes.hex(),
                    }
                    pd_messages.append(pd_msg_info)
                    
                    # Track negotiation flow
                    msg_type = msg.header.message_type
                    
                    if msg_type == "Source_Capabilities":
                        # Start new negotiation
                        if current_negotiation.source_capabilities:
                            negotiations.append(current_negotiation)
                        
                        current_negotiation = PowerNegotiation(
                            source_capabilities=msg,
                            timestamp_start=time_s,
                            voltage_before=vbus_v
                        )
                        last_source_capabilities = msg
                        
                    elif msg_type == "Request":
                        current_negotiation.request = msg
                        
                    elif msg_type == "Accept":
                        current_negotiation.accept = msg
                        
                    elif msg_type == "PS_RDY":
                        current_negotiation.ps_rdy = msg
                        current_negotiation.timestamp_end = time_s
                        current_negotiation.voltage_after = vbus_v
                        
                except Exception as e:
                    print(f"Failed to parse PD message: {e}")
                    continue
    
    # Add final negotiation
    if current_negotiation.source_capabilities:
        negotiations.append(current_negotiation)
    
    # Analysis results
    print(f"Total PD messages parsed: {len(pd_messages)}")
    
    message_types = Counter(msg_info["message"].header.message_type for msg_info in pd_messages)
    print(f"Message type distribution: {dict(message_types.most_common())}")
    print()
    
    # Detailed Source Capabilities Analysis
    source_caps_messages = [m for m in pd_messages if m["message"].header.message_type == "Source_Capabilities"]
    if source_caps_messages:
        print("=== SOURCE CAPABILITIES ANALYSIS ===")
        first_caps = source_caps_messages[0]["message"]
        
        print(f"Source Power Profile ({len(first_caps.data_objects)} PDOs):")
        for i, pdo in enumerate(first_caps.data_objects):
            print(f"  PDO{i+1}: {pdo}")
            if pdo.pdo_type == "FixedSupply":
                extra_info = []
                if pdo.unconstrained_power:
                    extra_info.append("Unconstrained power")
                if pdo.usb_communications_capable:
                    extra_info.append("USB comm")
                if pdo.dual_role_power:
                    extra_info.append("Dual role")
                    
                info_str = f" ({', '.join(extra_info)})" if extra_info else ""
                print(f"    └─ {pdo.voltage_v}V @ {pdo.max_current_a}A = {pdo.max_power_w}W{info_str}")
            elif pdo.pdo_type == "PPS":
                print(f"    └─ Programmable: {pdo.min_voltage_v:.1f}-{pdo.max_voltage_v}V @ {pdo.max_current_a}A")
        print()
    
    # Detailed Request Analysis
    request_messages = [m for m in pd_messages if m["message"].header.message_type == "Request"]
    if request_messages:
        print("=== REQUEST MESSAGE ANALYSIS ===")
        for req_info in request_messages:
            req_msg = req_info["message"]
            print(f"Request at {req_info['time_s']:.3f}s (Vbus: {req_info['vbus_v']:.3f}V):")
            
            if req_msg.request_objects:
                rdo = req_msg.request_objects[0]
                print(f"  └─ Requesting PDO #{rdo.object_position}")
                print(f"  └─ RDO Type: {rdo.rdo_type}")
                print(f"  └─ Raw RDO: 0x{rdo.raw:08x}")
                
                if rdo.operating_current_a is not None:
                    print(f"  └─ Operating Current: {rdo.operating_current_a}A")
                if rdo.max_operating_current_a is not None:
                    print(f"  └─ Max Operating Current: {rdo.max_operating_current_a}A")
                
                flags = []
                if rdo.capability_mismatch:
                    flags.append("Capability mismatch")
                if rdo.usb_communications_capable:
                    flags.append("USB comm")
                if rdo.no_usb_suspend:
                    flags.append("No USB suspend")
                    
                if flags:
                    print(f"  └─ Flags: {', '.join(flags)}")
                
                # Cross-reference with PDO
                if last_source_capabilities and 1 <= rdo.object_position <= len(last_source_capabilities.data_objects):
                    requested_pdo = last_source_capabilities.data_objects[rdo.object_position - 1]
                    print(f"  └─ Requested PDO details: {requested_pdo}")
            else:
                print(f"  └─ RDO parsing failed (no PDO state available)")
            print()
    
    # Power Negotiation Flow Analysis
    complete_negotiations = [n for n in negotiations if n.source_capabilities and n.request and n.ps_rdy]
    if complete_negotiations:
        print("=== POWER NEGOTIATION ANALYSIS ===")
        for i, neg in enumerate(complete_negotiations):
            print(f"Negotiation {i+1}:")
            print(f"  Duration: {neg.timestamp_end - neg.timestamp_start:.3f}s")
            print(f"  Voltage transition: {neg.voltage_before:.3f}V → {neg.voltage_after:.3f}V")
            
            if neg.request.request_objects:
                rdo = neg.request.request_objects[0]
                requested_pdo = neg.source_capabilities.data_objects[rdo.object_position - 1]
                print(f"  Negotiated power: PDO{rdo.object_position} ({requested_pdo.voltage_v}V @ {requested_pdo.max_current_a}A)")
                
                # Calculate power change
                if requested_pdo.voltage_v and requested_pdo.max_current_a:
                    max_power = requested_pdo.voltage_v * requested_pdo.max_current_a
                    print(f"  Maximum available power: {max_power:.1f}W")
            print()
    
    # Summary Statistics
    print("=== SUMMARY STATISTICS ===")
    print(f"Complete negotiations detected: {len(complete_negotiations)}")
    print(f"Source Capabilities messages: {len(source_caps_messages)}")
    print(f"Request messages: {len(request_messages)}")
    print(f"PDO state-aware Request parsing: {sum(1 for r in request_messages if r['message'].request_objects)}")
    
    if complete_negotiations:
        voltage_changes = [n.voltage_after - n.voltage_before for n in complete_negotiations]
        avg_change = sum(voltage_changes) / len(voltage_changes)
        print(f"Average voltage change: {avg_change:+.3f}V")


def main() -> None:
    db_path = Path("data/sqlite/pd_new.sqlite")
    if not db_path.exists():
        print(f"Database not found: {db_path}")
        return
        
    analyze_power_negotiation(db_path)


if __name__ == "__main__":
    main()