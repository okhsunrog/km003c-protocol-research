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

**Key finding:** The device DOES verify the payload for 0x4C. The plaintext (before encryption) must contain the 12-byte HardwareID from address 0x40010450. Without this, AdcQueue streaming returns empty responses.

---

## Command 0x4C: StreamingAuth

Required before AdcQueue streaming. The device decrypts the payload and checks it against the HardwareID stored in memory.

### Request (36 bytes)

| Offset | Size | Field | Description |
|--------|------|-------|-------------|
| 0 | 1 | Type | `0x4C` |
| 1 | 1 | TID | Transaction ID |
| 2 | 2 | Attribute | `0x0002` (LE) |
| 4 | 32 | Encrypted Payload | AES-128-ECB encrypted (see below) |

### Plaintext Structure (32 bytes, before encryption)

| Offset | Size | Field | Required |
|--------|------|-------|----------|
| 0 | 8 | Timestamp | Any value (not checked) |
| 8 | 12 | HardwareID | **MUST match** 0x40010450 |
| 20 | 12 | Padding/Random | Any value (not checked) |

**Encryption key:** `Fa0b4tA25f4R038a`

### HardwareID Structure (12 bytes at 0x40010450)

The HardwareID is a 12-byte authentication blob stored in device memory. It is **NOT a serial number** - the real serial is `serial_id` in CalibrationData at 0x3000C00 (e.g., "007965").

| Offset | Size | Field | Example |
|--------|------|-------|---------|
| 0 | 6 | Identifier | `"071KBP"` (ASCII, not a serial) |
| 6 | 2 | Separator | `0x0D 0xFF` |
| 8 | 2 | Device ID | `0x0A11` (LE) = 2577 |
| 10 | 2 | Padding | `0xFFFF` |

Each device has a unique HardwareID. To authenticate, you must either:
1. Read it first using MemoryRead (0x44) at address 0x40010450
2. Or know it from a previous capture

### Response (36 bytes)

| Offset | Size | Field | Description |
|--------|------|-------|-------------|
| 0 | 1 | Type | `0x4C` |
| 1 | 1 | TID | Always `0x00` |
| 2 | 2 | Attribute | Auth result (see below) |
| 4 | 32 | Encrypted Payload | AES(input_payload, device_key) |

### Response Attribute Values

| Value | Meaning | AdcQueue |
|-------|---------|----------|
| 0x0201 | Auth failed (HardwareID mismatch) | Empty responses |
| 0x0203 | Auth success (Level 1) | Works |

The device acts as an AES-128-ECB encryption oracle - it encrypts whatever payload is sent and returns the ciphertext. However, auth level is determined by whether the decrypted plaintext matches the HardwareID.

### Cryptographic Details

**Keys (from Mtools.exe at 0x140184b60):**

| Usage | Key |
|-------|-----|
| Encrypt (host→device) | `Fa0b4tA25f4R038a` |
| Decrypt (device→host) | `FX0b4tA25f4R038a` (byte[1] = 'X') |

**Device operation:**
1. Receive 32-byte encrypted payload
2. Decrypt with key `Fa0b4tA25f4R038a`
3. Compare bytes 8-19 against HardwareID at 0x40010450
4. If match: set auth level 1 (attr bit 1)
5. Re-encrypt payload and return

### What Mtools.exe Does

The official software:
1. Reads HardwareID from device (via MemoryRead 0x44 at 0x40010450)
2. Constructs plaintext: `[timestamp 8B][HardwareID 12B][random 12B]`
3. Encrypts with `Fa0b4tA25f4R038a`
4. Sends to device
5. Decrypts response with `FX0b4tA25f4R038a`
6. Verifies decrypted timestamp matches (proves device authenticity)

---

## Command 0x44: MemoryRead

Used for downloading device data (logs, calibration, device info).

### Request (36 bytes)

| Offset | Size | Field | Description |
|--------|------|-------|-------------|
| 0 | 1 | Type | `0x44` |
| 1 | 1 | TID | Transaction ID |
| 2 | 2 | Attribute | `0x0101` (LE) |
| 4 | 32 | Encrypted Payload | AES-128 ECB encrypted request |

**Encrypted payload structure (32 bytes plaintext):**

| Offset | Size | Field |
|--------|------|-------|
| 0 | 4 | Address (LE) |
| 4 | 4 | Size (LE) |
| 8 | 4 | Magic: 0xFFFFFFFF |
| 12 | 4 | CRC32 of bytes 0-11 |
| 16 | 16 | Padding (0xFF × 16) |

**Key:** `Lh2yfB7n6X7d9a5Z`

**CRC32 calculation:** Standard CRC32 over address + size + magic (12 bytes).

### Response

Two packets are returned:

**Confirmation (20 bytes):**

| Offset | Size | Field | Description |
|--------|------|-------|-------------|
| 0 | 1 | Type | `0xC4` (0x44 \| 0x80) |
| 1 | 1 | TID | Echo |
| 2 | 2 | Attribute | Echo |
| 4 | 4 | Address | Echo |
| 8 | 4 | Size | Echo |
| 12 | 8 | Reserved | |

