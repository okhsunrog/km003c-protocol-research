# Unknown76 Streaming Enable Command

This document describes the Unknown76 (0x4C) command required for AdcQueue streaming on the POWER-Z KM003C.

## TL;DR

- Unknown76 is required before AdcQueue streaming returns samples
- **Payload content doesn't matter** - any 32 bytes work, including all zeros
- Device has an AES-128 encryption oracle but doesn't use it for access control
- Simplest working command: `4c XX 02 00` + 32 zero bytes

## Overview

The KM003C requires an Unknown76 command before AdcQueue streaming will return samples. Without it, `StartGraph` succeeds but returns 0 samples.

**Key finding:** The device does NOT verify the payload content. Any Unknown76 packet enables streaming, regardless of the "session key" value. The AES encryption oracle is likely vestigial DRM that was never fully implemented.

## Packet Structure

### Request (Host -> Device)

| Offset | Size | Field | Description |
|--------|------|-------|-------------|
| 0 | 1 | Type | `0x4C` (76 decimal) |
| 1 | 1 | TID | Transaction ID |
| 2 | 2 | Attribute | `0x0002` (little-endian: `02 00`) |
| 4 | 16 | Challenge | Random/arbitrary 16 bytes |
| 20 | 16 | Session Key | Authentication key |

**Total: 36 bytes**

### Response (Device -> Host)

| Offset | Size | Field | Description |
|--------|------|-------|-------------|
| 0 | 1 | Type | `0x4C` (76 decimal) |
| 1 | 1 | TID | `0x00` |
| 2 | 2 | Attribute | `0x0203` (little-endian) |
| 4 | 16 | Encrypted Challenge | AES(challenge, device_key) |
| 20 | 16 | Encrypted Session Key | AES(session_key, device_key) |

**Total: 36 bytes**

## Cryptographic Mechanism

The device contains a secret AES-128 key and operates as an encryption oracle:

```
Response = AES_ECB_Encrypt(Challenge, DeviceKey) || AES_ECB_Encrypt(SessionKey, DeviceKey)
```

Key properties:
- **ECB mode**: Each 16-byte block is encrypted independently
- **Deterministic**: Same input always produces same output
- **No IV/nonce**: Pure block cipher encryption

## Known Values

### Session Key (required for AdcQueue)

```
e6aac1b12a6ac07c20fde58c7bf517ca
```

When this session key is sent, the device responds with:

```
dd435c1f50918f858aa42eaa33b608b2
```

This appears to be a device identifier or "authorized" marker.

### Example Transaction

**Request:**
```
4c 02 00 02 55 38 81 5b 69 a4 52 c8 3e 54 ef 1d
70 f3 bc 9a e6 aa c1 b1 2a 6a c0 7c 20 fd e5 8c
7b f5 17 ca
```

Breakdown:
- `4c` - Type (76)
- `02` - TID
- `00 02` - Attribute
- `5538815b69a452c83e54ef1d70f3bc9a` - Challenge (arbitrary)
- `e6aac1b12a6ac07c20fde58c7bf517ca` - Session key

**Response:**
```
4c 00 03 02 88 82 f4 24 b5 09 9f 86 d7 91 97 3a
7a 98 79 47 dd 43 5c 1f 50 91 8f 85 8a a4 2e aa
33 b6 08 b2
```

Breakdown:
- `4c` - Type (76)
- `00` - TID
- `03 02` - Attribute
- `8882f424b5099f86d791973a7a987947` - AES(challenge)
- `dd435c1f50918f858aa42eaa33b608b2` - AES(session_key) = Device ID

## Minimal Working Command

The simplest command that enables streaming:

```
4c 02 02 00 00 00 00 00 00 00 00 00 00 00 00 00
00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
00 00 00 00
```

The device responds with `06 02 00 00` (Reject), but streaming is enabled anyway.

## Mtools.exe Reverse Engineering

Analysis of the official ChargerLAB software (Mtools.exe) reveals:

### AES Key Location

The AES key is embedded in the binary at address `0x140184b60`:

```
Full string: "XwcPWtquq0yNVdaQjaFO7LFa0b4tA25f4R038azbeXoxQ41po940gl90mNGZmdRv"
Key offset: 0x16 (22), length: 0x10 (16)
Encryption key: "Fa0b4tA25f4R038a"
Decryption key: "FX0b4tA25f4R038a" (byte[1] modified to 'X')
```

