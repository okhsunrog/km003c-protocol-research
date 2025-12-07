#!/usr/bin/env python3
"""Test PD parsing using existing captures from the parquet dataset."""

import polars as pl
from pathlib import Path
import usbpdpy
from km003c import parse_packet, PdEventStream

DATASET = Path("data/processed/usb_master_dataset.parquet")


def get_pd_events(packet):
    """Extract PD events from DataResponse packet."""
    if "DataResponse" not in packet:
        return None
    for payload in packet["DataResponse"]["payloads"]:
        if isinstance(payload, PdEventStream):
            return payload
    return None


def main():
    print("Loading dataset...")
    df = pl.read_parquet(DATASET)

    # Filter for PD capture file with larger payloads (actual events)
    pd_capture = df.filter(
        (pl.col("source_file").str.contains("pd_capture_new.9"))
        & (pl.col("endpoint_address") == "0x81")
        & (pl.col("urb_type") == "C")
        & (pl.col("data_length") > 12)  # Larger than just PdStatus
    )

    print(f"Found {len(pd_capture)} packets with PD event streams")

    # Track Source Capabilities for Request decoding
    source_caps = None
    seen_events = set()

    for row in pd_capture.iter_rows(named=True):
        payload_hex = row.get("payload_hex")
        if not payload_hex:
            continue

        try:
            raw_bytes = bytes.fromhex(payload_hex)
            packet = parse_packet(raw_bytes)
        except Exception as e:
            continue

        pd_events = get_pd_events(packet)
        if not pd_events:
            continue

        for event in pd_events.events:
            ts = event.timestamp
            data = event.data

            # Create unique key
            event_key = (ts, str(data))
            if event_key in seen_events:
                continue
            seen_events.add(event_key)

            # Handle PD messages
            if isinstance(data, dict) and "sop" in data and "wire_data" in data:
                sop = data["sop"]
                wire = bytes(data["wire_data"])

                # Empty wire = connection event
                if len(wire) == 0:
                    if sop == 0x11:
                        print(f"[{ts}ms] ** CONNECT **")
                        source_caps = None
                    elif sop == 0x12:
                        print(f"[{ts}ms] ** DISCONNECT **")
                    continue

                if len(wire) < 2:
                    continue

                # Parse with or without state
                try:
                    if source_caps:
                        msg = usbpdpy.parse_pd_message_with_state(wire, source_caps)
                    else:
                        msg = usbpdpy.parse_pd_message(wire)

                    msg_type = msg.header.message_type
                    msg_id = msg.header.message_id
                    role = f"{msg.header.port_power_role}/{msg.header.port_data_role}"

                    print(f"[{ts}ms] SOP{sop}: {msg_type:20s} (ID={msg_id}, {role})")

                    # Handle Source Capabilities
                    if msg.is_source_capabilities():
                        source_caps = list(msg.data_objects)
                        for i, pdo in enumerate(msg.data_objects):
                            print(f"       PDO[{i+1}]: {pdo}")

                    # Handle Request with RDOs
                    if msg.request_objects:
                        for rdo in msg.request_objects:
                            pos = rdo.object_position
                            if source_caps and 1 <= pos <= len(source_caps):
                                pdo = source_caps[pos - 1]
                                if rdo.operating_current_a is not None:
                                    print(f"       RDO: Requesting PDO#{pos} ({pdo}) @ {rdo.operating_current_a:.2f}A")
                                else:
                                    print(f"       RDO: Requesting PDO#{pos} ({pdo})")
                            else:
                                print(f"       RDO: Requesting PDO#{pos} (raw=0x{rdo.raw:08X})")
                            if rdo.capability_mismatch:
                                print("            [CAPABILITY MISMATCH]")

                except Exception as e:
                    print(f"[{ts}ms] SOP{sop}: Parse error: {e}, raw={wire.hex()}")

    print("\n" + "=" * 60)
    print(f"Processed {len(seen_events)} unique PD events")


if __name__ == "__main__":
    main()
