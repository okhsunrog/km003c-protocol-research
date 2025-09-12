#!/usr/bin/env python3
"""
Interactive USB Protocol Analyzer - Streamlit App

A modern web interface for analyzing KM003C USB protocol transactions
with interactive tables, detailed transaction views, and data visualization.
"""
import streamlit as st
import polars as pl
import plotly.express as px
import plotly.graph_objects as go
from plotly import subplots
from pathlib import Path
import sys

# Local package imports
from usb_transaction_splitter import split_usb_transactions
from transaction_tagger import tag_transactions

# Import the proper Rust library for packet parsing
from km003c_lib import parse_packet, parse_raw_packet, Packet, RawPacket, AdcData

def extract_transaction_payloads(transaction_frames: pl.DataFrame) -> dict:
    """
    Extract request and response payloads from transaction frames.
    
    Args:
        transaction_frames: DataFrame containing frames for a single transaction
        
    Returns:
        Dictionary with request_data, response_data, and metadata
    """
    result = {
        "request_data": None,
        "response_data": None,
        "request_frames": [],
        "response_frames": [],
        "transaction_type": "UNKNOWN"
    }
    
    # Extract OUT endpoint frames (requests)
    out_frames = transaction_frames.filter(
        (pl.col("endpoint_address") == "0x01") & 
        (pl.col("payload_hex").is_not_null()) &
        (pl.col("payload_hex") != "")
    )
    
    # Extract IN endpoint frames (responses)  
    in_frames = transaction_frames.filter(
        (pl.col("endpoint_address") == "0x81") &
        (pl.col("payload_hex").is_not_null()) &
        (pl.col("payload_hex") != "")
    )
    
    # Collect request data
    if not out_frames.is_empty():
        request_payloads = out_frames.select("payload_hex").to_series().to_list()
        result["request_frames"] = out_frames.to_dicts()
        # For now, take the first non-empty payload as the main request
        result["request_data"] = next((p for p in request_payloads if p), None)
    
    # Collect response data
    if not in_frames.is_empty():
        response_payloads = in_frames.select("payload_hex").to_series().to_list()
        result["response_frames"] = in_frames.to_dicts()
        # For now, take the first non-empty payload as the main response
        result["response_data"] = next((p for p in response_payloads if p), None)
    
    # Determine transaction type based on pattern
    if result["request_data"] and result["response_data"]:
        result["transaction_type"] = "COMMAND_RESPONSE"
    elif result["request_data"] and not result["response_data"]:
        result["transaction_type"] = "COMMAND_ONLY"
    elif not result["request_data"] and result["response_data"]:
        result["transaction_type"] = "RESPONSE_ONLY"
    
    return result

def parse_packet_preview(hex_data: str) -> dict:
    """
    Parse hex data using the proper Rust km003c_lib and return a preview.
    
    Args:
        hex_data: Hex string of packet data
        
    Returns:
        Dictionary with parsed packet information for preview
    """
    if not hex_data or len(hex_data) < 8:
        return {"type": "EMPTY", "preview": "No data", "details": {}}
    
    
    try:
        packet_bytes = bytes.fromhex(hex_data)
        
        # Use the proper Rust library to parse the packet
        parsed_packet = parse_packet(packet_bytes)
        
        # Extract information based on the packet type
        packet_type = parsed_packet.packet_type
        
        if packet_type == "CmdGetSimpleAdcData":
            return {
                "type": "ADC_REQUEST",
                "preview": f"GetAdcData ({len(packet_bytes)} bytes)",
                "details": {
                    "packet_type": packet_type,
                    "raw_packet": parsed_packet
                },
                "parsed_packet": parsed_packet
            }
        elif packet_type == "SimpleAdcData":
            adc_preview = "ADC Data"
            if parsed_packet.adc_data:
                adc = parsed_packet.adc_data
                # Show key values for table preview (using absolute current)
                adc_preview = f"{adc.vbus_v:.3f}V, {abs(adc.ibus_a):.3f}A, {adc.temp_c:.1f}°C"
            return {
                "type": "ADC_RESPONSE", 
                "preview": adc_preview,
                "details": {
                    "packet_type": packet_type,
                    "adc_data": parsed_packet.adc_data,
                    "raw_packet": parsed_packet
                },
                "parsed_packet": parsed_packet
            }
        elif packet_type == "Generic":
            # For generic packets, try to parse as raw packet for more details
            try:
                raw_packet = parse_raw_packet(packet_bytes)
                return {
                    "type": "GENERIC",
                    "preview": f"{raw_packet.packet_type} ({len(packet_bytes)} bytes)",
                    "details": {
                        "packet_type": raw_packet.packet_type,
                        "id": raw_packet.id,
                        "has_extended_header": raw_packet.has_extended_header,
                        "raw_packet": raw_packet
                    },
                    "raw_packet": raw_packet
                }
            except Exception:
                # Fallback to basic info
                return {
                    "type": "GENERIC",
                    "preview": f"Generic packet ({len(packet_bytes)} bytes)",
                    "details": {"packet_type": packet_type},
                    "parsed_packet": parsed_packet
                }
        else:
            return {
                "type": "OTHER",
                "preview": f"{packet_type} ({len(packet_bytes)} bytes)",
                "details": {"packet_type": packet_type},
                "parsed_packet": parsed_packet
            }
            
    except Exception as e:
        return {
            "type": "PARSE_ERROR",
            "preview": f"Parse error: {str(e)[:50]}...",
            "details": {"error": str(e), "hex": hex_data[:32] + "..." if len(hex_data) > 32 else hex_data}
        }

