# KM003C Protocol Research

Complete reverse engineering documentation for the **ChargerLAB POWER-Z KM003C** USB-C power analyzer.

## Device Identification

| Property | Value |
|----------|-------|
| Vendor ID | `0x5FC9` (ChargerLAB) |
| Product ID | `0x0063` (KM003C) |
| USB Speed | Full Speed (12 Mbps) |
| Primary Interface | Vendor bulk (IF0, EP 0x01/0x81) |

---

## Documentation Map

### Core Protocol

| Document | Description |
|----------|-------------|
| **[Protocol Reference](protocol_reference.md)** | Complete protocol specification - commands, attributes, data structures, cryptography |
| [USB Transport](usb_transport.md) | USB descriptors, endpoints, bulk transfer details |

### Feature Deep-Dives

| Document | Description |
|----------|-------------|
| [Authentication](features/authentication.md) | Streaming auth (0x4C) and memory access (0x44) |
| [AdcQueue Streaming](features/adcqueue.md) | High-rate power logging (up to 1000 SPS) |
| [Offline Logs](features/offline_logs.md) | Downloading device-stored measurement logs |
| [PD Analysis](features/pd_analysis.md) | USB Power Delivery capture and SQLite export |

### Firmware Reverse Engineering

| Document | Description |
|----------|-------------|
| [Firmware Index](firmware/README.md) | Overview of firmware documentation |
| [Firmware Overview](firmware/overview.md) | MCU identification, RTOS, charging protocols |
| [Firmware Format](firmware/format.md) | .mencrypt file decryption |
| [Device Handlers](firmware/handlers.md) | Ghidra analysis of device firmware command handlers |
| [Mtools.exe Analysis](firmware/mtools_analysis.md) | Ghidra analysis of official Windows application |

### Work in Progress

| Document | Description |
|----------|-------------|
| [Unknown Commands](research/unknown_commands.md) | Partially understood commands, bootloader protocol |
| [Transaction Correlation](research/transaction_correlation.md) | Bitmask/latency validation across captures |
| [Code Organization](research/code_organization_strategy.md) | Repo layout: production vs research vs experiments |
| [Research Notes](research/notes.md) | Ongoing investigation notes |

### Official Documentation

| Document | Description |
|----------|-------------|
| [KM002C&3C API Description.pdf](official/KM002C%263C%20API%20Description.pdf) | Vendor API documentation |
| [Protocol Trigger Instructions.pdf](official/KM003C_002C%20Protocol%20Trigger%20by%20Virtual%20Serial%20Port%20(Instructions).pdf) | Serial port trigger protocol |

---

## Quick Start

### Minimal ADC Reading

```python
# 1. Connect
send([0x02, tid, 0x00, 0x00])  # Connect
# 2. Request ADC
send([0x0C, tid, 0x02, 0x00])  # GetData, attr=0x0001
# 3. Parse 52-byte response (4B header + 4B ext header + 44B ADC data)
```

### Minimal AdcQueue Streaming

```python
# 1. Connect
send([0x02, tid, 0x00, 0x00])
# 2. Auth (required for streaming)
send([0x4C, tid, 0x00, 0x02] + bytes(32))
# 3. Start streaming at 50 SPS
send([0x0E, tid, 0x04, 0x00])
# 4. Poll for samples
send([0x0C, tid, 0x04, 0x00])  # GetData, attr=0x0002
# 5. Stop
send([0x0F, tid, 0x00, 0x00])
```

See [Protocol Reference](protocol_reference.md) for complete details.

---

## Related Projects

### Implementations

| Project | Language | Description |
|---------|----------|-------------|
| [km003c-rs](https://github.com/okhsunrog/km003c-rs) | Rust | Full-featured library with Python bindings |
| [chaseleif/km003c](https://github.com/chaseleif/km003c) | Python | Multi-interface analysis |
| [LongDirtyAnimAlf/km003c](https://github.com/LongDirtyAnimAlf/km003c) | Pascal | Datalogger implementation |
| [fqueze/usb-power-profiling](https://github.com/fqueze/usb-power-profiling) | JavaScript | WebUSB implementation |

### Linux Kernel

The `powerz` hwmon driver provides basic voltage/current monitoring:
- [drivers/hwmon/powerz.c](https://github.com/torvalds/linux/blob/master/drivers/hwmon/powerz.c)

---

## Document Conventions

- **Addresses** are in hex (e.g., `0x4C`)
- **Byte order** is little-endian unless noted
- **Sizes** are in bytes
- **Firmware addresses** use format `0x0004eaf0` (device) or `0x14006e9e0` (Mtools.exe)
- **Cross-references** link to the canonical location (no duplication)
