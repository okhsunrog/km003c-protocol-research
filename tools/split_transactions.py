#!/usr/bin/env python3
import json
import sys
from typing import List, Dict, Any, Tuple


def load_frames(path: str) -> List[Dict[str, Any]]:
    frames: List[Dict[str, Any]] = []
    with open(path, 'r', encoding='utf-8') as f:
        for raw in f:
            raw = raw.rstrip('\n')
            if not raw or raw.lstrip().startswith('#'):
                # Skip comments/blank lines in manual file
                continue
            try:
                frames.append(json.loads(raw))
            except json.JSONDecodeError:
                # Skip non-JSON lines (e.g., manual separators)
                continue
    return frames


def split_transactions(frames: List[Dict[str, Any]]):
    control_txns: List[List[Dict[str, Any]]] = []
    bulk_txns: List[List[Dict[str, Any]]] = []
    cancelled: List[Dict[str, Any]] = []

    i = 0
    n = len(frames)
    while i < n:
        f = frames[i]
        tt = f.get("transfer_type")
        urb = f.get("urb_type") or f.get("urb")

        # Control transfers (0x02): pair S and C with same urb_id
        if tt == "0x02" and urb == "S":
            urb_id = f.get("urb_id")
            txn = [f]
            j = i + 1
            while j < n:
                g = frames[j]
                txn.append(g)
                if g.get("urb_type") in ("C", "Complete", "C ") and g.get("urb_id") == urb_id:
                    break
                j += 1
            control_txns.append(txn)
            i = j + 1
            continue

        # Bulk transfers (0x03): S(cmd 0x01) -> C(0x01) -> C(0x81) -> S(0x81)
        if (
            tt == "0x03"
            and urb == "S"
            and f.get("endpoint_address") == "0x01"
            and (f.get("data_length", 0) or f.get("urb_length", 0))
        ):
            txn = [f]
            j = i + 1
            # Ack complete on 0x01
            if j < n and frames[j].get("urb_type") == "C" and frames[j].get("endpoint_address") == "0x01":
                txn.append(frames[j])
                j += 1
            # Data complete on 0x81
            if j < n and frames[j].get("urb_type") == "C" and frames[j].get("endpoint_address") == "0x81":
                txn.append(frames[j])
                j += 1
            # Pre-position submit on 0x81
            if j < n and frames[j].get("urb_type") == "S" and frames[j].get("endpoint_address") == "0x81":
                txn.append(frames[j])
                j += 1
            bulk_txns.append(txn)
            i = j
            continue

        # Cancelled receives (urb_status == -2)
        if tt == "0x03" and urb == "C" and f.get("urb_status") == "-2":
            cancelled.append(f)
            i += 1
            continue

        i += 1

    return control_txns, bulk_txns, cancelled


def summarize_bulk(txn: List[Dict[str, Any]]) -> Tuple[int, str]:
    start = txn[0]
    frame = start.get("frame_number") or start.get("frame")
    payload = start.get("payload_hex", "")
    cmd_byte = payload[2:4] if len(payload) >= 4 else "??"
    return frame, f"0x{cmd_byte}"


def main():
    if len(sys.argv) < 2:
        print("Usage: split_transactions.py <jsonl_file>")
        return 2
    path = sys.argv[1]
    frames = load_frames(path)
    control_txns, bulk_txns, cancelled = split_transactions(frames)

    print(f"Control transactions: {len(control_txns)}")
    for t in control_txns:
        s = t[0]
        e = t[-1]
        print(f"  CTL frames {s.get('frame_number')}–{e.get('frame_number')} urb_id={s.get('urb_id')}")

    print(f"Bulk transactions: {len(bulk_txns)}")
    for t in bulk_txns:
        sframe, cmd = summarize_bulk(t)
        eframe = t[-1].get('frame_number')
        print(f"  BULK {cmd} frames {sframe}–{eframe} len={len(t)}")

    if cancelled:
        print(f"Cancelled: {len(cancelled)}")
        for c in cancelled:
            print(f"  CANCEL frame {c.get('frame_number')} urb_id={c.get('urb_id')}")


if __name__ == "__main__":
    sys.exit(main())

