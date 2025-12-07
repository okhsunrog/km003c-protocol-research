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
| 0x0E | StartGraph | **Fully Reversed** | adc_*, pd_adcqueue | Start streaming with rate_index (see below) |
| 0x0F | StopGraph | **Fully Reversed** | all normal captures | Stop streaming |
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
| 0x0004 | AdcQueue10k | **Not Implemented** | Defined but unused (see below) |
| 0x0008 | Settings | **Fully Reversed** | Device settings (180 bytes) |
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

## Settings Attribute (0x0008) - Device Configuration

**Status:** Fully Reversed

**Size:** 180 bytes | **Attribute:** 0x0008

**Purpose:** Contains device configuration, calibration offsets, thresholds, and user-configurable device name.

### Structure (180 bytes)

```
Offset  Size  Type      Field               Description
──────────────────────────────────────────────────────────────────────
0x00    4     u32       flags               Configuration flags (0xf8500161)
0x04    4     u32       reserved            Always 0x00000000
0x08    2     u16       sample_interval     ADC sample interval in microseconds (10000 = 10ms)
0x0a    1     u8        display_brightness  Display brightness level (65 = default)
0x0b    1     u8        unknown             Always 0xFF
0x0c    4     u32       reserved            Always 0x00000000

0x10    32    i32[8]    thresholds          Alert threshold values (-1 = disabled, -6 = enabled)
                                            [0-2]: voltage thresholds
                                            [3-7]: current/power thresholds

0x30    40    u32[10]   calibration         ADC calibration offsets (e.g., 1002221 = 0x000F4AED)
                                            Applied to raw ADC readings

0x58    4     u32       counter             Sequence counter or settings version
0x5c    4     u32       timestamp           Settings modification timestamp (Unix epoch)

0x60    1     u8        mode_flags          Operating mode flags
                                            Bits 2-3: Mode (0-3), extracted by firmware
                                            Bit 0: Unknown flag
                                            Bit 1: Unknown flag
                                            Bit 6: Unknown flag
0x61    15    bytes     reserved            Always zeros

0x70    64    char[64]  device_name         User-configurable device name ("POWER-Z" default)
                                            Null-terminated UTF-8 string

0xb0    4     u32       checksum            Device-generated checksum (not verified by host)
```

**Note on checksum:** The last 4 bytes appear to be a checksum but:
- Host software (Mtools) does NOT verify it
- Not standard CRC32 (tested with various init values and byte ranges)
- Likely calculated by device firmware using unknown algorithm
- Safe to ignore when reading Settings; unknown if device validates on write

### Example Values (from captures)

```
flags:              0xf8500161
sample_interval:    10000 µs (10 ms)
display_brightness: 65
thresholds:         [-1, -1, -1, -6, -6, -6, -6, -6]
calibration[0-9]:   1002221 (all same in this device)
counter:            94
mode_flags:         0x43 (bits 0,1,6 set, mode=0)
device_name:        "POWER-Z"
```

### Firmware Handling (from Ghidra)

```c
// handle_response_packet at 0x14006d1b0
else if (attr == 8) {  // Settings
    FUN_140161470(device_context);  // Emit signal
    QByteArray::remove(local_108, 0, 0x60);  // Skip to offset 0x60
    // Read 16 bytes (mode_flags + reserved)
    local_f0 = *puVar15;
    uStack_e8 = puVar15[1];
    QByteArray::remove(local_108, 0, 0x54);  // Skip rest
    // Extract mode from bits 2-3
    *(byte *)(device_context + 0x160) = (byte)((uint)local_f0 >> 2) & 3;
}
```

The firmware extracts the operating mode (bits 2-3 of byte 0x60) and stores it in the device context.

---

## AdcQueue10k Attribute (0x0004) - NOT IMPLEMENTED

**Status:** Defined in code but NOT implemented/used

**Analysis Results:**

1. **String reference exists**: `"AttributeAdcQueue10K"` found at Mtools.exe:0x14022ddd8 (debug enum name)

2. **UI has 10KSPS button**: The software shows sample rate buttons ("10SPS", "50SPS", "1KSPS", "10KSPS") at FUN_140016940, but these are **UI labels only**, not protocol attributes

