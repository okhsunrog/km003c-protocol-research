# KM003C Protocol Research

Reverse engineering the **ChargerLAB POWER-Z KM003C** USB-C power analyzer protocol through comprehensive packet capture analysis.

## 🎯 Project Purpose

Understand the KM003C USB communication patterns to enable protocol documentation and implementation for research and development purposes.

## 🏗️ Architecture

### Data Pipeline
The project uses a **Rust-based converter** that transforms pcap files into structured Parquet datasets for analysis.

**Key Component**: `rust_pcap_converter/`
- Extracts 41 comprehensive USB protocol fields from pcapng files
- Handles multiple devices and sessions with auto-detection from filenames
- Provides complete USB communication visibility (control + data + status packets)

### Master Dataset
**File**: `usb_master_dataset.parquet` (506KB)
- **11,514 USB packets** across 4 devices (addresses 6, 9, 13, 16)
- **7 capture sessions** with full source tracking
- **41 fields per packet** including payload data, control packet parsing, URB tracking

### Analysis Tools
**Notebooks**:
- `usb_protocol_analysis.ipynb` - Interactive analysis of master dataset
- `usbpdpy_examples.ipynb` - USB Power Delivery message parsing

**Scripts**:
- `helpers.py` - Core analysis functions for USB protocol research
- `analyze_parquet_with_payload.py` - Command-line analysis tool
- `parse_messages.py` - USB PD message parsing utility

## 🔧 Usage

### Converting PCAP Files
```bash
# Auto-detects device address and session from filename
./rust_pcap_converter/target/debug/pcap_to_parquet --input capture.13.pcapng

# Append to existing dataset
./rust_pcap_converter/target/debug/pcap_to_parquet --input new_capture.16.pcapng --output usb_master_dataset.parquet --append
```

### Analysis Workflow
```python
# Load and analyze
from helpers import load_master_dataset, get_session_stats
df = load_master_dataset('usb_master_dataset.parquet')
stats = get_session_stats(df)

# Filter for specific analysis
device_13 = df.filter(pl.col('device_address') == 13)
payload_data = df.filter(pl.col('payload_hex') != '')
control_packets = df.filter(pl.col('transfer_type') == '0x02')
```

### Setup Environment
```bash
# Install dependencies
uv sync

# Start analysis
cd analysis/notebooks
jupyter notebook usb_protocol_analysis.ipynb
```

## 🔍 Key Technical Insights

### USB Protocol Structure
- **URB IDs**: Unique identifiers for tracking USB transactions (Submit/Complete pairs)
- **Transfer Types**: 0x02 (control), 0x03 (interrupt) - different purposes and data patterns
- **Control Packets**: USB setup requests with parsed bmRequestType, bRequest, wLength fields
- **Payload Data**: Raw hex data extracted via rtshark (not accessible through pyshark)

### Data Extraction Approach
- **Complete capture strategy** - Capture ALL USB communication by default, filter in analysis
- **Transaction-level analysis** - Use URB IDs to match Submit/Complete pairs for timing analysis
- **Multi-device datasets** - Combine captures from different devices for comparative analysis

### Why Rust + tshark
- **pyshark limitation**: Cannot extract field containing actual USB payload
- **Performance**: Direct tshark integration provides complete USB protocol access
- **Data completeness**: Extracts all 41 available USB fields vs limited Python alternatives

## 📊 Dataset Overview

**Current Data**: 11,514 USB packets across 4 devices
- **Device 6**: 2,230 packets (ADC measurements, high data rate)
- **Device 9**: 6,930 packets (Power Delivery analysis)
- **Device 13**: 2,056 packets (Complete protocol communication)
- **Device 16**: 298 packets (Device operations)

**Analysis Capabilities**:
- Transaction pairing using URB IDs
- Control packet parsing with USB setup requests
- Payload pattern recognition and timing analysis
- Multi-session comparative analysis

## 🎯 Research Applications

1. **Transaction timing** - Submit/Complete latency analysis
2. **Payload pattern recognition** - Protocol command/response structure
3. **Multi-device comparison** - Different device behavior analysis
4. **Control flow understanding** - USB enumeration and setup sequences

## 🚀 Quick Start

1. **Load the dataset**: `df = load_master_dataset('usb_master_dataset.parquet')`
2. **Explore sessions**: `stats = get_session_stats(df)`
3. **Analyze patterns**: Use URB IDs for transaction pairing
4. **Deep dive**: Focus on payload data for protocol reverse engineering

## 🔗 Related Projects

**Production Implementation**: [km003c-rs](https://github.com/okhsunrog/km003c-rs) - Rust library for KM003C device communication

---

The infrastructure is production-ready for advanced USB protocol reverse engineering research.
