#!/usr/bin/env python3
"""
Export PD wire messages from the official Windows SQLite export into Parquet.

Input:  data/sqlite/pd_new.sqlite (pd_table with Raw BLOB event stream)
Output: data/processed/pd_messages_from_sqlite.parquet

Each PD event is decoded from the wrapped-event format:
- 0x45 .......... : 6-byte connection/status (skipped; not a PD wire)
- 0x80..0x9F Hdr. : 6-byte event header (size_flag, ts[4], sop[1]) + PD wire
                     wire_len = (size_flag & 0x3F) - 5

For each PD wire, we record hex bytes plus light header introspection
(ndo, extended flag, expected_len) to aid downstream parsing/debugging.

Run:
  .venv/bin/python notebooks/export_pd_messages_to_parquet.py
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

import polars as pl


def parse_pd_events_from_blob(blob: bytes):
    events = []
    i = 0
    b = blob
    while i < len(b):
        t0 = b[i]
        if t0 == 0x45:
            # 6-byte connection/status; skip
            if i + 6 > len(b):
                break
            i += 6
            continue
        if 0x80 <= t0 <= 0x9F:
            if i + 6 > len(b):
                break
            size_flag = b[i]
            ts = int.from_bytes(b[i + 1 : i + 5], "little")
            sop = b[i + 5]
            i += 6
            size_code = size_flag & 0x3F
            wire_len = max(0, size_code - 5)
            if wire_len == 0 or i + wire_len > len(b):
                break
            wire = b[i : i + wire_len]
            i += wire_len
            events.append((ts, sop, size_code, wire_len, wire))
            continue
        # Unknown marker; stop for this blob
        break
    return events


def main() -> None:
    sqlite_path = Path("data/sqlite/pd_new.sqlite")
    out_path = Path("data/processed/pd_messages_from_sqlite.parquet")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    con = sqlite_path.exists() and sqlite3.connect(str(sqlite_path))
    if not con:
        raise SystemExit(f"SQLite file not found: {sqlite_path}")

    rows = con.execute(
        "SELECT rowid, Time, Vbus, Ibus, Raw FROM pd_table ORDER BY Time"
    ).fetchall()

    records: List[Dict[str, Any]] = []
    for rowid, time, vbus, ibus, raw in rows:
        for ts, sop, size_code, wire_len, wire in parse_pd_events_from_blob(raw):
            # Light header decoding if wire has >=2 bytes
            header_le = None
            header_hex = None
            ndo = None
            msg_type_code = None
            extended = None
            if wire_len >= 2:
                header_le = wire[0] | (wire[1] << 8)
                header_hex = wire[:2].hex()
                ndo = (header_le >> 12) & 0x7
                msg_type_code = header_le & 0x0F
                extended = (header_le >> 15) & 0x01
            expected_len = None
            expected_match = None
            if ndo is not None and extended == 0:
                expected_len = 2 + 4 * ndo
                expected_match = (expected_len == wire_len)

            records.append(
                {
                    "source": sqlite_path.name,
                    "sqlite_rowid": rowid,
                    "sqlite_time": float(time),
                    "vbus_v": float(vbus),
                    "ibus_a": float(ibus),
                    "event_ts": int(ts),
                    "sop": int(sop),
                    "size_code": int(size_code),
                    "wire_len": int(wire_len),
                    "wire_hex": wire.hex(),
                    "header_le_hex": header_hex,
                    "header_ndo": ndo,
                    "header_msg_type": msg_type_code,
                    "header_extended": extended,
                    "expected_len": expected_len,
                    "expected_len_match": expected_match,
                }
            )

    if not records:
        raise SystemExit("No PD events found in SQLite export")

    df = pl.DataFrame(records)
    df.write_parquet(str(out_path))
    print(f"Wrote {len(df)} PD messages to {out_path}")
    print("Preview:")
    print(df.select(["sqlite_time", "event_ts", "wire_len", "header_ndo", "expected_len", "expected_len_match"]).head(10))


if __name__ == "__main__":
    main()

