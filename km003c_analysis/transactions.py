import polars as pl
import json
from typing import List, Dict, Any, Optional

try:
    import km003c_lib
    KM003C_LIB_AVAILABLE = True
except ImportError:
    KM003C_LIB_AVAILABLE = False
    print("Warning: km003c_lib not available. Payload parsing will be skipped.")


def parse_payload(payload_hex: str) -> Optional[Dict[str, Any]]:
    """Parse payload using km003c_lib if available."""
    if not KM003C_LIB_AVAILABLE or not payload_hex:
        return None
    
    try:
        # Convert hex to bytes
        payload_bytes = bytes.fromhex(payload_hex)
        
        # Use km003c_lib to parse the packet
        parsed = km003c_lib.parse_packet(payload_bytes)
        # Convert to dict if it's not already
        if hasattr(parsed, '__dict__'):
            return vars(parsed)
        else:
            return {"parsed_data": str(parsed)}
    except Exception as e:
        # Return error info for debugging
        return {"parse_error": str(e)}


def frames_to_jsonl(
    df: pl.DataFrame, source_file: str, output_file: str, limit: int = 100
) -> None:
    """Export frames from a source file to JSONL format for manual transaction grouping."""

    # Filter by source file and take first N frames
    frames = df.filter(pl.col("source_file") == source_file).head(limit)

    with open(output_file, "w") as f:
        for row in frames.iter_rows(named=True):
            payload_hex = row.get("payload_hex", "")
            
            # Calculate actual payload length in bytes (hex string / 2)
            payload_len = len(payload_hex) // 2 if payload_hex else 0
            
            frame_dict = {
                "transaction": 1,  # Start with all frames in transaction 1
                "frame": row["frame_number"],
                "time": round(row["timestamp"], 6),
                "src": row["usb_src"],
                "dst": row["usb_dst"],
                "urb": row["urb_type"],
                "len": payload_len,  # Use actual payload length instead of data_length
                "urb_id": row["urb_id"] if "urb_id" in row else None,
                "payload_hex": payload_hex,
            }
            
            # Add parsed payload data if available
            if payload_hex:
                parsed = parse_payload(payload_hex)
                if parsed:
                    frame_dict["parsed"] = parsed
            
            f.write(json.dumps(frame_dict) + "\n")

    print(f"Exported {frames.height} frames to {output_file}")
    print("Edit the JSONL file to assign different transaction numbers to group frames")


def jsonl_to_dataframe(jsonl_file: str) -> pl.DataFrame:
    """Import JSONL transaction file back to DataFrame with transaction IDs."""

    rows = []
    with open(jsonl_file, "r") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            
            # Skip empty lines
            if not line:
                continue
                
            # Skip comment lines (starting with # or //)
            if line.startswith('#') or line.startswith('//'):
                continue
            
            try:
                frame = json.loads(line)
                row = {
                    "transaction_id": frame["transaction"],
                    "frame_number": frame["frame"],
                    "timestamp": frame["time"],
                    "usb_src": frame["src"],
                    "usb_dst": frame["dst"],
                    "urb_type": frame["urb"],
                    "payload_length": frame["len"],  # Now represents actual payload length
                    "urb_id": frame.get("urb_id"),
                }
                rows.append(row)
            except json.JSONDecodeError as e:
                print(f"Warning: Skipping invalid JSON on line {line_num}: {line[:50]}...")
                continue

    return pl.DataFrame(rows)


def render_transactions_md(
    jsonl_file: str, output_file: str = "transactions.md"
) -> None:
    """Generate markdown visualization of transactions from JSONL file."""

    # Read all frames and group by transaction
    transactions = {}
    with open(jsonl_file, "r") as f:
        for line in f:
            frame = json.loads(line.strip())
            tid = frame["transaction"]
            if tid not in transactions:
                transactions[tid] = []
            transactions[tid].append(frame)

    md_lines = [f"# Transactions from {jsonl_file}\n"]

    for tid in sorted(transactions.keys()):
        frames = transactions[tid]

        md_lines.append(f"## Transaction {tid}")
        md_lines.append("| Frame | Time | Direction | URB | Length | URB_ID |")
        md_lines.append("|-------|------|-----------|-----|--------|--------|")

        for frame in frames:
            direction = f"{frame['src']}→{frame['dst']}"
            urb_id = frame.get("urb_id", "N/A")
            md_lines.append(
                f"| {frame['frame']} | {frame['time']} | {direction} | {frame['urb']} | {frame['len']} | {urb_id} |"
            )

        md_lines.append("")  # Empty line between transactions

    with open(output_file, "w") as f:
        f.write("\n".join(md_lines))

    print(f"Generated markdown visualization at {output_file}")
