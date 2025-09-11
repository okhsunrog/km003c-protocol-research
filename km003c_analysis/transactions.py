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
        if hasattr(parsed, "__dict__"):
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
                "transfer_type": row.get("transfer_type", ""),  # Critical for grouping
                "endpoint": row.get("endpoint_address", ""),  # Endpoint information
                "urb": row["urb_type"],
                "urb_status": row.get("urb_status", ""),  # Status code
                "urb_id": row.get("urb_id", ""),
                "src": row["usb_src"],
                "dst": row["usb_dst"],
                "len": payload_len,  # Use actual payload length
                "payload_hex": payload_hex,
            }

            # Add control transfer specific fields if present
            if row.get("transfer_type") == "0x02":
                if row.get("bmrequest_type"):
                    frame_dict["bmrequest_type"] = row["bmrequest_type"]
                if row.get("brequest"):
                    frame_dict["brequest"] = row["brequest"]
                if row.get("wlength") is not None:
                    frame_dict["wlength"] = row["wlength"]
                if row.get("descriptor_type"):
                    frame_dict["descriptor_type"] = row["descriptor_type"]

            # Add data direction flags
            if row.get("data_flag"):
                frame_dict["data_flag"] = row["data_flag"]
            if row.get("setup_flag"):
                frame_dict["setup_flag"] = row["setup_flag"]

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
            if line.startswith("#") or line.startswith("//"):
                continue

            try:
                frame = json.loads(line)
                row = {
                    "transaction_id": frame.get("transaction_id", frame.get("transaction", 1)),
                    "frame_number": frame.get("frame_number", frame.get("frame")),
                    "timestamp": frame.get("timestamp", frame.get("time")),
                    "transfer_type": frame.get("transfer_type", ""),
                    "endpoint": frame.get("endpoint_address", frame.get("endpoint", "")),
                    "urb_type": frame.get("urb_type", frame.get("urb")),
                    "urb_status": frame.get("urb_status", ""),
                    "urb_id": frame.get("urb_id"),
                    "usb_src": frame.get("usb_src", frame.get("src")),
                    "usb_dst": frame.get("usb_dst", frame.get("dst")),
                    "payload_length": frame.get("data_length", frame.get("len", 0)),
                }
                rows.append(row)
            except json.JSONDecodeError as e:
                print(
                    f"Warning: Skipping invalid JSON on line {line_num}: {line[:50]}..."
                )
                continue

    return pl.DataFrame(rows)


def create_usb_dataset(
    df: pl.DataFrame, 
    source_file: str, 
    output_file: str = "usb_dataset.jsonl",
    exclude_fields: List[str] = None
) -> None:
    """Create comprehensive USB dataset JSONL from parquet data."""
    
    if exclude_fields is None:
        exclude_fields = ["session_id", "source_file", "timestamp_absolute"]
    
    # Filter by source file
    frames = df.filter(pl.col("source_file") == source_file)
    
    if frames.height == 0:
        print(f"ERROR: No frames found for source_file '{source_file}'")
        # Show available source files
        available = df.select("source_file").unique().sort("source_file")
        print("Available source files:")
        for row in available.iter_rows(named=True):
            count = df.filter(pl.col("source_file") == row["source_file"]).height
            print(f"  {row['source_file']} ({count:,} frames)")
        return

    print(f"Processing {frames.height:,} frames from {source_file}")

    with open(output_file, "w") as f:
        for row in frames.iter_rows(named=True):
            # Start with transaction_id as first field
            frame_dict = {"transaction_id": 1}
            
            # Copy all fields from the row, excluding unwanted fields
            for key, value in row.items():
                if key in exclude_fields:
                    continue
                    
                if value is not None:
                    frame_dict[key] = value
                else:
                    # Handle None values based on expected field types
                    if key in ["data_length", "urb_length", "endpoint_number", "device_address", "bus_id", 
                              "interval", "start_frame", "frame_length", "wvalue", "windex", "wlength",
                              "descriptor_index", "language_id", "urb_ts_sec", "urb_ts_usec"]:
                        frame_dict[key] = 0
                    elif key in ["payload_hex", "setup_flag", "data_flag", "bmrequest_type", "brequest",
                                "brequest_name", "descriptor_type", "transfer_flags", "copy_of_transfer_flags"]:
                        frame_dict[key] = ""
                    else:
                        frame_dict[key] = None

            # Add parsed payload if available
            payload_hex = row.get("payload_hex", "")
            if payload_hex:
                parsed = parse_payload(payload_hex)
                if parsed:
                    frame_dict["parsed_payload"] = parsed

            f.write(json.dumps(frame_dict) + "\n")

    print(f"Created {output_file} with {frames.height:,} frames")


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
