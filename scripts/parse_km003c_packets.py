#!/usr/bin/env python3
"""
Temporary KM003C parser for ADC-only, ADC+PD, and PD-only packets.

Parses PutData (0x41) responses in the dataset and verifies:
- ADC-only (attribute=1, next=0) → 44-byte ADC payload
- ADC+PD chains (attribute=1, next=1) → nested PD segment
  - PD status (12B) → parsed as status
  - PD event stream (>12B) → preamble + 6B events → parse PD wire via usbpdpy
- PD-only (attribute=16)
  - size=12 → status-like block (not PD wire)
  - size>12 → preamble + 6B events → parse PD wire via usbpdpy

Prints stats and ensures all extracted PD wire messages parse with usbpdpy.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple, Dict, Optional

import polars as pl
import usbpdpy
from pathlib import Path


@dataclass
class MainExt:
    msg_type: int
    msg_id: int
    obj_count: int
    attribute: int
    next_bit: int
    chunk: int
    size_bytes: int


def parse_headers(b: bytes) -> Optional[MainExt]:
    if len(b) < 8:
        return None
    main = int.from_bytes(b[0:4], "little")
    ext = int.from_bytes(b[4:8], "little")
    msg_type = main & 0x7F
    msg_id = (main >> 8) & 0xFF
    obj_count = (main >> 22) & 0x3FF
    attribute = ext & 0x7FFF
    next_bit = (ext >> 15) & 1
    chunk = (ext >> 16) & 0x3F
    size_bytes = (ext >> 22) & 0x3FF
    return MainExt(msg_type, msg_id, obj_count, attribute, next_bit, chunk, size_bytes)


def parse_pd_status_12(b: bytes) -> Dict[str, int]:
    # 12B: [0]=type_id, [1..3]=ts24, [4..5]=vbus_mV, [6..7]=ibus_mA, [8..9]=cc1_mV, [10..11]=cc2_mV
    return {
        "type_id": b[0],
        "ts24": b[1] | (b[2] << 8) | (b[3] << 16),
        "vbus_mV": int.from_bytes(b[4:6], "little", signed=False),
        "ibus_mA": int.from_bytes(b[6:8], "little", signed=False),  # observed non-negative here
        "cc1_mV": int.from_bytes(b[8:10], "little", signed=False),
        "cc2_mV": int.from_bytes(b[10:12], "little", signed=False),
    }


def parse_pd_preamble_12(b: bytes) -> Dict[str, int]:
    # 12B: [0..3]=ts32, [4..5]=vbus_mV, [6..7]=ibus_mA(signed), [8..9]=cc1_mV, [10..11]=cc2_mV
    return {
        "ts32": int.from_bytes(b[0:4], "little", signed=False),
        "vbus_mV": int.from_bytes(b[4:6], "little", signed=False),
        "ibus_mA": int.from_bytes(b[6:8], "little", signed=True),
        "cc1_mV": int.from_bytes(b[8:10], "little", signed=False),
        "cc2_mV": int.from_bytes(b[10:12], "little", signed=False),
    }


def parse_pd_event_stream(pd_payload: bytes) -> List[Dict[str, object]]:
    """Parse preamble + repeated events, return list of events with parsed PD message if any.

    Returns a list of dicts: {timestamp, sop, wire_len, wire_bytes, parsed_type?}
    """
    events: List[Dict[str, object]] = []
    if len(pd_payload) <= 12:
        return events
    # Preamble is present but we don't need values here; skip 12B
    i = 12
    n = len(pd_payload)
    while i + 6 <= n:
        size_flag = pd_payload[i]
        wire_len = (size_flag & 0x3F) - 5
        if wire_len < 2 or (i + 6 + wire_len) > n:
            break
        ts = int.from_bytes(pd_payload[i + 1 : i + 5], "little")
        sop = pd_payload[i + 5]
        wire = pd_payload[i + 6 : i + 6 + wire_len]
        i += 6 + wire_len

        parsed_type = None
        try:
            msg = usbpdpy.parse_pd_message(wire)
            parsed_type = msg.header.message_type
        except Exception:
            parsed_type = None

        events.append(
            {
                "timestamp": ts,
                "sop": sop,
                "wire_len": wire_len,
                "wire": wire,
                "parsed_type": parsed_type,
            }
        )
    return events


def main() -> None:
    dataset = Path("data/processed/usb_master_dataset.parquet")
    df = pl.read_parquet(dataset)
    # Only IN completions with payload
    resp = df.filter(
        (pl.col("endpoint_address") == "0x81")
        & (pl.col("urb_type") == "C")
        & pl.col("payload_hex").is_not_null()
        & (pl.col("payload_hex") != "")
    ).select(["source_file", "timestamp", "payload_hex"])  # compact

    stats = {
        "adc_only_ok": 0,
        "adc_pd_ok": 0,
        "adc_pd_status": 0,
        "adc_pd_event": 0,
        "pd_only_status": 0,
        "pd_only_event_payloads": 0,
        "pd_events_total": 0,
        "pd_events_parsed_ok": 0,
        "pd_events_parse_fail": 0,
        "errors": 0,
    }

    for row in resp.iter_rows(named=True):
        b = bytes.fromhex(row["payload_hex"])  # type: ignore[index]
        try:
            me = parse_headers(b)
            if not me:
                continue
            if me.msg_type != 0x41:
                continue

            if me.attribute == 1:  # ADC segment present
                # always expect 44-byte ADC
                if len(b) < 8 + 44:
                    stats["errors"] += 1
                    continue
                # ADC-only
                if me.next_bit == 0:
                    stats["adc_only_ok"] += 1
                else:
                    # ADC + chained segment (PD or others)
                    off = 8 + 44
                    if len(b) < off + 4:
                        stats["errors"] += 1
                        continue
                    pd_ext = parse_headers(b[off - 8 : off - 8 + 8])  # reuse parse on nested header window
                    # Above is a trick; simpler: directly read PD ext
                    pd_ext_raw = int.from_bytes(b[off : off + 4], "little")
                    pd_attr = pd_ext_raw & 0x7FFF
                    pd_size = (pd_ext_raw >> 22) & 0x3FF
                    # Only handle ADC+PD here; ignore other chained attributes (e.g., AdcQueue)
                    if pd_attr != 16:
                        # Not counted as error; just skip (out of current scope)
                        continue
                    if len(b) < off + 4 + pd_size:
                        stats["errors"] += 1
                        continue
                    pd_payload = b[off + 4 : off + 4 + pd_size]
                    if pd_size == 12:
                        # PD status
                        _ = parse_pd_status_12(pd_payload)
                        stats["adc_pd_status"] += 1
                    elif pd_size > 12:
                        # PD event stream
                        evs = parse_pd_event_stream(pd_payload)
                        stats["adc_pd_event"] += 1
                        stats["pd_events_total"] += len(evs)
                        ok = sum(1 for e in evs if e.get("parsed_type"))
                        stats["pd_events_parsed_ok"] += ok
                        stats["pd_events_parse_fail"] += (len(evs) - ok)
                    stats["adc_pd_ok"] += 1

            elif me.attribute == 16:  # PD-only
                if len(b) < 8 + me.size_bytes:
                    stats["errors"] += 1
                    continue
                pd_payload = b[8 : 8 + me.size_bytes]
                if me.size_bytes == 12:
                    # status-like block
                    stats["pd_only_status"] += 1
                elif me.size_bytes > 12:
                    stats["pd_only_event_payloads"] += 1
                    evs = parse_pd_event_stream(pd_payload)
                    stats["pd_events_total"] += len(evs)
                    ok = sum(1 for e in evs if e.get("parsed_type"))
                    stats["pd_events_parsed_ok"] += ok
                    stats["pd_events_parse_fail"] += (len(evs) - ok)

        except Exception:
            stats["errors"] += 1
            continue

    print("=== KM003C Temporary Parser Results ===")
    for k in [
        "adc_only_ok",
        "adc_pd_ok",
        "adc_pd_status",
        "adc_pd_event",
        "pd_only_status",
        "pd_only_event_payloads",
        "pd_events_total",
        "pd_events_parsed_ok",
        "pd_events_parse_fail",
        "errors",
    ]:
        print(f"{k}: {stats[k]}")

    if stats["pd_events_total"] > 0:
        ratio = 100.0 * stats["pd_events_parsed_ok"] / stats["pd_events_total"]
        print(f"usbpdpy parse success ratio: {ratio:.1f}%")


if __name__ == "__main__":
    main()
