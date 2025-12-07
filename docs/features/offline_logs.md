# Offline Log Download

Protocol for downloading device-stored measurement logs.

For encryption keys and general protocol, see [Protocol Reference](../protocol_reference.md).

---

## Overview

The KM003C can record power measurements to internal flash while offline. This protocol downloads stored logs.

**Encryption:** AES-128 ECB with key `Lh2yfB7n6X7d9a5Z` (key index 0)

---

## Protocol Flow

Initialization and transfer as observed in captures (reading_logs0.11):

1. Connect (0x02) → Accept
2. Unknown68 ×3 with small responses (challenge/echo)
3. Head (0x40) and Unknown117/Unknown26 responses
4. (Optional) Unknown76 auth
5. GetData Settings (0x0008)
6. GetData LogMetadata (0x0200) to fetch sizes
7. MemoryRead (0x44, address 0x98100000) to start download
8. Receive chunk sequence 0x34 → 0x4E → 0x76 → 0x68 (final, may be smaller)
9. Concatenate, decrypt, parse 16-byte samples

---

## Log Metadata (Attribute 0x0200)

### Request

```
0C TID 00 04  # GetData attr=0x0200
```

### Response Structure (48 bytes after 8-byte header)

| Offset | Size | Type | Field |
|--------|------|------|-------|
| 0x00 | 16 | char[] | Filename (null-terminated, e.g. "A01.d") |
| 0x10 | 2 | u16 | Unknown |
| 0x12 | 2 | u16 | Sample count |
| 0x14 | 2 | u16 | Interval (ms) |
| 0x16 | 2 | u16 | Flags |
| 0x18 | 4 | u32 | Estimated size |
| 0x1C | 20 | bytes | Additional metadata |

**Data size:** `sample_count × 16` bytes
**Duration:** `sample_count × interval_ms / 1000` seconds

---

## Memory Read Command (0x44)

### Request (36 bytes)

| Offset | Size | Field |
|--------|------|-------|
| 0 | 1 | Type: `0x44` |
| 1 | 1 | TID |
| 2 | 2 | Flags: `0x0101` |
| 4 | 32 | Encrypted payload |

**Payload structure (plaintext before encryption):**

| Offset | Size | Field |
|--------|------|-------|
| 0 | 4 | Address (LE) |
| 4 | 4 | Size (LE) |
| 8 | 4 | `0xFFFFFFFF` |
| 12 | 4 | CRC32 of bytes 0-11 |
| 16 | 16 | Padding (`0xFF`) |

### Known Addresses

| Address | Response Type | Size | Description |
|---------|---------------|------|-------------|
| 0x00000420 | 0x1A | 64 | Device info block 1 |
| 0x00004420 | 0x3A | 64 | Device info block 2 |
| 0x03000C00 | 0x40 | 64 | Calibration data |
| 0x40010450 | 0x75 | 12 | Hardware device ID |
| 0x98100000 | 0x34+ | varies | **Offline log data** |

### Response (20 bytes)

| Offset | Size | Field |
|--------|------|-------|
| 0 | 1 | Type: `0xC4` (0x44 | 0x80) |
| 1 | 1 | TID |
| 2 | 2 | Flags (bit 0 = data encrypted) |
| 4 | 4 | Address echo |
| 8 | 4 | Size echo |
| 12 | 4 | `0xFFFFFFFF` |
| 16 | 4 | CRC32 of data |

---

## Data Chunks

After the 0x44 response, data arrives in sequential chunks:

| Packet Type | Hex | Purpose |
|-------------|-----|---------|
| Unknown(52) | 0x34 | Data chunk 1 |
| Unknown(78) | 0x4E | Data chunk 2 |
| Unknown(118) | 0x76 | Data chunk 3 |
| Unknown(104) | 0x68 | Final chunk (may be smaller) |

Each chunk up to 2544 bytes, encrypted with AES-128 ECB.

