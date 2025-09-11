#!/usr/bin/env python3
import json
from pathlib import Path
from typing import List, Dict, Any
from split_transactions import load_frames, split_transactions


def write_manual(frames: List[Dict[str, Any]], out_path: Path):
    control, bulk, cancelled = split_transactions(frames)

    with out_path.open('w', encoding='utf-8') as w:
        w.write('# Manual grouping to show correct transaction boundaries based on real USB dataset\n')
        w.write('# Each transaction is a complete command-response sequence following the guide\'s rules\n\n')

        # Control transfers
        if control:
            w.write('# Control Transfer Transactions (Device Enumeration Phase)\n')
        for idx, txn in enumerate(control, 1):
            s, e = txn[0], txn[-1]
            w.write(f'# Transaction {idx}: Control transfer\n')
            for f in txn:
                rec = {
                    "transaction": f"Control_{idx}",
                    "frame_number": f.get("frame_number"),
                    "timestamp": f.get("timestamp"),
                    "transfer_type": f.get("transfer_type"),
                    "endpoint_address": f.get("endpoint_address"),
                    "urb_type": f.get("urb_type") or f.get("urb"),
                    "urb_status": f.get("urb_status"),
                    "urb_id": f.get("urb_id"),
                    "payload_hex": f.get("payload_hex", ""),
                    "parsed": ("Control S" if (f.get("urb_type") or f.get("urb")) == "S" else "Control C")
                }
                w.write(json.dumps(rec) + '\n')
            w.write('\n')

        # Bulk transfers
        for t_idx, txn in enumerate(bulk, 1):
            # Extract command id from payload_hex like 0cXX0200
            start = txn[0]
            ph = start.get('payload_hex', '')
            cmd_byte = ph[2:4] if len(ph) >= 4 else '??'
            label = f'ADC_{cmd_byte.lower()}'
            w.write(f'# Transaction (ADC Sample 0x{cmd_byte})\n')
            for f in txn:
                parsed = 'Pre-position for next'
                if f.get('urb_type') == 'S' and f.get('endpoint_address') == '0x01':
                    parsed = f'CmdGetSimpleAdcData 0x{cmd_byte}'
                elif f.get('urb_type') == 'C' and f.get('endpoint_address') == '0x01':
                    parsed = f'ACK for 0x{cmd_byte}'
                elif f.get('urb_type') == 'C' and f.get('endpoint_address') == '0x81':
                    parsed = f'SimpleAdcData 0x{cmd_byte}'
                rec = {
                    "transaction": label,
                    "frame_number": f.get("frame_number"),
                    "timestamp": f.get("timestamp"),
                    "transfer_type": f.get("transfer_type"),
                    "endpoint_address": f.get("endpoint_address"),
                    "urb_type": f.get("urb_type") or f.get("urb"),
                    "urb_status": f.get("urb_status"),
                    "urb_id": f.get("urb_id"),
                    "payload_hex": f.get("payload_hex", ""),
                    "parsed": parsed,
                }
                w.write(json.dumps(rec) + '\n')
            w.write('\n')

        # Cancelled entries (separate group)
        if cancelled:
            w.write('# Cancelled bulk completes (ENOENT)\n')
            for f in cancelled:
                rec = {
                    "transaction": "CANCELLED",
                    "frame_number": f.get("frame_number"),
                    "timestamp": f.get("timestamp"),
                    "transfer_type": f.get("transfer_type"),
                    "endpoint_address": f.get("endpoint_address"),
                    "urb_type": f.get("urb_type") or f.get("urb"),
                    "urb_status": f.get("urb_status"),
                    "urb_id": f.get("urb_id"),
                    "payload_hex": f.get("payload_hex", ""),
                    "parsed": "Cancelled complete",
                }
                w.write(json.dumps(rec) + '\n')


def main():
    src = Path('for_manual_split_gpt.jsonl')
    dst = Path('for_manual_split_gpt_manually_split.jsonl')
    frames = load_frames(str(src))
    write_manual(frames, dst)
    print(f"Wrote {dst}")


if __name__ == '__main__':
    main()

