# Authentication

This document covers the authentication mechanisms on the KM003C: streaming auth (0x4C) and memory access (0x44).

For packet header formats, see [Protocol Reference](../protocol_reference.md).

---

## Overview

The KM003C has two authentication-related commands:

| Command | Name | Purpose |
|---------|------|---------|
| 0x4C | StreamingAuth | Enable AdcQueue streaming |
| 0x44 | MemoryRead | Access device memory (logs, calibration) |

**Key finding:** The device does NOT verify payload content for 0x4C. Any Unknown76 packet enables streaming, regardless of the "session key" value. The host software verifies, but the device doesn't enforce.

---

## Command 0x4C: StreamingAuth

### Request (36 bytes)

| Offset | Size | Field | Description |
|--------|------|-------|-------------|
| 0 | 1 | Type | `0x4C` |
| 1 | 1 | TID | Transaction ID |
| 2 | 2 | Attribute | `0x0002` (LE) |
| 4 | 16 | Challenge | Random/arbitrary 16 bytes |
| 20 | 16 | Session Key | Authentication key |

### Response (36 bytes)

| Offset | Size | Field | Description |
|--------|------|-------|-------------|
| 0 | 1 | Type | `0x4C` |
| 1 | 1 | TID | `0x00` |
| 2 | 2 | Attribute | Auth level in bits (see below) |
| 4 | 16 | Encrypted Challenge | AES(challenge, device_key) |
| 20 | 16 | Encrypted Session Key | AES(session_key, device_key) |

### Minimal Working Command

The simplest packet that enables streaming (device responds 0x06 Reject but streaming works):

```
4c 02 02 00 00 00 00 00 00 00 00 00 00 00 00 00
00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
00 00 00 00
```

### Cryptographic Details

The device acts as an AES-128 ECB encryption oracle:

```
Response = AES_ECB_Encrypt(Challenge, DeviceKey) || AES_ECB_Encrypt(SessionKey, DeviceKey)
```

**Keys (from Mtools.exe at 0x140184b60):**

| Usage | Key |
|-------|-----|
| Encrypt (host→device) | `Fa0b4tA25f4R038a` |
| Decrypt (device→host) | `FX0b4tA25f4R038a` (byte[1] = 'X') |

### Official Protocol (Mtools.exe)

The official software constructs challenge as:

| Offset | Size | Content |
|--------|------|---------|
| 0 | 8 | Timestamp (QDateTime::toMSecsSinceEpoch) |
| 8 | 8 | Device-specific data |
| 16 | 8 | Random (QRandomGenerator64) |

This 24-byte plaintext is AES-encrypted to 32 bytes.

**Verification flow:**
1. Decrypt response using modified key (`FX...`)
2. Check decrypted timestamp matches original
3. Check decrypted random matches original

This proves the device has the correct AES key (authenticity check).

### Why Any Payload Works

- Device encrypts whatever is sent (acts as encryption oracle)
- Device enables streaming regardless of payload content
- Verification only happens on host side
- Vestigial DRM that was never enforced on device

---

## Command 0x44: MemoryRead

Used for downloading device data (logs, calibration, device info).

### Request (36 bytes)

| Offset | Size | Field | Description |
|--------|------|-------|-------------|
| 0 | 1 | Type | `0x44` |
| 1 | 1 | TID | Transaction ID |
| 2 | 2 | Attribute | Varies by target |
| 4 | 32 | Encrypted Payload | AES-128 ECB encrypted request |

**Encrypted payload structure (32 bytes plaintext):**

| Offset | Size | Field |
|--------|------|-------|
| 0 | 4 | Address (LE) |
| 4 | 4 | Size (LE) |
| 8 | 4 | Magic: 0xFFFFFFFF |
| 12 | 4 | CRC32 of bytes 0-11 |
| 16 | 16 | Padding (0xFF × 16) |

**Key:** `Lh2yfB7n6X7d9a5Z` (key index 0)

**CRC32 calculation:** Standard CRC32 over address + size + magic (12 bytes).

### Response (20 bytes)

| Offset | Size | Field | Description |
|--------|------|-------|-------------|
| 0 | 1 | Type | Response type (varies) |
| 1 | 1 | TID | `0x00` |
| 2 | 2 | Attribute | Echo |
| 4 | 16 | Payload | Plaintext with data CRC32 |

### Known Memory Addresses

| Address | Response Type | Size | Description |
|---------|---------------|------|-------------|
| 0x420 | 0x1A | 64 | Device info block 1 |
| 0x4420 | 0x3A | 64 | Device info block 2 |
| 0x3000C00 | 0x40 | 64 | Calibration data |
| 0x40010450 | 0x75 | 12 | Hardware device ID |
| 0x98100000 | 0x34/4E/76/68 | varies | Offline ADC log data |