**Verified working** - tested encryption/decryption matches device responses exactly.

### Actual Protocol (from `send_auth_packet_and_verify`)

The official software constructs the challenge as:

| Offset | Size | Content |
|--------|------|---------|
| 0 | 8 | Timestamp (QDateTime::toMSecsSinceEpoch) |
| 8 | 8 | Device-specific data |
| 16 | 8 | Random data (QRandomGenerator64) |

This 24-byte plaintext is AES-encrypted to 32 bytes (with padding).

### Verification Flow

The software DOES verify the response:
1. Decrypts device response using modified key (`FX0b4tA25f4R038a` - byte[1] = 'X')
2. Checks if decrypted timestamp matches original
3. Checks if decrypted random data matches original

This proves the device has the same AES key (device authenticity check).

### Why Any Payload Works

Although the software verifies responses, the **device doesn't enforce** the key:
- Device encrypts whatever is sent (acts as encryption oracle)
- Device enables streaming regardless of payload content
- The verification only happens on the host side

## Purpose (Revised)

Originally appears to be **DRM/license protection**, but testing reveals:

1. **Feature gating**: AdcQueue streaming requires Unknown76, but content doesn't matter
2. **Host-side only verification**: Software checks device authenticity, but device doesn't check host
3. **Vestigial enforcement**: The AES encryption oracle exists but device doesn't gate features on it

The official ChargerLAB software:
- Sends properly encrypted challenge with timestamp + random
- Verifies device response to confirm genuine hardware
- But the device enables streaming even without valid challenge

## Firmware Implementation (FUN_0004eaf0 case 0x4C)

The authentication handler is in the main USB dispatcher at **0x0004eaf0**:

### Handler Flow

```c
case 0x4c:
    // 1. Set AES key prefix to 0x6146 ("aF" - part of "Fa0b4tA25f4R038a")
    _DAT_20000748 = 0x6146;

    // 2. Encrypt the input challenge (FUN_00000fb0 uses hardware AES at 0x40008010)
    iVar2 = FUN_00000fb0(input_buffer, size, &key, &output);
    if (iVar2 != 0) goto REJECT;

    // 3. Copy result and verify against device-specific values
    FUN_000003cc(&local_38, &DAT_20010b00, 0x20);

    // 4. Check if decrypted matches hardware device ID (0x40010450-0x40010458)
    if ((local_30 == _DAT_40010450) &&
        (local_2c == _DAT_40010454) &&
        (local_28 == _DAT_40010458)) {
        DAT_20004041 = 1;  // Authentication level 1
    }
    else {
        // 5. Or check against calibration data (0x03000c00/0x03000d80)
        if (matches_calibration_data) {
            DAT_20004041 = 2;  // Authentication level 2
        }
    }

    // 6. Build response with auth level
    _DAT_20010b00 = CONCAT22((DAT_20004041 & 3) << 1, 0x4c) | 0x2010000;

    // 7. Modify key (prepend 0x58 = 'X') for decryption key variant
    _DAT_20000748 = CONCAT11(0x58, DAT_20000748);  // 'a' -> 'X'

    // 8. Encrypt response using modified key
    FUN_00001090(&local_38, 0x20, &DAT_20000748, &DAT_20010b04);
```

### Key Addresses

| Address | Purpose |
|---------|---------|
| FUN_00000fb0 | AES encrypt (hardware crypto, uRam42100004=1) |
| FUN_00001090 | AES decrypt (hardware crypto, uRam42100004=0) |
| 0x40008010 | Hardware AES input register |
| 0x40008020 | Hardware AES key register |
| DAT_20004041 | Authentication level (0=none, 1=device, 2=calibration) |
| 0x40010450 | Hardware device ID (12 bytes) |
| 0x03000c00 | Calibration data table |

### Key Transformation

The firmware confirms the Mtools.exe reverse engineering:
- Encryption key base: `0x6146` → `Fa0b4tA25f4R038a`
- For decryption: byte[1] changed from `0x61` ('a') to `0x58` ('X')
- Decryption key: `FX0b4tA25f4R038a`

This matches the observed behavior where the device returns the challenge encrypted with a slightly different key.

### Authentication Flag Usage (DAT_20004041)

The authentication level is checked in other command handlers:

