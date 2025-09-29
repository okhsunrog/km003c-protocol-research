# ChargerLAB POWER-Z KM003C: Complete Protocol Documentation

## Document Overview

This document provides the definitive, comprehensive protocol specification for the **ChargerLAB POWER-Z KM003C** USB-C power analyzer. It consolidates reverse engineering findings from multiple sources, official documentation, and community implementations to present a complete understanding of the device's communication protocol.

## Table of Contents

1. [Device Identification](#device-identification)
2. [Official Documentation Sources](#official-documentation-sources)
3. [Community Implementations](#community-implementations)
4. [USB Protocol Fundamentals](#usb-protocol-fundamentals)
5. [Device Enumeration and Control Protocol](#device-enumeration-and-control-protocol)
6. [Application Layer Protocol](#application-layer-protocol)
7. [USB Bulk Transfer Protocol](#usb-bulk-transfer-protocol)
8. [Data Formats and Structures](#data-formats-and-structures)
9. [Power Delivery (PD) Protocol Support](#power-delivery-pd-protocol-support)
10. [Communication Patterns](#communication-patterns)
11. [Implementation Examples](#implementation-examples)
12. [Protocol Analysis Findings](#protocol-analysis-findings)
13. [References and Attribution](#references-and-attribution)

---

## Device Identification

### USB Device Properties
- **Vendor ID**: `0x5FC9` (ChargerLAB)
- **Product ID**: `0x0063` (KM003C model)
- **Device Version**: `1.00` (bcdDevice)
- **USB Version**: `2.10` (USB 2.1 compliant)
- **Serial Number**: `007965` (example device)
- **Device Class**: `0xEF` (Miscellaneous Device)
- **Device SubClass**: `0x02` (Interface Association)
- **Device Protocol**: `0x01` (Interface Association)
- **Max Packet Size**: `32 bytes` (EP0)
- **Power Requirements**: `100mA` (Bus powered)
- **Speed**: `12 Mbps` (Full Speed)

### Complete Interface Configuration

The KM003C implements **4 distinct USB interfaces** with different capabilities:

#### Interface 0: Vendor Specific (Primary Protocol)
- **Interface Class**: `0xFF` (Vendor Specific)
- **Driver**: `powerz` (Linux kernel hwmon driver)
- **Function**: Main ADC and PD protocol communication
- **Endpoints**:
  - `0x01 OUT`: Bulk, 64 bytes max packet, 0ms interval
  - `0x81 IN`: Bulk, 64 bytes max packet, 0ms interval

#### Interface 1: CDC Communications (Serial Interface)
- **Interface Class**: `0x02` (Communications)
- **Interface SubClass**: `0x02` (Abstract Control Model)
- **Driver**: `cdc_acm` (CDC ACM serial driver)
- **Function**: Serial command interface
- **Endpoints**:
  - `0x83 IN`: Interrupt, 8 bytes max packet, 10ms interval

#### Interface 2: CDC Data (Serial Data)
- **Interface Class**: `0x0A` (CDC Data)
- **Driver**: `cdc_acm` (paired with Interface 1)
- **Function**: Serial data transfer
- **Endpoints**:
  - `0x02 OUT`: Bulk, 64 bytes max packet, 0ms interval
  - `0x82 IN`: Bulk, 64 bytes max packet, 0ms interval

#### Interface 3: Human Interface Device
- **Interface Class**: `0x03` (HID)
- **HID Version**: `1.11`
- **Driver**: `usbhid` (Generic HID driver)
- **Function**: HID-based data interface (alternative access method)
- **Endpoints**:
  - `0x05 OUT`: Interrupt, 64 bytes max packet, 1ms interval
  - `0x85 IN`: Interrupt, 64 bytes max packet, 1ms interval

### USB Descriptor Hierarchy

```
Device Descriptor (18 bytes)
└── Configuration Descriptor (130 bytes total)
    ├── Interface 0 (Vendor Specific - powerz driver)
    │   ├── Endpoint 0x01 OUT (Bulk)
    │   └── Endpoint 0x81 IN (Bulk)
    ├── Interface Association Descriptor (CDC)
    ├── Interface 1 (CDC Communications)
    │   ├── CDC Header Descriptor (v1.10)
    │   ├── CDC Call Management Descriptor
    │   ├── CDC ACM Descriptor
    │   ├── CDC Union Descriptor
    │   └── Endpoint 0x83 IN (Interrupt)
    ├── Interface 2 (CDC Data)
    │   ├── Endpoint 0x02 OUT (Bulk)
    │   └── Endpoint 0x82 IN (Bulk)
    └── Interface 3 (HID)
        ├── HID Descriptor (9 bytes, v1.11)
        ├── Endpoint 0x05 OUT (Interrupt)
        └── Endpoint 0x85 IN (Interrupt)
```

### Binary Object Store (BOS) Descriptor

The device includes a BOS descriptor with Platform Device Capability:
- **UUID**: `{d8dd60df-4589-4cc7-9cd2-659d9e648a9f}`
- **Capability Data**: `00 00 03 06 aa 00 20 00`
- **Purpose**: Likely USB-C specific capabilities or vendor extensions

### Device Family
The KM003C is part of the POWER-Z family of USB-C analyzers:
- **KM002C**: Product ID `0x0061` (earlier model)
- **KM003C**: Product ID `0x0063` (current focus)

### Linux System Integration

**USB Topology**: Bus 1, Port 1.3, Device 21
**Kernel Drivers**:
- `powerz`: Interface 0 (hwmon driver for voltage/current monitoring)
- `cdc_acm`: Interfaces 1&2 (serial communication)
- `usbhid`: Interface 3 (HID generic driver)

**System Paths**:
- `/sys/bus/usb/devices/1-1.3/` - Device sysfs directory
- `/dev/ttyACM*` - CDC ACM serial devices
- `/sys/class/hwmon/hwmonX/` - Hardware monitoring interface

---

## Official Documentation Sources

### ChargerLAB Documentation
Located in `docs/` directory:

#### Primary Sources
1. **KM003C_002C Protocol Trigger by Virtual Serial Port (Instructions).pdf**
   - Official protocol documentation from ChargerLAB
   - Covers serial port trigger protocol
   - Available in both PDF and DOCX formats

2. **KM002C&3C API Description.pdf**
   - Comprehensive API documentation for both KM002C and KM003C
   - Includes data structures and communication protocols
   - Available in both PDF and DOCX formats

#### Key Official Specifications
Based on official documentation, the device provides:
- ADC measurements with multiple sample rates (1, 10, 50, 1000, 10000 SPS)
- USB Power Delivery protocol analysis capabilities
- Real-time voltage, current, power, and temperature monitoring
- CC pin voltage monitoring for USB-C connection analysis

---

## Community Implementations

### 1. Python Implementation (chaseleif/km003c)
**Repository**: https://github.com/chaseleif/km003c

**Key Findings**:
- Uses PyUSB for device communication
- Identifies multiple USB interfaces with different sampling rates:
  - **Interface 0**: Vendor Specific (bulk 0x01/0x81) — primary protocol interface
  - **Interface 2**: CDC Data (bulk 0x02/0x82) — serial data interface
  - **Interface 3**: HID (interrupt 0x05/0x85) — alternative access path
- 64-byte data buffer structure with dual 4-byte headers
- Handles signed 32-bit integers for measurements
- Motivation: "Looking for a power meter that didn't need Windows"

**Real Device Verification**: The connected device confirms 4 interfaces (0-3), with Interface 3 being HID (as mentioned in the implementation) and Interface 2 being CDC Data.

**Protocol Insights (bulk interface)**:
```python
# Data parsing example from community implementation
data_buffer = 64  # bytes
headers = 2 * 4   # bytes (dual 4-byte headers)
measurements = {
    'vbus': signed_32bit,
    'ibus': signed_32bit,
    'vbus_avg': signed_32bit,
    'ibus_avg': signed_32bit,
    'temperature': calculated,
    'vcc1': auxiliary_voltage,
    'vcc2': auxiliary_voltage,
    'vdp': auxiliary_voltage,
    'vdm': auxiliary_voltage,
    'vdd': auxiliary_voltage
}
```

### 2. Pascal Implementation (LongDirtyAnimAlf/km003c)
**Repository**: https://github.com/LongDirtyAnimAlf/km003c

**Key Findings**:
- Cross-platform datalogger implementation (98.8% Pascal)
- Uses libusb for USB communication
- Requires platform-specific libusb installation
- Provides PC-based logging capabilities for KM003C

### 3. Linux Kernel Driver (drivers/hwmon/powerz.c)
**Repository**: Linux kernel mainline

**Key Protocol Details**:
```c
// Official kernel driver protocol
#define POWERZ_EP_CMD_OUT    0x01
#define POWERZ_EP_DATA_IN    0x81
#define POWERZ_CMD_SIZE      4
#define POWERZ_DATA_SIZE     64

// Command sequence to trigger data read
static const u8 cmd_trigger[] = {0x0c, 0x00, 0x02, 0x00};

// Data structure from kernel driver
struct powerz_sensor_data {
    __le32 bus_voltage;      // V_bus
    __le32 bus_current;      // I_bus  
    __le32 bus_voltage_avg;  // Average V_bus
    __le32 bus_current_avg;  // Average I_bus
    // Additional measurements...
    __le16 temperature[2];   // Temperature sensors
    __le16 vcc1, vcc2;       // CC pin voltages
    __le16 vdp, vdm;         // Data line voltages
    __le16 vdd;              // Internal voltage
};
```

**Scaling Factors**:
- Current measurements: Divide by 1000 (µA → mA)
- Bus voltage: Divide by 1000 (µV → mV)
- Auxiliary voltages (instantaneous CC1/CC2, D+, D-, VDD): 0.1 mV units (divide by 10 for mV, 10,000 for V)
- Averaged auxiliary voltages (CC2_avg, D+_avg, D-_avg): 1.0 mV units (divide by 1 for mV, 1,000 for V)
- Temperature: Two-byte calculation (see Temperature Conversion)

### 4. JavaScript Implementation (fqueze/usb-power-profiling)
**Repository**: https://github.com/fqueze/usb-power-profiling

**Key Features**:
- Node.js implementation for USB power profiling
- Sampling interval: 1ms
- HTTP API server on `localhost:2121`
- Firefox Profiler integration for power visualization
- WinUSB driver requirement on Windows
- Characteristic: "Sampling driven by the computer"

---

## USB Protocol Fundamentals

### USB Transaction Structure
Every USB transaction consists of three phases:
1. **Token Packet**: Defines transaction type and target
2. **Data Packet**: Contains payload (optional)
3. **Handshake Packet**: Acknowledgment and error correction

### Transfer Types
The KM003C uses **Bulk Transfers** for its primary vendor-specific protocol (Interface 0). The HID interface (Interface 3) uses **Interrupt Transfers**:
- Bulk: large data transfers with error correction; CRC16 with retransmission; uses spare bandwidth; up to 64 bytes at full-speed USB.
- Interrupt (HID): periodic polling with guaranteed service interval; 64-byte reports.

### Host-Centric Protocol
- Only the host (computer) initiates transactions
- Device responds to host requests
- No device-initiated interrupts
- Polling-based data acquisition

---

## Device Enumeration and Control Protocol

### Standard USB Enumeration

The KM003C follows standard USB enumeration with comprehensive descriptor requests:

#### Device Descriptor Pattern
```
bmRequestType: 0x80 (Device-to-Host)
bRequest: 0x06 (GET_DESCRIPTOR)  
wValue: 0x0100 (Device Descriptor)
wLength: 18 bytes
```

#### Configuration Descriptor Pattern
Two-stage request for complete configuration:
1. **Header Request**: wLength=9 (basic info)
2. **Full Request**: wLength=130 (complete configuration)

#### String Descriptor Requests
High-volume requests for device identification:
- Manufacturer, Product, Serial Number strings
- Multiple language support (Language ID in wIndex)
- Variable lengths: 4, 255, 258 bytes

### Multi-Stage Initialization (VM Environment)

When used in virtualized environments, a three-stage initialization occurs:

1. **Physical Connection (Host OS)**
   - Basic USB enumeration by host OS
   - Generic drivers loaded (`cdc_acm`, `hid-generic`)
   - Standard descriptors requested

2. **VM Redirection (Guest OS)**
   - Device redirected to virtual machine
   - Guest OS performs thorough enumeration
   - **Critical**: Proprietary commands sent by official driver
   - Custom command `bRequest=0x32` with `bmRequestType=0xC2`

3. **Application Startup**
   - Official software opens device
   - Additional descriptor verification
   - Main communication loop begins

### Proprietary Control Commands

#### Vendor-Specific Request (0x32)
```c
// Critical proprietary command during enumeration
struct vendor_request {
    .bmRequestType = 0xC2,  // Vendor-specific, Device-to-Host
    .bRequest = 0x32,       // Proprietary command
    .wValue = 0x0000,
    .wIndex = 0x0000,
    .wLength = 170          // Device returns 170 bytes
};
```

**Purpose**: Likely device capability query or calibration data retrieval

#### Unknown Control Commands
Additional proprietary commands discovered:
- **Type 0x10** with attribute 0x0001 (zero length)
- **Type 0x11** with attribute 0x0000 (zero length)
- **GetData** with attribute 0x0011 (undocumented)

---

## Application Layer Protocol

### Packet Structure Overview

The KM003C implements a sophisticated dual-layer protocol:
1. **Low-level**: USB bulk transfer handshaking
2. **High-level**: Application command/response protocol

### Control Packet Format
```c
struct ctrl_header {
    uint8_t packet_type;    // Command type identifier
    bool extend_flag;       // Extended packet indicator
    uint8_t transaction_id; // Rolling transaction ID (0-255)
    uint16_t attribute;     // Command/response attribute
};
```

### Data Packet Format
**All PutData packets (type 0x41) have extended headers by design**:

```c
struct data_header {
    uint8_t packet_type;     // 0x41 (CMD_PUT_DATA)
    bool extend_flag;        // Purpose unclear (not size indicator)
    uint8_t transaction_id;  // Rolling ID (0-255)
    uint8_t object_count;    // Packet size / 4 words
};

struct extended_header {
    uint16_t attribute;      // Data type (ADC=1, PD=16, etc.)
    bool next_flag;          // Extension data present
    uint8_t chunk_number;    // Chunk ID (typically 0)
    uint16_t payload_size;   // Attribute-specific size
};
```

### Command Types

#### Control Commands
| Type | Hex | Attribute | Description |
|------|-----|-----------|-------------|
| GetData | 0x0C | 0x0001 (Adc) | Request ADC measurements |
| GetData | 0x0C | 0x0010 (PdPacket) | Request PD protocol data |
| Accept | 0x05 | 0x0000 | Acknowledge command |

#### Data Responses  
| Type | Hex | Attribute | Description |
|------|-----|-----------|-------------|
| PutData | 0x41 | 0x0001 (Adc) | ADC measurement data |
| PutData | 0x41 | 0x0010 (PdPacket) | PD protocol events |
| PutData | 0x41 | 0x0002 (AdcQueue) | Queued ADC data |
| PutData | 0x41 | 0x0008 (Settings) | Device configuration |

### Extended Header Usage by Attribute

| Attribute | Count | Size Field Meaning | Examples |
|-----------|-------|-------------------|----------|
| ATT_ADC (1) | 1,875 | Always 44 (base ADC size) | Standard/Extended variants |
| ATT_PdPacket (16) | 657 | Exact payload size | 12-108 bytes |
| ATT_AdcQueue (2) | 288 | Fixed 20 (header size) | 28-968 bytes payload |
| ATT_Settings (8) | 7 | Exact payload size | 180 bytes |

---

## USB Bulk Transfer Protocol

### Zero-Length Packet Protocol

The KM003C uses sophisticated zero-length packet (ZLP) signaling:

#### URB Status Codes
| Status | Meaning | Count | Usage Pattern |
|--------|---------|-------|---------------|
| -115 | EINPROGRESS | 102 | IN URB pending (host buffer posted) |
| 0 | SUCCESS | 95 | Command acknowledged |
| -2 | ENOENT | 2 | Operation cancelled/not found |

#### Transfer Flags
| Flag | Hex | Meaning |
|------|-----|---------|
| URB_SHORT_NOT_OK | 0x00000200 | Strict length validation |
| Standard | 0x00000000 | Relaxed requirements |

### Handshaking Patterns

#### Pattern 1: Data Request Handshake
```
1. Host→Device: submits IN URB (buffer posted) → urb_status = -115 (EINPROGRESS)
2. Device produces data
3. Device→Host: completion with actual data (e.g., 52+ bytes for ADC PutData)
```

#### Pattern 2: Command Acknowledgment
```
1. Host→Device: Submit with command (4 bytes)
2. Device→Host: Empty Complete (Status=0, "acknowledged")
```

#### Pattern 3: Error Signaling
```
Device→Host: Empty Complete (Status=-2, "operation failed")
```

### URB Transaction Management

#### Critical Understanding: URB ID Reuse
The `urb_id` field in USB monitoring tools (like Wireshark/usbmon) represents a **kernel memory address**, not a unique transaction identifier:

- **Memory Recycling**: Same address reused for new transactions
- **Analysis Impact**: Must group by Submit→Complete pairs, not URB ID
- **Transaction Definition**: One logical transaction = One S→C pair
- **Performance**: Rapid transaction cycling creates "streaming" illusion

#### Timing Characteristics
- **Command Latency**: 77-85 microseconds
- **ADC Polling**: ~200ms intervals  
- **PD Capture**: ~40ms when active
- **Maximum Throughput**: 133 packets/second sustained

---

## Data Formats and Structures

### Complete ADC Packet Structure

Based on official KM003C documentation and reverse engineering:

```c
// Complete ADC packet format (52-876 bytes total)
struct adc_packet {
    // Main header (4 bytes)
    struct {
        uint32_t type : 7;      // 65 (CMD_PUT_DATA)
        uint32_t extend : 1;    // Purpose unclear
        uint32_t id : 8;        // Transaction ID
        uint32_t reserved : 6;  // Unused
        uint32_t obj_count : 10; // Total size / 4
    } main_header;
    
    // Extended header (4 bytes) - Always present
    struct {
        uint32_t attribute : 15; // 1 (ATT_ADC)
        uint32_t next : 1;       // PD extension flag
        uint32_t chunk : 6;      // Always 0
        uint32_t size : 10;      // ADC payload size (44)
    } extended_header;
    
    // ADC data payload (44 bytes)
    struct adc_data {
        int32_t vbus;             // VBUS voltage (1µV units)
        int32_t ibus;             // IBUS current (1µA units)  
        int32_t vbus_avg;         // Averaged VBUS (1µV)
        int32_t ibus_avg;         // Averaged IBUS (1µA)
        int32_t vbus_ori_avg;     // Uncalibrated VBUS average
        int32_t ibus_ori_avg;     // Uncalibrated IBUS average
        int16_t temperature;      // Internal temperature (LSB = 1/128 °C)
        uint16_t vcc1_tenth_mv;   // CC1 voltage (0.1mV units)
        uint16_t vcc2_tenth_mv;   // CC2 voltage (0.1mV units)
        uint16_t vdp_tenth_mv;    // D+ voltage (0.1mV units)
        uint16_t vdm_tenth_mv;    // D- voltage (0.1mV units)
        uint16_t vdd_tenth_mv;    // Internal VDD (0.1mV units)
        uint8_t sample_rate:2;    // Sample rate index (0-4)
        uint8_t flags;            // Vendor flags (observed 128)
        uint16_t cc2_avg_mv;      // CC2 averaged voltage (1mV units)
        uint16_t vdp_avg_mv;      // D+ averaged voltage (1mV units)
        uint16_t vdm_avg_mv;      // D- averaged voltage (1mV units)
    } adc_data;
    
    // Optional PD extension (12-824 bytes)
    // Present when next=1 in extended header
    uint8_t pd_extension[];
};
```

### ADC Packet Size Variants

**Perfect 100% correlation between `next` bit and packet size**:

| next Bit | Packet Count | Total Size | Structure |
|----------|--------------|------------|-----------|
| next=0 | 1,823 | 52 bytes | 4B main + 4B ext + 44B ADC |
| next=1 | 52 | 68-876 bytes | Standard + Variable PD data |

### Sample Rate Mapping
```c
enum sample_rate {
    RATE_1_SPS = 0,     // 1 sample per second
    RATE_10_SPS = 1,    // 10 samples per second  
    RATE_50_SPS = 2,    // 50 samples per second
    RATE_1000_SPS = 3,  // 1000 samples per second
    RATE_10000_SPS = 4  // 10000 samples per second
};
```

### Temperature Conversion
Uses INA228/INA229 formula:
```c
float temperature_celsius(int16_t temp_raw) {
    uint8_t high = (temp_raw >> 8) & 0xFF;
    uint8_t low = temp_raw & 0xFF;
    
    // LSB = 7.8125 m°C = 1000/128
    return ((high * 2000.0) + (low * 1000.0/128.0)) / 1000.0;
}
```

### Current Direction and Power Flow
```c
// Current sign indicates power flow direction:
// Positive: USB female (input) → USB male (output)  
// Negative: USB male (input) → USB female (output)
float power_watts = (vbus_microvolts / 1000000.0) * (ibus_microamps / 1000000.0);
```

---

## Power Delivery (PD) Protocol Support

### PD Packet Types

The KM003C provides comprehensive USB Power Delivery analysis:

#### New Packet Types (PD Mode)
- **CmdGetPdData**: Host requests for PD protocol data
- **PdRawData**: Device responses containing PD events and messages

### PD Data (Consolidated)

KM003C PD data appears in two forms:

- PD Status block (12 bytes): measurement/status summary often chained after ADC (ADC+PD = 68 bytes total).
- PD Event stream (≥18 bytes): wrapped USB PD wire messages with a 12‑byte preamble followed by repeated 6‑byte event headers and PD wire payloads. Present in PD‑only responses and, rarely, as the PD segment within an ADC+PD.

#### PD Status (12 bytes)
Included with ADC+PD (most commonly 68‑byte total packets). Not a PD wire message.

| Offset | Size | Field         | Description |
|--------|------|---------------|-------------|
| 0      | 1    | type_id       | Event/status identifier |
| 1      | 3    | timestamp24   | 24‑bit little‑endian timestamp |
| 4      | 2    | vbus_raw_mV   | VBUS voltage (mV) |
| 6      | 2    | ibus_raw_mA   | IBUS current (mA) |
| 8      | 2    | cc1_raw_mV    | CC1 voltage (mV) |
| 10     | 2    | cc2_raw_mV    | CC2 voltage (mV) |

Correlation: vbus_raw_mV and ibus_raw_mA closely track ADC measurements near the same timestamp (median diffs ~0.3 mV and ~0.01 mA observed).

#### PD Event Stream (preamble + events)
Payload layout observed in PD‑only responses and in the rare 84‑byte ADC+PD case:

- Preamble: 12 bytes of device metadata. First 4 bytes are a 32‑bit little‑endian timestamp framing the following events. This preamble is not a measurement status.
- Events: repeated blocks with a 6‑byte header followed by PD wire bytes.

Preamble (12 bytes):
- 0..3: timestamp (uint32, little‑endian) framing the following events
- 4..5: vbus_mV (uint16)
- 6..7: ibus_mA (int16)
- 8..9: cc1_mV (uint16)
- 10..11: cc2_mV (uint16)

Event header format:
- size_flag: 1 byte
- timestamp: 4 bytes, little‑endian (32‑bit)
- sop: 1 byte (SOP type)

Wire length computation:
- wire_len = (size_flag & 0x3F) − 5
- Validated on all event‑bearing payloads; yields standard 2/6/26‑byte PD wire messages. PD‑only 18‑byte payloads contain preamble + empty header (no wire data).

Example (84‑byte ADC+PD with PD event stream of 28 bytes):
- PD payload (28 bytes): `22fb12008323eaff73060800870efb120000a607870ffb1200004106`
- Parsed as: preamble `22fb12008323eaff73060800`, then two events
  - size_flag=0x87 → wire_len=2, ts=0x00120EF7, SOP=0, wire=`a607` → PS_RDY
  - size_flag=0x87 → wire_len=2, ts=0x00120FF7, SOP=0, wire=`4106` → GoodCRC

Note on SQLite Raw: The per‑event 6‑byte headers and wire length encoding are the same in SQLite `pd_table.Raw` blobs. SQLite rows do not include the 12‑byte preamble found in USB PD‑only payloads; they may include separate 6‑byte connection/status events (type 0x45) documented in the SQLite section.

Connection/status (0x45) event codes:
- 0x11 → Connect (observed at the beginning of a capture)
- 0x12 → Disconnect (observed after the PD transfer sequence)

Observed preamble behavior:
- The 32‑bit preamble timestamp closely matches the first/last event timestamps in the same payload.
- vbus_mV/ibus_mA reflect live measurements similar to ADC readings (typical |ΔVBUS| < 12 mV, |ΔIBUS| < 75 mA when non‑zero). Attach/detach preambles may show 0/0.
- cc1_mV/cc2_mV track CC line voltages (e.g., ~1.65 V levels for CC presence), generally stable during a burst and changing around connect/disconnect.

### PD Status vs PD Preamble (12 bytes)

Where they appear:
- PD Status (12B): Chained after ADC in ADC+PD packets (commonly 68‑byte total).
- PD Preamble (12B): The first 12 bytes of PD‑only payloads >12B; also seen in the rare 84‑byte ADC+PD that embeds an event stream.

Side‑by‑side field layout (little‑endian):

| Field | PD Status (ADC+PD 68B) | PD Preamble (PD‑only/evented) | Notes |
|------|-------------------------|-------------------------------|-------|
| Lead | [0] type_id (1B) | none | Status has type byte; preamble does not |
| Timestamp | [1..3] timestamp24 (3B) | [0..3] timestamp32 (4B) | Preamble’s 32‑bit ts frames the following events |
| VBUS | [4..5] vbus_mV (u16) | [4..5] vbus_mV (u16) | Both correlate with ADC |
| IBUS | [6..7] ibus_mA (u16, observed ≥0) | [6..7] ibus_mA (i16, signed) | Preamble shows small negatives (e.g., −72 mA) |
| CC1 | [8..9] cc1_mV (u16) | [8..9] cc1_mV (u16) | Tracks CC presence/level |
| CC2 | [10..11] cc2_mV (u16) | [10..11] cc2_mV (u16) | Tracks CC presence/level |

Behavior and usage:
- PD Status: Self‑contained measurement snapshot appended to ADC; not followed by PD event headers in the common 68B packets.
- PD Preamble: Measurement snapshot that precedes a wrapped event stream; immediately followed by repeated 6‑byte event headers + PD wire data.
- Connect/disconnect markers are separate 6‑byte `0x45 …` events after the preamble (0x11 = Connect at start, 0x12 = Disconnect at end).
- Neither block encodes PD message direction; direction comes from PD wire headers (decoded roles: Source/Sink, Dfp/Ufp).

### Dual Mode Operation

During PD analysis, the KM003C operates in dual mode:

1. **Continuous ADC Polling**: ~200ms intervals (maintains normal rate)
2. **PD Event Capture**: ~40ms intervals when PD activity detected

This allows simultaneous power monitoring and protocol analysis.

---

## Communication Patterns

### ADC Data Request Flow
```
1. Host → Device: GetData command (4 bytes, attribute=Adc)
   Payload: [0x0C, 0x01, 0x02, 0x00]
   
2. Device → Host: ZLP Complete (Status=0, acknowledged)

3. Device → Host: ZLP Submit (Status=-115, requesting permission)

4. Device → Host: PutData with ADC (52+ bytes)
   Structure: [main_header][extended_header][adc_data][optional_pd]
```

### PD Data Request Flow  
```
1. Host → Device: GetData command (4 bytes, attribute=PdPacket)
   Payload: [0x0C, 0x10, 0x02, 0x00]
   
2. Device → Host: PutData with PD events
   Structure: [main_header][extended_header][pd_event_stream]
   
3. Multi-packet streaming for large PD captures
```

### Transaction Management
- **Transaction ID**: 8-bit rolling counter (0-255, wraps)
- **Correlation**: Use application-layer transaction ID, not URB ID
- **Timeout**: 2 seconds for all operations
- **Error Recovery**: Automatic retry at USB level

---

## KM003C Application‑Layer Protocol (Consolidated)

This section consolidates the working protocol details for application‑layer messages observed over the vendor bulk interface.

### Message Structure

All application messages follow: `[Main Header (4B)] [Extended Header (4B)] [Payload]`.

Main Header (4 bytes, little‑endian, bit‑fields):
- bits 0..6: `type` (0x0C=GetData, 0x41=PutData)
- bit 7: `extend` (extended header flag)
- bits 8..15: `id` (rolling counter 0..255)
- bits 16..21: reserved
- bits 22..31: `obj_count` (approx total_length/4 − 3)

Extended Header (4 bytes, little‑endian):
- bits 0..14: `attribute` (1=ADC, 16=PD)
- bit 15: `next` (1=another payload follows in this message)
- bits 16..21: `chunk` (0 for these cases)
- bits 22..31: `size_bytes` (payload size for this segment)

Chained payloads: If `next=1`, read the next 4‑byte extended header and its payload immediately after the previous payload.

### Requests and Responses

Host GetData requests (examples):
- `0C [id] 02 00` → ADC only → device PutData with 52‑byte total (44B ADC)
- `0C [id] 22 00` → ADC+PD → device PutData with 68‑byte total (44B ADC + 12B PD status)
- `0C [id] 20 00` → PD only → device PutData with 20+ byte PD payload (status or event stream)

IDs increment modulo 256; response `id` matches the request.

### ADC Payload (44 bytes)

Offsets and fields (little‑endian):
- 0: vbus_uV (int32)
- 4: ibus_uA (int32)
- 8: vbus_avg_uV (int32)
- 12: ibus_avg_uA (int32)
- 16: vbus_ori_avg_uV (int32)
- 20: ibus_ori_avg_uA (int32)
- 24: temp_raw (int16)
- 26: vcc1_tenth_mV (uint16)
- 28: vcc2_tenth_mV (uint16)
- 30: vdp_tenth_mV (uint16)
- 32: vdm_tenth_mV (uint16)
- 34: vdd_tenth_mV (uint16)
- 36: sample_rate_idx (uint8)
- 37: flags (uint8)
- 38: cc2_avg_mV (uint16)
- 40: vdp_avg_mV (uint16)
- 42: vdm_avg_mV (uint16)

### PD Payloads

- PD Status (12B): measurement/status block as described above. Common in ADC+PD 68‑byte total messages; correlates with ADC values.
- PD Event Stream (≥18B): preamble (12B) + repeated events (6B header + wire_len bytes). `wire_len = (size_flag & 0x3F) − 5`.

### Observed Sizes (dataset)

- ADC‑only: total=52 bytes
- ADC+PD: total=68 bytes (PD size=12) common; one instance total=84 bytes (PD size=28, event stream)
- PD‑only payload sizes: 12, 18, 28, 44, 76, 88, 108 bytes
  - 12B = status block (not PD wire)
  - 18B = preamble + empty header (no PD message)
  - ≥28B = event stream containing 1+ PD wire messages

### PD Status vs Preamble (Verified)

- PD Status (12B): includes 24‑bit timestamp and measured VBUS/IBUS/CC values; tracks ADC measurements.
- PD‑only preamble (first 12B of PD‑only payloads >12B): includes a 32‑bit timestamp (first 4 bytes) and metadata; not measurements. Parsing it as status yields unrealistic currents/voltages; do not treat it as PD status.

### Control (Mode) Commands

- Enable PD monitoring: request `10 [id] 02 00` → response `05 [id] 00 00` (accept)
- Disable PD monitoring: request `11 [id] 00 00` → response `05 [id] 00 00`

### Object Count Calculation

Empirical relation: `obj_count ≈ (total_message_length / 4) − 3` for standard single‑segment messages; adjust when chained segments are present.

---

## Implementation Examples

### Linux Kernel Driver Usage
```c
// From drivers/hwmon/powerz.c
static int powerz_get_data(struct powerz_data *data) {
    static const u8 cmd[] = {0x0c, 0x00, 0x02, 0x00};
    int ret;
    
    // Send trigger command
    ret = usb_bulk_msg(data->udev, 
                      usb_sndbulkpipe(data->udev, POWERZ_EP_CMD_OUT),
                      (void *)cmd, sizeof(cmd), NULL, 1000);
    if (ret < 0) return ret;
    
    // Read response  
    ret = usb_bulk_msg(data->udev,
                      usb_rcvbulkpipe(data->udev, POWERZ_EP_DATA_IN), 
                      data->buffer, POWERZ_DATA_SIZE, NULL, 1000);
    
    return ret;
}
```

### Python Implementation Pattern
```python
# Based on chaseleif/km003c approach
import usb.core
import struct

def read_km003c_data():
    # Find device
    dev = usb.core.find(idVendor=0x5FC9, idProduct=0x0063)
    
    # Use Interface 1 (HID, 500 SPS)
    interface = 1
    
    # Read 64-byte buffer
    data = dev.read(0x81, 64)
    
    # Parse headers (2 x 4 bytes)
    header1, header2 = struct.unpack('<II', data[:8])
    
    # Parse measurements (signed 32-bit)
    measurements = struct.unpack('<iiiiii', data[8:32])
    vbus, ibus, vbus_avg, ibus_avg, temp_raw, aux = measurements
    
    return {
        'voltage': vbus / 1000.0,    # µV to mV
        'current': ibus / 1000.0,    # µA to mA  
        'power': (vbus * ibus) / 1e12  # Watts
    }
```

### JavaScript WebUSB Pattern
```javascript
// Based on fqueze/usb-power-profiling
class KM003CDevice {
    constructor() {
        this.device = null;
        this.samplingInterval = 1; // ms
    }
    
    async connect() {
        this.device = await navigator.usb.requestDevice({
            filters: [{ vendorId: 0x5FC9, productId: 0x0063 }]
        });
        
        await this.device.open();
        await this.device.selectConfiguration(1);
        await this.device.claimInterface(0);
    }
    
    async readData() {
        const result = await this.device.transferIn(0x81, 64);
        return new DataView(result.data.buffer);
    }
}
```

---

## Protocol Analysis Findings

### Dataset Analysis Summary
**Multi-session traffic analysis of 11,514+ USB packets across 7 capture sessions:**

| Session | Duration | Packets | Primary Mode | Key Discoveries |
|---------|----------|---------|--------------|-----------------|
| orig_adc_record.6 | 16.2s | 2,152 | ADC only | High-frequency sampling (133 pps) |
| pd_capture_new.9 | 295.6s | 6,930 | Mixed ADC+PD | Dual-mode operation |
| orig_with_pd.13 | 42.1s | 2,056 | PD analysis | New packet types discovered |
| orig_open_close.16 | 5.6s | 248 | ADC monitoring | Low-volume testing |

### Protocol Coverage Analysis

**Known Packet Types (100% parsed)**:
- **Head (64)**: Initialization packets
- **PutData (65)**: Main data responses with extended headers
- **GetData, Connect, Sync**: Standard control commands
- **Accept**: Command acknowledgments

**Known Attributes**:
- **Adc (1)**: ADC measurement data
- **AdcQueue (2)**: Queued ADC measurements  
- **Settings (8)**: Device configuration
- **PdPacket (16)**: USB Power Delivery messages

**Unknown Elements** (discovered through analysis):
- **Control packet types**: Unknown26, Unknown44, Unknown58
- **Data packet types**: Unknown68, Unknown76, Unknown117
- **Attributes**: Unknown512, Unknown1609, Unknown11046, Unknown26817

**Parsing Success Rate**: 100% (2,934/2,934 bulk frames parsed successfully)

### Performance Characteristics

#### Device Performance Profiles
| Device Addr | Packets | Rate (pps) | Avg Payload | Use Case |
|-------------|---------|------------|-------------|----------|
| 6 | 2,152 | 133.1 | 97.2 bytes | High-frequency ADC |
| 13 | 2,030 | 66.0 | 8.7 bytes | Fast command-response |
| 16 | 248 | 44.0 | 12.4 bytes | Low-volume monitoring |
| 9 | 6,924 | 23.4 | 12.6 bytes | PD protocol analysis |

#### Latency Analysis
- **Ultra-low command latency**: 77-85 microseconds
- **ADC collection interval**: ~200ms per reading
- **PD event capture**: ~40ms when active
- **Transaction duration range**: 40µs to 453ms
- **Sustained throughput**: Up to 133 packets/second

---

## Troubleshooting and Edge Cases

### Common Implementation Issues

#### URB ID Misinterpretation
**Problem**: Grouping packets by `urb_id` thinking it's a unique transaction identifier
**Solution**: Use Submit→Complete pairs for transaction boundaries
**Impact**: Incorrect protocol flow analysis

#### Missing Extended Headers
**Problem**: Not recognizing that all PutData packets have extended headers
**Solution**: Always parse 4-byte extended header after main header for type 0x41
**Impact**: Data structure parsing failures

#### Current Direction Confusion
**Problem**: Misinterpreting negative current values
**Solution**: Negative current indicates reverse power flow (male→female)
**Impact**: Incorrect power flow direction analysis

### Edge Case Handling

#### Large PD Captures
- **Issue**: PD extension data can reach 824 bytes
- **Solution**: Dynamic buffer allocation based on `next` flag and size field
- **Validation**: Check total packet size against extended header size field

#### Sample Rate Changes
- **Issue**: Device can change sample rates dynamically  
- **Solution**: Parse sample rate field in each ADC packet
- **Impact**: Timing analysis must account for rate variations

#### Multi-Interface Support
- **Issue**: Device has multiple USB interfaces with different capabilities
- **Solution**: Test each interface to determine optimal sampling rate
- **Recommendation**: Interface 3 (HID) for compatibility, Interface 0 for primary bulk protocol

---

## References and Attribution

### Original Research
This comprehensive documentation is based on extensive reverse engineering research documented at:
**[km003c-protocol-research](https://github.com/okhsunrog/km003c-protocol-research)**

### Related Projects and Implementations

#### Rust Implementation
- **[km003c-rs](https://github.com/okhsunrog/km003c-rs)** - Complete Rust library and applications for KM003C
  - Cross-platform USB HID communication
  - Real-time ADC data acquisition
  - USB Power Delivery message capture
  - GUI application with live plotting
  - Python bindings via PyO3/maturin

#### USB PD Protocol Libraries
- **[usbpdpy](https://github.com/okhsunrog/usbpdpy)** - Python bindings for USB PD message parsing
- **[usbpd](https://crates.io/crates/usbpd)** - Rust USB PD protocol parsing library

#### Analysis and Visualization Tools
- **[Firefox Profiler](https://profiler.firefox.com/)** - Power consumption visualization (works with fqueze/usb-power-profiling)
- **[sigrok/PulseView](https://sigrok.org/wiki/PulseView)** - Logic analyzer software (can work with USB captures)

#### Commercial Software
- **[ChargerLAB Power-Z Official Software](https://www.power-z.com/software)** - Official Windows application
- **[KMbox/PC Computer Suite](https://www.power-z.com/)** - Official software suite for POWER-Z devices

#### Hardware Alternatives and Related Devices
- **[Nordic Power Profiler Kit II (PPK2)](https://www.nordicsemi.com/Products/Development-hardware/Power-Profiler-Kit-2)** - Nordic's power profiling solution
- **[Joulescope](https://www.joulescope.com/)** - Precision DC energy analyzer
- **[Total Phase Power Delivery Analyzer](https://www.totalphase.com/products/power-delivery-analyzer/)** - USB PD protocol analyzer
- **[Ellisys USB Explorer](https://www.ellisys.com/products/uex280/)** - Professional USB protocol analyzer

### Community Contributions
1. **[chaseleif/km003c](https://github.com/chaseleif/km003c)** - Python implementation and multi-interface analysis
2. **[LongDirtyAnimAlf/km003c](https://github.com/LongDirtyAnimAlf/km003c)** - Pascal datalogger implementation
3. **[fqueze/usb-power-profiling](https://github.com/fqueze/usb-power-profiling)** - JavaScript WebUSB implementation
4. **[Linux Kernel Community](https://kernel.googlesource.com/pub/scm/linux/kernel/git/akpm/mm/+/refs/tags/mm-everything-2023-12-29-21-56/drivers/hwmon/powerz.c)** - Official hwmon driver (drivers/hwmon/powerz.c)

### Official Documentation
- ChargerLAB KM003C Protocol Documentation (PDF/DOCX)
- ChargerLAB KM002C&3C API Description (PDF/DOCX)
- USB Power Delivery Specification v3.0/3.1
- USB 2.0 Specification

### Technical References
- [USB Power Delivery Specification](https://www.usb.org/document-library/usb-power-delivery)
- [INA228 Datasheet](https://www.ti.com/lit/ds/symlink/ina228.pdf) - Temperature calculation
- [POWER-Z KM003C Product Page](https://www.power-z.com/products/262)
- [USB 2.0 Specification](https://www.usb.org/document-library/usb-20-specification)
- [Linux USB Monitoring](https://www.kernel.org/doc/html/latest/usb/usbmon.html)

### Analysis Tools
- **Wireshark + usbmon**: USB traffic capture and analysis
- **Polars**: Large-scale data analysis framework
- **Custom Rust tools**: Protocol parsing and correlation analysis
- **Python analysis suite**: Data processing and visualization

---

## Document Status

- **Version**: 1.0.0
- **Last Updated**: 2025-01-14
- **Status**: Comprehensive - All major protocol elements documented
- **Coverage**: 11,514+ packets analyzed across 7 capture sessions
- **Validation**: 100% parsing success rate on captured data

*This document represents the most complete protocol specification for the ChargerLAB POWER-Z KM003C device, consolidating findings from multiple reverse engineering efforts, community implementations, and official documentation sources.*
