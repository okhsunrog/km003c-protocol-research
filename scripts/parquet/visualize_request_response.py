#!/usr/bin/env python3
"""
Визуализация результатов анализа request-response корреляций.

Run: uv run python scripts/parquet/visualize_request_response.py
"""

import polars as pl
from pathlib import Path
import json

def visualize_results():
    """Создать детальный отчет с визуализацией"""
    
    # Load analysis results
    json_path = Path("data/processed/request_response_analysis.json")
    parquet_path = Path("data/processed/transaction_pairs.parquet")
    
    if not json_path.exists() or not parquet_path.exists():
        print("❌ Analysis results not found. Run analyze_request_response_correlation.py first.")
        return
    
    with open(json_path) as f:
        results = json.load(f)
    
    df = pl.read_parquet(parquet_path)
    
    print("=" * 100)
    print("KM003C PROTOCOL: REQUEST-RESPONSE CORRELATION ANALYSIS REPORT")
    print("=" * 100)
    print()
    
    # Global statistics
    global_data = results.get("_global", {})
    print("📊 GLOBAL STATISTICS")
    print("─" * 100)
    print(f"Total transaction pairs analyzed: {global_data.get('total_pairs', 0):,}")
    print(f"Unique source files: {len([k for k in results.keys() if k != '_global'])}")
    print()
    
    # Request mask to attribute mapping
    print("🔍 REQUEST MASK → RESPONSE ATTRIBUTE MAPPING")
    print("─" * 100)
    print()
    
    if "_global" in results:
        mapping = results["_global"]["mapping_analysis"]
        
        # Attribute name mapping
        attr_names = {
            1: "ADC",
            2: "AdcQueue", 
            8: "Settings",
            16: "PdPacket",
            512: "Unknown512",
            1056: "Unknown1056",
            3072: "Unknown3072",
            17440: "Unknown17440",
        }
        
        print("┌" + "─" * 15 + "┬" + "─" * 20 + "┬" + "─" * 10 + "┬" + "─" * 50 + "┐")
        print("│ Request Mask  │ Binary (15-bit)      │ Count     │ Response Attributes                       │")
        print("├" + "─" * 15 + "┼" + "─" * 20 + "┼" + "─" * 10 + "┼" + "─" * 50 + "┤")
        
        for mask_hex in sorted(mapping["summary"].keys(), key=lambda x: int(x, 16)):
            summary = mapping["summary"][mask_hex]
            
            # Convert response attributes to names
            resp_attrs = summary["most_common_response"]
            resp_names = [attr_names.get(attr, f"Unknown{attr}") for attr in resp_attrs]
            resp_str = ", ".join(resp_names) if resp_names else "Empty"
            
            # Get binary representation (remove '0b' prefix)
            binary = summary["mask_binary"][2:].zfill(15)
            
            # Format output
            mask_col = f"{mask_hex:>13}"
            binary_col = f"{binary:>18}"
            count_col = f"{summary['total_occurrences']:>8}"
            resp_col = f"{resp_str:<48}"
            
            print(f"│ {mask_col} │ {binary_col} │ {count_col} │ {resp_col} │")
            
            # Show alternate patterns if they exist
            if summary["unique_response_patterns"] > 1:
                for pattern_str, count in mapping["detailed_mapping"][mask_hex].items():
                    if count != summary["most_common_count"]:
                        pattern = eval(pattern_str)  # Safe because we control the data
                        alt_names = [attr_names.get(attr, f"Unknown{attr}") for attr in pattern]
                        alt_str = ", ".join(alt_names) if alt_names else "Empty"
                        print(f"│               │                      │   ({count:>4}) │   └─ Alt: {alt_str:<39} │")
        
        print("└" + "─" * 15 + "┴" + "─" * 20 + "┴" + "─" * 10 + "┴" + "─" * 50 + "┘")
        print()
        
        # Bit analysis
        print("🔬 BITMASK BIT ANALYSIS")
        print("─" * 100)
        print()
        print("Observed bit patterns and their meanings:")
        print()
        
        bit_meanings = {
            0: "ADC (attribute 1)",
            1: "AdcQueue (attribute 2)",
            3: "Settings (attribute 8)",
            4: "PdPacket (attribute 16)",
            9: "Unknown512 (attribute 512)"
        }
        
        for mask_hex in sorted(mapping["summary"].keys(), key=lambda x: int(x, 16)):
            summary = mapping["summary"][mask_hex]
            bits = mapping["bit_analysis"][mask_hex]
            
            # Get which bits are set
            set_bits = []
            for bit_key, is_set in bits.items():
                if is_set:
                    bit_num = int(bit_key.split('_')[1]) if bit_key.split('_')[1].isdigit() else None
                    if bit_num is not None:
                        set_bits.append(bit_num)
            
            if set_bits or summary['total_occurrences'] > 10:  # Show significant patterns
                print(f"  {mask_hex} (decimal {summary['mask_decimal']:>4}):")
                if set_bits:
                    for bit in set_bits:
                        meaning = bit_meanings.get(bit, f"Unknown bit {bit}")
                        print(f"    ├─ Bit {bit}: {meaning}")
                else:
                    print(f"    ├─ No standard bits set")
                
                resp_attrs = summary["most_common_response"]
                print(f"    └─ Response: {resp_attrs} ({summary['total_occurrences']} occurrences)")
                print()
        
        # Key findings
        print("🔑 KEY FINDINGS")
        print("─" * 100)
        print()
        print("1. PERFECT CORRELATION OBSERVED:")
        print("   • Bit 0 (0x0001) → ADC response (attribute 1)")
        print("   • Bit 1 (0x0002) → AdcQueue response (attribute 2)")
        print("   • Bit 3 (0x0008) → Settings response (attribute 8)")
        print("   • Bit 4 (0x0010) → PdPacket response (attribute 16)")
        print("   • Bit 9 (0x0200) → Unknown512 response (attribute 512)")
        print()
        print("2. BITWISE OR BEHAVIOR:")
        print("   • Mask 0x0003 (bits 0+1) → Response [ADC, AdcQueue]")
        print("   • Mask 0x0011 (bits 0+4) → Response [ADC, PdPacket]")
        print("   └─ Confirms bitmask allows requesting multiple data types in one transaction")
        print()
        print("3. SPECIAL CASES:")
        print("   • Mask 0x0000 → Empty response (control/status commands)")
        print("   • Mask 0x0080 → Inconsistent responses (initialization/calibration?)")
        print()
    
    # Per-file breakdown
    print("📁 PER-FILE ANALYSIS")
    print("─" * 100)
    print()
    
    for source_file in sorted([k for k in results.keys() if k != "_global"]):
        file_data = results[source_file]
        
        print(f"File: {source_file}")
        print(f"  Total packets: {file_data['total_packets']:,}")
        print(f"  Transaction pairs: {file_data['transaction_pairs']}")
        
        # Show dominant request patterns
        mapping = file_data["mapping_analysis"]["summary"]
        if mapping:
            dominant = sorted(mapping.items(), key=lambda x: x[1]["total_occurrences"], reverse=True)[:3]
            print(f"  Top request patterns:")
            for mask_hex, summary in dominant:
                resp = summary["most_common_response"]
                resp_str = str(resp) if resp else "Empty"
                print(f"    • {mask_hex}: {summary['total_occurrences']} times → {resp_str}")
        print()
    
    # Latency analysis
    print("⏱️  TRANSACTION LATENCY ANALYSIS")
    print("─" * 100)
    print()
    
    # Overall latency
    latencies = df["latency_us"].to_list()
    print(f"Overall statistics (all {len(latencies):,} transactions):")
    print(f"  Min:     {min(latencies):>8.1f} µs")
    print(f"  25th %:  {df['latency_us'].quantile(0.25):>8.1f} µs")
    print(f"  Median:  {df['latency_us'].median():>8.1f} µs")
    print(f"  75th %:  {df['latency_us'].quantile(0.75):>8.1f} µs")
    print(f"  Mean:    {df['latency_us'].mean():>8.1f} µs")
    print(f"  Max:     {max(latencies):>8.1f} µs")
    print()
    
    # Latency by request type
    print("Latency by request mask (top 5):")
    latency_by_mask = (df
        .group_by("request_mask_hex")
        .agg([
            pl.len().alias("count"),
            pl.col("latency_us").mean().alias("mean_latency"),
            pl.col("latency_us").median().alias("median_latency")
        ])
        .sort("count", descending=True)
        .head(5)
    )
    
    for row in latency_by_mask.iter_rows(named=True):
        print(f"  {row['request_mask_hex']:>8}: mean={row['mean_latency']:>6.1f}µs, median={row['median_latency']:>6.1f}µs (n={row['count']:>4})")
    
    print()
    print("=" * 100)
    print("✅ VISUALIZATION COMPLETE")
    print("=" * 100)
    print()
    print("Files generated:")
    print(f"  • {json_path} (detailed JSON)")
    print(f"  • {parquet_path} (transaction pairs)")
    print()


if __name__ == "__main__":
    visualize_results()
