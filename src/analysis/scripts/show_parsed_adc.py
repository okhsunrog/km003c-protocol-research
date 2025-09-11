#!/usr/bin/env python3
"""
A script to demonstrate the final Rust-backed parser by loading the master
dataset, parsing a known-good session, and printing the first 5 ADC packets.
"""

import sys
from pathlib import Path

import polars as pl

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from km003c_lib import parse_packet

from analysis.scripts.helpers import load_master_dataset


def main():
    """Load data, run parser, and print the first 5 ADC data entries."""
    print("--- Demonstrating ADC Data Parsing (Direct Loop Method) ---")

    df = load_master_dataset("usb_master_dataset.parquet")
    session_id = "orig_adc_1000hz.6"
    df_session = df.filter(pl.col("session_id") == session_id)
    print(f"\n[1] Using session: '{session_id}'")

    print("[2] Parsing ADC packets...")

    results = []
    for row in df_session.iter_rows(named=True):
        payload_hex = row.get("payload_hex")
        if not payload_hex:
            continue

        try:
            payload_bytes = bytes.fromhex(payload_hex)
            adc_data = parse_packet(payload_bytes)

            if adc_data:
                results.append(
                    {
                        "timestamp": row["timestamp"],
                        "vbus_v": adc_data.vbus_v,
                        "ibus_a": adc_data.ibus_a,
                        "power_w": adc_data.power_w,
                        "temp_c": adc_data.temp_c,
                    }
                )
        except (ValueError, TypeError):
            continue

    df_results = pl.DataFrame(results)
    print(f"[3] Found and parsed {len(df_results)} valid ADC data packets.")

    print("\n--- First 5 Parsed ADC Packets ---")
    print(df_results.head(5))


if __name__ == "__main__":
    main()
