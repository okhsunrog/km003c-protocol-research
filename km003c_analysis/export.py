#!/usr/bin/env python3
"""
Export functionality for USB datasets.
Part of the km003c_analysis module.
"""

import argparse
import polars as pl
import sys
from .transactions import create_usb_dataset


def main():
    """CLI entry point for exporting USB datasets."""
    parser = argparse.ArgumentParser(
        description="Export USB dataset to JSONL format",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Export specific source file
  uv run python -m km003c_analysis.export --source orig_open_close.16
  
  # Export with custom output name
  uv run python -m km003c_analysis.export --source orig_adc_50hz.6 --output adc_data.jsonl
  
  # List available source files
  uv run python -m km003c_analysis.export --list-sources
        """
    )
    
    parser.add_argument(
        "--parquet", 
        default="data/processed/usb_master_dataset.parquet",
        help="Path to parquet file (default: data/processed/usb_master_dataset.parquet)"
    )
    
    parser.add_argument(
        "--source", 
        help="Source file to export (e.g., orig_open_close.16)"
    )
    
    parser.add_argument(
        "--output", 
        default="usb_dataset.jsonl",
        help="Output JSONL file (default: usb_dataset.jsonl)"
    )
    
    parser.add_argument(
        "--list-sources", 
        action="store_true",
        help="List available source files and exit"
    )
    
    args = parser.parse_args()
    
    # Load dataset
    try:
        df = pl.read_parquet(args.parquet)
        print(f"Loaded {df.height:,} USB packets from {args.parquet}")
    except Exception as e:
        print(f"Error loading parquet file: {e}")
        return 1
    
    # List sources if requested
    if args.list_sources:
        available = df.select("source_file").unique().sort("source_file")
        print("\nAvailable source files:")
        for row in available.iter_rows(named=True):
            count = df.filter(pl.col("source_file") == row["source_file"]).height
            print(f"  {row['source_file']} ({count:,} frames)")
        return 0
    
    # Require source file
    if not args.source:
        print("Error: --source is required (or use --list-sources to see options)")
        return 1
    
    # Export dataset
    create_usb_dataset(df, args.source, args.output)
    print(f"\nDone! Created {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())