# Page configuration
st.set_page_config(
    page_title="USB Protocol Analyzer",
    page_icon="🔌",
    layout="wide",
    initial_sidebar_state="expanded"
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

    # Create the aggregated transaction summary view with enhanced payload extraction
    transactions_summary = df_tagged.group_by("transaction_id").agg(
        pl.min("timestamp").alias("start_time"),
        (pl.max("timestamp") - pl.min("timestamp")).alias("duration_s"),
        pl.first("tags").alias("tags"),
        pl.len().alias("frame_count"),
        # Extract request data (OUT endpoint with payload)
        pl.col("payload_hex").filter(
            (pl.col("endpoint_address") == "0x01") & 
            (pl.col("payload_hex").is_not_null()) &
            (pl.col("payload_hex") != "")
        ).first().alias("request_hex"),
        # Extract response data (IN endpoint with payload)  
        pl.col("payload_hex").filter(
            (pl.col("endpoint_address") == "0x81") &
            (pl.col("payload_hex").is_not_null()) &
            (pl.col("payload_hex") != "")
        ).first().alias("response_hex"),
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
    
    # Get available source files with packet counts
    source_file_stats = df.group_by("source_file").len().sort("len", descending=True)
    source_file_options = []
    for row in source_file_stats.iter_rows(named=True):
        source_file_options.append(f"{row['source_file']} ({row['len']} packets)")
    
    selected_option = st.sidebar.selectbox(
        "Source File", source_file_options, help="Select a capture file to analyze"
    )
    selected_file = selected_option.split(' (')[0]

    hide_enumeration = st.sidebar.checkbox(
        "Hide enumeration transactions",
        value=True,
        help="Filter out USB enumeration transactions",
    )
    
    show_adc_plot = st.sidebar.checkbox(
        "Show ADC data plot",
        value=False,
        help="Display voltage/current measurements over time"
    )
    
    # Table configuration
    st.sidebar.subheader("🔧 Display Options")
    rows_per_page = st.sidebar.selectbox(
        "Rows per page",
        options=[10, 25, 50, 100, 200, 300, 500, 1000, 2000],
        index=5,  # Default to 300
        help="Number of transactions to show per page"
    )

    # Get processed data
    with st.spinner("Splitting and tagging transactions..."):
        transactions_summary, all_frames_tagged = load_and_process_data(
            selected_file, hide_enumeration
        )

    if transactions_summary.is_empty():
        st.warning("No transactions found for the selected file and filters.")
        return

    # Calculate pagination in sidebar
    total_transactions = len(transactions_summary)
    total_pages = (total_transactions + rows_per_page - 1) // rows_per_page  # Ceiling division
    
    if total_pages > 1:
        current_page = st.sidebar.selectbox(
            "Page",
            options=list(range(1, total_pages + 1)),
            index=0,
            format_func=lambda x: f"Page {x} of {total_pages}",
            key="transaction_page",
            help="Navigate through transaction pages"
        )
    else:
        current_page = 1

    # Main content area
    col1, col2 = st.columns([2, 1])

    with col1:
        st.subheader(f"📋 Transactions: {selected_file}")
        
        # Calculate slice indices for current page
        start_idx = (current_page - 1) * rows_per_page
        end_idx = min(start_idx + rows_per_page, total_transactions)
        
        # Show pagination info
        st.caption(f"Showing transactions {start_idx + 1}-{end_idx} of {total_transactions} total")
        
        # Get current page data
        current_page_data = transactions_summary.slice(start_idx, rows_per_page)
        
        # Prepare display DataFrame with parsed packet information
        display_rows = []
        for row in current_page_data.iter_rows(named=True):
            # Parse request and response packets for preview
            request_info = parse_packet_preview(row["request_hex"]) if row["request_hex"] else {"preview": "No request"}
            response_info = parse_packet_preview(row["response_hex"]) if row["response_hex"] else {"preview": "No response"}
            
            display_rows.append({
                "transaction_id": row["transaction_id"],
                "start_time_s": round(row["start_time"], 3),
                "duration_s": round(row["duration_s"], 4),
                "frame_count": row["frame_count"],
                "tags": row["tags"] if row["tags"] else [],
                "request_type": request_info["preview"],
                "response_type": response_info["preview"],
                "request_hex": row["request_hex"][:16] + "..." if row["request_hex"] and len(row["request_hex"]) > 16 else (row["request_hex"] or ""),
                "response_hex": row["response_hex"][:16] + "..." if row["response_hex"] and len(row["response_hex"]) > 16 else (row["response_hex"] or ""),
            })
        
        display_df = pl.DataFrame(display_rows)

        # Use st.dataframe for selection with optimized column widths
        selection = st.dataframe(
            display_df,
            on_select="rerun",
            selection_mode="single-row",
            hide_index=True,
            width='stretch',
            # Hide hex columns by default - only show these columns (hex columns can be shown via column visibility controls)
            column_order=("transaction_id", "start_time_s", "duration_s", "frame_count", "tags", "request_type", "response_type"),
            column_config={
                "transaction_id": st.column_config.NumberColumn(
                    "ID",
                    help="Transaction ID",
                    width="small"
                ),
                "start_time_s": st.column_config.NumberColumn(
                    "Time (s)",
                    help="Start time in seconds",
                    format="%.3f",
                    width="small"
                ),
                "duration_s": st.column_config.NumberColumn(
                    "Duration (s)",
                    help="Transaction duration",
                    format="%.4f",
                    width="small"
                ),
                "frame_count": st.column_config.NumberColumn(
                    "Frames",
                    help="Number of frames in transaction",
                    width="small"
                ),
                "tags": st.column_config.ListColumn(
                    "Tags",
                    help="Transaction tags",
                    width="large"
                ),
                "request_type": st.column_config.TextColumn(
                    "Request",
                    help="Request packet type and preview",
                    width="medium"
                ),
                "response_type": st.column_config.TextColumn(
                    "Response", 
                    help="Response packet type and preview",
                    width="medium"
                ),
                "request_hex": st.column_config.TextColumn(
                    "Req Hex",
                    help="Request hex data (truncated)",
                    width="small"
                ),
                "response_hex": st.column_config.TextColumn(
                    "Resp Hex", 
                    help="Response hex data (truncated)",
                    width="small"
                ),
            }
        )

    with col2:
        st.subheader("🔍 Transaction Details")
        
        if not selection.selection.rows:
            st.info("👆 Click a transaction in the table to see details")
        else:
            selected_page_idx = selection.selection.rows[0]  # Index within current page
            selected_global_idx = start_idx + selected_page_idx  # Global index in full dataset
            selected_transaction = transactions_summary.row(selected_global_idx, named=True)
            selected_tid = selected_transaction['transaction_id']
            
            # Transaction overview
            st.success(f"Transaction ID: **{selected_tid}**")
            
            # Metrics in columns
            col_a, col_b = st.columns(2)
            with col_a:
                st.metric("Start Time", f"{selected_transaction['start_time']:.3f}s")
                st.metric("Frame Count", selected_transaction['frame_count'])
            with col_b:
                st.metric("Duration", f"{selected_transaction['duration_s']:.4f}s")
                if selected_transaction['tags']:
                    st.metric("Tags", ", ".join(selected_transaction['tags']))
            
            # Get detailed transaction payload data
            transaction_frames = all_frames_tagged.filter(
                pl.col("transaction_id") == selected_tid
            )
            payload_data = extract_transaction_payloads(transaction_frames)
            
            # Request details
            with st.expander("📤 Request Details", expanded=True):
                if payload_data["request_data"]:
                    request_parsed = parse_packet_preview(payload_data["request_data"])
                    
                    # Show type information above raw data
                    st.metric("Type", request_parsed["type"])
                    
                    # Parse as RawPacket for detailed structure info
                    try:
                        packet_bytes = bytes.fromhex(payload_data["request_data"])
                        raw_packet = parse_raw_packet(packet_bytes)
                        
                        # Show key packet details
                        col_r1, col_r2, col_r3 = st.columns(3)
                        with col_r1:
                            st.text(f"Packet Type: {raw_packet.packet_type}")
                            st.text(f"ID: {raw_packet.id}")
                        with col_r2:
                            st.text(f"Extended Header: {raw_packet.has_extended_header}")
                            st.text(f"Reserved Flag: {raw_packet.reserved_flag}")
                        with col_r3:
                            if raw_packet.attribute:
                                st.text(f"Attribute: {raw_packet.attribute}")
                            if raw_packet.has_extended_header and raw_packet.ext_size:
                                st.text(f"Ext Size: {raw_packet.ext_size}")
                                
                    except Exception as e:
                        st.text(f"Raw packet parsing failed: {str(e)}")
                    
                    # Raw data section
                    st.text("Raw Data:")
                    st.code(payload_data["request_data"], language="text")
                    
                    # Show full parsed packet and raw packet details
                    if "parsed_packet" in request_parsed:
                        with st.expander("🔍 Full Parsed Packet", expanded=False):
                            st.text(str(request_parsed["parsed_packet"]))
                    
                    # Show detailed raw packet info
                    try:
                        packet_bytes = bytes.fromhex(payload_data["request_data"])
                        raw_packet = parse_raw_packet(packet_bytes)
                        with st.expander("⚙️ Raw Packet Details", expanded=False):
                            st.text(str(raw_packet))
                            
                            if raw_packet.has_extended_header:
                                st.text("Extended Header Fields:")
                                st.text(f"  Attribute ID: {raw_packet.ext_attribute_id}")
                                st.text(f"  Next: {raw_packet.ext_next}")
                                st.text(f"  Chunk: {raw_packet.ext_chunk}")
                                st.text(f"  Size: {raw_packet.ext_size}")
                    except Exception:
                        pass
                        
                    if len(payload_data["request_frames"]) > 1:
                        st.info(f"Note: {len(payload_data['request_frames'])} request frames found")
                else:
                    st.info("No request data")
            
            # Response details
            with st.expander("📥 Response Details", expanded=True):
                if payload_data["response_data"]:
                    response_parsed = parse_packet_preview(payload_data["response_data"])
                    
                    # Show type information above raw data
                    st.metric("Type", response_parsed["type"])
                    
                    # Parse as RawPacket for detailed structure info
                    try:
                        packet_bytes = bytes.fromhex(payload_data["response_data"])
                        raw_packet = parse_raw_packet(packet_bytes)
                        
                        # Show key packet details
                        col_r1, col_r2, col_r3 = st.columns(3)
                        with col_r1:
                            st.text(f"Packet Type: {raw_packet.packet_type}")
                            st.text(f"ID: {raw_packet.id}")
                        with col_r2:
                            st.text(f"Extended Header: {raw_packet.has_extended_header}")
                            st.text(f"Reserved Flag: {raw_packet.reserved_flag}")
                        with col_r3:
                            if raw_packet.attribute:
                                st.text(f"Attribute: {raw_packet.attribute}")
                            if raw_packet.has_extended_header and raw_packet.ext_size:
                                st.text(f"Ext Size: {raw_packet.ext_size}")
                                
                    except Exception as e:
                        st.text(f"Raw packet parsing failed: {str(e)}")
                    
                    # Special handling for ADC data - show as metrics immediately
                    if "parsed_packet" in response_parsed:
                        packet = response_parsed["parsed_packet"]
                        if packet.packet_type == "SimpleAdcData" and packet.adc_data:
                            adc = response_parsed["parsed_packet"].adc_data
                            
                            # Show main ADC values as metrics in 2x2 grid
                            col_adc1, col_adc2, col_adc3, col_adc4 = st.columns(4)
                            with col_adc1:
                                st.metric("VBUS", f"{adc.vbus_v:.3f}V")
                            with col_adc2:
                                st.metric("IBUS", f"{adc.ibus_a:.3f}A")
                            with col_adc3:
                                st.metric("Power", f"{adc.power_w:.3f}W")
                            with col_adc4:
                                st.metric("Temp", f"{adc.temp_c:.1f}°C")
                            
                            # Show additional measurements in expandable section
                            with st.expander("🔌 USB-C Pin Voltages", expanded=False):
                                col_pin1, col_pin2, col_pin3, col_pin4 = st.columns(4)
                                with col_pin1:
                                    st.metric("CC1", f"{adc.cc1_v:.3f}V")
                                with col_pin2:
                                    st.metric("CC2", f"{adc.cc2_v:.3f}V")
                                with col_pin3:
                                    st.metric("D+", f"{adc.vdp_v:.3f}V")
                                with col_pin4:
                                    st.metric("D-", f"{adc.vdm_v:.3f}V")
                    
                    # Raw data section
                    st.text("Raw Data:")
                    st.code(payload_data["response_data"], language="text")
                    
                    # Show full parsed packet and raw packet details
                    if "parsed_packet" in response_parsed:
                        with st.expander("🔍 Full Parsed Packet", expanded=False):
                            st.text(str(response_parsed["parsed_packet"]))
                    
                    # Show detailed raw packet info
                    try:
                        packet_bytes = bytes.fromhex(payload_data["response_data"])
                        raw_packet = parse_raw_packet(packet_bytes)
                        with st.expander("⚙️ Raw Packet Details", expanded=False):
                            st.text(str(raw_packet))
                            
                            if raw_packet.has_extended_header:
                                st.text("Extended Header Fields:")
                                st.text(f"  Attribute ID: {raw_packet.ext_attribute_id}")
                                st.text(f"  Next: {raw_packet.ext_next}")
                                st.text(f"  Chunk: {raw_packet.ext_chunk}")
                                st.text(f"  Size: {raw_packet.ext_size}")
                    except Exception:
                        pass
                        
                    if len(payload_data["response_frames"]) > 1:
                        st.info(f"Note: {len(payload_data['response_frames'])} response frames found")
                else:
                    st.info("No response data")
            
            # Frame details
            with st.expander("🖼️ Frame Details", expanded=False):
                frame_display = transaction_frames.select([
                "frame_number",
                    pl.col("timestamp").round(6).alias("timestamp"),
                "transfer_type",
                "endpoint_address",
                "urb_type",
                "data_length",
                    pl.when(pl.col("payload_hex").str.len_chars() > 32)
                      .then(pl.col("payload_hex").str.slice(0, 32) + "...")
                      .otherwise(pl.col("payload_hex"))
                      .alias("payload_preview")
            ]).sort("frame_number")

                st.dataframe(frame_display, width='stretch', hide_index=True)
    
    # ADC Plot Section
    if show_adc_plot:
        st.subheader("📈 ADC Data Visualization")
        
        # Filter for ADC transactions only (using proper Rust library parsing)
        adc_data = []
        
        with st.spinner("Parsing ADC data from transactions..."):
            for row in transactions_summary.iter_rows(named=True):
                if row["response_hex"]:
                    try:
                        packet_bytes = bytes.fromhex(row["response_hex"])
                        parsed_packet = parse_packet(packet_bytes)
                        
                        if parsed_packet.packet_type == "SimpleAdcData" and parsed_packet.adc_data:
                            adc = parsed_packet.adc_data
                            adc_data.append({
                                'time': row['start_time'],
                                'transaction_id': row['transaction_id'],
                                'vbus_v': adc.vbus_v,
                                'ibus_a': abs(adc.ibus_a),  # Use absolute current for plot
                                'power_w': adc.power_w,
                                'temp_c': adc.temp_c,
                                'cc1_v': adc.cc1_v,
                                'cc2_v': adc.cc2_v,
                                'vdp_v': adc.vdp_v,
                                'vdm_v': adc.vdm_v,
                            })
                    except Exception as e:
                        # Skip transactions that can't be parsed as ADC data
                        continue
        
        if adc_data:
            adc_df = pl.DataFrame(adc_data)
            adc_pandas = adc_df.to_pandas()
            
            st.success(f"Found {len(adc_data)} ADC measurements")
            
            # Create subplot with 2x2 layout
            fig = subplots.make_subplots(
                rows=2, cols=2,
                subplot_titles=('Power Measurements', 'USB-C Pins', 'Data Lines', 'Temperature'),
                specs=[[{"secondary_y": True}, {"secondary_y": False}], 
                       [{"secondary_y": False}, {"secondary_y": False}]]
            )
            
            # Power measurements (VBUS & IBUS)
            fig.add_trace(
                go.Scatter(x=adc_pandas['time'], y=adc_pandas['vbus_v'], 
                         name='VBUS (V)', line=dict(color='red'), showlegend=True),
                row=1, col=1
            )
            fig.add_trace(
                go.Scatter(x=adc_pandas['time'], y=adc_pandas['ibus_a'], 
                         name='|IBUS| (A)', line=dict(color='blue'), showlegend=True),
                row=1, col=1, secondary_y=True
            )
            
            # USB-C CC pins
            fig.add_trace(
                go.Scatter(x=adc_pandas['time'], y=adc_pandas['cc1_v'], 
                         name='CC1 (V)', line=dict(color='purple'), showlegend=True),
                row=1, col=2
            )
            fig.add_trace(
                go.Scatter(x=adc_pandas['time'], y=adc_pandas['cc2_v'], 
                         name='CC2 (V)', line=dict(color='brown'), showlegend=True),
                row=1, col=2
            )
            
            # Data lines
            fig.add_trace(
                go.Scatter(x=adc_pandas['time'], y=adc_pandas['vdp_v'], 
                         name='D+ (V)', line=dict(color='cyan'), showlegend=True),
                row=2, col=1
            )
            fig.add_trace(
                go.Scatter(x=adc_pandas['time'], y=adc_pandas['vdm_v'], 
                         name='D- (V)', line=dict(color='magenta'), showlegend=True),
                row=2, col=1
            )
            
            # Temperature and Power
            fig.add_trace(
                go.Scatter(x=adc_pandas['time'], y=adc_pandas['temp_c'], 
                         name='Temp (°C)', line=dict(color='orange'), showlegend=True),
                row=2, col=2
            )
            
            # Update layout
            fig.update_layout(
                height=600,
                title_text=f"ADC Measurements Over Time - {selected_file}",
                showlegend=True,
                legend=dict(
                    orientation="h",
                    yanchor="bottom",
                    y=1.02,
                    xanchor="right",
                    x=1
                )
            )
            
            # Update y-axis labels
            fig.update_yaxes(title_text="Voltage (V)", row=1, col=1)
            fig.update_yaxes(title_text="Current (A)", row=1, col=1, secondary_y=True)
            fig.update_yaxes(title_text="Voltage (V)", row=1, col=2)
            fig.update_yaxes(title_text="Voltage (V)", row=2, col=1)
            fig.update_yaxes(title_text="Temperature (°C)", row=2, col=2)
            
            fig.update_xaxes(title_text="Time (s)")
            
            st.plotly_chart(fig, use_container_width=True)
            
            # Show some statistics
            col_stat1, col_stat2, col_stat3, col_stat4 = st.columns(4)
            with col_stat1:
                st.metric("Avg VBUS", f"{adc_pandas['vbus_v'].mean():.3f}V")
                st.metric("Max VBUS", f"{adc_pandas['vbus_v'].max():.3f}V")
            with col_stat2:
                st.metric("Avg |IBUS|", f"{adc_pandas['ibus_a'].mean():.3f}A")
                st.metric("Max |IBUS|", f"{adc_pandas['ibus_a'].max():.3f}A")
            with col_stat3:
                st.metric("Avg Power", f"{adc_pandas['power_w'].mean():.3f}W")
                st.metric("Max Power", f"{adc_pandas['power_w'].max():.3f}W")
            with col_stat4:
                st.metric("Avg Temp", f"{adc_pandas['temp_c'].mean():.1f}°C")
                st.metric("Max Temp", f"{adc_pandas['temp_c'].max():.1f}°C")
                
        else:
            st.info("No ADC transactions found in selected file")


if __name__ == "__main__":
    main()
