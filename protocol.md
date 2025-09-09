# POWER-Z KM003C USB Protocol Documentation

## Overview

This document provides comprehensive documentation of the ChargerLAB POWER-Z KM003C USB-C power analyzer protocol, based on extensive USB traffic analysis and reverse engineering. The KM003C implements a sophisticated dual-layer protocol using both high-level application commands and low-level USB bulk transfer handshaking.

## USB Device Identification

- **Vendor ID**: `0x5FC9`
- **Product ID**: `0x0063`
- **Interface**: USB HID with bulk transfer endpoints
- **Endpoints**:
  - **OUT**: `0x01` (host to device)
  - **IN**: `0x81` (device to host)

## Dataset Analysis Summary

**Multi-Session Traffic Analysis:**
- **Total packets across all sessions**: 11,514 USB packets
- **Capture sessions**: 7 distinct sessions (filter by `source_file` column)
- **Analysis approach**: Session-specific analysis (not aggregated)
- **Session examples**: `orig_adc_record.6`, `pd_capture_new.9`, `orig_with_pd.13`
- **Devices**: 4 (addresses 6, 9, 13, 16) across different sessions

**Important**: Each session represents a different use case or device configuration. Protocol analysis should be performed per session using `source_file` filtering to avoid mixing different operational contexts.

## USB Control Transfer Protocol

### Standard USB Enumeration

The KM003C follows standard USB enumeration procedures with comprehensive descriptor requests:

#### Device Descriptor Requests
- **Purpose**: Basic device identification
- **Pattern**: bmRequestType=0x80, bRequest=6, wValue=0x0100, wLength=18
- **Present on all devices**: 6 packets per device (3 Submit + 3 Complete)

#### Configuration Descriptor Requests
- **Purpose**: Interface and endpoint configuration
- **Pattern**: Two-stage request (short header + full descriptor)
  - Stage 1: wLength=9 (header only)
  - Stage 2: wLength=130 (full configuration)

#### String Descriptor Requests
- **Purpose**: Manufacturer, product, and serial number strings
- **High volume**: Up to 60 packets per device
- **Variable lengths**: wLength=4,255,258

#### Binary Object Store (BOS) Descriptors
- **Purpose**: USB 3.0+ capabilities (Device 16 only)
- **Pattern**: Two-stage request (header + full)

### Non-Standard Control Requests

#### Unknown Control Commands
- **Type 0x10** with attribute 0x0001 (length 0)
- **Type 0x11** with attribute 0x0000 (length 0)
- **GetData** with attribute 0x0011
- These may be proprietary configuration or status commands

## Application Layer Protocol

### Packet Structure

The KM003C uses a custom binary protocol with two main packet types:

#### Control Packets
Used for commands and simple responses.

```rust
struct CtrlHeader {
    packet_type: u8,    // Command type
    extend: bool,       // Extended packet flag
    id: u8,            // Transaction ID
    attribute: u16,    // Command attribute
}
```

#### Data Packets
Used for data transfer with extended headers for large payloads.

```rust
struct DataHeader {
    packet_type: u8,    // Data type
    extend: bool,       // Extended packet flag
    id: u8,            // Transaction ID
    obj_count_words: u8, // Object count
}

struct ExtendedHeader {
    attribute: u16,     // Data attribute
    next: bool,         // More data flag
    chunk: u8,          // Chunk number
    size: u16,          // Payload size
}
```

### Command Types

#### Control Commands
| Type | Attribute | Description |
|------|-----------|-------------|
| `GetData` | `Adc` | Request ADC data |
| `GetData` | `PdPacket` | Request PD data |

#### Data Responses
| Type | Attribute | Description |
|------|-----------|-------------|
| `PutData` | `Adc` | ADC measurement data |
| `PutData` | `PdPacket` | PD message data |

## USB Bulk Transfer Protocol

### Transfer Characteristics
- **Transfer Type**: 0x03 (USB Interrupt transfers)
- **Direction Balance**: ~50% Host→Device, ~50% Device→Host
- **Payload Distribution**: 49.7% of packets contain payload data

### Command Structure Analysis

#### Command Format
- **Primary command byte**: 0x0C (control/configuration)
- **Command length**: 4 bytes fixed
- **Parameter space**: 0x00-0xFF (256 possible values)
- **Examples**: `0c160200`, `0c4f0200`, `0c2e0200`

#### Response Patterns
- **ADC data responses**: 52 bytes with `41...` prefix
- **Status responses**: 20 bytes, 4 bytes
- **Large data blocks**: Up to 968 bytes (device-specific)

### Zero-Length Packet Protocol

#### Metadata-Based Control Channel

Empty bulk packets encode rich control information in USB metadata fields:

**URB Status Codes:**
| Status | Meaning | Count | Usage |
|--------|---------|-------|-------|
| -115   | EINPROGRESS | 102 | Device requesting data send permission |
| 0      | SUCCESS | 95 | Command acknowledged successfully |
| -2     | ENOENT | 2 | Operation cancelled/not found |

