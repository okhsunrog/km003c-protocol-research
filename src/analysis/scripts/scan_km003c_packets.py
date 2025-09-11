#!/usr/bin/env python3
"""
Scan a parquet dataset, run the Rust-backed KM003C parser over payloads,
and report what packet types are present plus how parsed data looks in Python.

Usage:
  python analysis/scripts/scan_km003c_packets.py --input usb_master_dataset.parquet [--limit 5000]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Dict, Optional

import polars as pl

# Ensure project root on sys.path so we can import km003c_lib when run from anywhere
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Rust Python bindings
try:
    from km003c_lib import parse_packet
except Exception as e:
    print(
        "✗ Failed to import km003c_lib. Ensure the Rust bindings are built and available."
    )
    print(f"  Error: {e}")
    sys.exit(1)


# Lightweight header parsing to classify non-ADC packets for summary purposes.
# Mirrors km003c-rs packet.rs structures at a high level.
def classify_packet(payload: bytes) -> Optional[str]:
    """Best-effort classification of KM003C packet types from raw bytes.

    Returns one of: 'ADC_DATA', 'PD_RAW', 'CMD_GET_ADC', 'CMD_GET_PD', 'GENERIC', or None if too short.
    """
    if len(payload) < 4:
        return None

    # First byte: lower 7 bits = packet_type; top bit is 'extend'.
    first = payload[0]
    packet_type = first & 0x7F
    is_ctrl = packet_type < 0x40

    # Attribute constants from km003c-rs Attribute enum
    ATTR_ADC = 0x0001
    ATTR_PD = 0x0010

    if is_ctrl:
        # CtrlHeader layout (LE): [0]=type+extend, [1]=id, [2..3]=unused(1b)+attribute(15b)
        if len(payload) < 4:
            return None
        attr = int.from_bytes(payload[2:4], "little") & 0x7FFF
        if packet_type == 0x0C:  # GetData
            if attr == ATTR_ADC:
                return "CMD_GET_ADC"
            if attr == ATTR_PD:
                return "CMD_GET_PD"
        return "GENERIC"
    else:
        # DataHeader uses an ExtendedHeader at start of payload for PutData packets
        # ExtendedHeader: [0..1]=attribute(15b)+next(1b), [2]=chunk(6b)+size[9:8], [3]=size[7:0]
        if packet_type == 0x41 and len(payload) >= 6:
            # Data header (4 bytes) already consumed in 'payload'; but in our dataset, 'payload'
            # refers to the whole device message, so extended header starts at payload[4:].
            # However, here we parse directly from provided payload (full message). Skip 4-byte header.
            ext_start = 4
            if len(payload) < ext_start + 4:
                return "GENERIC"
            attr = int.from_bytes(payload[ext_start : ext_start + 2], "little") & 0x7FFF
            if attr == ATTR_ADC:
                return "ADC_DATA"
            if attr == ATTR_PD:
                return "PD_RAW"
            return "GENERIC"
        return "GENERIC"


def parse_non_adc_details(payload: bytes) -> Dict[str, object]:
    """Return a structured view for non-ADC packets using header fields.

    This mirrors the Rust bitfields enough to provide human-readable details.
    """
    if len(payload) < 4:
        return {"kind": "TOO_SHORT", "len": len(payload)}

    first = payload[0]
    pkt_type = first & 0x7F
    is_ctrl = pkt_type < 0x40

    if is_ctrl:
        # CtrlHeader
        if len(payload) < 4:
            return {"kind": "CTRL", "error": "short"}
        pkt_id = payload[1]
        raw_attr = int.from_bytes(payload[2:4], "little") & 0x7FFF
        type_name = {0x0C: "GetData"}.get(pkt_type, f"Ctrl(0x{pkt_type:02X})")
        kind = (
            "CMD_GET_PD"
            if raw_attr == 0x0010
            else ("CMD_GET_ADC" if raw_attr == 0x0001 else "GENERIC")
        )
        return {
            "kind": kind,
            "ctrl_type": type_name,
            "id": pkt_id,
            "attribute": raw_attr,
        }
    else:
        # DataHeader + optional ExtendedHeader
        if len(payload) < 8:
            return {"kind": "DATA", "error": "short"}
        pkt_id = payload[1]
        # Extended header starts at 4
        ext = payload[4:8]
        raw_attr = int.from_bytes(ext[:2], "little") & 0x7FFF
        # Data after extended header
        body = payload[8:]
        kind = (
            "PD_RAW"
            if raw_attr == 0x0010
            else ("ADC_DATA" if raw_attr == 0x0001 else "GENERIC")
        )
        return {
            "kind": kind,
            "data_type": {0x41: "PutData", 0x40: "Head"}.get(
                pkt_type, f"Data(0x{pkt_type:02X})"
            ),
            "id": pkt_id,
            "attribute": raw_attr,
            "payload_len": len(body),
            "payload_head": body[:16].hex(),
        }


def main() -> None:
    ap = argparse.ArgumentParser(description="Scan parquet and parse KM003C packets")
    ap.add_argument("--input", required=True, help="Path to usb_master_dataset.parquet")
    ap.add_argument(
        "--limit", type=int, default=None, help="Optional row limit for quick scan"
    )
    args = ap.parse_args()

    parquet_path = Path(args.input)
    if not parquet_path.exists():
        print(f"✗ Parquet file not found: {parquet_path}")
        sys.exit(1)

    print(f"Loading dataset: {parquet_path}")
    df = pl.read_parquet(str(parquet_path))
    if args.limit:
        df = df.head(args.limit)

    # Only consider packets with payload
    df_payload = df.filter(pl.col("payload_hex") != "")
    total_payload = len(df_payload)
    print(f"Total rows with payload: {total_payload}")

    type_counts: Dict[str, int] = {}
    parsed_samples = []  # store small number of parsed AdcData examples
    non_adc_samples: Dict[str, list] = {
        "PD_RAW": [],
        "CMD_GET_PD": [],
        "CMD_GET_ADC": [],
        "GENERIC": [],
    }

    for row in df_payload.iter_rows(named=True):
        payload_hex = row.get("payload_hex")
        try:
            raw = bytes.fromhex(payload_hex)
        except Exception:
            continue

        # Use Rust parser to detect ADC packets and get parsed data
        parsed = None
        try:
            parsed = parse_packet(raw)
        except Exception:
            parsed = None

        if parsed is not None:
            pkt_type = "ADC_DATA"
            # Capture a few examples to show the Python shape
            if len(parsed_samples) < 5:
                parsed_samples.append(
                    {
                        "repr": repr(parsed),
                        "fields": {
                            "vbus_v": parsed.vbus_v,
                            "ibus_a": parsed.ibus_a,
                            "power_w": parsed.power_w,
                            "vbus_avg_v": parsed.vbus_avg_v,
                            "ibus_avg_a": parsed.ibus_avg_a,
                            "temp_c": parsed.temp_c,
                            "vdp_v": parsed.vdp_v,
                            "vdm_v": parsed.vdm_v,
                            "vdp_avg_v": parsed.vdp_avg_v,
                            "vdm_avg_v": parsed.vdm_avg_v,
                            "cc1_v": parsed.cc1_v,
                            "cc2_v": parsed.cc2_v,
                        },
                    }
                )
        else:
            # Attempt best-effort classification for summary purposes
            pkt_type = classify_packet(raw) or "GENERIC"
            details = parse_non_adc_details(raw)
            # Collect a few examples per non-ADC kind
            bucket = details.get("kind", "GENERIC")
            if bucket in non_adc_samples and len(non_adc_samples[bucket]) < 3:
                non_adc_samples[bucket].append(details)

        type_counts[pkt_type] = type_counts.get(pkt_type, 0) + 1

    # Print summary
    print("\nPacket Type Summary (best effort):")
    for k in sorted(type_counts.keys()):
        print(f"  {k:12s} : {type_counts[k]}")

    # Show how parsed AdcData looks in Python
    adc_count = type_counts.get("ADC_DATA", 0)
    print(f"\nParsed ADC packets via Rust binding: {adc_count}")
    if parsed_samples:
        print("\nSample parsed AdcData objects:")
        for i, sample in enumerate(parsed_samples, 1):
            print(f"[{i}] {sample['repr']}")
            # Flatten key: value one-liners for readability
            fields = sample["fields"]
            keys = [
                "vbus_v",
                "ibus_a",
                "power_w",
                "temp_c",
                "vbus_avg_v",
                "ibus_avg_a",
                "vdp_v",
                "vdm_v",
                "vdp_avg_v",
                "vdm_avg_v",
                "cc1_v",
                "cc2_v",
            ]
            print("    {" + ", ".join(f"{k}: {fields[k]:.6g}" for k in keys) + "}")
    else:
        print("No ADC packets parsed in the scanned rows.")

    print("\nNotes:")
    print("- parse_packet returns an AdcData object only for ADC data packets.")
    print("- Non-ADC (e.g., PD, command, other) currently return None in Python.")

    # Show examples of non-ADC parsing via header interpretation
    print("\nNon-ADC examples (header-derived):")
    for kind in ["PD_RAW", "CMD_GET_PD", "CMD_GET_ADC", "GENERIC"]:
        samples = non_adc_samples.get(kind, [])
        if not samples:
            continue
        print(f"- {kind} ({len(samples)} samples):")
        for i, s in enumerate(samples, 1):
            # Compact key: value printing
            items = ", ".join(f"{k}={v}" for k, v in s.items() if k != "kind")
            print(f"  [{i}] {items}")


if __name__ == "__main__":
    main()
