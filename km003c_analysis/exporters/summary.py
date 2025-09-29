#!/usr/bin/env python3
"""
Summarize PD wire messages across all sources using the wrapped-event parser.

For each source_file:
- Consider PD-only PutData (attribute=16) with size_bytes > 12
- Parse payloads as an event stream: 12B preamble + repeated (6B header + PD wire)
- Attempt to parse the PD wire with usbpdpy and count message types

Run:
  .venv/bin/python notebooks/summarize_pd_messages.py
"""

from __future__ import annotations

from pathlib import Path
from collections import Counter, defaultdict
import polars as pl
import usbpdpy

from ..core.usb_transaction_splitter import split_usb_transactions
from ..core.transaction_tagger import tag_transactions


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

        # Clear bits 7..6, keep lower 6 bits for size code
        size = size_flag & 0x3F
        sop_valid = (size_flag & 0x80) != 0
        wire_len = max(0, size - 5)  # -5 for the SOP header length
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


def summarize_source(df: pl.DataFrame, source_file: str) -> dict:
    per_type = Counter()
    payloads = 0
    decoded_payloads = 0
    per_len = Counter()
    # Build transaction view
    tx = (
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
    )
    for r in tx.iter_rows(named=True):
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
        payloads += 1
        payload = b[8 : 8 + size]
        per_len[size] += 1
        events = parse_pd_wrapped_payload(payload)
        names = [e["pd_name"] for e in events if e.get("pd_name")]
        if names:
            decoded_payloads += 1
            for n in names:
                per_type[n] += 1
    return {
        "source": source_file,
        "pd_payloads": payloads,
        "decoded_payloads": decoded_payloads,
        "type_counts": per_type,
        "size_counts": per_len,
    }


def main() -> None:
    df = pl.read_parquet(PROJECT_ROOT / "data" / "processed" / "usb_master_dataset.parquet")
    summaries = []
    for sf in sorted(df.select("source_file").unique().to_series().to_list()):
        d = df.filter(pl.col("source_file") == sf)
        if d.is_empty():
            continue
        d = tag_transactions(split_usb_transactions(d))
        s = summarize_source(d, sf)
        summaries.append(s)

    print("=== PD message summary (wrapped-event parser) ===")
    for s in summaries:
        print(f"Source: {s['source']}")
        print(
            f"  PD-only payloads>12B: {s['pd_payloads']} | decoded: {s['decoded_payloads']}"
        )
        if s["size_counts"]:
            top_sizes = ", ".join(
                f"{k}:{v}" for k, v in s["size_counts"].most_common(5)
            )
            print(f"  size_bytes counts: {top_sizes}")
        if s["type_counts"]:
            top_types = ", ".join(
                f"{k}:{v}" for k, v in s["type_counts"].most_common(8)
            )
            print(f"  PD types: {top_types}")
        print()


if __name__ == "__main__":
    main()

