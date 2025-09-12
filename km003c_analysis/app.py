#!/usr/bin/env python3
"""
Interactive USB Protocol Analyzer - Streamlit App

A modern web interface for analyzing KM003C USB protocol transactions
with interactive tables, detailed transaction views, and ADC data visualization.
"""
import streamlit as st
import polars as pl
from pathlib import Path
import sys

# Local package imports
from usb_transaction_splitter import split_usb_transactions
from transaction_tagger import tag_transactions

# Page configuration
st.set_page_config(
    page_title="USB Protocol Analyzer",
    page_icon="🔌",
    layout="wide",
)

@st.cache_data
def load_and_process_data(source_file: str, hide_enumeration: bool) -> tuple[pl.DataFrame, pl.DataFrame]:
    """
    Loads, splits, and tags USB data for a given source file.

    Returns:
        A tuple containing:
        - The aggregated transaction summary DataFrame.
        - The full DataFrame of all frames with transaction_id and tags.
    """
    # Load master dataset
    project_root = Path(__file__).parent.parent
    master_df = pl.read_parquet(project_root / "data" / "processed" / "usb_master_dataset.parquet")
    
    # Filter for the selected source file
    df_source = master_df.filter(pl.col("source_file") == source_file)
    
    # Core processing pipeline
    df_split = split_usb_transactions(df_source)
    df_tagged = tag_transactions(df_split)
    
    # Optional: Filter out enumeration transactions
    if hide_enumeration:
        df_tagged = df_tagged.filter(~pl.col("tags").list.contains("ENUMERATION"))

    if df_tagged.is_empty():
        return pl.DataFrame(), pl.DataFrame()

    # Create the aggregated transaction summary view
    transactions_summary = df_tagged.group_by("transaction_id").agg(
        pl.min("timestamp").alias("start_time"),
        (pl.max("timestamp") - pl.min("timestamp")).alias("duration_s"),
        pl.first("tags").alias("tags"),
        pl.count().alias("frame_count"),
        pl.col("payload_hex").filter(pl.col("direction") == "Out").first().alias("request_hex"),
        pl.col("payload_hex").filter(pl.col("direction") == "In").first().alias("response_hex"),
    ).sort("start_time")
    
    return transactions_summary, df_tagged


def main():
    st.title("🔌 USB Protocol Analyzer")
    st.markdown("Interactive analysis of KM003C USB protocol transactions")

    # Load master dataset to get source file list
    try:
        project_root = Path(__file__).parent.parent
        df = pl.read_parquet(project_root / "data" / "processed" / "usb_master_dataset.parquet")
    except Exception as e:
        st.error(f"Failed to load dataset: {e}")
        return

    # Sidebar controls
    st.sidebar.header("📊 Analysis Controls")
    source_files = sorted(df["source_file"].unique().to_list())
    selected_file = st.sidebar.selectbox(
        "Source File", source_files, help="Select a capture file to analyze"
    )

    hide_enumeration = st.sidebar.checkbox(
        "Hide enumeration transactions",
        value=True,
        help="Filter out USB enumeration transactions",
    )

    # Get processed data
    with st.spinner("Splitting and tagging transactions..."):
        transactions_summary, all_frames_tagged = load_and_process_data(
            selected_file, hide_enumeration
        )

    if transactions_summary.is_empty():
        st.warning("No transactions found for the selected file and filters.")
        return

    # Main content area
    col1, col2 = st.columns([3, 2])

    with col1:
        st.subheader(f"📋 Transactions: {selected_file}")
        st.caption(f"Found {len(transactions_summary)} transactions")

        # Use st.dataframe for selection
        selection = st.dataframe(
            transactions_summary,
            on_select="rerun",
            selection_mode="single-row",
            hide_index=True,
            use_container_width=True
                )

    with col2:
        st.subheader("🔍 Frame Details")
        
        if not selection.selection.rows:
            st.info("👆 Click a transaction in the table to see its frames")
        else:
            selected_idx = selection.selection.rows[0]
            selected_tid = transactions_summary.row(selected_idx, named=True)['transaction_id']
            
            st.info(f"Showing frames for Transaction ID: **{selected_tid}**")
            
            transaction_frames = all_frames_tagged.filter(
                pl.col("transaction_id") == selected_tid
            ).select([
                "frame_number",
                "timestamp",
                "transfer_type",
                "endpoint_address",
                "direction",
                "urb_type",
                "data_length",
                "payload_hex"
            ]).sort("frame_number")

            st.dataframe(transaction_frames, use_container_width=True, hide_index=True)


if __name__ == "__main__":
    main()
