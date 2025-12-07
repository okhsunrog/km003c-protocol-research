# KM003C Unknown Commands Tracker

This document tracks the status of all command types and attributes in the KM003C protocol, identifying what's fully implemented in `km003c-lib` vs what remains unknown or partially understood.

## Command Coverage Summary

| Type | Hex | Name | Status | Source Files | Notes |
|------|-----|------|--------|--------------|-------|
| 0x00 | ? | Unknown | fw_update | Bootloader? |
| 0x01 | Sync | Unknown | fw_update | Bootloader sync? |
| 0x02 | Connect | **Implemented** | all normal captures | Session start (optional for AdcQueue) |
| 0x03 | Disconnect | **Implemented** | adc_*, open_close, pd_adcqueue, with_pd | |
| 0x04 | Reset | Unknown | fw_update | Device-level reset? |
| 0x05 | Accept | **Implemented** | all captures | Response to commands |
| 0x06 | Rejected | **Implemented** | fw_update, pd_adcqueue | Error response |
| 0x07 | Finished | Unknown | fw_update | Bootloader? |
| 0x08 | JumpAprom | Unknown | fw_update | Bootloader: jump to app? |
| 0x09 | JumpDfu | Unknown | fw_update | Bootloader: jump to DFU? |
| 0x0B | Error | Unknown | fw_update | Error response? |
| 0x0C | GetData | **Implemented** | all normal captures | Request data by attribute mask |
| 0x0D | GetFile | Unknown | fw_update | File download? |
| 0x0E | StartGraph | **Implemented** | adc_*, pd_adcqueue | Start AdcQueue streaming |
| 0x0F | StopGraph | **Implemented** | all normal captures | Stop AdcQueue streaming |
| 0x10 | EnablePdMonitor | **Documented** | pd_capture, pd_epr0, with_pd | Enable PD sniffer mode |
| 0x11 | DisablePdMonitor | **Documented** | fw_update, pd_capture, pd_epr0, with_pd | Disable PD sniffer mode |
| 0x1A | DeviceInfo1 | **Fully Reversed** | all normal captures | Device info: model, HW ver, mfg date |
| 0x2C | FirmwareInfo2 | **Fully Reversed** | adc_*, open_close, rust_simple, with_pd, fw_update | FW info (attr=0x564D) |
| 0x34 | LogDataChunk1 | **Documented** | reading_logs, fw_update | Offline log chunk 1 (2544B) |
| 0x3A | FirmwareInfo | **Fully Reversed** | new_adcsimple, fw_update | FW version, build date |
| 0x40 | CalibrationData | **Fully Reversed** | all normal captures | Serial, UUID, timestamp |
| 0x41 | PutData | **Implemented** | all captures | Data response with logical packets |
| 0x44 | MemoryDownload | **Fully Reversed** | all normal captures | Memory download request |
| 0x4C | StreamingAuth | **Fully Reversed** | all normal captures | Required for AdcQueue streaming |
| 0x4E | LogDataChunk2 | **Documented** | reading_logs, fw_update | Offline log chunk 2 (2544B) |
| 0x68 | LogDataChunk4 | **Documented** | reading_logs, fw_update | Offline log chunk 4 (704B) |
| 0x75 | DeviceSerial | **Fully Reversed** | all normal captures | Serial prefix + device ID |
| 0x76 | LogDataChunk3 | **Documented** | reading_logs, fw_update | Offline log chunk 3 (2544B) |

### Firmware Update Only Commands (0x14-0x7E)

These commands appear **only** in `updating_firmware.*` captures and are likely bootloader/DFU protocol:

