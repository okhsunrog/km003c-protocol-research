# KM003C USB-C Power Analyzer Protocol Specification

## Overview

The KM003C USB-C power analyzer uses a structured USB application-layer protocol for communication between host software and device firmware. This document specifies the complete protocol format based on reverse engineering analysis.

## Message Structure

### Base Message Format

All messages follow a consistent structure with mandatory headers:

```
┌─────────────────┬─────────────────┬──────────────────┐
│  Main Header    │ Extended Header │     Payload      │
│    (4 bytes)    │    (4 bytes)    │   (variable)     │
└─────────────────┴─────────────────┴──────────────────┘
```

### Main Header (4 bytes, little-endian)

| Bits  | Field      | Description                                    |
|-------|------------|------------------------------------------------|
| 0-6   | `type`     | Message type (0x0C=GetData, 0x41=PutData)     |
| 7     | `extend`   | Extended header flag (always 0 for PutData)   |
| 8-15  | `id`       | Message ID (rolling counter 0-255)            |
| 16-21 | *reserved* | Reserved bits                                  |
| 22-31 | `obj_count`| Object count (payload words, see calculation) |

### Extended Header (4 bytes, little-endian)

| Bits  | Field        | Description                                  |
|-------|--------------|----------------------------------------------|
| 0-14  | `attribute`  | Payload type (1=ADC, 16=PD, 2=AdcQueue)     |
| 15    | `next`       | Chained payload flag (1=more data follows)  |
| 16-21 | `chunk`      | Chunk index (used for queued data)          |
| 22-31 | `size_bytes` | Payload size in bytes                        |

## Request/Response Patterns

### Host Requests (GetData - 0x0C)

| Request Pattern | Target Data | Response Size | Description           |
|-----------------|-------------|---------------|-----------------------|
| `0C [id] 02 00` | ADC only    | 52 bytes      | ADC measurements only |
| `0C [id] 22 00` | ADC+PD      | 68 bytes      | ADC + PD status       |
| `0C [id] 20 00` | PD only     | 20+ bytes     | PD data only          |

### Device Responses (PutData - 0x41)

#### ADC-Only Response (52 bytes)
```
Main Header:     41 [id] [obj_count] 03
Extended Header: 01 00 00 0B          # attribute=1(ADC), next=0, size=44
ADC Payload:     [44 bytes of ADC data]
```

#### ADC+PD Combined Response (68 bytes)
```
Main Header:     41 [id] [obj_count] 03
Extended Header: 01 80 00 0B          # attribute=1(ADC), next=1, size=44
ADC Payload:     [44 bytes of ADC data]
Extended Header: 10 00 00 03          # attribute=16(PD), next=0, size=12
PD Payload:      [12 bytes of PD status]
```

#### PD-Only Response (20+ bytes)
```
Main Header:     41 [id] [obj_count] 00
Extended Header: 10 00 00 [size]      # attribute=16(PD), next=0, size=variable
PD Payload:      [PD status or event data]
```

## Payload Formats

### ADC Payload (44 bytes)

ADC measurements from the KM003C's analog frontend:

| Offset | Size | Field             | Unit | Description                    |
|--------|------|-------------------|------|--------------------------------|
| 0      | 4    | `vbus_uV`         | µV   | VBUS voltage (instantaneous)   |
| 4      | 4    | `ibus_uA`         | µA   | IBUS current (instantaneous)   |
| 8      | 4    | `vbus_avg_uV`     | µV   | VBUS voltage (averaged)        |
| 12     | 4    | `ibus_avg_uA`     | µA   | IBUS current (averaged)        |
| 16     | 4    | `vbus_ori_avg_uV` | µV   | VBUS voltage (original avg)    |
| 20     | 4    | `ibus_ori_avg_uA` | µA   | IBUS current (original avg)    |
| 24     | 2    | `temp_raw`        | -    | Temperature sensor reading     |
| 26     | 2    | `vcc1_tenth_mV`   | 0.1mV| VCC1 supply voltage           |
| 28     | 2    | `vcc2_tenth_mV`   | 0.1mV| VCC2 supply voltage           |
| 30     | 2    | `vdp_tenth_mV`    | 0.1mV| D+ voltage                    |
| 32     | 2    | `vdm_tenth_mV`    | 0.1mV| D- voltage                    |
| 34     | 2    | `vdd_tenth_mV`    | 0.1mV| VDD supply voltage            |
| 36     | 1    | `sample_rate_idx` | -    | ADC sample rate index          |
| 37     | 1    | `flags`           | -    | Status flags                   |
| 38     | 2    | `cc2_avg_mV`      | mV   | CC2 voltage (averaged)         |
| 40     | 2    | `vdp_avg_mV`      | mV   | D+ voltage (averaged)          |
| 42     | 2    | `vdm_avg_mV`      | mV   | D- voltage (averaged)          |

