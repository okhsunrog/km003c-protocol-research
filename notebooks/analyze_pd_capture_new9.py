#!/usr/bin/env python3
"""
Analyze transactions for source_file == 'pd_capture_new.9' using the
existing transaction splitter/tagger. Summarize PD/ADC patterns by
parsing request/response payloads at the transaction level.

Run:
  .venv/bin/python notebooks/analyze_pd_capture_new9.py
"""

from __future__ import annotations

from pathlib import Path
import sys
from collections import Counter, defaultdict
from typing import Any, Dict, Tuple

import polars as pl

try:
    # Optional: more detailed parsing if the Rust extension is available
    from km003c_lib import parse_packet, parse_raw_packet  # type: ignore
    HAS_KM003C = True
except Exception:  # pragma: no cover - optional dependency
    HAS_KM003C = False

project_root = Path(__file__).resolve().parents[1]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from km003c_analysis.usb_transaction_splitter import split_usb_transactions
from km003c_analysis.transaction_tagger import tag_transactions


def first_payload(df: pl.DataFrame, endpoint: str) -> str | None:
    col = (
        df.filter(
            (pl.col("endpoint_address") == endpoint)
            & (pl.col("payload_hex").is_not_null())
            & (pl.col("payload_hex") != "")
        )
        .select("payload_hex")
        .to_series()
        .to_list()
    )
    return col[0] if col else None


def parse_headers(hexs: str) -> Dict[str, Any] | None:
    try:
        b = bytes.fromhex(hexs)
        if len(b) < 8:
            return None
        main = int.from_bytes(b[0:4], "little")
        typ = main & 0x7F
        extend = (main >> 7) & 0x1
        pkt_id = (main >> 8) & 0xFF
        obj_count = (main >> 22) & 0x3FF
        ext = int.from_bytes(b[4:8], "little")
        attribute = ext & 0x7FFF
        next_bit = (ext >> 15) & 0x1
        chunk = (ext >> 16) & 0x3F
        size_words = (ext >> 22) & 0x3FF
        size_bytes = size_words * 4 if False else (ext >> 22) & 0x3FF  # bytes mode below
        # Clarify: empirical reading in this repo uses size as bytes
        size_bytes = (ext >> 22) & 0x3FF
        total_len = len(b)
        words_total = total_len // 4
        return {
            "type": typ,
            "extend": extend,
            "id": pkt_id,
            "obj_count": obj_count,
            "attribute": attribute,
            "next": next_bit,
            "chunk": chunk,
            "size_bytes": size_bytes,
            "total_len": total_len,
            "words_total": words_total,
        }
    except Exception:
        return None


def main() -> None:
    data_path = project_root / "data" / "processed" / "usb_master_dataset.parquet"
    df = pl.read_parquet(data_path)
    df_src = df.filter(pl.col("source_file") == "pd_capture_new.9")
    if df_src.is_empty():
        print("No rows for source_file == pd_capture_new.9")
        return

    df_split = split_usb_transactions(df_src)
    df_tagged = tag_transactions(df_split)

    # Summarize tags at transaction level
    tx_summary = (
        df_tagged.group_by("transaction_id")
        .agg(
            pl.min("timestamp").alias("start_time"),
            pl.len().alias("frame_count"),
            pl.first("tags").alias("tags"),
        )
        .sort("start_time")
    )

    # Build request/response hex per transaction
    tx_hex = (
        df_tagged.group_by("transaction_id")
        .agg(
            pl.col("payload_hex")
            .filter(
                (pl.col("endpoint_address") == "0x01")
                & (pl.col("payload_hex").is_not_null())
                & (pl.col("payload_hex") != "")
            )
            .first()
            .alias("request_hex"),
            pl.col("payload_hex")
            .filter(
                (pl.col("endpoint_address") == "0x81")
                & (pl.col("payload_hex").is_not_null())
                & (pl.col("payload_hex") != "")
            )
            .first()
            .alias("response_hex"),
        )
        .sort("transaction_id")
    )

    tx = tx_summary.join(tx_hex, on="transaction_id")

    # Counters
    tags_counter = Counter()
    resp_type_counter = Counter()
    attr_counter = Counter()
    adc_next = Counter()
    adc_extra_bytes = Counter()
    pd_sizes = Counter()

    # Optional: parse via km003c_lib for classification
    used_rust = HAS_KM003C

    for row in tx.iter_rows(named=True):
        tags = row.get("tags") or []
        for t in tags:
            tags_counter[t] += 1

        resp_hex = row.get("response_hex")
        if not resp_hex:
            continue

        parsed = parse_headers(resp_hex)
        if parsed and parsed["type"] == 65:
            attr = parsed["attribute"]
            attr_counter[attr] += 1
            if attr == 1:
                # ADC
                nb = parsed["next"]
                adc_next[nb] += 1
                base = 8 + 44
                extra = max(0, parsed["total_len"] - base)
                if nb == 1 and extra > 0:
                    adc_extra_bytes[extra] += 1
            elif attr == 16:
                # PD
                pd_sizes[parsed["size_bytes"]] += 1
            resp_type_counter["PutData"] += 1
        else:
            if parsed:
                resp_type_counter[f"Type{parsed['type']}"] += 1
            else:
                resp_type_counter["UNPARSED"] += 1

    print("=== pd_capture_new.9 transaction-level summary ===")
    print(f"Total transactions: {len(tx)}")
    print("Top tags:", tags_counter.most_common(10))
    print("Response packet types:", resp_type_counter.most_common())
    print("PutData attributes:", attr_counter.most_common())
    print("ADC next distribution:", adc_next)
    if adc_extra_bytes:
        print("ADC extra bytes (PD extension):", sorted(adc_extra_bytes.items()))
    if pd_sizes:
        print("PD size_bytes distribution:", sorted(pd_sizes.items()))

    # Print a few example transactions with PD extensions
    examples = 0
    for row in tx.iter_rows(named=True):
        if not row.get("response_hex"):
            continue
        p = parse_headers(row["response_hex"])
        if p and p["type"] == 65 and p["attribute"] == 1 and p["next"] == 1:
            examples += 1
            print("\nExample ADC+PD transaction:")
            print(
                f"tx={row['transaction_id']}, frames={row['frame_count']}, tags={row['tags']}, total_len={p['total_len']}, size={p['size_bytes']}, next={p['next']}"
            )
            print("request:", (row.get("request_hex") or "")[:64])
            print("response:", (row.get("response_hex") or "")[:64], "...")
            if examples >= 3:
                break


if __name__ == "__main__":
    main()
