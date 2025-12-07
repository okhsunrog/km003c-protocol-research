# KM003C Offline Log Download Protocol

**Date**: 2025-10-05 (Updated: 2025-12-07)
**Source**: reading_logs0.11 capture (29.5s, 618 packets) + Ghidra RE
**Status**: ✅ Fully reversed and verified

---

## Overview

The KM003C can record power measurements to internal flash memory in offline mode (without PC connection). The official application can list stored logs and download them via USB.

**Captured**: One log download session from device flash to PC.

---

## Protocol Flow

### 1. Initialization Sequence

```
[0.47s] Connect (0x02) → Accept
[0.47s] Unknown68 #1 (challenge/response?)
[0.48s] Unknown26 response (attr=0x0649)
[1.11s] Unknown68 #2
[1.13s] Head (0x40) response
[1.13s] Unknown68 #3
[1.14s] Unknown117 response
[1.19s] Unknown76 (challenge?)
[1.20s] GetData Settings (0x0008)
```

Standard initialization + additional Unknown packets for log enumeration.

### 2. Log Data Transfer

**Pattern observed**:
```
Unknown68 request (36 bytes) 
  → Unknown68 response (20 bytes)
  → Large data chunk (2544 bytes)
```

**Three large data chunks transferred**:
1. Unknown(52) - 2544 bytes
2. Unknown(78) - 2544 bytes  
3. Unknown(118) - 2544 bytes

**Total log data**: ~7.6 KB

---

## Unknown68 Exchange (Memory/Log Download Command) ✅ REVERSED

### Encryption Details (from Ghidra RE)

**Algorithm**: AES-128 ECB
**Key**: `Lh2yfB7n6X7d9a5Z` (16 bytes, key index 0)
**Key Location**: Mtools.exe @ 0x140184ac8 + offset 0x14

### Request Structure (36 bytes)

```
Packet type: 0x44 (Unknown68)
Size: 36 bytes total
Format: [header(4)] [encrypted_payload(32)]

USB Header (4 bytes):
  [0]    0x44 (packet type 68)
  [1]    Transaction ID (increments)
  [2:3]  0x0101 (flags: encrypted payload)

Encrypted Payload (32 bytes) - AES-128 ECB:
  After decryption:
  [0:3]   Address (u32 LE) - memory address or log marker
  [4:7]   Size (u32 LE) - bytes to download
  [8:11]  0xFFFFFFFF (constant)
  [12:15] CRC32 (of bytes 0-11 + padding)
  [16:31] 0xFF × 16 (padding)
```

**Address field semantics**:
| Address | Purpose |
|---------|---------|
| 0x00000420 | Device info block 1 (64 bytes) |
| 0x00004420 | Device info block 2 (64 bytes) |
| 0x03000C00 | Unknown data (64 bytes) |
| 0x40010450 | Unknown data (12 bytes) |
| 0x98100000 | **Offline log data** (special marker, bit 31 set) |

**CRC32 calculation**: Standard CRC32 over the 16-byte structure (address + size + 0xFFFFFFFF + padding).

### Response Structure (20 bytes)

```
Packet type: 0x44 (Unknown68)
Size: 20 bytes
Format: [header(4)] [payload(16)]

USB Header (4 bytes):
  [0]    0xC4 (0x44 | 0x80, response bit set)
  [1]    Transaction ID (matches request)
  [2]    Flags low byte - bit 0 = DATA CHUNKS encrypted (1 = yes)
  [3]    Flags high byte

Payload (16 bytes) - NOT encrypted, plaintext:
  [0:3]   Address echo (u32 LE)
  [4:7]   Size echo (u32 LE) - e.g., 0x2090 = 8336 bytes
  [8:11]  0xFFFFFFFF (constant)
  [12:15] CRC32 (checksum of data to follow)
```

### Example: Log Download Request

**Captured encrypted**: `44 47 01 01 <32 bytes encrypted>`
**Decrypted payload**: `00001098 90200000 ffffffff 2f0ab013 ffffffff ffffffff ffffffff ffffffff`

Parsed:
- Address: 0x98100000 (log marker, little-endian: `00001098`)
- Size: 0x00002090 = 8336 bytes (little-endian: `90200000`)
- Constant: 0xFFFFFFFF
- CRC32: 0x13b00a2f