3. **NO handler in protocol**: The `handle_response_packet` function (0x14006d1b0) handles:
   - 0x01 (ADC) → `process_adc_packet`
   - 0x02 (AdcQueue) → `process_adc_data`
   - 0x08 (Settings)
   - 0x10 (PdPacket)
   - 0x20 (debug log)
   - 0x40 (QcPacket)
   - 0x80 (unknown)

   **Attribute 0x04 is NOT handled** - would fall through with no action

4. **Only in firmware update captures**: The 0x0004 bit appearing in attribute masks like 0x6fd4 is coincidental overlap with firmware data, not actual protocol usage

**Conclusion:**

The attribute 0x0004 was planned/reserved but never implemented. Sample rate is controlled via the **StartGraph (0x0E) command** using a rate_index parameter, NOT via Settings or a separate attribute. All streaming uses AdcQueue (0x02) with StartGraph setting the rate.

---

## StartGraph Command (0x0E) - Streaming Control

**Status:** Fully Reversed

**Purpose:** Start AdcQueue streaming at a specified sample rate.

### Packet Structure

**Request (4 bytes):**
```
Byte 0: 0x0E (type)
Byte 1: TID (transaction ID)
Byte 2: rate_index (0-3, sample rate selector)
Byte 3: 0x00
```

**Response:** Accept (0x05) or Reject (0x06)

### Sample Rate Encoding

The rate byte uses bits 1-2 as the rate selector: `effective_index = (byte >> 1) & 3`

| Byte value | Effective index | Sample Rate |
|------------|-----------------|-------------|
| 0-1 | 0 | 2 SPS |
| 2-3 | 1 | 10 SPS |
| 4-5 | 2 | 50 SPS |
| 6-7 | 3 | 1000 SPS |

**To set a specific rate:** Send `rate_index * 2` in byte 2.

**Note:** Mtools.exe has a lookup table at 0x14017acb0 with timing values [1000, 100, 20, 1] ms - these are for host-side polling intervals, not the device's actual sample rates.

### Firmware Implementation (Ghidra)

From `manage_data_stream` at 0x14006ef10:

```c
// Line 61: Build StartGraph command with rate_index
build_command_header(local_70, '\x0e', (uchar)rate_index);

// Line 63-64: Store timing value from lookup table
// Table at 0x14017acb0: [1000, 100, 20, 1] (ms intervals)
*(undefined4 *)(device_context + 0x1b8) =
     *(undefined4 *)((longlong)&local_50 + (ulonglong)((byte)rate_index & 7) * 4);
```

### Python Example

```python
def build_start_graph(tid: int, rate_index: int) -> bytes:
    """Build StartGraph command.

    Args:
        tid: Transaction ID (0-255)
        rate_index: 0=2SPS, 1=10SPS, 2=50SPS, 3=1000SPS
    """
    # Device uses (byte >> 1) & 3 as rate selector, so multiply by 2
    return bytes([0x0E, tid, (rate_index * 2) & 0x07, 0x00])

# Start streaming at 50 SPS (rate_index=2, sends byte value 4)
packet = build_start_graph(tid=0x01, rate_index=2)
```

### Rust Library Reference

The `km003c-lib` crate should use:

```rust
pub enum GraphSampleRate {
    Sps2 = 0,     // 2 SPS (sends 0x00)
    Sps10 = 1,    // 10 SPS (sends 0x02)
    Sps50 = 2,    // 50 SPS (sends 0x04)
    Sps1000 = 3,  // 1000 SPS (sends 0x06)
}
```

**Note:** The current Rust lib has `Sps1` but device actually uses 2 SPS for index 0.

---

## StopGraph Command (0x0F) - Stop Streaming

**Status:** Fully Reversed

**Purpose:** Stop AdcQueue streaming.

### Packet Structure

**Request (4 bytes):**
```
Byte 0: 0x0F (type)
Byte 1: TID (transaction ID)
Byte 2-3: 0x0000
```

**Response:** Accept (0x05)

