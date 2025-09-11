#!/usr/bin/env python3
import re
import sys
from typing import Dict, List, Tuple
import json
import importlib.util
from pathlib import Path

def load_root_splitter():
    root = Path(__file__).resolve().parents[1] / 'split_transactions.py'
    spec = importlib.util.spec_from_file_location("root_split_transactions", str(root))
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod.KM003CTransactionSplitter


manual_txn_re = re.compile(r"^#\s*Transaction\s+(?:\(ADC Sample (0x[0-9a-f]{2})\)|(?:(0x[0-9a-f]{2})|CTL-([0-9]+))).*", re.I)


def parse_manual_headers(path: str) -> Tuple[Dict[int, str], Dict[int, str]]:
    bulk: Dict[int, str] = {}
    ctl: Dict[int, str] = {}
    last_label: str | None = None
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            s = line.strip()
            if not s or s.startswith('{'):
                # If we are inside a transaction header context, capture the first JSON as the start frame
                if last_label and s.startswith('{'):
                    try:
                        obj = json.loads(s)
                        sf = int(obj.get('frame_number'))
                        if last_label.startswith('0x'):
                            bulk[sf] = last_label.lower()
                        else:
                            ctl[sf] = last_label
                        last_label = None
                    except Exception:
                        last_label = None
                continue
            m = manual_txn_re.match(s)
            if m:
                adc1, adc2, ctl_idx = m.groups()
                if adc1 or adc2:
                    last_label = (adc1 or adc2).lower()
                elif ctl_idx:
                    last_label = f'CTL-{ctl_idx}'
                else:
                    last_label = None
            else:
                last_label = None
    return bulk, ctl


def main():
    if len(sys.argv) < 3:
        print("Usage: compare_manual_vs_auto.py <manual_jsonl> <raw_jsonl>")
        return 2
    manual_path = sys.argv[1]
    raw_path = sys.argv[2]
    KM = load_root_splitter()
    splitter = KM()
    frames = splitter.load_frames(raw_path)
    transactions = splitter.split_transactions(frames)

    # build auto maps
    auto_ctl = [t for t in transactions if t.transaction_type == 'Control']
    auto_bulk = [t for t in transactions if t.transaction_type == 'KM003C_Command']
    auto_cancel = [f for f in frames if f.transfer_type == '0x03' and f.urb_type == 'C' and f.urb_status == '-2']

    manual_bulk, manual_ctl = parse_manual_headers(manual_path)

    auto_bulk_map: Dict[int, str] = {}
    for t in auto_bulk:
        sframe = t.frames[0].frame_number
        # derive cmd from payload_hex of first frame
        ph = t.frames[0].payload_hex
        cmd = (f"0x{ph[2:4]}" if ph and len(ph) >= 4 else "0x??").lower()
        auto_bulk_map[int(sframe)] = cmd

    # Control comparisons by start frame only
    auto_ctl_starts = {int(t.frames[0].frame_number) for t in auto_ctl}

    print("Manual bulk starts:", len(manual_bulk))
    print("Auto   bulk starts:", len(auto_bulk_map))
    missing_in_auto = sorted([sf for sf in manual_bulk if sf not in auto_bulk_map])
    missing_in_manual = sorted([sf for sf in auto_bulk_map if sf not in manual_bulk])
    label_mismatch = sorted([sf for sf, lbl in manual_bulk.items() if sf in auto_bulk_map and auto_bulk_map[sf] != lbl])

    print(f"Missing in auto: {missing_in_auto}")
    print(f"Missing in manual: {missing_in_manual[:20]}{'...' if len(missing_in_manual)>20 else ''}")
    if label_mismatch:
        print("Label mismatches:")
        for sf in label_mismatch:
            print(f"  frame {sf}: manual {manual_bulk[sf]} vs auto {auto_bulk_map[sf]}")

    print("\nManual CTL starts:", len(manual_ctl))
    print("Auto   CTL starts:", len(auto_ctl_starts))
    missing_ctl_in_auto = sorted([sf for sf in manual_ctl if sf not in auto_ctl_starts])
    missing_ctl_in_manual = sorted([sf for sf in auto_ctl_starts if sf not in manual_ctl])
    print(f"Missing CTL in auto: {missing_ctl_in_auto}")
    print(f"Missing CTL in manual: {missing_ctl_in_manual[:20]}{'...' if len(missing_ctl_in_manual)>20 else ''}")

    # Report cancelled summaries too
    if auto_cancel:
        print("\nAuto cancelled summaries:")
        for c in auto_cancel:
            print(f"  CANCEL frame {c.frame_number} urb_id={c.urb_id}")


if __name__ == '__main__':
    sys.exit(main())