| Type | Hex | Count | Notes |
|------|-----|-------|-------|
| 0x14 | ? | 1 | |
| 0x15 | ? | 2 | |
| 0x1C | ? | 1 | |
| 0x1D | ? | 1 | |
| 0x1F | ? | 2 | |
| 0x20 | ? | 1 | |
| 0x22 | ? | 1 | |
| 0x23 | ? | 2 | |
| 0x24 | ? | 2 | |
| 0x26 | ? | 1 | |
| 0x27 | ? | 2 | |
| 0x28 | ? | 2 | |
| 0x2B | ? | 2 | |
| 0x2E | ? | 2 | |
| 0x30 | ? | 2 | |
| 0x32 | ? | 1 | |
| 0x33 | ? | 1 | |
| 0x36 | ? | 1 | |
| 0x38 | ? | 2 | |
| 0x39 | ? | 1 | |
| 0x3C | ? | 1 | |
| 0x42 | ? | 1 | |
| 0x46 | ? | 1 | |
| 0x47 | ? | 1 | |
| 0x4B | ? | 1 | |
| 0x4F | ? | 3 | |
| 0x50 | ? | 2 | |
| 0x52 | ? | 3 | |
| 0x54 | ? | 2 | |
| 0x56 | ? | 1 | |
| 0x58 | ? | 2 | |
| 0x59 | ? | 2 | |
| 0x5B | ? | 1 | |
| 0x5C | ? | 2 | |
| 0x5E | ? | 3 | |
| 0x60 | ? | 1 | |
| 0x61 | ? | 1 | |
| 0x63 | ? | 1 | |
| 0x64 | ? | 1 | |
| 0x67 | ? | 1 | |
| 0x6D | ? | 3 | |
| 0x6E | ? | 1 | |
| 0x6F | ? | 1 | |
| 0x70 | ? | 1 | |
| 0x73 | ? | 1 | |
| 0x77 | ? | 1 | |
| 0x78 | ? | 3 | |
| 0x79 | ? | 3 | |
| 0x7A | ? | 3 | |
| 0x7D | ? | 1 | |
| 0x7E | ? | 1 | |

**Note:** The firmware update captures also show heavy use of type 0x01 (113 occurrences) which may be a data transfer command for firmware chunks.

## Attribute Coverage Summary

| Attribute | Hex | Name | km003c-lib Status | Notes |
|-----------|-----|------|-------------------|-------|
| 0x0001 | Adc | **Implemented** | Simple ADC (44 bytes) |
| 0x0002 | AdcQueue | **Implemented** | Streaming ADC (20 bytes/sample) |
| 0x0004 | AdcQueue10k | Listed | 10kHz mode? |
| 0x0008 | Settings | Listed | Device settings |
| 0x0010 | PdPacket | **Implemented** | PD status (12B) or events (>12B) |
| 0x0020 | PdStatus | Listed | PD status only |
| 0x0040 | QcPacket | Listed | Quick Charge data |
| 0x0200 | LogMetadata | **Fully Reversed** | Offline log info (name, samples, interval) |
| 0x0649 | Unknown1609 | **Unknown** | With Unknown26 |
| 0x564D | Unknown22093 | **Data Response** | Unknown44 response attribute |
| 0x68C1 | Unknown26817 | **Unknown** | With Unknown58 |

---

## Fully Reversed Commands

### Unknown76 (0x4C) - Streaming Authentication

**Status:** Fully reversed and documented

**Purpose:** Required to enable AdcQueue streaming. Without it, StartGraph succeeds but returns 0 samples.

**Key Finding:** Device does NOT verify payload content - any 32-byte payload works. The AES encryption is vestigial DRM that was never enforced.

**Packet Structure:**
```
Request:  4C TID 00 02 [16-byte challenge] [16-byte session key]
Response: 4C 00 03 02 [16-byte AES(challenge)] [16-byte AES(session_key)]
```

**Cryptographic Details:**
- AES-128 ECB encryption oracle
- Encryption key: `Fa0b4tA25f4R038a`
- Decryption key: `FX0b4tA25f4R038a` (byte[1] = 'X')
- Keys located at Mtools.exe:0x140184b60 + offset 0x16

**Minimal Working Command:**
```python
# Any 32 bytes work - device enables streaming regardless
unknown76_minimal = bytes([0x4C, tid, 0x00, 0x02]) + bytes(32)
```

**Full Documentation:** See [unknown76_authentication.md](unknown76_authentication.md)

---

### Unknown68 (0x44) - Memory Download

**Status:** Fully reversed and verified working

**Purpose:** Download/read data from device memory at specified addresses. Used for reading device configuration, calibration data, and firmware information.

**Packet Structure:**

Request (36 bytes total):
```
Header (4 bytes):
  Byte 0: 0x44 (type)
  Byte 1: TID (transaction ID)
  Byte 2-3: 0x0101 (attribute, little-endian)

Payload (32 bytes plaintext, then AES-128 ECB encrypted):
  Bytes 0-3:   Address (little-endian uint32)
  Bytes 4-7:   Size to read (little-endian uint32)
  Bytes 8-11:  Padding (0xFFFFFFFF)
  Bytes 12-15: CRC32 of bytes 0-11 (standard CRC32 over addr+size+padding)
  Bytes 16-31: Padding (0xFF * 16, encrypts to constant d18b539a39c407d5c063d91102e36a9e)
```