**Transfer Flags:**
| Flag | Meaning | Usage |
|------|---------|-------|
| 0x00000200 | URB_SHORT_NOT_OK | Strict length checking |
| 0x00000000 | Standard | Relaxed transfer requirements |

**Data Direction Flags:**
| Flag | Meaning | Direction |
|------|---------|-----------|
| `<` | Expecting incoming data | Device→Host Submit |
| `>` | Outgoing direction | Host→Device Complete |
| `\0` | No direction/neutral | Error states |

#### Protocol Handshaking Patterns

**Pattern 1: Data Request Handshake**
```
Device → Host: Empty Submit (Status=-115, Flag=0x200, Data=<)
"I have data to send, requesting permission"

Host response triggers actual data transfer
Device → Host: Complete with 52-byte ADC data
```

**Pattern 2: Command Acknowledgment**
```
Host → Device: Submit with 4-byte command (e.g., 0c160200)
Device → Host: Empty Complete (Status=0, Flag=0x000, Data=>)
"Command received and executed successfully"
```

**Pattern 3: Error Handling**
```
Device → Host: Empty Complete (Status=-2, Flag=0x000, Data=\0)
"Operation failed or cancelled"
```

### URB Transaction Analysis

#### Session-Specific Analysis Example (`orig_adc_record.6`)
- **420 total packets** in this session (210 Submit + 210 Complete)
- **62 unique URB IDs** for this specific session
- **Transaction complexity**:
  - Simple pairs (Submit→Complete): 19 URBs (31%)
  - Multi-packet streaming: 43 URBs (69%)

**Note**: URB patterns vary significantly between sessions. Always filter by `source_file` for meaningful analysis.

#### Performance Characteristics
- **Command latency**: 77-85 microseconds
- **ADC data collection**: ~200ms per reading
- **Transaction duration range**: 40μs to 453ms
- **Streaming throughput**: Up to 133 packets/second

### Streaming Protocol

#### Multi-Packet URB Transactions (Session: `orig_adc_record.6`)
- **Continuous data streaming**: Up to 32 packets per URB (URB ID: 46b45180)
- **Duration**: Up to 9.348 seconds per streaming transaction
- **Purpose**: Efficient continuous ADC data collection for this session's use case
- **Session-specific**: Pattern varies significantly between different capture sessions
- **URB reuse**: Optimizes bandwidth for high-frequency sampling

## Data Formats

### ADC Data Structure

ADC data is transmitted as a 32-byte structure:

```rust
#[repr(C)]
struct AdcDataRaw {
    vbus_uv: i32,              // VBUS voltage in microvolts
    ibus_ua: i32,              // IBUS current in microamps
    vbus_avg_uv: i32,          // Average VBUS voltage
    ibus_avg_ua: i32,          // Average IBUS current
    vbus_ori_avg_raw: i32,     // Uncalibrated VBUS average
    ibus_ori_avg_raw: i32,     // Uncalibrated IBUS average
    temp_raw: i16,             // Temperature (Celsius * 100)
    vcc1_tenth_mv: u16,        // CC1 voltage (0.1mV)
    vcc2_raw: u16,             // CC2 voltage (0.1mV)
    vdp_mv: u16,               // D+ voltage (0.1mV)
    vdm_mv: u16,               // D- voltage (0.1mV)
    internal_vdd_raw: u16,     // Internal VDD (0.1mV)
    rate_raw: u8,              // Sample rate index
    reserved: u8,              // Reserved/padding
    vcc2_avg_raw: u16,         // Average CC2 voltage
    vdp_avg_mv: u16,           // Average D+ voltage
    vdm_avg_mv: u16,           // Average D- voltage
}
```

### Sample Rates

| Index | Rate | Description |
|-------|------|-------------|
| 0 | 1 SPS | 1 sample per second |
| 1 | 10 SPS | 10 samples per second |
| 2 | 50 SPS | 50 samples per second |
| 3 | 1000 SPS | 1k samples per second |
| 4 | 10000 SPS | 10k samples per second |

### Temperature Conversion

Temperature uses the INA228/9 formula:
```
LSB = 7.8125 m°C = 1000/128
Temperature = ((high_byte * 2000 + low_byte * 1000/128) / 1000)
```

### PD Data Format

PD data contains an "inner event stream" with three packet types:

#### Connection Events (6 bytes)
```rust
#[repr(C, packed)]
struct ConnectionEvent {
    type_id: u8,              // Always 0x45
    timestamp_bytes: [u8; 3], // 24-bit little-endian timestamp
    _reserved: u8,
    event_data: u8,           // CC pin (bits 7-4) + action (bits 3-0)
}
```

#### Status Packets (12 bytes)
```rust
#[repr(C, packed)]
struct StatusPacket {
    type_id: u8,              // Any value except 0x45, 0x80-0x9F
    timestamp_bytes: [u8; 3], // 24-bit little-endian timestamp
    vbus_raw: u16,            // VBUS voltage (raw)
    ibus_raw: u16,            // IBUS current (raw)
    cc1_raw: u16,             // CC1 voltage (raw)
    cc2_raw: u16,             // CC2 voltage (raw)
}
```

