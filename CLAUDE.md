# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This repository contains research tools for reverse engineering the **ChargerLAB POWER-Z KM003C** USB-C power analyzer protocol. The project combines Rust-based packet processing, Python analysis tools, and a Streamlit web interface.

## Development Commands

### Environment Setup
```bash
# Install dependencies and sync environment
uv sync

# Install development dependencies (includes maturin for Rust bindings)
uv sync -E dev
```

### Rust Extension Build
The project includes a Rust Python extension (`km003c_lib`) from an external crate:

```bash
# Build and install Rust extension (recommended)
just rust-ext

# Alternative direct command
uv run maturin develop \
  --manifest-path /home/okhsunrog/code/rust/km003c-rs/km003c-lib/Cargo.toml \
  --features python
```

### Testing and Code Quality
```bash
# Run test suite
just test
# or
uv run pytest -q

# Type check with mypy
uv run mypy km003c_analysis/

# Lint code
just lint
# or
uv run ruff check --output-format=github src tests

# Format code
just format
# or
uv run ruff format src tests
```

### Run Applications
```bash
# Launch Streamlit protocol analyzer web interface
just app
# or
uv run streamlit run km003c_analysis/app.py
```

## Architecture

### Core Components

1. **Rust PCAP Converter** (`rust_pcap_converter/`)
   - Transforms pcapng files to structured Parquet datasets
   - Extracts 41 USB protocol fields using tshark integration
   - Auto-detects device addresses and sessions from filenames

2. **Python Analysis Library** (`km003c_analysis/`)
   - `usb_transaction_splitter.py`: Groups USB frames into logical transactions
   - `transaction_tagger.py`: Tags transactions with semantic meaning
   - `app.py`: Streamlit web interface for interactive analysis

3. **External Rust Library Integration (`km003c_lib`)**
   - Located at `/home/okhsunrog/code/rust/km003c-rs/km003c-lib`
   - Provides comprehensive KM003C protocol parsing and device communication
   - Built with PyO3 for Python integration via maturin

### Data Pipeline
1. **Capture**: USB protocol data in pcapng format
2. **Convert**: Rust converter extracts structured data to Parquet
3. **Process**: Python tools split frames into transactions and add semantic tags  
4. **Analyze**: Streamlit app provides interactive exploration interface

### Key Technical Patterns

- **URB (USB Request Block) tracking**: Uses URB IDs to match Submit/Complete pairs
- **Transaction-level analysis**: Groups related USB frames for protocol understanding
- **Multi-device datasets**: Combines data from different device addresses for comparison
- **Complete capture strategy**: Records all USB communication, filters during analysis
- **100% Protocol Coverage**: All packet types and attributes in captured data are explicitly recognized

## Data Structure

The master dataset (`data/processed/usb_master_dataset.parquet`) contains USB packets with these key fields:
- `frame_number`, `timestamp`: Temporal ordering
- `urb_id`, `urb_type`, `urb_status`: USB transaction tracking
- `transfer_type`, `endpoint_address`: USB protocol details
- `payload_hex`: Raw packet data for protocol analysis
- `device_address`, `session_id`: Multi-device/session support

## Testing Notes

- Tests are in `tests/` directory
- Ruff linting excludes `notebooks/` and `tests/` directories
- Use `uv run pytest` to execute tests
- External Rust crate must be built before running tests that import `km003c_lib`

## km003c-lib API Reference

The `km003c_lib` Python module provides comprehensive KM003C protocol support with detailed documentation and examples. The library achieves **100% parsing success** on all captured protocol data, with explicit recognition of all packet types and attributes.

Use `help()` on any class or function to see detailed usage information:

### Core Functions

```python
from km003c_lib import parse_packet, parse_raw_packet, parse_raw_adc_data, get_sample_rates

# Get detailed help for any function or class
help(parse_packet)  # Shows comprehensive usage documentation
help(RawPacket)     # Shows all fields with detailed explanations

# Parse a complete packet with semantic meaning
packet = parse_packet(raw_bytes)  # Returns Packet object

# Parse raw packet structure without semantic interpretation  
raw_packet = parse_raw_packet(raw_bytes)  # Returns RawPacket object

# Parse raw ADC data bytes directly
adc_data = parse_raw_adc_data(raw_bytes)  # Returns AdcData object

# Get available sample rates
rates = get_sample_rates()  # Returns list of SampleRate objects
```

### Data Types

#### `Packet` (High-level semantic packets)
- `packet_type`: String - "SimpleAdcData", "CmdGetSimpleAdcData", "PdRawData", "CmdGetPdData", "Generic"
- `adc_data`: Optional[AdcData] - Parsed ADC measurements (for SimpleAdcData)
- `pd_data`: Optional[bytes] - Raw PD packet bytes (for PdRawData)  
- `pd_extension_data`: Optional[bytes] - Additional extension data
- `raw_payload`: Optional[bytes] - Raw payload for Generic packets

