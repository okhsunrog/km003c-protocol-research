"""
Transaction Tagger for USB Protocol Analysis

This module provides functionality to analyze and tag USB transactions based on
their composition and patterns. It is designed to be a flexible, post-processing
step after transaction splitting.

Tagging is expressed as Polars aggregations rather than a Python callback per
transaction group: every tag is a property of the frames in a transaction, so
there is no cross-row state to carry and no reason to leave the query engine.
"""

import polars as pl

# USB standard request codes used during enumeration.
# 0x00 = GET_STATUS, 0x01 = CLEAR_FEATURE, 0x03 = SET_FEATURE,
# 0x05 = SET_ADDRESS, 0x06 = GET_DESCRIPTOR, 0x08 = GET_CONFIGURATION,
# 0x09 = SET_CONFIGURATION
STANDARD_ENUMERATION_REQUESTS = [0x00, 0x01, 0x03, 0x05, 0x06, 0x08, 0x09]

CONTROL_TRANSFER_TYPE = "0x02"
BULK_TRANSFER_TYPE = "0x03"
OUT_ENDPOINT = "0x01"
IN_ENDPOINT = "0x81"
SUBMIT_URB = "S"
COMPLETE_URB = "C"
CANCEL_STATUS = "-2"

TRANSACTION_ID_COL = "transaction_id"


def _brequest_as_int() -> pl.Expr:
    """Parse the `brequest` column, which holds either decimal or hex strings."""
    text = pl.col("brequest").cast(pl.String).str.strip_chars()
    return (
        pl.when(text.str.starts_with("0x"))
        .then(text.str.slice(2).str.to_integer(base=16, strict=False))
        .otherwise(text.str.to_integer(base=10, strict=False))
    )


def _tag_expressions() -> dict[str, pl.Expr]:
    """One boolean aggregation per tag, evaluated per transaction group."""
    has_control = (pl.col("transfer_type") == CONTROL_TRANSFER_TYPE).any()
    has_bulk = (pl.col("transfer_type") == BULK_TRANSFER_TYPE).any()

    control_only = has_control & ~has_bulk
    bulk_only = has_bulk & ~has_control

    out_requests = (
        (pl.col("endpoint_address") == OUT_ENDPOINT)
        & (pl.col("urb_type") == SUBMIT_URB)
    ).sum()
    in_responses = (
        (pl.col("endpoint_address") == IN_ENDPOINT)
        & (pl.col("urb_type") == COMPLETE_URB)
    ).sum()

    enumeration = (
        _brequest_as_int().is_in(STANDARD_ENUMERATION_REQUESTS).fill_null(False).any()
    )

    return {
        "CONTROL_ONLY": control_only,
        "BULK_ONLY": bulk_only,
        "MIXED_COMPOSITION": has_bulk & has_control,
        "SINGLE_FRAME": pl.len() == 1,
        "CANCELLATION": (pl.col("urb_status") == CANCEL_STATUS).any(),
        "BULK_COMMAND_RESPONSE": bulk_only & (out_requests == 1) & (in_responses == 1),
        "BULK_FRAGMENTED_RESPONSE": bulk_only
        & (out_requests == 1)
        & (in_responses > 1),
        "ENUMERATION": control_only & enumeration,
    }


def tag_transactions(df: pl.DataFrame) -> pl.DataFrame:
    """
    Analyzes a DataFrame of frames and adds a 'tags' column.

    Args:
        df: A DataFrame containing frames with a 'transaction_id' column.

    Returns:
        The original DataFrame with an added 'tags' list column.
    """
    if TRANSACTION_ID_COL not in df.columns:
        raise ValueError(
            f"Input DataFrame must contain a '{TRANSACTION_ID_COL}' column."
        )

    tags = _tag_expressions()
    if "brequest" not in df.columns:
        # Enumeration is only detectable when the capture kept the request code.
        tags["ENUMERATION"] = pl.lit(False)

    # Each tag becomes its own boolean column, then the set ones are collected
    # into a sorted list so the output matches a `sorted(set(...))` per group.
    tags_df = df.group_by(TRANSACTION_ID_COL).agg(
        [expression.alias(name) for name, expression in tags.items()]
    )
    tags_df = tags_df.select(
        TRANSACTION_ID_COL,
        pl.concat_list(
            [pl.when(pl.col(name)).then(pl.lit(name)).alias(name) for name in tags]
        )
        .list.drop_nulls()
        .list.sort()
        .alias("tags"),
    )

    return df.join(tags_df, on=TRANSACTION_ID_COL, how="left")