### PD Payload Formats

#### PD Status (12 bytes)
Basic PD monitoring data included with ADC measurements:

| Offset | Size | Field          | Description                      |
|--------|------|----------------|----------------------------------|
| 0      | 1    | `type_id`      | Event type or sequence ID        |
| 1      | 3    | `timestamp`    | 24-bit timestamp (µs)            |
| 4      | 2    | `vbus_raw_mV`  | VBUS voltage measurement (mV)    |
| 6      | 2    | `ibus_raw_mA`  | IBUS current measurement (mA)    |
| 8      | 2    | `cc1_raw_mV`   | CC1 voltage measurement (mV)     |
| 10     | 2    | `cc2_raw_mV`   | CC2 voltage measurement (mV)     |

#### PD Event Data (18-108 bytes)
Larger PD payloads containing wrapped USB PD protocol messages:

```
Preamble:        [12 bytes - KM003C metadata]
Event Header:    [6 bytes - size_flag, timestamp(4), sop(1)]
PD Wire Data:    [2-32 bytes - USB PD protocol message]
[Additional events may follow...]
```

**Event Header Format:**
- `size_flag`: Total event size, wire length = (size_flag & 0x3F) - 5
- `timestamp`: 32-bit little-endian timestamp in microseconds
- `sop`: Start of Packet type (USB PD protocol)

## Chained Payload System

The KM003C protocol supports chaining multiple payloads in a single response:

1. **Parse Main + Extended Headers** (8 bytes total)
2. **Read payload** using `size_bytes` from Extended Header
3. **If `next=1`**: Read next Extended Header and payload
4. **If `next=0`**: Message complete

### Example: ADC+PD Chain
```
[Main Header: 8 bytes total offset]
├── Extended Header: attribute=1(ADC), next=1, size=44
├── ADC Payload: [44 bytes] → cursor = 8 + 44 = 52
├── Extended Header: attribute=16(PD), next=0, size=12  → cursor = 52 + 4 = 56
└── PD Payload: [12 bytes] → cursor = 56 + 12 = 68 (complete)
```

## PD Message Integration

### USB PD Protocol Messages
The KM003C can capture and embed actual USB PD wire protocol messages within its event data format. These include:

- **Source_Capabilities**: Power supply advertisements (26 bytes wire data)
- **Request**: Power negotiation requests (6 bytes wire data)
- **Accept/Reject**: Negotiation responses (2 bytes wire data)
- **PS_RDY**: Power supply ready notifications (2 bytes wire data)
- **GoodCRC**: Protocol acknowledgments (2 bytes wire data)

### Message Extraction
PD wire messages can be extracted from KM003C event data and parsed using standard USB PD protocol parsers (e.g., usbpdpy library).

## Mode Control Commands

### Enable PD Monitoring
- **Request**: `10 [id] 02 00` (Unknown command type 16)
- **Response**: `05 [id] 00 00` (Accept)
- **Effect**: Enables PD capture mode, ADC+PD combined responses become available

### Disable PD Monitoring
- **Request**: `11 [id] 00 00` (Unknown command type 17)
- **Response**: `05 [id] 00 00` (Accept)
- **Effect**: Disables PD capture mode, returns to ADC-only responses

## Implementation Notes

### Object Count Calculation
The `obj_count` field in the main header follows the pattern:
```
obj_count ≈ (total_message_length / 4) - 3
```

### Request ID Management
- Request IDs increment sequentially (0-255, then wrap)
- Response ID matches corresponding request ID
- IDs help correlate request/response pairs in captures

### Error Handling
- Invalid requests receive no response (timeout)
- Malformed commands may return error responses (format TBD)

---

*This specification is based on reverse engineering analysis of KM003C USB captures and SQLite export data. All field interpretations have been validated against actual device behavior.*