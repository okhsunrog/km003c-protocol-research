#!/usr/bin/env python3
"""
Extract and parse all Source_Capabilities from SQLite PD data using usbpdpy v0.2.0

Now that we know usbpdpy v0.2.0 correctly parses the 26-byte Source_Capabilities,
let's extract all of them from the SQLite data and analyze the power profiles.
"""

import sqlite3
import usbpdpy
from pathlib import Path
from collections import defaultdict


def extract_source_capabilities_from_sqlite():
    """Extract all Source_Capabilities from SQLite PD export."""

    sqlite_path = Path("data/sqlite/pd_new.sqlite")
    if not sqlite_path.exists():
        print(f"❌ SQLite file not found: {sqlite_path}")
        return

    print("=== EXTRACTING ALL SOURCE_CAPABILITIES FROM SQLITE ===")
    print(f"Using usbpdpy v{usbpdpy.__version__}")
    print()

    conn = sqlite3.connect(sqlite_path)
    cursor = conn.cursor()

    # Get all PD events
    cursor.execute("SELECT Time, Raw FROM pd_table ORDER BY Time")
    rows = cursor.fetchall()

    print(f"Total PD events in SQLite: {len(rows)}")

    source_caps_found = []
    all_26byte_messages = []
    parse_attempts = 0
    successful_parses = 0

    for time_val, raw_blob in rows:
        if not raw_blob:
            continue

        # Parse the wrapped event format (from previous research)
        # Skip 12-byte preamble, then parse 6-byte headers + PD wire
        raw_data = raw_blob
        cursor_pos = 12  # Skip preamble

        while cursor_pos < len(raw_data):
            if cursor_pos + 6 > len(raw_data):
                break

            # Read 6-byte event header
            event_header = raw_data[cursor_pos:cursor_pos + 6]
            if len(event_header) < 6:
                break

            # Extract size from header (first byte, mask 0x3F)
            size_flag = event_header[0]
            wire_size = (size_flag & 0x3F) - 5  # Subtract header overhead

            if wire_size <= 0 or cursor_pos + 6 + wire_size > len(raw_data):
                break

            # Extract PD wire message
            cursor_pos += 6  # Skip event header
            wire_bytes = raw_data[cursor_pos:cursor_pos + wire_size]
            cursor_pos += wire_size

            if len(wire_bytes) == 26:  # Source_Capabilities candidate
                wire_hex = wire_bytes.hex()
                all_26byte_messages.append({
                    'timestamp': time_val,
                    'hex': wire_hex,
                    'bytes': wire_bytes
                })

                parse_attempts += 1
                try:
                    msg = usbpdpy.parse_pd_message(wire_bytes)
                    successful_parses += 1

                    if msg.header.message_type == "Source_Capabilities":
                        source_caps_found.append({
                            'timestamp': time_val,
                            'hex': wire_hex,
                            'message': msg,
                            'pdos': msg.data_objects
                        })

                except Exception as e:
                    # Ignore parse errors for now
                    pass

    conn.close()

    print(f"26-byte messages found: {len(all_26byte_messages)}")
    print(f"Parse attempts: {parse_attempts}")
    print(f"Successful parses: {successful_parses}")
    print(f"Source_Capabilities found: {len(source_caps_found)}")
    print()

    # Analyze unique power profiles
    if source_caps_found:
        print("=== SOURCE_CAPABILITIES ANALYSIS ===")

        power_profiles = defaultdict(list)

        for i, cap in enumerate(source_caps_found):
            print(f"--- Source_Capabilities #{i+1} (t={cap['timestamp']}ms) ---")
            print(f"Hex: {cap['hex']}")

            # Create power profile signature
            profile_sig = []
            for j, pdo in enumerate(cap['pdos']):
                pdo_desc = f"{pdo.pdo_type}_{pdo.voltage_v}V_{pdo.max_current_a}A"
                profile_sig.append(pdo_desc)
                print(f"  PDO{j+1}: {pdo.pdo_type} {pdo.voltage_v}V @ {pdo.max_current_a}A = {pdo.max_power_w}W")
                if hasattr(pdo, 'unconstrained_power') and pdo.unconstrained_power:
                    print(f"    (Unconstrained power)")

            profile_key = " | ".join(profile_sig)
            power_profiles[profile_key].append(cap['timestamp'])
            print()

        print("=== UNIQUE POWER PROFILES ===")
        for profile, timestamps in power_profiles.items():
            print(f"Profile: {profile}")
            print(f"Occurrences: {len(timestamps)} times")
            print(f"Timestamps: {timestamps[:5]}{'...' if len(timestamps) > 5 else ''}")
            print()

    # Also try direct parsing of all 26-byte messages
    print("=== DIRECT PARSING OF ALL 26-BYTE CANDIDATES ===")
    direct_source_caps = 0

    for msg_data in all_26byte_messages:
        try:
            msg = usbpdpy.parse_pd_message(msg_data['bytes'])
            if msg.header.message_type == "Source_Capabilities":
                direct_source_caps += 1
        except:
            pass

    print(f"Direct parsing: {direct_source_caps}/{len(all_26byte_messages)} are Source_Capabilities")

    return source_caps_found


if __name__ == "__main__":
    capabilities = extract_source_capabilities_from_sqlite()