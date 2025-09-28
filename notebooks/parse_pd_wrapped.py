#!/usr/bin/env python3
"""
Parse PD-only PutData payloads (attribute=16, size>12) using the
"wrapped event stream" format observed in community Pascal code.

Format inside PD-only payload (size_bytes > 12):
- First 12 bytes: metadata/preamble
- Then repeated events, each with a 6-byte header followed by a PD wire message:
  - size_flag: 1 byte (bit7 indicates SOP-valid; bits[6..0] carry size)
  - timestamp: 4 bytes (little-endian)
  - sop: 1 byte (SOP type)
  - wire: (size & 0x3F) - 5 bytes of PD wire message (2-byte header + optional data objects)

We extract the PD wire message and parse with usbpdpy when possible.

Run:
  .venv/bin/python notebooks/parse_pd_wrapped.py
"""

from __future__ import annotations

import polars as pl
import usbpdpy
from pathlib import Path

import sys
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from km003c_analysis.usb_transaction_splitter import split_usb_transactions
from km003c_analysis.transaction_tagger import tag_transactions


def parse_pd_wrapped_payload(payload: bytes) -> list[dict]:
    events: list[dict] = []
    if len(payload) <= 12:
        return events
    i = 12
    while i + 6 <= len(payload):
        size_flag = payload[i]
        t0, t1, t2, t3 = payload[i + 1 : i + 5]
        sop = payload[i + 5]
        timestamp = int.from_bytes(bytes([t0, t1, t2, t3]), "little")
        i += 6

        size = size_flag & 0x3F  # clear bits 7 and 6
        sop_valid = (size_flag & 0x80) != 0
        # size includes +5 overhead in Pascal impl; subtract to get PD bytes
        wire_len = max(0, size - 5)
        if wire_len == 0 or i + wire_len > len(payload):
            break
        wire = payload[i : i + wire_len]
        i += wire_len

        parsed_name = None
        try:
            msg = usbpdpy.parse_pd_message(wire)
            parsed_name = usbpdpy.get_message_type_name(msg.header.message_type)
        except Exception:
            pass

        events.append(
            {
                "sop_valid": sop_valid,
                "sop": sop,
                "timestamp": timestamp,
                "size_flag": size_flag,
                "size": size,
                "wire_len": wire_len,
                "pd_name": parsed_name,
            }
        )

    return events


def analyze_source(source_file: str) -> None:
    df = pl.read_parquet(PROJECT_ROOT / "data" / "processed" / "usb_master_dataset.parquet")
    df = df.filter(pl.col("source_file") == source_file)
    df = tag_transactions(split_usb_transactions(df))

    rows = (
        df.group_by("transaction_id")
        .agg(
            pl.min("timestamp").alias("start_time"),
            pl.col("payload_hex")
            .filter(
                (pl.col("endpoint_address") == "0x81")
                & (pl.col("payload_hex").is_not_null())
                & (pl.col("payload_hex") != "")
            )
            .first()
            .alias("response_hex"),
        )
        .sort("start_time")
        .iter_rows(named=True)
    )

    total = 0
    decoded = 0
    for r in rows:
        rh = r.get("response_hex")
        if not rh:
            continue
        b = bytes.fromhex(rh)
        if len(b) < 8:
            continue
        main = int.from_bytes(b[0:4], "little")
        if (main & 0x7F) != 65:
            continue
        ext = int.from_bytes(b[4:8], "little")
        attribute = ext & 0x7FFF
        size = (ext >> 22) & 0x3FF
        if attribute != 16 or size <= 12:
            continue
        total += 1
        payload = b[8 : 8 + size]
        events = parse_pd_wrapped_payload(payload)
        if any(e.get("pd_name") for e in events):
            decoded += 1
            sample = [(e["pd_name"], e["wire_len"]) for e in events if e.get("pd_name")][:6]
            print(
                f"tx {r['transaction_id']} start={r['start_time']:.3f} size={size} events={sample}"
            )

    print(f"Decoded {decoded}/{total} PD-only payloads (size>12) in {source_file}.")


if __name__ == "__main__":
    analyze_source("pd_capture_new.9")