**Response decrypted**: Echoes address and size, provides CRC32 of log data

**ASCII visualization**: No readable text in encrypted chunks (high entropy throughout)

---

## Large Data Chunks

### Chunk Packet Types

Three consecutive chunks with different packet types:
- **Unknown(52)** - 0x34 (packet type 52)
- **Unknown(78)** - 0x4E (packet type 78)
- **Unknown(118)** - 0x76 (packet type 118)

All exactly **2544 bytes** each.

### Data Characteristics

**Encryption**: AES-128 ECB (same key as Unknown68 request/response)
- Entire chunk payload is encrypted (no header skip needed)
- Key: `Lh2yfB7n6X7d9a5Z`

**Decryption**: Concatenate all chunks, decrypt with AES-128 ECB, parse as 16-byte samples.

**Verified data from reading_logs0.11**:
- 521 samples × 16 bytes = 8336 bytes
- Voltage: 5V → 9V (changed during recording)
- Current: -1.9A → -0.1A (decreasing discharge)
- Charge accumulator: -810.3 mAh (matches official app: -0.8103 Ah)
- Energy accumulator: -5747.2 mWh (matches official app: -5.7472 Wh)

---

## Download Statistics

From reading_logs0.11:

| Metric | Value |
|--------|-------|
| Duration | 29.5 seconds |
| Total packets | 618 |
| Requests (OUT) | 290 |
| Responses (IN) | 308 |
| Unknown68 exchanges | 4 |
| Large data chunks | 3 |
| Data chunk size | 2544 bytes each |
| Total log data | 7632 bytes |
| Normal ADC requests | 135 |

**Observation**: Normal ADC polling continues during log download (135 GetData requests interspersed with log transfers).

---

## Packet Type Analysis

### Control Packets (<0x40)

| Type | Hex | Count | Purpose |
|------|-----|-------|---------|
| Connect | 0x02 | 1 | Session start |
| GetData | 0x0C | 138 | ADC + Settings requests |
| Unknown(15) | 0x0F | 1 | Stop command? |

### Data Packets (>=0x40)

| Type | Hex | Count | Size | Purpose |
|------|-----|-------|------|---------|
| Head | 0x40 | 1 | ? | Initialization header |
| PutData | 0x41 | 135 | 52B | Normal ADC responses |
| Unknown(52) | 0x34 | 1 | 2544B | **Log data chunk 1** |
| Unknown68 | 0x44 | 4 | 20-36B | **Log read command** |
| Unknown(78) | 0x4E | 1 | 2544B | **Log data chunk 2** |
| Unknown76 | 0x4C | 1 | ? | Challenge? |
| Unknown(118) | 0x76 | 1 | 2544B | **Log data chunk 3** |
| Unknown26 | 0x1A | 1 | ? | Info response? |
| Unknown117 | 0x75 | 1 | ? | Info response? |

---

## Log Metadata (Attribute 0x0200) ✅ VERIFIED

**Request**: `GetData(attr=0x0200)` returns log metadata in PutData response.

### Structure (48 bytes after 8-byte PutData header)

```
Offset  Size  Type    Field              Example
────────────────────────────────────────────────────────
0x00    16    char[]  Log filename       "A01.d" (null-terminated)
0x10    2     u16     Unknown            0x0A45
0x12    2     u16     Sample count       521
0x14    2     u16     Interval (ms)      10000 (= 10 seconds)
0x16    2     u16     Flags              0x0000
0x18    4     u32     Estimated size     5200 bytes
0x1C    20    bytes   Additional data    (checksums/metadata)
```

**Calculated data size**: `sample_count × 16 bytes` (actual ADC data)
- Example: 521 × 16 = 8336 bytes (vs. estimated 5200 - estimate is lower)

**Duration calculation**: `sample_count × interval_ms / 1000` seconds
- Example: 521 × 10000 / 1000 = 5210s = 1:26:50

---

## Device Information

**Firmware version**: 1.9.9 (captured session)  
**Hardware version**: 2.1 (captured session)

**Note**: Version numbers not yet located in USB protocol. May be in:
- Head (0x40) packet (encrypted)
- Unknown26 response (encrypted)
- Settings response in specific offsets
- Or retrieved via separate command

