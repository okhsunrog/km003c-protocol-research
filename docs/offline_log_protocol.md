# KM003C Offline Log Download Protocol

**Date**: 2025-10-05  
**Source**: reading_logs0.11 capture (29.5s, 618 packets)  
**Status**: 🔍 Partially understood, encryption/compression detected

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

## Unknown68 Exchange (Log Read Command)

### Request Structure

```
Packet type: 0x44 (Unknown68)
Size: 36 bytes total
Format: [header(4)] [payload(32)]

Example: 44 47 01 01 06fd6d233e3bc6d0e28ca4c7635a1ad26ae4c2c0e9b903c0810ea0e0
  [0]    0x44 (packet type 68)
  [1]    0x47 (ID = 71)
  [2:3]  0x0101 (flags/extended?)
  [4:35] 32-byte payload (challenge? encryption key? log selector?)
```

**32-byte payload characteristics**:
- Appears random/encrypted
- Different for each Unknown68 in initialization
- Possibly: authentication challenge, encryption key, or log file selector

### Response Structure

```
Packet type: 0x44 (Unknown68)  
Size: 20 bytes

Example: c4 47 01 01 0000109890200000ffffffff2f0ab013
  [0]    0xC4 (0x44 with reserved bit set)
  [1]    0x47 (ID = 71, matches request)
  [2:3]  0x0101 (matches request)
  [4:19] 16-byte response data
```

**Response data fields** (decoded):
```
Bytes 4-7:   Unknown/flags (varies)
Bytes 8-11:  Total log size in bytes (0x00002090 = 8336 bytes) ✓
Bytes 12-15: 0xFFFFFFFF (constant marker)
Bytes 16-19: CRC32 or hash of log data
```

**Validation**: ID=71 response before data transfer:
- Field2 = 8336 bytes
- Actual chunks: 3 × 2544 = 7632 bytes
- Close match (overhead for headers/padding?)

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

**Observation**: Data appears encrypted or compressed
- High entropy (random-looking bytes)
- No obvious text or structured data
- No repeated patterns

**Examples** (first 50 bytes):
```
Chunk 1 (type=52):  b4 45 20 62 1e 2e 78 d8 f5 95 83 96 12 45 4b 96...
Chunk 2 (type=78):  4e ed bf 16 0e d8 21 92 6f 60 39 ce 5d 7c bf 5d...
Chunk 3 (type=118): 76 4f cf ad 0a 89 a1 f4 ce eb ec 13 7b 3d e4 df...
```

**Hypothesis**: 
- Log data is encrypted/compressed before USB transfer
- Unknown68 exchange provides decryption key or authentication
- Three chunks = three segments of log file
- Packet types (52/78/118) might indicate chunk number or file type

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

## Research Questions

### 1. Unknown68 Payload Purpose

**32-byte request payload**:
- Random-looking data (different each time)
- Could be: encryption key, challenge, nonce, log file ID
- Need: comparison with multiple log downloads

### 2. Encryption/Compression

**Evidence**:
- High entropy in large data chunks
- No obvious patterns
- Fixed chunk sizes (2544 bytes)

**Possibilities**:
- AES encryption (32-byte key from Unknown68?)
- Proprietary compression
- Raw flash dump with vendor-specific format

### 3. Chunk Packet Types

Why three different types (52, 78, 118)?
- Chunk sequence indicator?
- Different file segments?
- Protocol versioning?

### 4. Response Format

Unknown68 response (20 bytes):
- What do the fields mean?
- Is 0x00001098 a file size?
- Is 0x90200000 a timestamp?

---

## Testing Recommendations

### Test 1: Multiple Log Downloads

**Procedure**:
1. Record several logs on device (different durations/conditions)
2. Download each log while capturing USB
3. Compare Unknown68 payloads
4. Check if chunk count varies with log size

**Goal**: Understand log file structure and Unknown68 payload meaning

### Test 2: Empty Log Download

**Procedure**:
1. Clear device logs
2. Attempt download with no logs
3. Capture USB traffic

**Goal**: Understand error handling and empty state protocol

### Test 3: Decryption Attempt

**Procedure**:
1. Download known log (record exact conditions)
2. Compare encrypted USB data with expected values
3. Try XOR, AES with various keys from Unknown68

**Goal**: Determine if data is encrypted and find decryption method

---

## Implementation Status

### km003c-rs Library

❌ **Not yet implemented**:
- Unknown68 (0x44) packet type
- Unknown(52/78/118) data chunk packets
- Log enumeration protocol
- Data decryption/decompression

### Recommendations

1. **Add packet types**:
```rust
// In PacketType enum
LogReadCommand = 68,   // 0x44, Unknown68
LogDataChunk1 = 52,    // 0x34
LogDataChunk2 = 78,    // 0x4E
LogDataChunk3 = 118,   // 0x76
```

2. **Add API**:
```rust
pub async fn list_offline_logs(&mut self) -> Result<Vec<LogInfo>, KMError>;
pub async fn download_log(&mut self, log_id: u32) -> Result<Vec<u8>, KMError>;
```

3. **Research needed**:
- Reverse engineer Unknown68 payload format
- Decrypt/decompress log data
- Parse log file structure

---

## Related Captures

Files for further analysis:
- `reading_logs0.11` - Single log download (this document)
- Need: captures with multiple logs, empty logs, different log sizes

---

## Conclusions

✅ **Understood**:
- Log download uses Unknown68 command
- Data transferred in 2544-byte chunks
- Three chunk types observed
- Challenge/response pattern present

❌ **Unknown**:
- Unknown68 32-byte payload meaning
- Data encryption/compression method
- Chunk type significance
- Log file format after decryption

🔬 **Next steps**: Need more captures with known log content to reverse engineer encryption/format.

---

**Analysis date**: 2025-10-05  
**Confidence**: ⭐⭐ (Protocol flow understood, data format unknown)
