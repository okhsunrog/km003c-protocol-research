#!/usr/bin/env python3
"""
Export complete PD analysis to Parquet format using usbpdpy v0.2.0

This script creates a comprehensive dataset from KM003C SQLite exports with:
- Complete PDO parsing and analysis
- Full RDO parsing with PDO state management
- Power negotiation flow tracking
- Real-world voltage correlation

Output: data/processed/complete_pd_analysis.parquet
"""

import sqlite3
import pandas as pd
from pathlib import Path
from typing import Dict, List, Any, Optional
import usbpdpy


def extract_pdo_details(pdo: usbpdpy.PowerDataObj) -> Dict[str, Any]:
    """Extract detailed PDO information for analysis"""
    return {
        'pdo_raw': pdo.raw,
        'pdo_type': pdo.pdo_type,
        'voltage_v': pdo.voltage_v,
        'max_current_a': pdo.max_current_a,
        'max_power_w': pdo.max_power_w,
        'min_voltage_v': pdo.min_voltage_v,
        'max_voltage_v': pdo.max_voltage_v,
        'dual_role_power': pdo.dual_role_power,
        'usb_communications_capable': pdo.usb_communications_capable,
        'unconstrained_power': pdo.unconstrained_power,
    }


def extract_rdo_details(rdo: usbpdpy.RequestDataObj) -> Dict[str, Any]:
    """Extract detailed RDO information for analysis"""
    return {
        'rdo_raw': rdo.raw,
        'rdo_type': rdo.rdo_type,
        'object_position': rdo.object_position,
        'operating_current_a': rdo.operating_current_a,
        'max_operating_current_a': rdo.max_operating_current_a,
        'operating_voltage_v': rdo.operating_voltage_v,
        'operating_power_w': rdo.operating_power_w,
        'max_operating_power_w': rdo.max_operating_power_w,
        'capability_mismatch': rdo.capability_mismatch,
        'usb_communications_capable': rdo.usb_communications_capable,
        'no_usb_suspend': rdo.no_usb_suspend,
        'giveback_flag': rdo.giveback_flag,
    }


def parse_pd_blob(blob: bytes) -> List[Dict[str, Any]]:
    """Parse KM003C PD event BLOB"""
    events = []
    if not blob:
        return events
        
    b = blob
    i = 0
    
    while i < len(b):
        t0 = b[i]
        
        if t0 == 0x45:
            # Connection/Status event
            if i + 6 <= len(b):
                ts = int.from_bytes(b[i + 1 : i + 4], "little")
                events.append({
                    "event_type": "connection",
                    "timestamp_ms": ts,
                    "wire_bytes": b[i:i+6],
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
                "event_type": "pd_message",
                "timestamp_ms": ts,
                "sop": sop,
                "wire_len": wire_len,
                "wire_bytes": wire,
            })
        else:
            break
            
    return events