**CRC Calculation:**
```python
import binascii
import struct

def build_crc(address: int, size: int) -> int:
    data = struct.pack('<III', address, size, 0xFFFFFFFF)  # 12 bytes
    return binascii.crc32(data) & 0xFFFFFFFF
```

**Response Flow:**
1. First response: Type 0x44 confirmation (20 bytes)
2. Second response: Data packet with type depending on memory region

**Data Response Types (discovered):**
| Memory Address | Response Type | Description |
|----------------|---------------|-------------|
| 0x420 | 0x1A (Unknown26) | Device info block 1, 64 bytes |
| 0x4420 | 0x3A (Unknown58) | Device info block 2, 64 bytes |
| 0x3000C00 | 0x40 (Head) | Calibration/config data, 64 bytes |
| 0x40010450 | 0x75 (Unknown117) | Unknown data, 12 bytes |

**Cryptographic Details:**
- AES-128 ECB encryption for request payload
- Uses crypto key index 0: `Lh2yfB7n6X7d9a5Z`
- Data responses appear to be unencrypted binary data

**Key Functions in Mtools.exe:**
- `build_download_request_packet` (0x14006b5f0): Builds the encrypted request
- `download_large_data` (0x14006f870): Sends request and receives data

**Working Python Example:**
```python
from Crypto.Cipher import AES
import struct, binascii

AES_KEY_0 = b"Lh2yfB7n6X7d9a5Z"

def build_unknown68_request(address: int, size: int, tid: int) -> bytes:
    plaintext = bytearray(32)
    struct.pack_into('<I', plaintext, 0, address)
    struct.pack_into('<I', plaintext, 4, size)
    struct.pack_into('<I', plaintext, 8, 0xFFFFFFFF)
    crc = binascii.crc32(bytes(plaintext[0:12])) & 0xFFFFFFFF
    struct.pack_into('<I', plaintext, 12, crc)
    for i in range(16, 32):
        plaintext[i] = 0xFF

    cipher = AES.new(AES_KEY_0, AES.MODE_ECB)
    ciphertext = cipher.encrypt(bytes(plaintext))
    return bytes([0x44, tid, 0x01, 0x01]) + ciphertext
```

**NOT required** for AdcQueue streaming.

---

## Unknown68 Data Response Types - FULLY REVERSED

These are memory data response types for Unknown68 memory downloads. All data is **AES-128 ECB encrypted** with key `Lh2yfB7n6X7d9a5Z`.

### Unknown26 (0x1A) - Device Info Block 1

**Address:** 0x420 | **Size:** 64 bytes | **Status:** Fully Reversed

**Decrypted Structure (64 bytes):**
```
Offset  Size  Type    Field           Example
──────────────────────────────────────────────────
0x00    16    bytes   Reserved        (mostly 0xFF)
0x10    12    char[]  Model           "KM003C"
0x1C    12    char[]  HW Version      "2.1"
0x28    24    char[]  Mfg Date        "2022.11.7"
```

### Unknown58 (0x3A) - Firmware Info Block

**Address:** 0x4420 | **Size:** 64 bytes | **Status:** Fully Reversed

**Decrypted Structure (64 bytes):**
```
Offset  Size  Type    Field           Example
──────────────────────────────────────────────────
0x00    4     u32     Magic           0x00004000
0x04    4     u32     Reserved        0xFFFFFFFF
0x08    4     u32     Counter/ID      452460
0x0C    4     bytes   Random          (4 bytes)
0x10    12    char[]  Model           "KM003C"
0x1C    12    char[]  FW Version      "1.9.9"
0x28    12    char[]  FW Date         "2025.9.22"
0x34    4     u32     Build Number    0x33 (51)
0x38    8     bytes   Reserved        (zeros)
```

**Note:** If Magic == 0xFFFFFFFF, firmware info is invalid (use "none").

### Head (0x40) - Calibration Data

**Address:** 0x3000C00 | **Size:** 64 bytes | **Status:** Fully Reversed

