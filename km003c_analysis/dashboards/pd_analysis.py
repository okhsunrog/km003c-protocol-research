#!/usr/bin/env python3
"""
USB Power Delivery Analysis Dashboard

Interactive Streamlit dashboard for comprehensive KM003C PD analysis using usbpdpy v0.2.0.
Provides real-time visualization of power negotiations, PDO/RDO analysis, and protocol validation.

Run: streamlit run notebooks/pd_analysis_dashboard.py
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import sqlite3
import usbpdpy
from pathlib import Path
from typing import Dict, List, Any, Optional
import numpy as np


@st.cache_data
def load_pd_analysis_data() -> pd.DataFrame:
    """Load complete PD analysis data from Parquet"""
    parquet_path = Path("data/processed/complete_pd_analysis.parquet")
    
    if parquet_path.exists():
        return pd.read_parquet(parquet_path)
    else:
        # Fallback: generate from SQLite if Parquet doesn't exist
        st.warning("Parquet file not found. Run export_complete_pd_analysis.py first.")
        return pd.DataFrame()


def main():
    st.set_page_config(
        page_title="USB-PD Protocol Analysis",
        page_icon="⚡",
        layout="wide"
    )
    
    st.title("⚡ USB Power Delivery Protocol Analysis")
    st.markdown("**KM003C Capture Analysis with usbpdpy v0.2.0**")
    
    # Load data
    df = load_pd_analysis_data()
    
    if df.empty:
        st.error("No data available. Please run export_complete_pd_analysis.py first.")
        return
    
    # Sidebar filters
    st.sidebar.header("🔧 Analysis Filters")
    
    # Message type filter
    message_types = df['pd_message_type'].dropna().unique()
    selected_messages = st.sidebar.multiselect(
        "Message Types",
        message_types,
        default=message_types
    )
    
    # Negotiation filter
    negotiations = sorted(df['negotiation_id'].dropna().unique())
    selected_negotiations = st.sidebar.multiselect(
        "Negotiations",
        negotiations,
        default=negotiations
    )
    
    # Filter data
    filtered_df = df[
        (df['pd_message_type'].isin(selected_messages)) &
        (df['negotiation_id'].isin(selected_negotiations))
    ]
    
    # Main dashboard layout
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.header("📊 Power Negotiation Timeline")
        
        # Voltage timeline with message annotations
        fig_timeline = go.Figure()
        
        # Add voltage trace
        voltage_data = df.dropna(subset=['vbus_v'])
        fig_timeline.add_trace(go.Scatter(
            x=voltage_data['time_s'],
            y=voltage_data['vbus_v'],
            mode='lines+markers',
            name='Bus Voltage',
            line=dict(color='blue', width=2),
            hovertemplate='<b>Time:</b> %{x:.3f}s<br><b>Voltage:</b> %{y:.3f}V<extra></extra>'
        ))
        
        # Add message annotations
        for msg_type in ['Source_Capabilities', 'Request', 'Accept', 'PS_RDY']:
            msg_data = df[df['pd_message_type'] == msg_type]
            if not msg_data.empty:
                fig_timeline.add_trace(go.Scatter(
                    x=msg_data['time_s'],
                    y=msg_data['vbus_v'],
                    mode='markers',
                    name=msg_type,
                    marker=dict(size=10, symbol='diamond'),
                    hovertemplate=f'<b>{msg_type}</b><br>Time: %{{x:.3f}}s<br>Voltage: %{{y:.3f}}V<extra></extra>'
                ))
        
        fig_timeline.update_layout(
            title="Voltage Timeline with PD Messages",
            xaxis_title="Time (seconds)",
            yaxis_title="Bus Voltage (V)",
            hovermode='closest'
        )
        
        st.plotly_chart(fig_timeline, use_container_width=True)
    
    with col2:
        st.header("📈 Protocol Statistics")
        
        # Message distribution
        msg_counts = df['pd_message_type'].value_counts()
        
        fig_pie = px.pie(
            values=msg_counts.values,
            names=msg_counts.index,
            title="Message Type Distribution"
        )
        st.plotly_chart(fig_pie, use_container_width=True)
        
        # Key metrics
        st.metric("Total Messages", len(df))
        st.metric("Negotiations", int(df['negotiation_id'].max() or 0))
        
        voltage_change = df['vbus_v'].max() - df['vbus_v'].min()
        st.metric("Voltage Range", f"{voltage_change:.2f}V")
    
    # PDO Analysis Section
    st.header("🔋 Power Data Object (PDO) Analysis")
    
    pdo_data = df[df['pdo_type'].notna()].copy()
    
    if not pdo_data.empty:
        col1, col2 = st.columns(2)
        
        with col1:
            # PDO power capability chart
            fig_pdo = px.scatter(
                pdo_data,
                x='voltage_v',
                y='max_current_a',
                size='max_power_w',
                color='pdo_type',
                title="PDO Power Capabilities",
                labels={
                    'voltage_v': 'Voltage (V)',
                    'max_current_a': 'Max Current (A)',
                    'max_power_w': 'Max Power (W)'
                }
            )
            st.plotly_chart(fig_pdo, use_container_width=True)
        
        with col2:
            # PDO details table
            st.subheader("PDO Details")
            pdo_summary = pdo_data.groupby(['pdo_position', 'pdo_type']).agg({
                'voltage_v': 'first',
                'max_current_a': 'first',
                'max_power_w': 'first',
                'unconstrained_power': 'first'
            }).reset_index()
            
            st.dataframe(
                pdo_summary.style.format({
                    'voltage_v': '{:.1f}V',
                    'max_current_a': '{:.2f}A',
                    'max_power_w': '{:.1f}W'
                }),
                use_container_width=True
            )
    
    # RDO Analysis Section
    st.header("🔌 Request Data Object (RDO) Analysis")
    
    rdo_data = df[df['rdo_type'].notna()].copy()
    
    if not rdo_data.empty:
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Request Details")
            
            for _, rdo in rdo_data.iterrows():
                with st.expander(f"Request at {rdo['time_s']:.3f}s"):
                    st.write(f"**Requested PDO:** #{rdo['object_position']}")
                    st.write(f"**RDO Type:** {rdo['rdo_type']}")
                    st.write(f"**Raw RDO:** 0x{int(rdo['rdo_raw']):08x}")
                    
                    if pd.notna(rdo['operating_current_a']):
                        st.write(f"**Operating Current:** {rdo['operating_current_a']:.2f}A")
                    
                    st.write(f"**Capability Mismatch:** {rdo['capability_mismatch']}")
                    st.write(f"**USB Communications:** {rdo['usb_communications_capable']}")
        
        with col2:
            st.subheader("Power Selection Analysis")
            
            # Show requested vs available power
            if pd.notna(rdo_data['requested_voltage_v'].iloc[0]):
                requested_voltage = rdo_data['requested_voltage_v'].iloc[0]
                requested_current = rdo_data['requested_max_current_a'].iloc[0]
                requested_power = rdo_data['requested_max_power_w'].iloc[0]
                
                st.metric("Requested Voltage", f"{requested_voltage:.1f}V")
                st.metric("Available Current", f"{requested_current:.2f}A")
                st.metric("Available Power", f"{requested_power:.1f}W")
                
                # Voltage transition
                voltage_before = df['vbus_v'].iloc[0]
                voltage_after = df['vbus_v'].iloc[-1]
                
                st.write("**Voltage Transition:**")
                st.write(f"{voltage_before:.3f}V → {voltage_after:.3f}V")
                st.write(f"Change: {voltage_after - voltage_before:+.3f}V")
    
    # Protocol Flow Analysis
    st.header("🔄 Protocol Flow Analysis")
    
    flow_data = df[df['pd_message_type'].notna()].copy()
    flow_data = flow_data.sort_values('time_s')
    
    if not flow_data.empty:
        # Create flow timeline
        fig_flow = px.timeline(
            flow_data,
            x_start='time_s',
            x_end='time_s',
            y='pd_message_type',
            color='negotiation_id',
            title="Protocol Message Flow"
        )
        
        st.plotly_chart(fig_flow, use_container_width=True)
        
        # Flow table
        st.subheader("Message Sequence")
        flow_summary = flow_data[['time_s', 'pd_message_type', 'vbus_v', 'negotiation_id']].copy()
        flow_summary['time_s'] = flow_summary['time_s'].round(3)
        
        st.dataframe(
            flow_summary.style.format({
                'time_s': '{:.3f}s',
                'vbus_v': '{:.3f}V'
            }),
            use_container_width=True
        )
    
    # Raw Data Explorer
    with st.expander("🔍 Raw Data Explorer"):
        st.subheader("Complete Dataset")
        st.dataframe(df, use_container_width=True)
        
        # Download options
        st.subheader("Export Data")
        col1, col2 = st.columns(2)
        
        with col1:
            csv_data = df.to_csv(index=False)
            st.download_button(
                "Download CSV",
                csv_data,
                "pd_analysis.csv",
                "text/csv"
            )
        
        with col2:
            # JSON export for API use
            json_data = df.to_json(orient='records', indent=2)
            st.download_button(
                "Download JSON",
                json_data,
                "pd_analysis.json",
                "application/json"
            )


if __name__ == "__main__":
    main()