**Data packet (varies):**

The data response is AES-128-ECB encrypted using `MEMORY_READ_KEY` (`Lh2yfB7n6X7d9a5Z`).
The encryption flag is indicated by bit 0 of byte 2 in the confirmation response.

| Offset | Size | Field |
|--------|------|-------|
| 0 | N×16 | Encrypted blocks | AES-encrypted data (N = ceil(requested_size / 16)) |

**AES block alignment:** Responses are always padded to 16-byte boundaries. For example:
- Request 12 bytes → receive 16 bytes (1 block)
- Request 64 bytes → receive 64 bytes (4 blocks)

**Note:** The first byte of the encrypted response may appear to be a "type byte" (e.g., 0x75),
but this is coincidental - the entire response must be decrypted as 16-byte blocks.

### Known Memory Addresses

| Address | Size | Description |
|---------|------|-------------|
| 0x420 | 64 | Device info block 1 |
| 0x4420 | 64 | Firmware info |
| 0x3000C00 | 64 | Calibration data |
| 0x40010450 | 12 | HardwareID (for auth) |
| 0x98100000 | varies | Offline ADC log data |

See [Offline Logs](offline_logs.md) for the log download protocol.

---

### Memory Block Layouts (after decryption)

| Name | Address | Size | Fields |
|------|---------|------|--------|
| DeviceInfo1 | 0x420 | 64 | 0x00..0x0F reserved; 0x10 12B model (e.g., "KM003C"); 0x1C 12B HW version (e.g., "2.1"); 0x28 24B mfg date (e.g., "2022.11.7") |
| FirmwareInfo | 0x4420 | 64 | 0x00 u32 magic (0x00004000 or 0xFFFFFFFF if invalid); 0x04 u32 reserved; 0x08 u32 counter/ID; 0x0C 4B random; 0x10 12B model; 0x1C 12B FW version (e.g., "1.9.9"); 0x28 12B FW date (e.g., "2025.9.22"); 0x34 u32 build number; 0x38 8B reserved |
| CalibrationData | 0x3000C00 | 64 | 0x00 7B serial ID (e.g., "007965 "); 0x07 32B UUID/hash (e.g., "CDFDDF2886FD40AF8F05E149624C3892"); 0x27 1B space; 0x28 11B timestamp (Unix epoch ASCII); 0x33 1B space; 0x34 4B marker ("LYS5"); 0x38 8B reserved (0xFF) |
| HardwareID | 0x40010450 | 12 | Authentication blob (NOT a serial): 0x00 6B identifier (e.g., "071KBP"); 0x06 2B separator (0x0D 0xFF); 0x08 2B device ID (e.g., 0x0A11); 0x0A 2B padding (0xFF 0xFF) |

---

## Authentication Levels

The firmware (at `DAT_20004041`) tracks three authentication levels:

| Level | Name | Access |
|-------|------|--------|
| 0 | Unauthenticated | Basic ADC, PD data only |
| 1 | Device-authenticated | AdcQueue, flash write, extended attributes |
| 2 | Calibration-authenticated | Factory/calibration commands |

### Level Determination

From firmware at `FUN_0004eaf0` case 0x4C:

```c
// Decrypt payload with AES key
// Check bytes 8-19 against HardwareID (0x40010450, 12 bytes)
if (memcmp(&decrypted[8], (void*)0x40010450, 12) == 0) {
    DAT_20004041 = 1;  // Level 1 - device authenticated
}
// Or check against calibration data (0x03000c00)
else if (decrypted matches calibration_data) {
    DAT_20004041 = 2;  // Level 2
}
```

### Level Enforcement

```c
// Flash Write (0x4A) - requires level > 0
if (DAT_20004041 == 0) goto REJECT;

// GetData handler - limits attributes at level 0
if (auth_level == 0) {
    param_2 = param_2 & 0x19;  // ADC, Settings, PD only
}
// At level 1+: AdcQueue (0x02) is allowed

// Command 0x4D - requires level 2
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
| 0x40010450 | HardwareID (12 bytes) |
| 0x03000c00 | Calibration data table |

### Key Transformation

Firmware confirms Mtools.exe analysis:
- Encryption key base: `Fa0b4tA25f4R038a`
- For decryption: byte[1] changed from `0x61` ('a') to `0x58` ('X')
- Decryption key: `FX0b4tA25f4R038a`

---

## Python Examples

### StreamingAuth (0x4C)

```python
from Crypto.Cipher import AES
import struct
import time
import os

AES_KEY_ENC = b"Fa0b4tA25f4R038a"
AES_KEY_DEC = b"FX0b4tA25f4R038a"