**Decrypted Structure (64 bytes):**
```
Offset  Size  Type    Field           Example
──────────────────────────────────────────────────
0x00    7     char[]  Serial ID       "007965 "
0x07    32    char[]  UUID/Hash       "CDFDDF2886FD40AF8F05E149624C3892"
0x27    1     char    Space           " "
0x28    11    char[]  Timestamp       "1682306459" (Unix epoch)
0x33    1     char    Space           " "
0x34    4     char[]  Marker          "LYS5"
0x38    8     bytes   Reserved        (0xFF padding)
```

**Timestamp:** Unix epoch seconds (e.g., 1682306459 = 2023-04-24 04:20:59 UTC)

### Unknown117 (0x75) - Device Serial

**Address:** 0x40010450 | **Size:** 12 bytes (padded to 16) | **Status:** Fully Reversed

**Decrypted Structure (16 bytes):**
```
Offset  Size  Type    Field           Example
──────────────────────────────────────────────────
0x00    6     char[]  Serial Prefix   "071KBP"
0x06    2     bytes   Separator       0x0D 0xFF
0x08    2     bytes   Device ID       0x11 0x0A (or 0x110A)
0x0A    2     bytes   Padding         0xFF 0xFF
0x0C    4     bytes   Reserved        0x00000000
```

### Unknown44 (0x2C) - Alternative Firmware Info

**Attribute:** 0x564D | **Size:** 64 bytes | **Status:** Fully Reversed

Same structure as Unknown58 (0x3A). Appears in older capture sequences.

---

## AdcQueue Minimal Sequence

Based on research, the minimal sequence for AdcQueue streaming:

```
1. Connect (0x02)      -> Accept (0x05)        [REQUIRED]
2. Unknown76 (0x4C)    -> 0x4C response        [REQUIRED - enables streaming]
3. StartGraph (0x0E)   -> Accept (0x05)        [REQUIRED - sets sample rate]
4. GetData (0x0C)      -> PutData (0x41)       [Poll for samples]
5. StopGraph (0x0F)    -> Accept (0x05)        [Cleanup]
```

**NOT required:**
- Unknown68 (0x44) - 4-packet sequence during Mtools startup
- GetData for PD status
- GetData for Settings

---

## Protocol Header Reference

### Control Packet Header (4 bytes)
```
Byte 0: [type:7][reserved:1]
Byte 1: [transaction_id:8]
Byte 2-3: [unused:1][attribute:15] (little-endian)
```

### Data Packet Header (4 bytes)
```
Byte 0: [type:7][reserved:1]
Byte 1: [transaction_id:8]
Byte 2-3: [unused:6][obj_count_words:10] (little-endian)
```

### Extended Header (4 bytes, in PutData logical packets)
```
Bits 0-14: attribute (15 bits)
Bit 15: next (has more logical packets)
Bits 16-21: chunk (6 bits)
Bits 22-31: size (10 bits)
```

---

## Ghidra/ReVa Analysis Notes

### Key Functions in Mtools.exe

| Address | Name | Description |
|---------|------|-------------|
| 0x14006e9e0 | send_auth_packet_and_verify | Unknown76 handler |
| 0x1400735e0 | get_crypto_key | Returns AES key pointer |
| 0x14006b470 | build_command_header | Builds 4-byte control header |
| 0x14006b9b0 | build_data_packet_header | Builds data packet with extended header |
| 0x14006ef10 | manage_data_stream | StartGraph/StopGraph handler |
| 0x14006ec70 | send_simple_command | Generic command sender |

### Key Data Locations

| Address | Description |
|---------|-------------|
| 0x140184b60 | AES key string (64 chars, key at offset 0x16) |
| 0x140277089 | Transaction ID counter (incremented per packet) |

### AES Keys Summary

| Key | Usage | Command | Notes |
|-----|-------|---------|-------|
| `Lh2yfB7n6X7d9a5Z` | Encryption | Unknown68 (0x44) | Memory download requests and data chunk decryption |
| `Fa0b4tA25f4R038a` | Encryption | Unknown76 (0x4C) | Streaming auth challenge encryption |
| `FX0b4tA25f4R038a` | Decryption | Unknown76 (0x4C) | Streaming auth response verification (byte[1]='X') |

All keys use AES-128 ECB mode.

---

## Contributing

When analyzing a new unknown command:

1. Capture example packets (request and response)
2. Find handler function in Mtools.exe using ReVa
3. Document packet structure (offsets, sizes, fields)
4. Test minimal requirements (is it required? what enables it?)
5. Update this document with findings
