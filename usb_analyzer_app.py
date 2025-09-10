#!/usr/bin/env python3
"""
Interactive USB Protocol Analyzer - Streamlit App

A modern web interface for analyzing KM003C USB protocol transactions
with interactive tables, detailed transaction views, and ADC data visualization.
"""

import streamlit as st
import polars as pl
import plotly.express as px
import plotly.graph_objects as go
from plotly import subplots
import sys
from pathlib import Path

# Setup project paths
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / 'analysis' / 'scripts'))
import helpers

# Page configuration
st.set_page_config(
    page_title="USB Protocol Analyzer",
    page_icon="🔌",
    layout="wide",
    initial_sidebar_state="expanded"
)

@st.cache_data
def load_data():
    """Load the master dataset with caching."""
    return helpers.load_master_dataset(project_root / 'usb_master_dataset.parquet')

@st.cache_data
def get_transactions_cached(source_file: str, hide_enumeration: bool):
    """Get transactions for a source file with caching."""
    df = load_data()
    filtered_df = df.filter(pl.col('source_file') == source_file)
    return helpers.get_transactions(filtered_df, filter_out_enumeration=hide_enumeration)

def main():
    st.title("🔌 USB Protocol Analyzer")
    st.markdown("Interactive analysis of KM003C USB protocol transactions")
    
    # Load data
    try:
        df = load_data()
    except Exception as e:
        st.error(f"Failed to load dataset: {e}")
        st.stop()
    
    # Sidebar controls
    st.sidebar.header("📊 Analysis Controls")
    
    # Get available source files - sorted for consistent order
    source_files = sorted(df['source_file'].unique().to_list())
    source_file_options = []
    for file in source_files:
        count = len(df.filter(pl.col('source_file') == file))
        source_file_options.append(f"{file} ({count} packets)")
    
    # Source file selection
    selected_option = st.sidebar.selectbox(
        "Source File",
        source_file_options,
        help="Select a capture file to analyze"
    )
    selected_file = selected_option.split(' (')[0]
    
    # Filter options
    hide_enumeration = st.sidebar.checkbox(
        "Hide enumeration packets",
        value=True,
        help="Filter out USB enumeration transactions"
    )
    
    show_adc_plot = st.sidebar.checkbox(
        "Show ADC data plot",
        value=False,
        help="Display voltage/current measurements over time"
    )
    
    # Table configuration
    st.sidebar.subheader("🔧 Table Options")
    max_rows = st.sidebar.slider(
        "Maximum rows to display",
        min_value=10,
        max_value=500,
        value=50,
        step=10
    )
    
    # Get transactions
    with st.spinner("Loading transactions..."):
        transactions = get_transactions_cached(selected_file, hide_enumeration)
    
    if transactions.is_empty():
        st.warning("No transactions found for the selected file.")
        return
    
    # Main content area - adjust column ratios for better space
    col1, col2 = st.columns([3, 2])
    
    with col1:
        st.subheader(f"📋 Transactions: {selected_file}")
        st.caption(f"Found {len(transactions)} transactions")
        
        # Display transactions table
        display_df = transactions.head(max_rows).select([
            'start_time',
            'duration_ms', 
            'request_packet_type',
            'response_packet_type',
            pl.col('payload_length').alias('req_len'),
            pl.col('complete_data_length').alias('resp_len'),
            pl.when(pl.col('payload_hex').str.len_chars() > 16)
              .then(pl.col('payload_hex').str.slice(0, 16) + "...")
              .otherwise(pl.col('payload_hex'))
              .alias('request_hex'),
        ])
        
        # Convert to pandas for streamlit display
        display_pandas = display_df.to_pandas()
        
        # Interactive table with selection - corrected approach
        # Use source file in key to reset selection when file changes
        event = st.dataframe(
            display_pandas,
            use_container_width=True,
            hide_index=True,
            on_select="rerun",
            selection_mode="multi-row",
            key=f"transactions_table_{selected_file}"
        )
        
        # Get selected rows using correct syntax
        selected_indices = event.selection.rows
        
        # Debug info
        st.write(f"Selected row indices: {selected_indices}")
        st.write(f"Event object: {event}")
        st.write(f"Event selection: {event.selection}")
        
        if len(selected_indices) > 0:
            selected_idx = selected_indices[0]
            selected_transaction = transactions.row(selected_idx, named=True)
            
            # Show pagination info
            if len(transactions) > max_rows:
                st.info(f"Showing {max_rows} of {len(transactions)} transactions. Adjust the slider to see more.")
    
    with col2:
        st.subheader("🔍 Transaction Details")
        
        if len(selected_indices) > 0:
            st.success("Transaction selected")
            
            # Transaction overview card
            with st.container():
                st.markdown("### Overview")
                st.metric("Start Time", f"{selected_transaction['start_time']:.3f}s")
                st.metric("Duration", f"{selected_transaction['duration_ms']:.2f}ms")
                
                # Full width for packet types to prevent truncation
                st.markdown("**Request Type:**")
                st.code(selected_transaction['request_packet_type'], language=None)
                st.markdown("**Response Type:**")
                st.code(selected_transaction['response_packet_type'], language=None)
            
            # Request details
            with st.expander("📤 Request Details", expanded=True):
                st.text(f"Length: {selected_transaction['payload_length']} bytes")
                # Format hex with spaces for better readability
                hex_formatted = ' '.join([selected_transaction['payload_hex'][i:i+2] 
                                        for i in range(0, len(selected_transaction['payload_hex']), 2)])
                st.code(hex_formatted, language=None)
            
            # Response details  
            if selected_transaction['complete_payload_hex']:
                with st.expander("📥 Response Details", expanded=True):
                    st.text(f"Length: {selected_transaction['complete_data_length']} bytes")
                    # Format hex with spaces for better readability
                    response_hex_formatted = ' '.join([selected_transaction['complete_payload_hex'][i:i+2] 
                                                     for i in range(0, len(selected_transaction['complete_payload_hex']), 2)])
                    st.code(response_hex_formatted, language=None)
            else:
                st.warning("No response data available")
                
            # ADC data if available
            if selected_transaction['response_packet_type'] == 'SimpleAdcData':
                with st.expander("⚡ ADC Measurements", expanded=True):
                    try:
                        # Parse the response packet to get ADC data
                        from km003c_lib import parse_packet
                        response_bytes = bytes.fromhex(selected_transaction['complete_payload_hex'])
                        packet = parse_packet(response_bytes)
                        
                        if packet.adc_data:
                            adc = packet.adc_data
                            col_x, col_y = st.columns(2)
                            with col_x:
                                st.metric("VBUS", f"{adc.vbus_v:.3f}V")
                                st.metric("IBUS", f"{adc.ibus_a:.3f}A") 
                                st.metric("Power", f"{adc.power_w:.3f}W")
                                st.metric("Temperature", f"{adc.temp_c:.1f}°C")
                            with col_y:
                                st.metric("CC1", f"{adc.cc1_v:.3f}V")
                                st.metric("CC2", f"{adc.cc2_v:.3f}V")
                                st.metric("D+", f"{adc.vdp_v:.3f}V")
                                st.metric("D-", f"{adc.vdm_v:.3f}V")
                    except Exception as e:
                        st.error(f"Failed to parse ADC data: {e}")
        else:
            st.info("👆 Click a row in the table to see details")
    
    # ADC Plot Section
    if show_adc_plot:
        st.subheader("📈 ADC Data Visualization")
        
        # Filter for ADC transactions only
        adc_transactions = transactions.filter(
            pl.col('response_packet_type') == 'SimpleAdcData'
        )
        
        if not adc_transactions.is_empty():
            try:
                # Parse all ADC responses to extract measurement data
                adc_data = []
                for row in adc_transactions.iter_rows(named=True):
                    try:
                        from km003c_lib import parse_packet
                        response_bytes = bytes.fromhex(row['complete_payload_hex'])
                        packet = parse_packet(response_bytes)
                        
                        if packet.adc_data:
                            adc = packet.adc_data
                            adc_data.append({
                                'time': row['start_time'],
                                'vbus_v': adc.vbus_v,
                                'ibus_a': adc.ibus_a,
                                'power_w': adc.power_w,
                                'temp_c': adc.temp_c,
                                'cc1_v': adc.cc1_v,
                                'cc2_v': adc.cc2_v,
                                'vdp_v': adc.vdp_v,
                                'vdm_v': adc.vdm_v,
                            })
                    except Exception:
                        continue
                
                if adc_data:
                    adc_df = pl.DataFrame(adc_data)
                    adc_pandas = adc_df.to_pandas()
                    
                    # Create subplot
                    fig = subplots.make_subplots(
                        rows=2, cols=2,
                        subplot_titles=('Voltage & Current', 'Power & Temperature', 'CC Voltages', 'Data Lines'),
                        specs=[[{"secondary_y": True}, {"secondary_y": True}], 
                               [{"secondary_y": False}, {"secondary_y": False}]]
                    )
                    
                    # Voltage & Current
                    fig.add_trace(
                        go.Scatter(x=adc_pandas['time'], y=adc_pandas['vbus_v'], 
                                 name='VBUS (V)', line=dict(color='red')),
                        row=1, col=1
                    )
                    fig.add_trace(
                        go.Scatter(x=adc_pandas['time'], y=adc_pandas['ibus_a'], 
                                 name='IBUS (A)', line=dict(color='blue')),
                        row=1, col=1, secondary_y=True
                    )
                    
                    # Power & Temperature
                    fig.add_trace(
                        go.Scatter(x=adc_pandas['time'], y=adc_pandas['power_w'], 
                                 name='Power (W)', line=dict(color='green')),
                        row=1, col=2
                    )
                    fig.add_trace(
                        go.Scatter(x=adc_pandas['time'], y=adc_pandas['temp_c'], 
                                 name='Temp (°C)', line=dict(color='orange')),
                        row=1, col=2, secondary_y=True
                    )
                    
                    # CC Voltages
                    fig.add_trace(
                        go.Scatter(x=adc_pandas['time'], y=adc_pandas['cc1_v'], 
                                 name='CC1 (V)', line=dict(color='purple')),
                        row=2, col=1
                    )
                    fig.add_trace(
                        go.Scatter(x=adc_pandas['time'], y=adc_pandas['cc2_v'], 
                                 name='CC2 (V)', line=dict(color='brown')),
                        row=2, col=1
                    )
                    
                    # Data Lines
                    fig.add_trace(
                        go.Scatter(x=adc_pandas['time'], y=adc_pandas['vdp_v'], 
                                 name='D+ (V)', line=dict(color='cyan')),
                        row=2, col=2
                    )
                    fig.add_trace(
                        go.Scatter(x=adc_pandas['time'], y=adc_pandas['vdm_v'], 
                                 name='D- (V)', line=dict(color='magenta')),
                        row=2, col=2
                    )
                    
                    fig.update_layout(
                        height=600,
                        title_text="ADC Measurements Over Time",
                        showlegend=True
                    )
                    
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.warning("No valid ADC data found in selected transactions")
                    
            except Exception as e:
                st.error(f"Failed to create ADC plot: {e}")
        else:
            st.info("No ADC transactions found in selected file")

if __name__ == "__main__":
    main()