#### `RawPacket` (Low-level protocol structure)
- `packet_type`: String - Packet type name ("Sync", "Connect", "PutData", etc.)
- `packet_type_id`: int - Numeric packet type ID
- `id`: int - Transaction ID (0-255)
- `has_extended_header`: bool - Whether packet has extended header
- `reserved_flag`: bool - Protocol reserved flag bit
- `ext_attribute_id`: Optional[int] - Extended header attribute ID
- `ext_next`, `ext_chunk`, `ext_size`: Optional[int] - Extended header fields
- `attribute`, `attribute_id`: Optional[str/int] - Packet attribute information
- `payload`: bytes - Raw payload data
- `raw_bytes`: bytes - Complete packet bytes

#### `AdcData` (ADC measurements)
**Electrical Measurements:**
- `vbus_v`, `ibus_a`, `power_w`: float - VBUS voltage, IBUS current, calculated power
- `vbus_avg_v`, `ibus_avg_a`: float - Averaged VBUS/IBUS measurements
- `temp_c`: float - Device temperature in Celsius

**USB Data Lines:**
- `vdp_v`, `vdm_v`: float - D+/D- voltages  
- `vdp_avg_v`, `vdm_avg_v`: float - Averaged D+/D- voltages

**USB-C CC Lines:**
- `cc1_v`, `cc2_v`: float - CC1/CC2 voltages

**Note**: The Python `AdcData` class exposes a subset of fields from the full Rust `AdcDataSimple` struct. Missing fields include `cc2_avg_v` and `internal_vdd_v` which are available in the Rust implementation but not exposed to Python.

#### `SampleRate`
- `hz`: int - Sample rate in samples per second (1, 10, 50, 1000, 10000)
- `name`: str - Human readable name ("1 SPS", "10 SPS", etc.)

### Protocol Constants
- `VID = 0x5FC9` - USB Vendor ID for ChargerLAB
- `PID = 0x0063` - USB Product ID for KM003C

### Protocol Coverage Status

**Known Packet Types (6 types)**:
- `Head` (64) - Header/initialization packets
- `PutData` (65) - Main data packets with various attributes
- Standard control types: `Sync`, `Connect`, `GetData`, etc.

**Unknown Packet Types (6 types)** - *Discovered in protocol analysis*:
- Control types: `Unknown26`, `Unknown44`, `Unknown58`  
- Data types: `Unknown68`, `Unknown76`, `Unknown117`

**Known Attributes (4 types)**:
- `Adc` (1) - ADC measurement data
- `AdcQueue` (2) - Queued ADC data
- `Settings` (8) - Device settings
- `PdPacket` (16) - USB Power Delivery packets

**Unknown Attributes (4 types)** - *Discovered in protocol analysis*:
- `Unknown512` (0x200) - Found with PutData packets
- `Unknown1609` (0x649) - Found with Unknown26 packets
- `Unknown11046` (0x2B26) - Found with Unknown44 packets  
- `Unknown26817` (0x68C1) - Found with Unknown58 packets

**Parsing Success Rate**: 100% (2,934/2,934 bulk frames parsed successfully)

### Usage Patterns in Project

#### Packet Classification
```python
# Parse and classify packets from USB capture data
result = parse_packet(hex_bytes)
if result.packet_type == "SimpleAdcData":
    adc = result.adc_data
    print(f"VBUS: {adc.vbus_v:.3f}V, IBUS: {adc.ibus_a:.3f}A")
elif result.packet_type == "CmdGetSimpleAdcData":
    print("ADC data request command")
elif result.packet_type == "Generic":
    # Unrecognized packet - falls back to Generic
    print(f"Unknown packet type: {result.raw_payload}")
```

#### Protocol Analysis
```python
# Analyze protocol coverage
raw = parse_raw_packet(hex_bytes)
print(f"Type: {raw.packet_type} (ID: {raw.packet_type_id})")
if raw.attribute_id:
    print(f"Attribute: {raw.attribute} (ID: {raw.attribute_id})")
    
# All packet types in current dataset are explicitly recognized:
# No generic "Unknown(123)" patterns - all use specific enum values
```

#### Power Flow Analysis
```python
# Current/power sign indicates direction:
# Positive: USB female (input) → USB male (output)
# Negative: USB male (input) → USB female (output)
if adc_data.ibus_a > 0:
    print(f"Power flowing female→male: {adc_data.power_w:.3f}W")
else:
    print(f"Power flowing male→female: {abs(adc_data.power_w):.3f}W")
```

#### Transaction Matching
```python
# Use transaction IDs to match request/response pairs
raw = parse_raw_packet(bytes)
transaction_id = raw.id  # 0-255, wraps around
```

## Dependencies

- **Python**: polars, streamlit, matplotlib, plotly, usbpdpy
- **Rust**: Built separately via maturin, requires Rust toolchain
- **External tools**: tshark (used by Rust converter), just (task runner)