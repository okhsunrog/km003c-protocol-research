# ChargerLAB POWER-Z KM003C: Complete Protocol Documentation

## Document Overview

This document provides the definitive, comprehensive protocol specification for the **ChargerLAB POWER-Z KM003C** USB-C power analyzer. It consolidates reverse engineering findings from multiple sources, official documentation, and community implementations to present a complete understanding of the device's communication protocol.

## Table of Contents

1. [Device Overview](#device-overview)
2. [Official Documentation Sources](#official-documentation-sources)
3. [Application Layer Protocol](#application-layer-protocol)
4. [Data Formats and Structures](#data-formats-and-structures)
5. [Power Delivery (PD) Protocol Support](#power-delivery-pd-protocol-support)
6. [Communication Patterns](#communication-patterns)
7. [Protocol Analysis Findings](#protocol-analysis-findings)
8. [References and Attribution](#references-and-attribution)

---

## Device Overview

The **ChargerLAB POWER-Z KM003C** is a USB-C power analyzer that provides real-time monitoring of voltage, current, power, and USB Power Delivery protocol analysis.

### Key Device Properties
- **Vendor ID**: `0x5FC9` (ChargerLAB)
- **Product ID**: `0x0063` (KM003C model)
- **Primary Interface**: USB Bulk transfers on Interface 0
- **Communication**: Vendor-specific protocol over USB

For URB-level handshakes, descriptors, and transport details, see [USB Transport Specification](usb_transport_specification.md).

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

## Application Layer Protocol

### Packet Structure Overview

This section specifies the application-layer message formats. USB transport (URBs, ZLPs, descriptors) is documented separately in `docs/usb_transport_specification.md`.

### Message Headers (4 bytes, little‑endian)

The first 32 bits of every message encode a common header with type‑specific low bits. Bit numbering below is little‑endian, least‑significant bit = 0.

- GetData Header (type = 0x0C)
  - bits 0..6: `packet_type` = 0x0C
  - bit 7: `reserved_flag` (vendor‑specific; not an "extended header present" flag)
  - bits 8..15: `id` (8‑bit rolling transaction ID)
  - bit 16: reserved (unused)
  - bits 17..31: `attribute_mask` (15‑bit)
    - Bitmask semantics: combine independent bits with bitwise OR to request multiple data classes in one response
    - Observed bits → response attribute mapping:
      • 0x0001 → ADC (extended attribute 1)
      • 0x0002 → AdcQueue (extended attribute 2)
      • 0x0008 → Settings (extended attribute 8)
      • 0x0010 → PdPacket (extended attribute 16)
      • 0x0200 → Unknown512 (extended attribute 512)
    - Observed combinations (bitwise OR):
      • 0x0011 (0x0001 | 0x0010) → ADC + PD
      • 0x0003 (0x0001 | 0x0002) → ADC + AdcQueue
    - Example: `mask = 0x0001 | 0x0010` requests ADC plus PD in a single PutData response

- PutData Header (type = 0x41)
  - bits 0..6: `packet_type` = 0x41
  - bit 7: `reserved_flag` (vendor‑specific; not an "extended header present" flag)
  - bits 8..15: `id` (matches requesting GetData `id`)
  - bits 16..21: reserved (unused)
  - bits 22..31: `obj_count_words` (≈ total_message_length / 4)

- Logical Extended Header (4 bytes, little‑endian)
  - bits 0..14: `attribute` (1 = ADC, 2 = AdcQueue, 16 = PdPacket, 8 = Settings)
  - bit 15: `next` (1 = another logical packet follows, 0 = last)
  - bits 16..21: `chunk` (typically 0)
  - bits 22..31: `size_bytes` (payload size for THIS logical packet)

### Command Types

- Requests (GetData)
| Type | Hex | Attribute Mask | Description |
|------|-----|----------------|-------------|
| GetData | 0x0C | 0x0001 (ADC) | Request ADC measurements |
| GetData | 0x0C | 0x0002 (AdcQueue) | Request ADC queue summary/block |
| GetData | 0x0C | 0x0010 (PdPacket) | Request PD protocol data |
| GetData | 0x0C | 0x0011 (ADC+PD) | Request ADC plus PD (bitwise OR) |
| GetData | 0x0C | 0x0003 (ADC+AdcQueue) | Request ADC plus AdcQueue (bitwise OR) |
| GetData | 0x0C | 0x0008 (Settings) | Request settings/configuration |

- Responses
| Type | Hex | Attribute | Description |
|------|-----|-----------|-------------|
| PutData | 0x41 | 0x0001 (Adc) | ADC measurement data |
| PutData | 0x41 | 0x0010 (PdPacket) | PD protocol events/status |
| PutData | 0x41 | 0x0002 (AdcQueue) | Queued ADC data |
| PutData | 0x41 | 0x0008 (Settings) | Device configuration |
| Accept | 0x05 | 0x0000 | Command acknowledgment (mode/control)

### Extended Header Usage by Attribute

| Attribute | Count | Size Field Meaning | Examples |
|-----------|-------|-------------------|----------|
| ATT_ADC (1) | 1,875 | Always 44 (base ADC size) | Standard/Extended variants |
| ATT_PdPacket (16) | 657 | Exact payload size | 12-108 bytes |
| ATT_AdcQueue (2) | 288 | Fixed 20 (header size) | 28-968 bytes payload |
| ATT_Settings (8) | 7 | Exact payload size | 180 bytes |


## Data Formats and Structures

### PutData Packet Structure (Chained Logical Packets)

The KM003C uses a sophisticated chained logical packet structure within PutData packets. Each PutData packet contains one or more logical packets, each with its own extended header and payload:

```c
// PutData packet with chained logical packets (52-876 bytes total)
struct putdata_packet {
    // Main header (4 bytes, little endian)
    struct {
        uint32_t type : 7;       // 65 (CMD_PUT_DATA)
        uint32_t reserved : 1;   // Vendor-reserved (observed 1 for PutData)
        uint32_t id : 8;         // Transaction ID
        uint32_t unused : 6;     // Unused
        uint32_t obj_count_words : 10; // Approximate total_size/4
    } main_header;

    // Chained logical packets - continue until next=0
    struct logical_packet {
        // Extended header (4 bytes, little endian)
        struct {
            uint32_t attribute : 15; // Logical packet type (1=ADC, 16=PdPacket, 2=AdcQueue)
            uint32_t next : 1;       // 1=another logical packet follows, 0=last packet
            uint32_t chunk : 6;      // Chunk number (typically 0)
            uint32_t size : 10;      // Size of THIS logical packet's payload
        } extended_header;

        uint8_t payload[size];       // Payload data specific to this logical packet
    } logical_packets[];             // Repeat until next=0
};
```

### Logical Packet Types

| Attribute | Name | Description | Payload Size |
|-----------|------|-------------|--------------|
| 1 | ADC | Voltage, current, temperature measurements | 44 bytes |
| 2 | AdcQueue | Queued ADC data | Variable |
| 16 | PdPacket | USB Power Delivery protocol data | Variable |

### ADC Logical Packet Payload

See single source of truth in KM003C Application‑Layer Protocol (Consolidated) → "ADC Payload (44 bytes)" for the byte‑accurate offset table.

### Common Packet Patterns

**Verified across 2,836 packets with zero violations:**

| Pattern | Count | Total Size | Structure |
|---------|-------|------------|-----------|
| **ADC only** | 1,825 | 52 bytes | `ADC(next=0)` |
| **ADC + PdPacket** | 36 | 68 bytes | `ADC(next=1) + PdPacket(next=0)` |
| **ADC + AdcQueue** | 16 | Variable | `ADC(next=1) + AdcQueue(next=0)` |
| **PdPacket only** | 657 | Variable | `PdPacket(next=0)` |

### Chaining Rules

1. **Next Flag**: Set to `1` if another logical packet follows, `0` for the last packet
2. **Perfect Compliance**: All 2,836 analyzed packets follow this rule with zero violations
3. **Self-Contained**: Each logical packet has its own extended header and payload
4. **Variable Length**: Total packet size depends on number and size of chained logical packets

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

### ADC Data Request Flow (Application Layer)
```
1. Host → Device: GetData (type=0x0C) requesting ADC/PD
   - Attribute mask: 0x0001 (ADC), 0x0010 (PdPacket), or 0x0011 (ADC+PD)
   - Format: 4‑byte header with matching transaction ID

2. Device → Host: PutData (type=0x41) response
   - Main header (4B) + one or more logical packets
   - Typical responses:
     • ADC only (total 52B): [Main][ADC(next=0)]
     • ADC + PD status (total 68B): [Main][ADC(next=1)][PdPacket(next=0)]

Notes:
- The response `id` matches the request `id` (8‑bit rolling).
- For URB/USB transport handshakes (e.g., ZLP Submit/Complete statuses), see USB transport documentation: docs/usb_transport_specification.md.
```

### PD Data Request Flow
```
1. Host → Device: GetData (type=0x0C) with attribute mask 0x0010 (PdPacket)

2. Device → Host: PutData with PD logical packet
   Structure: [Main Header][PdPacket logical packet (next=0)]

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

PutData messages use chained logical packets: `[Main Header (4B)] [Logical Packet 1] [Logical Packet 2] ... [Logical Packet N]`

Each logical packet follows: `[Extended Header (4B)] [Payload]`

See Message Headers above for exact bit layouts of the 4‑byte main header and 4‑byte logical extended header. Continue reading logical packets until `next=0`.

### Transaction Notes

IDs increment modulo 256; the PutData response `id` matches the GetData request `id`.

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

See Power Delivery (PD) Protocol Support for detailed PD payload formats (status vs preamble + event stream) and parsing rules.

### Sizes (reference)

For common total sizes and structures, see Communication Patterns → Common Packet Patterns.

### PD Status vs Preamble (Verified)

- PD Status (12B): includes 24‑bit timestamp and measured VBUS/IBUS/CC values; tracks ADC measurements.
- PD‑only preamble (first 12B of PD‑only payloads >12B): includes a 32‑bit timestamp (first 4 bytes) and metadata; not measurements. Parsing it as status yields unrealistic currents/voltages; do not treat it as PD status.

### Control (Mode) Commands

- Enable PD monitoring: request `10 [id] 02 00` → response `05 [id] 00 00` (accept)
- Disable PD monitoring: request `11 [id] 00 00` → response `05 [id] 00 00`

### Object Count Calculation

Empirical relation: `obj_count_words ≈ (total_message_length / 4) − 3` for standard single‑segment messages; adjust when chained segments are present.

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

- **Command Latency**: 77-85 microseconds
- **ADC Polling**: ~200ms intervals
- **PD Capture**: ~40ms when active
- **Maximum Throughput**: 133 packets/second sustained

---

## References and Attribution

### Technical References
- [USB Power Delivery Specification](https://www.usb.org/document-library/usb-power-delivery)
- [INA228 Datasheet](https://www.ti.com/lit/ds/symlink/ina228.pdf) - Temperature calculation
- [POWER-Z KM003C Product Page](https://www.power-z.com/products/262)
- [USB Transport Specification](usb_transport_specification.md) - Detailed USB interface and URB-level documentation

### Community Implementations

Thanks to the earlier reverse engineering efforts by the community:
- **[chaseleif/km003c](https://github.com/chaseleif/km003c)** - Python implementation with multi-interface analysis
- **[LongDirtyAnimAlf/km003c](https://github.com/LongDirtyAnimAlf/km003c)** - Pascal datalogger implementation
- **[fqueze/usb-power-profiling](https://github.com/fqueze/usb-power-profiling)** - JavaScript WebUSB implementation

### Complete Implementation
- **[km003c-rs](https://github.com/okhsunrog/km003c-rs)** - Full-featured Rust library with Python bindings, implementing the complete protocol documented in this research