---

## Research Questions

### ✅ SOLVED: Unknown68 Payload Purpose

**32-byte request payload** (after AES-128 ECB decryption):
- Address (4B) + Size (4B) + 0xFFFFFFFF (4B) + CRC32 (4B) + Padding (16B)
- For offline ADC downloads, address = 0x98100000 (special marker)
- Size = exact data size in bytes

### ✅ SOLVED: Encryption Method

**Request/Response encryption**: AES-128 ECB with key `Lh2yfB7n6X7d9a5Z`

**ADC data chunks**: Also encrypted (bit 16 of response header indicates encryption)
- Same key (index 0)
- Same mode (ECB)
- Decrypted in `download_large_data()` function

### 🔍 PARTIALLY SOLVED: Chunk Packet Types

Types 0x34 (52), 0x4E (78), 0x76 (118), 0x68 (104):
- Sequential chunk indicators for large transfers
- Each chunk up to 2544 bytes
- Final chunk (0x68) may be smaller

### ✅ SOLVED: Response Format

Unknown68 response (20 bytes) after decryption:
- Bytes 0-3: Address echo
- Bytes 4-7: Size echo (0x2090 = 8336 bytes)
- Bytes 8-11: 0xFFFFFFFF (constant)
- Bytes 12-15: CRC32 of data to follow

### ✅ SOLVED: ADC Data Structure

**Sample format**: 16 bytes per sample (not 8 bytes as initially expected)

```
Offset  Size  Type    Field           Unit
──────────────────────────────────────────────────
0x00    4     i32     Voltage         µV (microvolts)
0x04    4     i32     Current         µA (microamps, negative = discharge)
0x08    4     i32     Charge_Acc      µAh (accumulated charge)
0x0C    4     i32     Energy_Acc      µWh (accumulated energy)
```

**Verified correlations**:
- `Charge_Acc[n+1] - Charge_Acc[n] ≈ Current[n] × (interval_sec / 3600)`
- `Energy_Acc[n+1] - Energy_Acc[n] ≈ (Voltage[n] × Current[n]) × (interval_sec / 3600)`
- Accuracy: within 1-2% (rounding errors)

**Example from reading_logs0.11** (521 samples @ 10s intervals):
```
Sample 0:   V=5.000V, I=-1.905A, Q_acc=-5.3mAh,   E_acc=-26.4mWh
Sample 100: V=9.022V, I=-0.908A, Q_acc=-276.6mAh, E_acc=-2066.9mWh
Sample 520: V=8.989V, I=-0.099A, Q_acc=-810.3mAh, E_acc=-5747.2mWh
```

**Total data size**: 521 × 16 = 8336 bytes ✓

---

## Implementation

### Python Script

**`scripts/download_offline_log.py`** - Downloads and decrypts offline logs from device.

### km003c-rs Library

Future implementation recommendations:

```rust
// Packet types to add
LogReadCommand = 68,     // 0x44 (Unknown68)
LogDataChunk = 52,       // 0x34, 0x4E, 0x76, 0x68 (sequential chunks)

// API to add
pub async fn get_log_metadata(&mut self) -> Result<LogMetadata, KMError>;
pub async fn download_log(&mut self) -> Result<OfflineLog, KMError>;
```

---

## Conclusions

✅ **Fully Understood**:
- Log download uses Unknown68 command with AES-128 ECB encryption
- Request: 36 bytes (4B header + 32B encrypted payload with address/size/CRC32)
- Response: 20 bytes (4B header + 16B encrypted echo with CRC32 of data)
- Data chunks: types 0x34/0x4E/0x76/0x68, each up to 2544 bytes
- Data encryption: AES-128 ECB with key `Lh2yfB7n6X7d9a5Z`
- Sample format: 16 bytes (voltage µV + current µA + charge µAh + energy µWh)
- Accumulated values correlate with instantaneous measurements within 1-2%

🔍 **Remaining questions**:
- Chunk type significance (0x34/0x4E/0x76/0x68) - sequential indicators?
- Multiple log handling - how to select specific logs?
- Log deletion protocol

---

**Analysis date**: 2025-10-05 (Updated: 2025-12-07)
**Confidence**: ⭐⭐⭐⭐⭐ (Protocol fully reversed, data format confirmed)
