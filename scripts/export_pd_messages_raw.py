#!/usr/bin/env python3
"""
Export ONLY raw PD wire payloads (bytes) from the official Windows SQLite export.

Input:  data/sqlite/pd_new.sqlite (pd_table with Raw BLOB event stream)
Output: data/processed/pd_messages_raw_from_sqlite.parquet

Each row of the output contains a single binary column `pd_wire` with the
exact bytes of one PD message (header + data objects), with no extra metadata.

Run:
  .venv/bin/python notebooks/export_pd_messages_raw_to_parquet.py
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import List

import polars as pl


def parse_pd_events_from_blob(blob: bytes) -> List[bytes]:
    out: List[bytes] = []
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
            # ts = b[i+1:i+5]  # not exported
            # sop = b[i+5]
            i += 6
            size_code = size_flag & 0x3F
            wire_len = max(0, size_code - 5)
            if wire_len == 0 or i + wire_len > len(b):
                break
            wire = b[i : i + wire_len]
            i += wire_len
            out.append(wire)
            continue
        break
    return out


def main() -> None:
    sqlite_path = Path("data/sqlite/pd_new.sqlite")
    out_path = Path("data/processed/pd_messages_raw_from_sqlite.parquet")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    con = sqlite3.connect(str(sqlite_path))
    rows = con.execute("SELECT Raw FROM pd_table ORDER BY Time").fetchall()

    wires: List[bytes] = []
    for (raw,) in rows:
        wires.extend(parse_pd_events_from_blob(raw))

    if not wires:
        raise SystemExit("No PD wires found in SQLite export")

    df = pl.DataFrame({"pd_wire": wires}, schema={"pd_wire": pl.Binary})
    df.write_parquet(str(out_path))
    print(f"Wrote {len(wires)} PD wires to {out_path}")


if __name__ == "__main__":
    main()

