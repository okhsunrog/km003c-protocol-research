#!/usr/bin/env python3
"""
Splits the master USB dataset into separate JSONL files for each source file,
with transaction IDs assigned to each.
"""
import polars as pl
from pathlib import Path
import json
from usb_transaction_splitter import split_usb_transactions

# Define paths
INPUT_FILE = Path("data/processed/usb_master_dataset.parquet")
OUTPUT_DIR = Path("transactions_per_source")
SOURCE_COL = "source_file"

def save_dataframe_to_jsonl(df: pl.DataFrame, output_file: Path) -> None:
    """Save Polars DataFrame to JSONL format with custom formatting."""
    
    # 1. Remove specified columns
    cols_to_remove = ["added_datetime", "timestamp_absolute", "session_id"]
    df = df.drop([col for col in cols_to_remove if col in df.columns])

    # 2. Reorder columns to make transaction_id first
    cols = df.columns
    if "transaction_id" in cols:
        cols.remove("transaction_id")
        cols.insert(0, "transaction_id")
        df = df.select(cols)
        
    # Ensure transaction_id is integer
    df = df.with_columns(pl.col("transaction_id").cast(pl.Int64))

    # 3. Write to file with newlines between transactions
    last_transaction_id = None
    with open(output_file, "w") as f:
        for row in df.to_dicts():
            current_transaction_id = row.get("transaction_id")
            
            if last_transaction_id is not None and current_transaction_id != last_transaction_id:
                f.write("\n")
            
            f.write(json.dumps(row) + "\n")
            last_transaction_id = current_transaction_id

def main():
    """Main script logic"""
    if not INPUT_FILE.exists():
        print(f"Error: Input file not found at {INPUT_FILE}")
        return

    # Create output directory if it doesn't exist
    OUTPUT_DIR.mkdir(exist_ok=True)
    print(f"Output will be saved to: {OUTPUT_DIR}")

    # Load data
    print(f"Loading data from {INPUT_FILE}...")
    df = pl.read_parquet(INPUT_FILE)
    print(f"Loaded {df.height:,} total frames.")

    # Get unique source files
    if SOURCE_COL not in df.columns:
        print(f"Error: Source column '{SOURCE_COL}' not found in DataFrame.")
        print(f"Available columns: {df.columns}")
        return
        
    source_files = sorted(df[SOURCE_COL].unique().to_list())
    print(f"Found {len(source_files)} unique source files.")

    for source_file in source_files:
        print(f"\nProcessing source file: {source_file}...")
        
        # Filter data for the current source
        df_source = df.filter(pl.col(SOURCE_COL) == source_file)
        print(f"  - Found {df_source.height:,} frames.")

        if df_source.height == 0:
            print("  - Skipping, no frames found.")
            continue
            
        # Split transactions
        df_transactions = split_usb_transactions(df_source)
        
        num_transactions = df_transactions["transaction_id"].n_unique()
        print(f"  - Split into {num_transactions:,} transactions.")
        
        # Save to JSONL
        output_filename = f"{Path(source_file).name}.jsonl"
        output_path = OUTPUT_DIR / output_filename
        
        save_dataframe_to_jsonl(df_transactions, output_path)
        print(f"  - Saved to {output_path}")
        
    print("\n✅ All source files processed.")

if __name__ == "__main__":
    main()
