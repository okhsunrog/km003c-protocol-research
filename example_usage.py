#!/usr/bin/env python3
"""
Example usage of the modular USB transaction splitter library.

This demonstrates how to use the library with different data sources
and configurations.
"""

import polars as pl
from usb_transaction_splitter import (
    USBTransactionSplitter,
    TransactionSplitterConfig, 
    split_usb_transactions
)


def example_jsonl_processing():
    """Example: Processing JSONL data"""
    print("=== Example 1: JSONL Processing ===")
    
    # Load data from JSONL
    df = pl.read_ndjson("usb_dataset.jsonl")
    print(f"Loaded {df.height} frames from JSONL")
    
    # Split transactions using convenience function
    df_with_transactions = split_usb_transactions(df)
    
    # Show results
    stats = df_with_transactions.group_by("transaction_id").len()
    print(f"Split into {stats.height} transactions")
    print(f"Average frames per transaction: {df.height / stats.height:.1f}")


def example_custom_columns():
    """Example: Using custom column names"""
    print("\n=== Example 2: Custom Column Names ===")
    
    # Load and rename columns to simulate different data source
    df = pl.read_ndjson("usb_dataset.jsonl")
    df_renamed = df.rename({
        "frame_number": "frame_id", 
        "urb_id": "request_id",
        "transaction_id": "group_id"  # Will be overwritten
    })
    
    # Configure for custom column names
    config = TransactionSplitterConfig(
        frame_number_col="frame_id",
        urb_id_col="request_id",
        transaction_id_col="group_id"
    )
    
    # Split with custom configuration
    df_result = split_usb_transactions(df_renamed, config)
    
    print(f"Processed data with custom columns:")
    print(f"- Frame column: {config.frame_number_col}")
    print(f"- URB ID column: {config.urb_id_col}")  
    print(f"- Output column: {config.transaction_id_col}")


def example_detailed_analysis():
    """Example: Detailed analysis with splitter instance"""
    print("\n=== Example 3: Detailed Analysis ===")
    
    # Create splitter instance for detailed control
    splitter = USBTransactionSplitter()
    
    # Load and process data
    df = pl.read_ndjson("usb_dataset.jsonl")
    df_result = splitter.split_transactions(df)
    
    # Validate results
    validation = splitter.validate_output(df_result)
    print(f"Validation results:")
    print(f"- Valid: {validation['valid']}")
    print(f"- Frame order: {validation['frame_order']}")
    print(f"- Transaction order: {validation['transaction_order']}")
    
    # Get detailed statistics
    stats = splitter.get_transaction_stats(df_result)
    print(f"\nDetailed statistics:")
    print(f"- Total transactions: {stats['total_transactions']}")
    print(f"- Largest transaction: {stats['largest_transaction_size']} frames")
    print(f"- Size distribution: {stats['size_distribution']}")


def example_different_formats():
    """Example: Working with different file formats"""
    print("\n=== Example 4: Different File Formats ===")
    
    # Load JSONL data
    df_jsonl = pl.read_ndjson("usb_dataset.jsonl")
    
    # Save as Parquet (more efficient for large datasets)
    df_jsonl.write_parquet("temp_usb_data.parquet")
    
    # Load from Parquet and process
    df_parquet = pl.read_parquet("temp_usb_data.parquet")
    df_result = split_usb_transactions(df_parquet)
    
    # Save result as CSV (select only simple columns)
    simple_cols = ["frame_number", "transaction_id", "timestamp", "transfer_type", "endpoint_address"]
    df_result.select(simple_cols).write_csv("temp_usb_transactions.csv")
    
    print("Demonstrated workflow:")
    print("JSONL → Parquet → Transaction Splitting → CSV")
    
    # Cleanup
    import os
    os.remove("temp_usb_data.parquet")
    os.remove("temp_usb_transactions.csv")


def example_streaming_processing():
    """Example: Processing large datasets in chunks"""
    print("\n=== Example 5: Chunk Processing Concept ===")
    
    # This is a conceptual example for very large datasets
    # In practice, you'd need to be careful about transaction boundaries
    
    df = pl.read_ndjson("usb_dataset.jsonl")
    
    # Simulate processing in chunks (for demo purposes)
    chunk_size = 50
    total_chunks = (df.height + chunk_size - 1) // chunk_size
    
    print(f"Dataset size: {df.height} frames")
    print(f"Chunk size: {chunk_size} frames")  
    print(f"Total chunks: {total_chunks}")
    
    # Note: Real chunk processing would need careful handling of 
    # transaction boundaries to avoid splitting logical transactions
    
    print("⚠️  Note: Real chunk processing needs careful transaction boundary handling")


if __name__ == "__main__":
    example_jsonl_processing()
    example_custom_columns() 
    example_detailed_analysis()
    example_different_formats()
    example_streaming_processing()
    
    print("\n🎉 All examples completed!")
    print("\nFor command-line usage, use: python split_usb_transactions_jsonl.py input.jsonl output.jsonl")