See [Offline Logs](offline_logs.md) for the log download protocol.

---

## Authentication Levels

The firmware (at `DAT_20004041`) tracks three authentication levels:

| Level | Name | Access |
|-------|------|--------|
| 0 | Unauthenticated | Basic ADC, PD data only |
| 1 | Device-authenticated | Flash write, extended attributes |
| 2 | Calibration-authenticated | Factory/calibration commands |

### Level Determination

From firmware at `FUN_0004eaf0` case 0x4C:

```c
// Check against hardware device ID (0x40010450-0x40010458)
if (decrypted matches hardware_id) {
    DAT_20004041 = 1;  // Level 1
}
// Or check against calibration data (0x03000c00)
else if (decrypted matches calibration_data) {
    DAT_20004041 = 2;  // Level 2
}
```

### Level Enforcement

```c
// Flash Write (0x4a) - requires level > 0
if (DAT_20004041 == 0) goto REJECT;

// GetData handler - limits attributes at level 0
if (auth_level == 0) {
    param_2 = param_2 & 0x19;  // Basic attributes only
}

// Command 0x4d - requires level 2
if (DAT_20004041 != 2) goto REJECT;
```

---

## Firmware Implementation

### Key Addresses

| Address | Purpose |
|---------|---------|
| FUN_00000fb0 | AES encrypt (hardware crypto) |
| FUN_00001090 | AES decrypt (hardware crypto) |
| 0x40008010 | Hardware AES input register |
| 0x40008020 | Hardware AES key register |
| DAT_20004041 | Authentication level (0/1/2) |
| 0x40010450 | Hardware device ID (12 bytes) |
| 0x03000c00 | Calibration data table |

### Key Transformation

Firmware confirms Mtools.exe analysis:
- Encryption key base: `0x6146` -> `Fa0b4tA25f4R038a`
- For decryption: byte[1] changed from `0x61` ('a') to `0x58` ('X')
- Decryption key: `FX0b4tA25f4R038a`

---

## Python Examples

### Full Authentication

```python
from Crypto.Cipher import AES
import struct
import time

AES_KEY_ENC = b"Fa0b4tA25f4R038a"
AES_KEY_DEC = b"FX0b4tA25f4R038a"

def build_auth_packet(tid=0x02):
    timestamp = int(time.time() * 1000)
    device_id = b"071KBP\r\xff"  # 8 bytes
    random_data = bytes(8)

    plaintext = struct.pack('<Q', timestamp) + device_id + random_data
    plaintext = plaintext + bytes(32 - len(plaintext))

    cipher = AES.new(AES_KEY_ENC, AES.MODE_ECB)
    ciphertext = cipher.encrypt(plaintext)

    return bytes([0x4C, tid, 0x00, 0x02]) + ciphertext, timestamp

def verify_response(response, expected_timestamp):
    if len(response) < 36 or (response[0] & 0x7F) != 0x4C:
        return False

    cipher = AES.new(AES_KEY_DEC, AES.MODE_ECB)
    decrypted = cipher.decrypt(response[4:36])
    dec_timestamp = struct.unpack('<Q', decrypted[0:8])[0]

    return dec_timestamp == expected_timestamp
```

### Minimal (Any Payload Works)

```python
# Simplest working packet - streaming enabled regardless
auth_minimal = bytes([0x4C, 0x02, 0x00, 0x02]) + bytes(32)
```

### Memory Read

```python
from Crypto.Cipher import AES
import struct
import binascii

AES_KEY = b"Lh2yfB7n6X7d9a5Z"

def build_memory_read(address, size, tid=0x02):
    # Build 32-byte plaintext
    plaintext = bytearray(32)
    struct.pack_into('<I', plaintext, 0, address)
    struct.pack_into('<I', plaintext, 4, size)
    struct.pack_into('<I', plaintext, 8, 0xFFFFFFFF)  # Magic

    # CRC32 over first 12 bytes (addr + size + magic)
    crc = binascii.crc32(bytes(plaintext[0:12])) & 0xFFFFFFFF
    struct.pack_into('<I', plaintext, 12, crc)

    # Pad bytes 16-31 with 0xFF
    for i in range(16, 32):
        plaintext[i] = 0xFF

    cipher = AES.new(AES_KEY, AES.MODE_ECB)
    encrypted = cipher.encrypt(bytes(plaintext))

    return bytes([0x44, tid, 0x01, 0x01]) + encrypted
```

---

## Interface Compatibility

| Feature | Vendor Bulk (IF0) | HID (IF3) |
|---------|-------------------|-----------|
| Simple ADC | Works | Works |
| AdcQueue + Auth | Works | Fails (Connect timeout) |
| Memory Read | Works | Untested |

Authentication and streaming only work over Interface 0 (vendor bulk).
