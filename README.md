# KM003C Protocol Research

Reverse engineering the ChargerLAB POWER-Z KM003C USB-C power analyzer protocol.

## Protocol Documentation

[`docs/protocol_specification.md`](docs/protocol_specification.md) - Complete protocol specification for the KM003C device. Consolidates reverse engineering findings, community implementations, and official documentation.
[`docs/pd_sqlite_export_format.md`](docs/pd_sqlite_export_format.md) - Format of PD captures exported by the official Windows app (SQLite schema + Raw BLOB wire layout).

## Architecture

### Data Pipeline
- Rust-based pcapng to Parquet converter 
- Extracts 41 USB protocol fields using tshark
- Handles multiple devices and capture sessions

### Dataset
`data/processed/usb_master_dataset.parquet` - 11,514 USB packets across 4 devices and 7 capture sessions.

### Analysis Tools
- `km003c_analysis/` - Python library for reusable USB transaction processing and GUI
- `scripts/` - Analysis and data export scripts for research workflows
- `notebooks/` - Jupyter notebooks for manual protocol exploration
- `rust_pcap_converter/` - PCAP processing tool

## Usage

### Linux USB Permissions

For device access and USB packet capture on Linux, install the provided udev rules:

```bash
# Device access (required for communicating with KM003C)
sudo cp 71-powerz-km003c.rules /etc/udev/rules.d/

# USB monitoring (required for capturing USB traffic with Wireshark)
sudo cp 99-usbmon.rules /etc/udev/rules.d/

# Reload rules
sudo udevadm control --reload-rules
sudo udevadm trigger
```

**Device access (`71-powerz-km003c.rules`):** Uses the modern `uaccess` tag approach for secure, dynamic access to logged-in users. See the [Arch Wiki on udev](https://wiki.archlinux.org/title/Udev#Allowing_regular_users_to_use_devices) for details.

**USB monitoring (`99-usbmon.rules`):** Grants the `wireshark` group access to `usbmon` devices for USB packet capture. Add your user to the `wireshark` group: `sudo usermod -aG wireshark $USER` (logout/login required).

### Environment Setup
```bash
uv sync
just rust-ext  # Build km003c_lib Python bindings
```

### PCAP Conversion
```bash
./rust_pcap_converter/target/debug/pcap_to_parquet --input capture.pcapng
```

### Analysis Library
```python
from km003c_analysis import split_usb_transactions, tag_transactions
import polars as pl

df = pl.read_parquet("data/processed/usb_master_dataset.parquet")
df_with_transactions = split_usb_transactions(df)
df_tagged = tag_transactions(df_with_transactions)
```

### Production Tools
```bash
# Comprehensive SQLite PD export analyzer
uv run python -m km003c_analysis.tools.pd_sqlite_analyzer --verbose

# Export PD analysis to JSON/Parquet
uv run python -m km003c_analysis.tools.pd_sqlite_analyzer --export-json results.json
uv run python -m km003c_analysis.tools.pd_sqlite_analyzer --export-parquet messages.parquet
```

### Analysis Scripts
```bash
# Complete KM003C protocol analysis
uv run python scripts/analyze_km003c_protocol.py

# Export PD messages to Parquet
uv run python scripts/export_pd_messages.py

# Wrapped PD format parsing
uv run python scripts/parse_pd_wrapped.py
```

### Web Interface
```bash
just app  # Launch Streamlit analyzer

## Protocol Parsing and Attribute Masks

- Use the Rust-backed parser `km003c_lib` for protocol parsing in scripts and tools. Prefer `parse_packet()` for semantic payloads (ADC, AdcQueue, PD status/events) and `parse_raw_packet()` for low-level headers and logical packets when needed.
- Control header layout (wire):
  - `type` 7 bits, `reserved_flag` 1 bit, `id` 8 bits, 1 unnamed bit, then `att` 15 bits.
- The 15-bit `att` field holds attribute values directly (no shifting). Examples: `0x0001` ADC, `0x0002` AdcQueue, `0x0008` Settings, `0x0010` PdPacket.
 - Byte layout gotcha (for humans/agents reading hex): the `att` field starts at bit 17 of the 32-bit little‑endian header. For `att=0x0001` (ADC), the third byte often appears as `0x02` — this is correct and does not mean `0x0002` (AdcQueue). Always parse via the 32‑bit little‑endian bitfield or use `km003c_lib`.
  - `reserved_flag` is vendor-specific and is NOT an indicator of extended headers. PutData (0x41) responses always include chained logical packets.
- Extended header (per logical packet): `att:15 | next:1 | chunk:6 | size:10`.

Recommended usage:
```
from km003c_lib import parse_packet, parse_raw_packet
from scripts.km003c_helpers import get_packet_type, get_adc_data, get_pd_status, get_pd_events

pkt = parse_packet(packet_bytes)
if get_packet_type(pkt) == "DataResponse":
    adc = get_adc_data(pkt)
    pdst = get_pd_status(pkt)
    pdev = get_pd_events(pkt)

raw = parse_raw_packet(packet_bytes)
if isinstance(raw, dict) and "Data" in raw:
    hdr = raw["Data"]["header"]
    for lp in raw["Data"]["logical_packets"]:
        attr = lp.get("attribute")  # e.g. 1, 2, 8, 16
```

Important: Avoid manual bit/byte parsing for KM003C headers in Python. Agents and scripts should use the Rust parser to prevent off-by-one mistakes in attribute masks and misinterpretation of `reserved_flag`.
```

## Protocol Insights

- USB VID: 0x5FC9, PID: 0x0063
- Bulk transfer endpoints: 0x01 (OUT), 0x81 (IN)
- Application layer protocol with extended headers
- Dual ADC measurement and Power Delivery analysis modes
- URB ID reuse pattern requires Submit/Complete pair analysis

## Related Projects

- [km003c-rs](https://github.com/okhsunrog/km003c-rs) - Rust implementation
- [Linux kernel driver](https://kernel.googlesource.com/pub/scm/linux/kernel/git/akpm/mm/+/refs/tags/mm-everything-2023-12-29-21-56/drivers/hwmon/powerz.c)
- [Community implementations](docs/protocol_specification.md#community-contributions)
