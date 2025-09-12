"""
Transaction Tagger for USB Protocol Analysis

This module provides functionality to analyze and tag USB transactions based on
their composition and patterns. It is designed to be a flexible, post-processing
step after transaction splitting.
"""

import polars as pl
from typing import List

def _tag_composition(transaction_group: pl.DataFrame) -> List[str]:
    """Determine tags based on the composition of transfer types."""
    tags = set()
    transfer_types = transaction_group["transfer_type"].unique().to_list()
    
    has_control = "0x02" in transfer_types
    has_bulk = "0x03" in transfer_types
    
    if has_control and not has_bulk:
        tags.add("CONTROL_ONLY")
    elif has_bulk and not has_control:
        tags.add("BULK_ONLY")
    elif has_bulk and has_control:
        tags.add("MIXED_COMPOSITION")
        
    return list(tags)

def _tag_structure_and_patterns(transaction_group: pl.DataFrame) -> List[str]:
    """Determine tags based on transaction structure and known patterns."""
    tags = set()
    
    # Structure
    if transaction_group.height == 1:
        tags.add("SINGLE_FRAME")
        
    # Cancellation
    if "-2" in transaction_group["urb_status"].to_list():
        tags.add("CANCELLATION")

    # Patterns (Bulk)
    if "BULK_ONLY" in _tag_composition(transaction_group):
        out_requests = transaction_group.filter(
            (pl.col("endpoint_address") == "0x01") & (pl.col("urb_type") == "S")
        ).height
        in_responses = transaction_group.filter(
            (pl.col("endpoint_address") == "0x81") & (pl.col("urb_type") == "C")
        ).height

        if out_requests == 1 and in_responses == 1:
            tags.add("BULK_COMMAND_RESPONSE")
        elif out_requests == 1 and in_responses > 1:
            tags.add("BULK_FRAGMENTED_RESPONSE")

    # Patterns (Enumeration)
    if "CONTROL_ONLY" in _tag_composition(transaction_group):
        enumeration_requests = {"Get Descriptor", "Set Address", "Set Configuration"}
        if "bRequest_name" in transaction_group.columns:
            requests = set(transaction_group["bRequest_name"].drop_nulls().to_list())
            if requests.intersection(enumeration_requests):
                tags.add("ENUMERATION")

    return list(tags)

def _apply_tags_to_group(group_df: pl.DataFrame) -> List[str]:
    """Helper function to generate tags for a single transaction group."""
    return sorted(list(set(
        _tag_composition(group_df) + 
        _tag_structure_and_patterns(group_df)
    )))

def tag_transactions(df: pl.DataFrame) -> pl.DataFrame:
    """
    Analyzes a DataFrame of frames and adds a 'tags' column.

    Args:
        df: A DataFrame containing frames with a 'transaction_id' column.

    Returns:
        The original DataFrame with an added 'tags' list column.
    """
    if "transaction_id" not in df.columns:
        raise ValueError("Input DataFrame must contain a 'transaction_id' column.")

    # Group by transaction, apply tagging functions, and create a tags DataFrame
    tags_df = df.group_by("transaction_id").map_groups(
        lambda group_df: pl.DataFrame({
            "transaction_id": group_df["transaction_id"][0],
            "tags": [_apply_tags_to_group(group_df)]
        })
    )

    # Merge the tags back into the original DataFrame
    return df.join(tags_df, on="transaction_id", how="left")
