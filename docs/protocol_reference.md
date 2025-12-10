# KM003C Protocol Reference

Complete application-layer protocol specification for the ChargerLAB POWER-Z KM003C.

For USB transport details (descriptors, endpoints), see [USB Transport](usb_transport.md).

---

## Table of Contents

1. [Overview](#overview)
2. [Packet Headers](#packet-headers)
3. [Commands](#commands)
4. [Attributes](#attributes)
5. [Data Structures](#data-structures)
6. [Cryptography](#cryptography)
7. [Communication Patterns](#communication-patterns)
8. [Response Types](#response-types)

---

## Overview

The KM003C uses a vendor-specific protocol over USB bulk transfers on Interface 0 (endpoints 0x01 OUT, 0x81 IN).

### Key Characteristics

- **Packet size**: 4-2544 bytes
- **Byte order**: Little-endian throughout
- **Transaction ID**: 8-bit rolling counter (0-255)
- **Timeout**: 2 seconds recommended

### Protocol Layers

```
┌─────────────────────────────────────┐
│  Application (this document)        │
│  Commands, Attributes, Data         │
├─────────────────────────────────────┤
│  USB Bulk Transport                 │
│  See usb_transport.md               │
└─────────────────────────────────────┘
```

---

## Packet Headers

All packets start with a 4-byte header. The header format depends on packet type.

### Control Header (Commands/Responses)

Used by: Connect, Disconnect, Accept, Reject, GetData, StartGraph, StopGraph, etc.

```
Byte 0: [type:7][reserved:1]
Byte 1: [transaction_id:8]
Byte 2-3: [unused:1][attribute:15]  (little-endian)
```

| Field | Bits | Description |
|-------|------|-------------|
| type | 0-6 | Command type (0x02, 0x0C, etc.) |
| reserved | 7 | Vendor-specific flag (usually 0) |
| transaction_id | 8-15 | Rolling counter, response matches request |
| attribute | 17-31 | Attribute mask or parameter |

**Bit Layout (32-bit little-endian):**
```
 31  30  29  28  27  26  25  24  23  22  21  20  19  18  17  16  15  14  13  12  11  10   9   8   7   6   5   4   3   2   1   0
├───┴───┴───┴───┴───┴───┴───┴───┴───┴───┴───┴───┴───┴───┴───┼───┼───┴───┴───┴───┴───┴───┴───┴───┼───┼───┴───┴───┴───┴───┴───┴───┤
│              attribute (15 bits)                          │ u │      transaction_id (8)       │ r │        type (7 bits)      │
└───────────────────────────────────────────────────────────┴───┴───────────────────────────────┴───┴───────────────────────────┘
```

### Data Header (PutData)

Used by: PutData (0x41) responses containing measurement data.

```
Byte 0: [type:7][reserved:1]
Byte 1: [transaction_id:8]
Byte 2-3: [unused:6][obj_count_words:10]  (little-endian)
```

| Field | Bits | Description |
|-------|------|-------------|
| type | 0-6 | Always 0x41 (PutData) |
| reserved | 7 | Usually 1 for PutData |
| transaction_id | 8-15 | Matches request ID |
| obj_count_words | 22-31 | Approximate total_size / 4 |

### Extended Header (Logical Packets)

Within PutData, each logical packet has a 4-byte extended header:

```
Bits 0-14:  attribute (15 bits) - ADC=1, AdcQueue=2, Settings=8, PdPacket=16
Bit 15:     next (1 = more packets follow, 0 = last packet)
Bits 16-21: chunk (6 bits) - typically 0
Bits 22-31: size (10 bits) - payload size in bytes
```

**Example PutData with chained logical packets:**
```
[Main Header 4B][Ext Header 4B][Payload N bytes][Ext Header 4B][Payload M bytes]...
                └─ next=1 ─────────────────────┘└─ next=0 (last) ─────────────┘
```

---

## Commands

### Command Summary Table

| Type | Hex | Name | Direction | Attribute | Description |
|------|-----|------|-----------|-----------|-------------|
| 0x02 | Connect | OUT→IN | 0x0000 | Start session |
| 0x03 | Disconnect | OUT→IN | 0x0000 | End session |
| 0x05 | Accept | IN | 0x0000 | Command acknowledged |
| 0x06 | Reject | IN | varies | Command rejected |
| 0x0C | GetData | OUT→IN | mask | Request data by attribute mask |
| 0x0E | StartGraph | OUT→IN | rate | Start streaming (rate: 0-3) |
| 0x0F | StopGraph | OUT→IN | 0x0000 | Stop streaming |
| 0x10 | EnablePdMonitor | OUT→IN | 0x0002 | Enable PD sniffer (purpose unclear, optional) |
| 0x11 | DisablePdMonitor | OUT→IN | 0x0000 | Disable PD sniffer (purpose unclear, optional) |
| 0x41 | PutData | IN | varies | Data response |
| 0x44 | MemoryRead | OUT→IN | 0x0101 | Read device memory |
| 0x4C | StreamingAuth | OUT→IN | 0x0002 | Enable streaming features |

### Command Details

#### Connect (0x02)

Starts a communication session.

```
Request:  02 TID 00 00
Response: 05 TID 00 00 (Accept)
```

#### Disconnect (0x03)

Ends the session.

```
Request:  03 TID 00 00
Response: 05 TID 00 00 (Accept)
```

#### GetData (0x0C)

Requests data by attribute mask. Multiple attributes can be combined with bitwise OR.

```
Request:  0C TID [attr_lo] [attr_hi]
Response: 41 TID ... (PutData with requested data)
```

**Attribute mask encoding** (bytes 2-3, little-endian, shifted):
| Mask | Bytes | Requests |
|------|-------|----------|
| 0x0001 | `02 00` | ADC |
| 0x0002 | `04 00` | AdcQueue |
| 0x0008 | `10 00` | Settings |
| 0x0010 | `20 00` | PdPacket |
| 0x0011 | `22 00` | ADC + PdPacket |
| 0x0200 | `00 04` | LogMetadata |

**Note:** The attribute is in bits 17-31, so value N appears as `(N << 1)` in byte 2.

#### StartGraph (0x0E)

Starts AdcQueue streaming at specified sample rate.

```
Request:  0E TID [rate*2] 00
Response: 05 TID 00 00 (Accept)
```

**Rate encoding:**
| Rate Index | Byte Value | Sample Rate |
|------------|------------|-------------|
| 0 | 0x00 | 2 SPS |
| 1 | 0x02 | 10 SPS |
| 2 | 0x04 | 50 SPS |
| 3 | 0x06 | 1000 SPS |

**Prerequisite:** StreamingAuth (0x4C) must be sent first.

#### StopGraph (0x0F)

Stops AdcQueue streaming.

```
Request:  0F TID 00 00
Response: 05 TID 00 00 (Accept)
```

#### EnablePdMonitor (0x10)

Enables USB Power Delivery protocol capture.

```
Request:  10 TID 02 00
Response: 05 TID 00 00 (Accept)
```

**Note:** The exact purpose of this command is unclear. PD events can be retrieved via polling (GetData with attr=0x0010) without explicitly calling EnablePdMonitor. The device appears to buffer PD events by default. This command may enable extended capture features or higher-rate buffering. Needs further investigation.

#### DisablePdMonitor (0x11)

Disables PD capture.

```
Request:  11 TID 00 00
Response: 05 TID 00 00 (Accept)
```

**Note:** Purpose unclear - see EnablePdMonitor note above.

#### MemoryRead (0x44)

Reads data from device memory. Request payload is AES-128 ECB encrypted.

```
Request:  44 TID 01 01 [32 bytes encrypted]
Response: C4 TID ... (confirmation) + data packet
```

See [Authentication](features/authentication.md) for full details.

#### StreamingAuth (0x4C)

Required before AdcQueue streaming. Device validates payload against HardwareID.

```
Request:  4C TID 00 02 [32 bytes AES-encrypted]
Response: 4C 00 XX XX [32 bytes re-encrypted]
```

**Plaintext structure (32 bytes, before AES-128-ECB encryption):**
- Bytes 0-7: Timestamp (any value, not checked)
- Bytes 8-19: HardwareID (12 bytes from 0x40010450, **required**)
- Bytes 20-31: Padding (any value, not checked)

**Response attribute:**
- 0x0201: Auth failed (HardwareID mismatch) - AdcQueue returns empty
- 0x0203: Auth success - AdcQueue works

**Encryption key:** `Fa0b4tA25f4R038a`

See [Authentication](features/authentication.md) for full details.

---

## Attributes

### Attribute Summary

| Value | Hex | Name | Size | Description |
|-------|-----|------|------|-------------|
| 1 | 0x0001 | ADC | 44 bytes | Voltage, current, temperature |
| 2 | 0x0002 | AdcQueue | 20 bytes/sample | Streaming measurements |
| 8 | 0x0008 | Settings | 180 bytes | Device configuration |
| 16 | 0x0010 | PdPacket | Variable | PD status or events |
| 512 | 0x0200 | LogMetadata | 48 bytes | Offline log info |

### Attribute Bitmask Usage

For GetData requests, combine attributes with bitwise OR:

| Request | Mask | Response |
|---------|------|----------|
| ADC only | 0x0001 | 52 bytes (4+4+44) |
| ADC + PD | 0x0011 | 68 bytes (4+4+44+4+12) |
| ADC + AdcQueue | 0x0003 | Variable |

---

## Data Structures

### ADC Payload (44 bytes)

Returned with attribute 0x0001.

| Offset | Size | Type | Field | Unit |
|--------|------|------|-------|------|
| 0 | 4 | i32 | vbus_uV | Microvolts |
| 4 | 4 | i32 | ibus_uA | Microamps (signed) |
| 8 | 4 | i32 | vbus_avg_uV | Microvolts |
| 12 | 4 | i32 | ibus_avg_uA | Microamps |
| 16 | 4 | i32 | vbus_ori_avg_uV | Microvolts |
| 20 | 4 | i32 | ibus_ori_avg_uA | Microamps |
| 24 | 2 | i16 | temp_raw | See conversion below |
| 26 | 2 | u16 | vcc1_tenth_mV | 0.1 mV units |
| 28 | 2 | u16 | vcc2_tenth_mV | 0.1 mV units |
| 30 | 2 | u16 | vdp_tenth_mV | 0.1 mV units (D+) |
| 32 | 2 | u16 | vdm_tenth_mV | 0.1 mV units (D-) |
| 34 | 2 | u16 | vdd_tenth_mV | 0.1 mV units |
| 36 | 1 | u8 | sample_rate_idx | 0-4 |
| 37 | 1 | u8 | flags | Status flags |
| 38 | 2 | u16 | cc2_avg_mV | Millivolts |
| 40 | 2 | u16 | vdp_avg_mV | Millivolts |
| 42 | 2 | u16 | vdm_avg_mV | Millivolts |

**Temperature conversion** (INA228/INA229, LSB = 1/128 °C = 7.8125 m°C):
```c
float temp_celsius(int16_t raw) {
    return raw / 128.0;
}
```

**Current direction:**
- Positive: USB female (input) → USB male (output)
- Negative: USB male (input) → USB female (output)

### AdcQueue Sample (20 bytes)

Returned with attribute 0x0002. Multiple samples per response.

| Offset | Size | Type | Field | Unit |
|--------|------|------|-------|------|
| 0 | 2 | u16 | sequence | Incrementing counter |
| 2 | 2 | u16 | marker | Always 0x3C (60) |
| 4 | 4 | i32 | vbus_uV | Microvolts |
| 8 | 4 | i32 | ibus_uA | Microamps (signed) |
| 12 | 2 | u16 | cc1_tenth_mV | 0.1 mV units |
| 14 | 2 | u16 | cc2_tenth_mV | 0.1 mV units |
| 16 | 2 | u16 | vdp_tenth_mV | 0.1 mV units (D+) |
| 18 | 2 | u16 | vdm_tenth_mV | 0.1 mV units (D-) |

**Note:** AdcQueue does NOT include temperature - request ADC periodically if needed.

See [AdcQueue](features/adcqueue.md) for streaming details.

### Settings (180 bytes)

Returned with attribute 0x0008.

| Offset | Size | Type | Field | Description |
|--------|------|------|-------|-------------|
| 0x00 | 4 | u32 | flags | Configuration flags |
| 0x04 | 4 | u32 | reserved | Always 0 |
| 0x08 | 2 | u16 | sample_interval | Microseconds (10000 = 10ms) |
| 0x0A | 1 | u8 | display_brightness | 0-100 (65 default) |
| 0x0B | 1 | u8 | unknown | Always 0xFF |
| 0x0C | 4 | u32 | reserved | Always 0 |
| 0x10 | 32 | i32[8] | thresholds | Alert thresholds (-1 = disabled) |
| 0x30 | 40 | u32[10] | calibration | ADC calibration offsets |
| 0x58 | 4 | u32 | counter | Settings version |
| 0x5C | 4 | u32 | timestamp | Unix epoch |
| 0x60 | 1 | u8 | mode_flags | Operating mode (bits 2-3) |
| 0x61 | 15 | bytes | reserved | Zeros |
| 0x70 | 64 | char[] | device_name | UTF-8, null-terminated |
| 0xB0 | 4 | u32 | checksum | Device-calculated |

**Example values:**
```
flags:              0xf8500161
sample_interval:    10000 µs (10 ms)
display_brightness: 65
thresholds:         [-1, -1, -1, -6, -6, -6, -6, -6]  // -1=disabled, -6=enabled
mode_flags:         0x43 (bits 0,1,6 set, mode=(bits 2-3)=0)
device_name:        "POWER-Z"
```

**Note on checksum:** The checksum is NOT verified by the host software. It's device-generated using an unknown algorithm. Safe to ignore when reading.

### PD Status (12 bytes)

Returned with attribute 0x0010 when size = 12.

| Offset | Size | Type | Field | Description |
|--------|------|------|-------|-------------|
| 0 | 1 | u8 | type_id | Event/status ID |
| 1 | 3 | u24 | timestamp | ~40ms per tick |
| 4 | 2 | u16 | vbus_mV | VBUS voltage |
| 6 | 2 | u16 | ibus_mA | IBUS current |
| 8 | 2 | u16 | cc1_mV | CC1 voltage |
| 10 | 2 | u16 | cc2_mV | CC2 voltage |

### PD Event Stream

Returned with attribute 0x0010 when size > 12.

**Structure:**
```
[Preamble 12B][Event Header 6B][Wire N bytes][Event Header 6B][Wire M bytes]...
```

**Preamble (12 bytes):**
| Offset | Size | Field |
|--------|------|-------|
| 0 | 4 | timestamp_ms (u32) |
| 4 | 2 | vbus_mV |
| 6 | 2 | ibus_mA (signed) |
| 8 | 2 | cc1_mV |
| 10 | 2 | cc2_mV |

**Event Header (6 bytes):**
| Offset | Size | Field |
|--------|------|-------|
| 0 | 1 | size_flag |
| 1 | 4 | timestamp_ms (u32) |
| 5 | 1 | sop_type |

**Wire length:** `(size_flag & 0x3F) - 5`

See [PD Analysis](features/pd_analysis.md) for full details.

### LogMetadata (48 bytes)

Returned with attribute 0x0200.

| Offset | Size | Type | Field | Description |
|--------|------|------|-------|-------------|
| 0x00 | 16 | char[] | filename | e.g., "A01.d" |
| 0x10 | 2 | u16 | unknown | |
| 0x12 | 2 | u16 | sample_count | Number of samples |
| 0x14 | 2 | u16 | interval_ms | Sample interval |
| 0x16 | 2 | u16 | flags | |
| 0x18 | 4 | u32 | estimated_size | Bytes |
| 0x1C | 20 | bytes | metadata | Checksums etc. |

See [Offline Logs](features/offline_logs.md) for download protocol.

---

## Cryptography

### AES Keys (Single Source of Truth)

All encryption uses **AES-128 ECB** mode.

| Index | Key | Usage | Notes |
|-------|-----|-------|-------|
| 0 | `Lh2yfB7n6X7d9a5Z` | Memory read (0x44), firmware, offline logs | Primary key |
| 1 | `sdkW78R3k5dj0fHv` | Unknown | Unused in analyzed code |
| 2 | `Uy34VW13jHj3598e` | Unknown | Unused in analyzed code |
| 3 | `Fa0b4tA25f4R038a` | Streaming auth (0x4C) encrypt | Encryption key |
| 3' | `FX0b4tA25f4R038a` | Streaming auth (0x4C) decrypt | byte[1] = 'X' |

**Firmware key variant:** Some firmware dumps show key 0 as `Lh2yfB7n6X7d9a4Z`; both `...a4Z` and `...a5Z` work in practice.

**Key extraction from Mtools.exe:**
```
Address 0x140184ac8: "NmR0R.uz3KgNOu4xufpWLh2yfB7n6X7d9a5ZBwLe..."
                                        ^^^^^^^^^^^^^^^^
                                        offset 0x14, length 0x10 = Key 0
```

See [Mtools Analysis](firmware/mtools_analysis.md) for key locations.

### MemoryRead (0x44) Encryption

**Request payload (32 bytes plaintext):**
```
[0:3]   Address (u32 LE)
[4:7]   Size (u32 LE)
[8:11]  0xFFFFFFFF (magic)
[12:15] CRC32 of bytes 0-11
[16:31] 0xFF padding
```

Encrypted with Key 0 before sending.

**CRC32 calculation:**
```python
import binascii, struct
crc = binascii.crc32(struct.pack('<III', address, size, 0xFFFFFFFF)) & 0xFFFFFFFF
```

### StreamingAuth (0x4C) Encryption

Device encrypts challenge and session key with Key 3, returns encrypted result.

**Key finding:** Device enables streaming regardless of payload content. The verification only happens on the host side (Mtools.exe).

---

## Communication Patterns

### Basic ADC Polling

```
1. Connect (0x02)      → Accept (0x05)
2. GetData (0x0C)      → PutData (0x41) with ADC
   attr=0x0001
   [repeat every ~200ms]
3. Disconnect (0x03)   → Accept (0x05)
```

### AdcQueue Streaming

```
1. Connect (0x02)      → Accept (0x05)
2. StreamingAuth       → 0x4C response (attr=0x0203)  [REQUIRED]
   (0x4C, encrypted payload with HardwareID)
3. StartGraph (0x0E)   → Accept (0x05)
   rate=0-3
4. GetData (0x0C)      → PutData (0x41) with AdcQueue samples
   attr=0x0002
   [repeat every 20-200ms]
5. StopGraph (0x0F)    → Accept (0x05)
6. Disconnect (0x03)   → Accept (0x05)
```

### PD Capture

```
1. Connect (0x02)      → Accept (0x05)
2. GetData (0x0C)      → PutData with PdPacket
   attr=0x0010
   [repeat every ~40ms]
3. Disconnect (0x03)   → Accept (0x05)
```

**Note:** EnablePdMonitor (0x10) and DisablePdMonitor (0x11) are optional. The device buffers PD events by default and returns them via GetData polling. The purpose of these commands is unclear and needs further investigation.

### Memory Read

```
1. Connect (0x02)      → Accept (0x05)
2. MemoryRead (0x44)   → Confirm (0xC4) + Data packet
   [encrypted request]
   [repeat for each address]
3. Disconnect (0x03)   → Accept (0x05)
```

---

## Response Types

### Standard Responses

| Type | Hex | Name | Size | Meaning |
|------|-----|------|------|---------|
| 0x05 | Accept | 4 bytes | Command succeeded |
| 0x06 | Reject | 4 bytes | Command failed |
| 0x27 | NotReadable | 4 bytes | Memory address not accessible |
| 0x41 | PutData | Variable | Data response |

### Data Response Types (from MemoryRead)

**Important:** MemoryRead data responses are AES-128-ECB encrypted using `MEMORY_READ_KEY`
(`Lh2yfB7n6X7d9a5Z`). The entire response block must be decrypted before parsing.
The "type" values below historically appeared as the first byte of responses, but this is
coincidental - they are simply the first byte of encrypted data for each address.

| Type | Hex | Address | Size | Content |
|------|-----|---------|------|---------|
| 0x1A | DeviceInfo1 | 0x420 | 64 bytes | Model, HW version, mfg date |
| 0x2C | FirmwareInfo2 | varies | 64 bytes | FW info (attr=0x564D) |
| 0x3A | FirmwareInfo | 0x4420 | 64 bytes | FW version, build date |
| 0x40 | CalibrationData | 0x3000C00 | 64 bytes | Serial, UUID, timestamp |
| 0x75 | HardwareID | 0x40010450 | 12 bytes | Serial prefix + device ID |

### Log Data Chunks

| Type | Hex | Size | Description |
|------|-----|------|-------------|
| 0x34 | LogChunk1 | 2544 bytes | First log data chunk |
| 0x4E | LogChunk2 | 2544 bytes | Second log data chunk |
| 0x76 | LogChunk3 | 2544 bytes | Third log data chunk |
| 0x68 | LogChunk4 | ≤704 bytes | Final log data chunk |


## Empirical Findings (Captured Traffic)

- **Transaction coverage:** 2,836 request/response pairs across seven captures; 100% ID match and bitmask→attribute correlation.
- **Common PutData sizes:** 52B (ADC only), 68B (ADC+PD status), 52–900B (AdcQueue), variable PD-only (≥18B preamble+events).
- **obj_count_words heuristic:** `≈ (total_bytes / 4) – 3` for single-segment packets; adjust upward when multiple logical packets are chained.
- **Latency (median):** ADC ~182 µs, PD ~158 µs, ADC+PD ~198 µs, AdcQueue ~1.06 ms (larger payloads).
- **Empty responses:** A PutData with `obj_count_words=0` is valid when AdcQueue has no buffered samples.

## References

- [USB Transport](usb_transport.md) - USB layer details
- [Authentication](features/authentication.md) - 0x4C and 0x44 deep dive
- [AdcQueue](features/adcqueue.md) - Streaming implementation
- [Firmware Handlers](firmware/handlers.md) - Device firmware analysis
- [Mtools Analysis](firmware/mtools_analysis.md) - Windows app reverse engineering