```c
// In case 0x4a (Flash Write) - requires auth level > 0
if (((DAT_20004041 == 0) || (0x100 < size)) ||
    ((0x3ff000 < size + address || ((address & 0xfff80000) != 0x300000))))
    goto REJECT;

// In FUN_0004286c (GetData handler) - affects attribute mask
if (auth_level == 0) {
    param_2 = param_2 & 0x19;  // Limit to basic attributes
}

// In case 0x4d - requires auth level 2
if (DAT_20004041 == 2) {
    // Allow operation
} else {
    goto REJECT;
}
```

**Authentication levels:**
- **0**: Unauthenticated - basic ADC/PD data only
- **1**: Device-authenticated - flash write, extended attributes
- **2**: Calibration-authenticated - factory/calibration commands

## Practical Usage

### Python Example (Full Authentication)

```python
from Crypto.Cipher import AES
import struct
import time

AES_KEY_ENC = b"Fa0b4tA25f4R038a"  # For encrypting challenge
AES_KEY_DEC = b"FX0b4tA25f4R038a"  # For decrypting response

def build_unknown76_packet(tid=0x02):
    # Build challenge: timestamp + device_id + random
    timestamp = int(time.time() * 1000)
    device_id = b"071KBP\r\xff"  # 8 bytes
    random_data = bytes([0x11, 0x0a, 0xff, 0xff, 0x00, 0x00, 0x00, 0x00])

    plaintext = struct.pack('<Q', timestamp) + device_id + random_data
    plaintext = plaintext + bytes(32 - len(plaintext))  # Pad to 32 bytes

    cipher = AES.new(AES_KEY_ENC, AES.MODE_ECB)
    ciphertext = cipher.encrypt(plaintext)

    header = bytes([0x4C, tid, 0x00, 0x02])
    return header + ciphertext, timestamp

def verify_response(response, expected_timestamp):
    if len(response) < 36 or (response[0] & 0x7F) != 0x4C:
        return False

    cipher = AES.new(AES_KEY_DEC, AES.MODE_ECB)
    decrypted = cipher.decrypt(response[4:36])
    dec_timestamp = struct.unpack('<Q', decrypted[0:8])[0]

    return dec_timestamp == expected_timestamp
```

### Minimal (Any Payload Works)

Since the device doesn't enforce the key, this also works:

```python
# Simplest working packet - device enables streaming regardless
unknown76_minimal = bytes([0x4C, 0x02, 0x00, 0x02]) + bytes(32)
```

## Minimal AdcQueue Sequence

```
1. Connect (0x02)      -> Required, rejected without it
2. Unknown76 (0x4C)    -> Required, 0 samples without it
3. StartGraph (0x0E)   -> Start streaming at specified rate
4. GetData (0x0C)      -> Poll for AdcQueue samples (attr=0x0002)
5. StopGraph (0x0F)    -> Stop streaming
```

## Unknown68 (0x44) - Memory Download (Not Required for AdcQueue)

Unknown68 is **not required** for AdcQueue streaming but is used for other features:

**Purpose:** Memory download/read command for accessing device data at specific addresses.

**Fully reversed:** See [offline_log_protocol.md](offline_log_protocol.md) for complete protocol documentation.

**Key Details:**
- AES-128 ECB encrypted request payload
- Key: `Lh2yfB7n6X7d9a5Z` (key index 0)
- Request: 36 bytes (4B header + 32B encrypted payload with address/size/CRC32)
- Response: 20 bytes (4B header + 16B plaintext echo with data CRC32)

**Known Memory Addresses:**
| Address | Response Type | Description |
|---------|---------------|-------------|
| 0x420 | 0x1A | Device info block 1 (64 bytes) |
| 0x4420 | 0x3A | Device info block 2 (64 bytes) |
| 0x3000C00 | 0x40 | Calibration data (64 bytes) |
| 0x40010450 | 0x75 | Unknown (12 bytes) |
| 0x98100000 | 0x34/4E/76/68 | Offline ADC log data (encrypted chunks) |

## Interface Compatibility

| Feature | Vendor Interface | HID Interface |
|---------|-----------------|---------------|
| Simple ADC | Works | Works |
| AdcQueue + Auth | Works | Fails (Connect timeout) |

The authentication and streaming features only work over the vendor bulk interface (interface 0, endpoints 0x01/0x81), not HID.
