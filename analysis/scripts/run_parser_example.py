#!/usr/bin/env python3
"""
Example script to demonstrate the output of the Rust-backed protocol parser.
"""
import sys
from pathlib import Path
import polars as pl

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from analysis.scripts.helpers import load_master_dataset
from km003c_lib import parse_packet, AdcData

def main():
    """Load data, run parser, and print results."""
    print("--- Running Parser Demonstration ---")

    df = load_master_dataset('usb_master_dataset.parquet')
    session_id = 'orig_adc_1000hz.6'
    df_session = df.filter(pl.col('session_id') == session_id)
    print(f"\n[1] Filtered for session: '{session_id}'")

    print("[2] Parsing ADC packets using a direct loop...")
    parsed_results = []
    for row in df_session.iter_rows(named=True):
        payload_hex = row.get("payload_hex")
        if not payload_hex:
            continue
        try:
            payload_bytes = bytes.fromhex(payload_hex)
            adc_data = parse_packet(payload_bytes)
            if adc_data:
                parsed_results.append({
                    "timestamp": row["timestamp"],
                    "vbus_v": adc_data.vbus_v,
                    "ibus_a": adc_data.ibus_a,
                    "power_w": adc_data.power_w,
                    "temp_c": adc_data.temp_c,
                })
        except (ValueError, TypeError):
            continue
    
    df_adc_data = pl.DataFrame(parsed_results)
    print(f"[3] Found and parsed {len(df_adc_data)} valid ADC data packets.")

    print("\n--- Parser Output (first 10 ADC packets) ---")
    print(df_adc_data.head(10))

if __name__ == "__main__":
    main()