def export_complete_pd_analysis() -> None:
    """Export complete PD analysis to Parquet"""
    
    db_path = Path("data/sqlite/pd_new.sqlite")
    if not db_path.exists():
        print(f"Database not found: {db_path}")
        return
    
    # Read SQLite data
    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()
    cur.execute("SELECT Time, Vbus, Ibus, Raw FROM pd_table ORDER BY Time")
    rows = cur.fetchall()
    
    print("=== EXPORTING PD ANALYSIS ===")
    
    # Process all events
    analysis_records = []
    last_source_capabilities = None
    negotiation_id = 0
    
    for row_id, (time_s, vbus_v, ibus_a, raw) in enumerate(rows):
        events = parse_pd_blob(raw)
        
        for event_id, event in enumerate(events):
            
            base_record = {
                'row_id': row_id,
                'event_id': event_id,
                'time_s': time_s,
                'vbus_v': vbus_v,
                'ibus_a': ibus_a,
                'event_type': event['event_type'],
                'timestamp_ms': event['timestamp_ms'],
                'wire_hex': event['wire_bytes'].hex(),
                'wire_len': len(event['wire_bytes']),
            }
            
            if event['event_type'] == 'connection':
                # Connection event
                record = {**base_record}
                record.update({
                    'pd_message_type': None,
                    'pd_power_role': None,
                    'pd_data_role': None,
                    'pd_message_id': None,
                    'pd_num_objects': None,
                })
                analysis_records.append(record)
                
            elif event['event_type'] == 'pd_message':
                # Parse PD message
                wire_bytes = event['wire_bytes']
                
                try:
                    # Basic parsing
                    msg = usbpdpy.parse_pd_message(wire_bytes)
                    
                    # Enhanced parsing for Request messages
                    if msg.header.message_type == "Request" and last_source_capabilities:
                        msg = usbpdpy.parse_pd_message_with_state(
                            wire_bytes, 
                            last_source_capabilities.data_objects
                        )
                    
                    # Base message info
                    record = {**base_record}
                    record.update({
                        'pd_message_type': msg.header.message_type,
                        'pd_power_role': msg.header.port_power_role,
                        'pd_data_role': msg.header.port_data_role,
                        'pd_message_id': msg.header.message_id,
                        'pd_num_objects': msg.header.num_data_objects,
                        'pd_spec_revision': msg.header.spec_revision,
                        'pd_extended': msg.header.extended,
                    })
                    
                    # Track negotiations
                    if msg.header.message_type == "Source_Capabilities":
                        negotiation_id += 1
                        last_source_capabilities = msg
                        
                    record['negotiation_id'] = negotiation_id
                    
                    # PDO data (Source_Capabilities)
                    if msg.data_objects:
                        for i, pdo in enumerate(msg.data_objects):
                            pdo_record = record.copy()
                            pdo_record['pdo_position'] = i + 1
                            pdo_record.update(extract_pdo_details(pdo))
                            analysis_records.append(pdo_record)
                    
                    # RDO data (Request messages)
                    elif msg.request_objects:
                        for i, rdo in enumerate(msg.request_objects):
                            rdo_record = record.copy()
                            rdo_record.update(extract_rdo_details(rdo))
                            
                            # Add requested PDO details if available
                            if (last_source_capabilities and 
                                1 <= rdo.object_position <= len(last_source_capabilities.data_objects)):
                                requested_pdo = last_source_capabilities.data_objects[rdo.object_position - 1]
                                rdo_record.update({
                                    'requested_pdo_type': requested_pdo.pdo_type,
                                    'requested_voltage_v': requested_pdo.voltage_v,
                                    'requested_max_current_a': requested_pdo.max_current_a,
                                    'requested_max_power_w': requested_pdo.max_power_w,
                                })
                            
                            analysis_records.append(rdo_record)
                    
                    else:
                        # Control messages (no data objects)
                        analysis_records.append(record)
                        
                except Exception as e:
                    # Failed parsing
                    record = {**base_record}
                    record.update({
                        'pd_message_type': 'PARSE_ERROR',
                        'parse_error': str(e),
                    })
                    analysis_records.append(record)
    
    # Create DataFrame
    df = pd.DataFrame(analysis_records)
    
    # Export to Parquet
    output_path = Path("data/processed/complete_pd_analysis.parquet")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    df.to_parquet(output_path, index=False)
    
    # Summary
    print(f"Exported {len(analysis_records)} records to {output_path}")
    print(f"DataFrame shape: {df.shape}")
    print(f"Message types: {df['pd_message_type'].value_counts().to_dict()}")
    print(f"Negotiations detected: {df['negotiation_id'].max()}")
    
    # Show sample data
    print("\\nSample records:")
    print(df[['time_s', 'pd_message_type', 'vbus_v', 'object_position', 'pdo_type', 'rdo_type']].head(10))
    
    return df


if __name__ == "__main__":
    export_complete_pd_analysis()