From `manage_data_stream`:
```c
// Line 47: Build StopGraph command
build_command_header(local_88, '\x0f', '\0');
```

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

## Device Firmware Implementation (Ghidra Analysis)

### Main Command Dispatcher: FUN_0004eaf0 @ 0x0004eaf0

The firmware's USB command processor uses a switch statement on `command_type & 0x7F`:

| Command | Hex | Firmware Handler | Address | Notes |
|---------|-----|------------------|---------|-------|
| Connect | 0x02 | Inline | - | Returns Accept (0x05) |
| GetData | 0x0C | FUN_0004286c | 0x0004286c | Builds ADC/PD/Settings responses |
| Unknown | 0x0D | FUN_00042c4a | 0x00042c4a | Data command |
| StartGraph | 0x0E | Inline | - | Starts streaming |
| StopGraph | 0x0F | Inline | - | Stops streaming |
| PdEnable | 0x10 | Inline | - | Enable PD monitoring |
| PdDisable | 0x11 | Inline | - | Disable PD monitoring |
| Unknown68 | 0x44 | FUN_00042cac | 0x00042cac | Memory read with validation |
| Unknown72 | 0x48 | FUN_00042df4 | 0x00042df4 | Unknown purpose |
| FlashWrite | 0x4A | Inline | - | Requires auth level > 0 |
| Unknown75 | 0x4B | FUN_00042cac | 0x00042cac | Memory read + 0x98000000 offset |
| Unknown76 | 0x4C | FUN_00000fb0 | 0x00000fb0 | Authentication (AES encrypt) |

### Hardware Crypto Functions

| Function | Address | Purpose | Control Bit |
|----------|---------|---------|-------------|
| FUN_00000fb0 | 0x00000fb0 | AES Encrypt | uRam42100004 = 1 |
| FUN_00001090 | 0x00001090 | AES Decrypt/Read | uRam42100004 = 0 |

Both use hardware AES peripheral:
- **0x40008010**: AES input data register
- **0x40008020**: AES key register

### Authentication System (DAT_20004041)

The firmware maintains an authentication level at address 0x20004041:

| Level | Value | Access Granted |
|-------|-------|----------------|
| None | 0 | Basic ADC/PD only, GetData mask limited to 0x19 |
| Device | 1 | Flash write, extended attributes |
| Calibration | 2 | Factory/calibration commands (0x4D) |

**How authentication is set (case 0x4C):**
```c
// Check against hardware device ID at 0x40010450-0x40010458
if (decrypted == device_id) {
    DAT_20004041 = 1;
}
// Or check against calibration data at 0x03000c00
else if (decrypted == calibration_data) {
    DAT_20004041 = 2;
}
```

### Memory Read Access Control (FUN_00042cac)

**Firmware validation (must pass all):**
```c
if ((param_3 == -1) &&           // Magic constant 0xFFFFFFFF
    (param_2 < 0x3d0901) &&      // Size < ~4MB
    (param_1 < 0x983d0901)) {    // Address < ~2.5GB
    // Allow read
} else {
    // Send REJECT (0x06)
}
```

**Response types by outcome:**
| Response | Hex | Cause |
|----------|-----|-------|
| REJECT | 0x06 | Firmware validation failed |
| NOT_READABLE | 0x27 | Hardware bus fault (protected memory) |
| DATA | 0x1A, 0x2C, 0x3A, 0x75 | Successful read |

### AES Keys (Verified Working)

| Index | Key | Usage |
|-------|-----|-------|
| 0 | `Lh2yfB7n6X7d9a5Z` | Memory download (0x44) |
| 1 | `Ea0b4tA25f4R038a` | Base for auth keys (0x4C) |

**Note:** The decrypted firmware binary shows `...9a4Z` at 0x0006e8cc, but the actual device uses `...9a5Z`. The firmware may be patched during flashing or the key is transformed at runtime.

---

## Contributing

When analyzing a new unknown command:

1. Capture example packets (request and response)
2. Find handler function in Mtools.exe using ReVa
3. Document packet structure (offsets, sizes, fields)
4. Test minimal requirements (is it required? what enables it?)
5. Update this document with findings
