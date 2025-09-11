#!/usr/bin/env python3
import json
import sys
from typing import Any, Dict, List, Optional


def load_raw_lines(path: str) -> List[str]:
    with open(path, 'r', encoding='utf-8') as f:
        return [ln.rstrip('\n') for ln in f]


def try_parse_json(line: str) -> Optional[Dict[str, Any]]:
    try:
        return json.loads(line)
    except Exception:
        return None


def is_control_start(o: Dict[str, Any]) -> bool:
    return (
        o.get('transfer_type') == '0x02' and
        (o.get('urb_type') or o.get('urb')) == 'S'
    )


def is_control_end(o: Dict[str, Any], start_urb_id: str) -> bool:
    return (
        o.get('transfer_type') == '0x02' and
        (o.get('urb_type') or o.get('urb')) == 'C' and
        o.get('urb_id') == start_urb_id
    )


def is_bulk_cmd_start(o: Dict[str, Any]) -> bool:
    urb_type = o.get('urb_type') or o.get('urb')
    return (
        o.get('transfer_type') == '0x03' and
        o.get('endpoint_address') == '0x01' and
        urb_type == 'S' and
        (o.get('data_length', 0) or o.get('urb_length', 0)) > 0
    )


def is_bulk_ack(o: Dict[str, Any], cmd_urb_id: str) -> bool:
    return (
        o.get('transfer_type') == '0x03' and
        o.get('endpoint_address') == '0x01' and
        (o.get('urb_type') or o.get('urb')) == 'C' and
        o.get('urb_id') == cmd_urb_id
    )


def is_bulk_data_complete(o: Dict[str, Any]) -> bool:
    return (
        o.get('transfer_type') == '0x03' and
        o.get('endpoint_address') == '0x81' and
        (o.get('urb_type') or o.get('urb')) == 'C'
    )


def is_bulk_prepos_submit(o: Dict[str, Any]) -> bool:
    return (
        o.get('transfer_type') == '0x03' and
        o.get('endpoint_address') == '0x81' and
        (o.get('urb_type') or o.get('urb')) == 'S'
    )


def is_cancelled(o: Dict[str, Any]) -> bool:
    return str(o.get('urb_status')) == '-2'


def annotate(in_path: str, out_path: str) -> None:
    lines = load_raw_lines(in_path)
    out = []

    txn_seq = 0
    in_txn = False
    txn_type = None  # 'control' | 'bulk'
    ctrl_urb_id = None
    bulk_cmd_urb_id = None

    printed_any_txn = False

    for raw in lines:
        obj = try_parse_json(raw)

        # passthrough non-JSON/comment lines unmodified
        if obj is None:
            out.append(raw)
            continue

        # Decide if this line starts a new transaction
        start_new = False
        new_txn_type = None
        if is_control_start(obj):
            start_new = True
            new_txn_type = 'control'
        elif is_bulk_cmd_start(obj):
            start_new = True
            new_txn_type = 'bulk'

        if start_new:
            txn_seq += 1
            in_txn = True
            txn_type = new_txn_type
            # control tracking
            ctrl_urb_id = obj.get('urb_id') if txn_type == 'control' else None
            # bulk tracking
            bulk_cmd_urb_id = obj.get('urb_id') if txn_type == 'bulk' else None

            # Insert empty line before the first frame of every transaction except the first
            if printed_any_txn:
                out.append("")
            printed_any_txn = True

        # Default behavior: if not in a transaction yet, we attach to previous transaction when one appears
        # but we must preserve order, so for now we keep in_txn as-is.

        # Assign annotation if we have an active transaction; otherwise leave as-is
        if in_txn:
            obj['transaction_seq'] = txn_seq
            obj['transaction_type'] = txn_type

            # Simple frame role
            role = None
            urb_type = obj.get('urb_type') or obj.get('urb')
            ep = obj.get('endpoint_address')
            if txn_type == 'control':
                role = 'control_submit' if urb_type == 'S' else 'control_complete'
            elif txn_type == 'bulk':
                if urb_type == 'S' and ep == '0x01':
                    role = 'bulk_cmd_submit'
                elif urb_type == 'C' and ep == '0x01' and bulk_cmd_urb_id == obj.get('urb_id'):
                    role = 'bulk_cmd_ack'
                elif urb_type == 'C' and ep == '0x81':
                    role = 'bulk_data_complete'
                elif urb_type == 'S' and ep == '0x81':
                    role = 'bulk_prepos_submit'
            if is_cancelled(obj):
                role = (role + '_cancelled') if role else 'cancelled'
            obj['frame_role'] = role

        # Write line
        out.append(json.dumps(obj))

        # Decide if transaction should end (for blank line purposes we only break when a new transaction starts)
        # We keep cancelled frames attached to previous transaction by NOT starting a new txn for them.
        # And we keep bulk pre-position frames in the same transaction.
        if in_txn and txn_type == 'control' and ctrl_urb_id and is_control_end(obj, ctrl_urb_id):
            # End control; but do not print a blank line now (we print before next txn starts)
            in_txn = True  # keep true so that following cancelled frames are still labeled
            ctrl_urb_id = None

        if in_txn and txn_type == 'bulk':
            # End after pre-position submit; but remain in_txn until next start so that
            # late-cancelled frames will still be marked as part of this txn
            if is_bulk_prepos_submit(obj):
                pass  # nothing to change; we keep txn open logically until next start

        # If no active transaction has been started yet, but we see setup/cancelled frames,
        # attach them to previous transaction when one exists (already handled by not starting new txn)

    with open(out_path, 'w', encoding='utf-8') as w:
        w.write('\n'.join(out) + ('\n' if out and not out[-1].endswith('\n') else ''))


def main():
    if len(sys.argv) < 3:
        print('Usage: annotate_transactions_minimal.py <input.jsonl> <output.jsonl>')
        sys.exit(2)
    annotate(sys.argv[1], sys.argv[2])


if __name__ == '__main__':
    main()