def build_auth_packet(hardware_id: bytes, tid: int = 0x02) -> bytes:
    """
    Build StreamingAuth packet.

    Args:
        hardware_id: 12-byte HardwareID from 0x40010450
        tid: Transaction ID

    Returns:
        36-byte packet ready to send
    """
    assert len(hardware_id) == 12, "HardwareID must be 12 bytes"

    # Build 32-byte plaintext
    timestamp = struct.pack('<Q', int(time.time() * 1000))
    padding = os.urandom(12)
    plaintext = timestamp + hardware_id + padding

    # Encrypt
    cipher = AES.new(AES_KEY_ENC, AES.MODE_ECB)
    ciphertext = cipher.encrypt(plaintext)

    # Build packet: type + tid + attr + encrypted_payload
    return bytes([0x4C, tid, 0x00, 0x02]) + ciphertext

def parse_auth_response(response: bytes) -> dict:
    """Parse StreamingAuth response."""
    if len(response) < 36 or (response[0] & 0x7F) != 0x4C:
        return {"success": False, "error": "Invalid response"}

    attr = int.from_bytes(response[2:4], 'little')

    # Decrypt payload
    cipher = AES.new(AES_KEY_DEC, AES.MODE_ECB)
    decrypted = cipher.decrypt(response[4:36])

    return {
        "success": (attr & 0x02) != 0,  # Bit 1 = AdcQueue enabled
        "attr": attr,
        "auth_level": 1 if (attr & 0x02) else 0,
        "decrypted_timestamp": struct.unpack('<Q', decrypted[0:8])[0],
    }

# Example usage:
# hardware_id = bytes.fromhex('3037314b42500dff110affff')  # "071KBP" device
# packet = build_auth_packet(hardware_id)
# response = send_to_device(packet)
# result = parse_auth_response(response)
# print(f"Auth success: {result['success']}")
```

### Memory Read (0x44)

```python
from Crypto.Cipher import AES
import struct
import binascii

AES_KEY_MEM = b"Lh2yfB7n6X7d9a5Z"

def build_memory_read(address: int, size: int, tid: int = 0x02) -> bytes:
    """
    Build MemoryRead packet.

    Args:
        address: Memory address to read
        size: Number of bytes to read
        tid: Transaction ID

    Returns:
        36-byte packet ready to send
    """
    # Build 32-byte plaintext
    plaintext = bytearray(32)
    struct.pack_into('<I', plaintext, 0, address)
    struct.pack_into('<I', plaintext, 4, size)
    struct.pack_into('<I', plaintext, 8, 0xFFFFFFFF)  # Magic

    # CRC32 over first 12 bytes
    crc = binascii.crc32(bytes(plaintext[0:12])) & 0xFFFFFFFF
    struct.pack_into('<I', plaintext, 12, crc)

    # Pad bytes 16-31 with 0xFF
    for i in range(16, 32):
        plaintext[i] = 0xFF

    # Encrypt
    cipher = AES.new(AES_KEY_MEM, AES.MODE_ECB)
    encrypted = cipher.encrypt(bytes(plaintext))

    return bytes([0x44, tid, 0x01, 0x01]) + encrypted

def read_hardware_id(send_fn) -> bytes:
    """
    Read HardwareID from device memory.

    Args:
        send_fn: Function that sends packet and returns response

    Returns:
        12-byte HardwareID
    """
    packet = build_memory_read(0x40010450, 12)

    # First response is confirmation
    confirm = send_fn(packet)
    if confirm[0] != 0xC4:
        raise Exception(f"Unexpected confirmation: 0x{confirm[0]:02X}")

    # Second response is encrypted data (16 bytes)
    encrypted = send_fn(bytes(4))  # Dummy read to get data packet
    if len(encrypted) != 16:
        raise Exception(f"Expected 16-byte encrypted block, got {len(encrypted)}")

    # Decrypt entire 16-byte block with MEMORY_READ_KEY
    cipher = AES.new(AES_KEY_MEM, AES.MODE_ECB)
    decrypted = cipher.decrypt(encrypted)

    # HardwareID is the first 12 bytes of decrypted data
    return decrypted[0:12]
```

### Complete Example

```python
def authenticate_device(dev):
    """Complete authentication flow for AdcQueue streaming."""

    def send_recv(data):
        dev.write(0x01, data)
        return bytes(dev.read(0x81, 1024, timeout=2000))

    # 1. Connect
    send_recv(bytes([0x02, 0x01, 0x00, 0x00]))

    # 2. Read HardwareID
    hardware_id = read_hardware_id(send_recv)
    print(f"HardwareID: {hardware_id.hex()}")

    # 3. Send StreamingAuth
    auth_packet = build_auth_packet(hardware_id)
    response = send_recv(auth_packet)
    result = parse_auth_response(response)

    if not result['success']:
        raise Exception("Authentication failed")

    print("Authentication successful - AdcQueue enabled")
    return True
```

---

## Interface Compatibility

| Feature | Vendor Bulk (IF0) | HID (IF3) |
|---------|-------------------|-----------|
| Simple ADC | Works | Works |
| AdcQueue + Auth | Works | Fails (Connect timeout) |
| Memory Read | Works | Untested |

Authentication and streaming only work over Interface 0 (vendor bulk).
