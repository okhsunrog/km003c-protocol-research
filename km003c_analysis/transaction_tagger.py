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
        # USB standard request codes for enumeration (as hex integers)
        # 0x00 = GET_STATUS, 0x01 = CLEAR_FEATURE, 0x03 = SET_FEATURE,
        # 0x05 = SET_ADDRESS, 0x06 = GET_DESCRIPTOR, 0x08 = GET_CONFIGURATION,
        # 0x09 = SET_CONFIGURATION
        STANDARD_ENUMERATION_REQUESTS = {0x00, 0x01, 0x03, 0x05, 0x06, 0x08, 0x09}
        
        if "brequest" in transaction_group.columns:
            # Convert brequest values to integers for comparison
            brequest_values = transaction_group["brequest"].drop_nulls().to_list()
            brequest_ints = set()
            for val in brequest_values:
                try:
                    # Handle both plain numbers and hex strings
                    if isinstance(val, str):
                        val = val.strip()
                        if val.startswith("0x"):
                            # Hex string
                            brequest_ints.add(int(val, 16))
                        else:
                            # Plain decimal string
                            brequest_ints.add(int(val, 10))
                    else:
                        brequest_ints.add(int(val))
                except (ValueError, AttributeError):
                    continue
            
            if brequest_ints.intersection(STANDARD_ENUMERATION_REQUESTS):
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
