#!/usr/bin/env python3
"""
KM003C response analysis using the Rust parser (km003c_lib).

This script scans PutData (0x41) responses and classifies payload chains via
the high-level km003c_lib.parse_packet() API instead of manual bit/byte math.

It verifies:
- ADC-only chains (Adc only)
- ADC + PD chains (Adc + PdStatus and/or PdEvents)
- PD-only chains (PdStatus and/or PdEvents with no Adc)

For PdEvents, it attempts to parse every PD wire message with usbpdpy to report
parse success ratio.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple, Dict, Optional, Any

import polars as pl
import usbpdpy
from pathlib import Path

# Use the Rust protocol parser
from km003c_lib import parse_packet
from scripts.km003c_helpers import (
    get_packet_type,
    get_adc_data,
    get_pd_status,
    get_pd_events,
)


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


def _extract_pd_messages_from_stream(pdev: Any) -> List[bytes]:
    """Extract raw PD wire messages (bytes) from a PdEventStream object.

    Falls back gracefully if the event objects don't expose wire_data.
    """
    messages: List[bytes] = []
    try:
        events = getattr(pdev, "events", None)
        if not events:
            return messages
        for e in events:
            # Prefer pyi-compatible fields if available
            event_type = getattr(e, "event_type", None)
            if event_type == "pd_message":
                wire_data = getattr(e, "wire_data", None)
                if wire_data is not None:
                    try:
                        messages.append(bytes(wire_data))
                        continue
                    except Exception:
                        pass
            # Fallback: try direct attributes (sop, wire_data) or dict-like
            if isinstance(e, dict):
                wd = e.get("wire_data")
                if wd is not None:
                    try:
                        messages.append(bytes(wd))
                    except Exception:
                        pass
            else:
                wd = getattr(e, "wire_data", None)
                if isinstance(wd, (bytes, bytearray)):
                    messages.append(bytes(wd))
    except Exception:
        return messages
    return messages


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
            pkt = parse_packet(b)
            if get_packet_type(pkt) != "DataResponse":
                continue

            adc = get_adc_data(pkt)
            pdst = get_pd_status(pkt)
            pdev = get_pd_events(pkt)

            if adc is not None and pdst is None and pdev is None:
                stats["adc_only_ok"] += 1
                continue

            if adc is not None and (pdst is not None or pdev is not None):
                stats["adc_pd_ok"] += 1
                if pdst is not None:
                    stats["adc_pd_status"] += 1
                if pdev is not None:
                    stats["adc_pd_event"] += 1

            if adc is None and pdst is not None and pdev is None:
                stats["pd_only_status"] += 1

            if adc is None and pdev is not None:
                stats["pd_only_event_payloads"] += 1

            # Validate PD messages via usbpdpy
            if pdev is not None:
                wires = _extract_pd_messages_from_stream(pdev)
                stats["pd_events_total"] += len(wires)
                ok = 0
                for w in wires:
                    try:
                        _ = usbpdpy.parse_pd_message(w)
                        ok += 1
                    except Exception:
                        pass
                stats["pd_events_parsed_ok"] += ok
                stats["pd_events_parse_fail"] += (len(wires) - ok)

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