**Processing:**
1. Concatenate all chunk payloads
2. Decrypt with key `Lh2yfB7n6X7d9a5Z`
3. Parse as 16-byte samples

**Observed download statistics (reading_logs0.11):**
- Duration: 29.5s; 618 packets total (290 requests, 308 responses)
- Unknown68 exchanges: 4; large data chunks: 3 × 2544 bytes
- Total encrypted log data ≈ 7632 bytes (521 samples × 16B)
- Normal ADC polling continued during download (135 GetData ADC)

---

## ADC Log Sample Structure (16 bytes)

| Offset | Size | Type | Field | Unit |
|--------|------|------|-------|------|
| 0 | 4 | i32 | Voltage | µV |
| 4 | 4 | i32 | Current | µA (negative = discharge) |
| 8 | 4 | i32 | Charge_Acc | µAh (accumulated) |
| 12 | 4 | i32 | Energy_Acc | µWh (accumulated) |

**Accumulator relationship:**
```
Charge_Acc[n+1] - Charge_Acc[n] ≈ Current[n] × (interval_sec / 3600)
Energy_Acc[n+1] - Energy_Acc[n] ≈ (V × I) × (interval_sec / 3600)
```

---

## Python Example

```python
from Crypto.Cipher import AES
import struct
import zlib

AES_KEY = b"Lh2yfB7n6X7d9a5Z"

def build_log_request(tid, size):
    address = 0x98100000  # Log marker
    plaintext = struct.pack('<II', address, size)
    plaintext += struct.pack('<I', 0xFFFFFFFF)
    crc = zlib.crc32(plaintext) & 0xFFFFFFFF
    plaintext += struct.pack('<I', crc)
    plaintext += b'\xFF' * 16  # Padding

    cipher = AES.new(AES_KEY, AES.MODE_ECB)
    encrypted = cipher.encrypt(plaintext)

    return bytes([0x44, tid, 0x01, 0x01]) + encrypted

def decrypt_log_data(chunks):
    cipher = AES.new(AES_KEY, AES.MODE_ECB)
    data = cipher.decrypt(b''.join(chunks))
    return data

def parse_log_samples(data):
    samples = []
    for i in range(0, len(data), 16):
        v, i_cur, q, e = struct.unpack_from('<iiii', data, i)
        samples.append({
            'voltage_v': v / 1_000_000,
            'current_a': i_cur / 1_000_000,
            'charge_ah': q / 1_000_000,
            'energy_wh': e / 1_000_000,
        })
    return samples

# Example usage
# 1. Request log metadata
send([0x0C, tid, 0x00, 0x04])  # GetData attr=0x0200
metadata = parse_metadata(read())

# 2. Request log download
data_size = metadata['sample_count'] * 16
send(build_log_request(tid, data_size))
response = read()  # 20-byte ack

# 3. Collect chunks
chunks = []
while True:
    chunk = read()
    if not chunk:
        break
    chunks.append(chunk[4:])  # Skip header

# 4. Decrypt and parse
data = decrypt_log_data(chunks)
samples = parse_log_samples(data)

for i, s in enumerate(samples):
    print(f"{i}: {s['voltage_v']:.3f}V {s['current_a']:.3f}A "
          f"Q={s['charge_ah']:.3f}Ah E={s['energy_wh']:.3f}Wh")
```

---

## Verified Data

From `reading_logs0.11` capture (521 samples @ 10s interval):

```
Sample 0:   5.000V  -1.905A  Q=-5.3mAh    E=-26.4mWh
Sample 100: 9.022V  -0.908A  Q=-276.6mAh  E=-2066.9mWh
Sample 520: 8.989V  -0.099A  Q=-810.3mAh  E=-5747.2mWh
```

**Matches official app display:** -0.8103 Ah, -5.7472 Wh

---

## Open Questions

- **Chunk type sequence:** Is 0x34→0x4E→0x76→0x68 fixed order?
- **Multiple logs:** How to select specific log when multiple exist?
- **Log deletion:** Protocol for clearing logs from device
