# KM003C Protocol Research

Reverse engineering documentation and analysis of the **ChargerLAB POWER-Z KM003C** USB-C power analyzer protocol.

## 🔍 Research Overview

This repository contains the complete reverse engineering process, findings, and analysis tools for understanding the KM003C communication protocol.

## 📁 Repository Structure

```
km003c-protocol-research/
├── docs/                       # Protocol documentation
│   ├── protocol.md            # Complete protocol specification
│   ├── analysis.md            # Detailed analysis findings
│   └── KM002C&3C API Description.*  # Original documentation
├── captures/                   # Raw data and captures
│   ├── wireshark/             # PCAPNG files from USB traffic
│   ├── logs/                  # Text logs and raw captures
│   ├── sqlite/                # Database exports from proprietary software
│   └── *.rules                # udev rules for device access
├── analysis/                   # Python analysis tools
│   ├── notebooks/             # Jupyter notebooks
│   └── scripts/               # Analysis scripts
├── pyproject.toml             # Python project configuration
└── uv.lock                    # Dependency lock file
```

## 🛠️ Implementation

For the production Rust implementation based on this research, see:
**[km003c-rs](https://github.com/okhsunrog/km003c-rs)**

## 📊 Key Findings

### Protocol Details
- **USB Device**: VID 0x5FC9, PID 0x0063
- **Communication**: USB HID with bulk transfer endpoints
- **Protocol**: Custom binary protocol with control and data packets
- **Data Types**: ADC measurements and USB PD message capture

### Packet Types Identified
- `GetData` (0x0C) - Request data from device
- `PutData` (0x41) - Device response with data
- `Accept` (0x05) - Command acknowledgment

### Data Formats
- **ADC Data**: 32-byte structure with voltage, current, temperature
- **PD Data**: Event stream with connection events, status, and wrapped PD messages

## 🔬 Reverse Engineering Tools Used

- **Wireshark + usbmon**: USB traffic capture and analysis
- **Ghidra**: Proprietary software reverse engineering
- **Python + usbpdpy**: Protocol analysis and message parsing
- **TShark**: Automated packet processing

## 📈 Analysis Tools

### Python Analysis Environment
- **Jupyter notebooks** for interactive analysis (`analysis/notebooks/`)
- **usbpdpy package** for fast USB PD message parsing
- **pandas/matplotlib** for data visualization
- **PCAPNG processing** tools and scripts

### Usage
```bash
# Setup environment
uv venv
source .venv/bin/activate
uv pip sync

# Run analysis
jupyter notebook analysis/notebooks/usbpdpy_examples.ipynb
```

## 🎯 Research Status

### ✅ Completed
- Basic protocol structure reverse engineered
- ADC data format documented
- USB PD message wrapper format identified
- Python analysis tools created
- Core packet types mapped

### 🔄 In Progress
- Advanced command investigation
- Extended header format analysis
- Additional packet type identification

### ❓ Unknown
- Device configuration commands
- Firmware update protocol
- Some proprietary packet types (0x10, 0x11)

## 📚 Documentation

- **[Protocol Specification](docs/protocol.md)** - Complete technical documentation
- **[Analysis Notes](docs/analysis.md)** - Detailed reverse engineering findings

## 🤝 Contributing

Contributions to the research are welcome! Areas where help is needed:

- Additional PCAPNG captures from different scenarios
- Analysis of unknown packet types
- Documentation improvements
- New analysis tools and techniques

## 📄 License

This research is shared under MIT License for educational and research purposes.

## 🙏 Acknowledgments

- **usbpd crate authors** for the excellent USB PD parsing library
- **Wireshark community** for powerful analysis tools
- **ChargerLAB** for creating innovative USB-C analysis hardware

---

**For the production Rust implementation, visit: [km003c-rs](https://github.com/okhsunrog/km003c-rs)**