#### Wrapped PD Messages (Variable length)
```rust
struct WrappedPdMessage {
    is_src_to_snk: bool,      // Message direction
    timestamp: u32,           // 24-bit timestamp
    pd_bytes: Bytes,          // Standard USB PD message
}
```

PD messages are wrapped with a 6-byte header:
- Byte 0: Type ID (0x80-0x9F) + direction bit
- Bytes 1-3: 24-bit timestamp
- Bytes 4-5: Reserved
- Bytes 6+: Standard USB PD message

## Device-Specific Behavior

### Device Performance Profiles

| Device | Packets | Rate (pps) | Avg Payload | Primary Use Case |
|--------|---------|------------|-------------|------------------|
| 6      | 2,152   | 133.1      | 97.2b       | High-frequency ADC sampling |
| 13     | 2,030   | 66.0       | 8.7b        | Fast command-response |
| 16     | 248     | 44.0       | 12.4b       | Low-volume monitoring |
| 9      | 6,924   | 23.4       | 12.6b       | PD protocol analysis |

### Payload Size Patterns

**Device 6** (High-throughput):
- Commands: 4 bytes (528 packets)
- Standard responses: 52 bytes (190 packets)
- Large data blocks: 808 bytes (127 packets)

**Device 9** (Balanced):
- Commands: 4 bytes (1,733 packets)
- ADC responses: 52 bytes (1,401 packets)
- Status responses: 20 bytes (305 packets)

## Communication Flow

### ADC Data Request Flow
1. Host sends: `GetData` command with `Adc` attribute (4 bytes)
2. Device acknowledges: Zero-length Complete (Status=0)
3. Device requests: Zero-length Submit (Status=-115)
4. Device responds: `PutData` with `Adc` containing 52-byte ADC data

### PD Data Request Flow
1. Host sends: `GetData` command with `PdPacket` attribute
2. Device responds: `PutData` with `PdPacket` attribute containing event stream
3. Streaming continues with multi-packet URB transactions

### Transaction Management
- Each request gets a unique transaction ID (0-255, wrapping)
- Responses include the same transaction ID for correlation
- URB IDs enable Submit/Complete packet correlation
- Timeout: 2 seconds for all operations

## Protocol Engineering Insights

### Design Excellence
The KM003C demonstrates sophisticated USB protocol engineering:

1. **Dual-Layer Architecture**: Application commands + USB bulk handshaking
2. **Efficient Bandwidth Usage**: Zero-length packets for control signaling
3. **Rich Metadata Channel**: USB status codes carry protocol state information
4. **Streaming Optimization**: Multi-packet URB transactions for continuous data
5. **Robust Error Handling**: Multiple error states and recovery mechanisms

### Performance Characteristics
- **Ultra-low latency**: 77-85 microsecond command responses
- **High throughput**: Up to 133 packets/second sustained
- **Efficient protocol overhead**: ~50% control packets (optimal for real-time)
- **Scalable streaming**: Multi-packet URBs handle continuous data efficiently

## Error Handling

The device implements comprehensive error handling:
- Automatic retry logic at USB level
- Protocol-level error codes in URB status
- Timeout handling (2 seconds)
- Graceful degradation on communication failures
- Error counting with maximum retry limits

## Reverse Engineering Methodology

### Tools Used
- **Wireshark + usbmon**: USB traffic capture and analysis
- **Ghidra**: Firmware and application reverse engineering
- **Custom Rust tools**: Packet analysis and protocol correlation
- **Polars**: Large-scale data analysis of 11,514+ packets

### Key Discoveries
- Zero-length packets carry rich control information in USB metadata
- URB status codes implement a sophisticated handshaking protocol
- Multi-packet URB transactions enable efficient streaming
- Protocol uses dual-layer design (application + USB bulk)
- **Session-specific behavior**: Each capture session shows different protocol usage patterns
- Device-specific performance optimization strategies vary by use case

### Analysis Limitations
- Some device configuration commands remain unknown
- Firmware update protocol not analyzed
- Advanced measurement modes may use undocumented packet types
- Some proprietary features require additional reverse engineering

## References

- [USB Power Delivery Specification](https://www.usb.org/document-library/usb-power-delivery)
- [INA228 Datasheet](https://www.ti.com/lit/ds/symlink/ina228.pdf)
- [POWER-Z KM003C Product Page](https://www.power-z.com/products/262)
- [USB 2.0 Specification](https://www.usb.org/document-library/usb-20-specification)
- [Linux USB Monitoring (usbmon)](https://www.kernel.org/doc/html/latest/usb/usbmon.html)

---
*Protocol documentation based on comprehensive analysis of 11,514 USB packets*
*Reverse engineered through traffic analysis, firmware examination, and protocol correlation*
