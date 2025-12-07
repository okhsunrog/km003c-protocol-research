# KM003C Firmware Format (.mencrypt)

This document describes the encrypted firmware file format used by ChargerLAB Mtools for the KM003C device.

## File Format Overview

The `.mencrypt` file uses Qt's QDataStream serialization format with AES-128-ECB encryption for the firmware binary.

### Structure

| Offset | Size | Description |
|--------|------|-------------|
| 0 | 4 | String count (big-endian uint32) |
| 4 | var | QString array (metadata strings) |
| var | 4 | Firmware length (big-endian uint32, QByteArray prefix) |
| var+4 | var | AES-128-ECB encrypted firmware binary |

### Hex Dump Example (KM003C_V1.9.9.mencrypt)

```
00000000: 0000 000a 0000 001a 0046 0069 0072 006d  .........F.i.r.m
00000010: 0077 0061 0072 0065 0020 0066 0069 006c  .w.a.r.e. .f.i.l
00000020: 0065 0000 0014 0043 0068 0061 0072 0067  .e.....C.h.a.r.g
00000030: 0065 0072 004c 0061 0062 0000 0008 0056  .e.r.L.a.b.....V
00000040: 0031 002e 0030 0000 000c 004b 004d 0030  .1...0.....K.M.0
00000050: 0030 0033 0043 0000 000a 0031 002e 0039  .0.3.C.....1...9
```

Breaking down the header:
- `00 00 00 0a` = 10 strings (big-endian)
- `00 00 00 1a` = 26 bytes for first QString
- `00 46 00 69...` = "Firmware file" in UTF-16BE

### Metadata Strings (Qt QString format)

Each QString is serialized as:
- 4-byte big-endian length (in bytes, not characters)
- UTF-16BE encoded string data (2 bytes per character)
- Note: A null QString has length 0xFFFFFFFF

The metadata contains 10 strings:

| Index | Field | Example Value | Notes |
|-------|-------|---------------|-------|
| 0 | Magic | "Firmware file" | Must match for valid file |
| 1 | Vendor | "ChargerLab" | |
| 2 | Format version | "V1.0" | Container format version |
| 3 | Device model | "KM003C" | Target device |
| 4 | Firmware version | "1.9.9" | Firmware version |
| 5 | Release date | "2025.9.22" | YYYY.M.DD format |
| 6 | Checksum | "E7A75D5B" | CRC32 or hash (hex string) |
| 7 | Firmware size | "453612" | Decrypted size in bytes |
| 8 | Changelog (CN) | 中文更新日志 | Chinese release notes |
| 9 | Changelog (EN) | English changelog | English release notes |

## Encryption

The firmware binary is encrypted with AES-128-ECB mode (Electronic Codebook).

### Why ECB?

ECB mode encrypts each 16-byte block independently, which has known security weaknesses (identical plaintext blocks produce identical ciphertext). However, for firmware distribution this provides:
- Simple implementation (no IV management)
- Random-access decryption (any block can be decrypted independently)
- Sufficient protection against casual inspection

### Decryption Key

**Key**: `Lh2yfB7n6X7d9a5Z` (16 ASCII bytes)

This is key index 0 in the Mtools.exe key table, shared with Unknown68 memory download commands.

### Key Extraction from Mtools.exe

The `get_crypto_key` function at `0x1400735e0` selects keys by index:

```c
// Pseudocode from Ghidra decompilation
QByteArray* get_crypto_key(QByteArray* result, int key_index) {
    switch(key_index) {
        case 0: return mid(DAT_140184ac8, 0x14, 0x10);  // "Lh2yfB7n6X7d9a5Z"
        case 1: return mid(DAT_140184af8, 0x0e, 0x10);  // "sdkW78R3k5dj0fHv"
        case 2: return mid(DAT_140184b28, 0x0d, 0x10);  // "Uy34VW13jHj3598e"
        case 3: return mid(DAT_140184b60, 0x16, 0x10);  // "Fa0b4tA25f4R038a"
    }
}
```

The keys are embedded as substrings within longer obfuscation strings:
```
DAT_140184ac8: "NmR0R.uz3KgNOu4xufpWLh2yfB7n6X7d9a5ZBwLe/CZ.iz8"
                                    ^^^^^^^^^^^^^^^^
                                    offset 0x14, length 0x10 = Key 0
```

### All Known Keys

| Index | Key | Usage | Cross-Reference |
|-------|-----|-------|-----------------|
| 0 | `Lh2yfB7n6X7d9a5Z` | Firmware decryption, Unknown68 memory read | [offline_log_protocol.md](offline_log_protocol.md) |
| 1 | `sdkW78R3k5dj0fHv` | Unknown (unused in analyzed code paths) | - |
| 2 | `Uy34VW13jHj3598e` | Unknown (unused in analyzed code paths) | - |
| 3 | `Fa0b4tA25f4R038a` | Unknown76 streaming auth | [unknown76_authentication.md](unknown76_authentication.md) |

## Decrypted Firmware

The decrypted binary is standard ARM Cortex-M firmware.

### Vector Table (first 0x200 bytes)

```
Offset  Value       Handler
------  ----------  --------
0x000   0x200067b0  Initial SP (SRAM)
0x004   0x00004295  Reset_Handler
0x008   0x0000a459  NMI_Handler
0x00C   0x00006cad  HardFault_Handler
0x010   0x00009491  MemManage_Handler
0x014   0x00005b59  BusFault_Handler
0x018   0x000115b7  UsageFault_Handler
0x01C   0x00000000  Reserved
...
0x02C   0x0000e815  SVCall_Handler
0x038   0x00004377  PendSV_Handler
0x03C   0x0000f64d  SysTick_Handler
0x040+  IRQ handlers...
```

Note: All handler addresses are odd (Thumb mode bit set).

### Memory Layout

| Region | Address Range | Size | Purpose |
|--------|---------------|------|---------|
| Flash/ROM | 0x00000000 | ~450KB | Firmware code |
| SRAM | 0x20000000+ | ~26KB | Stack, heap, data |

The base address 0x00000000 (instead of typical 0x08000000 for STM32) suggests:
- Firmware is loaded via bootloader
- Or flash is remapped to address 0

### Notable Strings

| Category | Examples |
|----------|----------|
| RTOS | `TASK_CHARGE`, `TASK_GUI`, `TASK_USB` |
| Protocols | `Find PD charger`, `Find UFCS`, `Detecting AFC`, `mtkpe2.0` |
| Display | `IPS 1.5'' 240 x 240` |
| PD Versions | `PD3.1 EPR`, `PD3.0 (SPR)`, `PD2/3.0 PPS QC4 QC5 EPR` |
| USB | `USB mode is running`, `[USB 3.2/USB4 Gen2]` |

## Decryption Script

Full script available at `scripts/decrypt_firmware.py`. Minimal example:

```python
from Crypto.Cipher import AES
from pathlib import Path
import struct

def decrypt_mencrypt(filepath: Path) -> tuple[dict, bytes]:
    """Decrypt a .mencrypt firmware file.

    Returns: (metadata_dict, decrypted_firmware_bytes)
    """
    data = filepath.read_bytes()

    # Parse Qt QString metadata
    offset = 0
    string_count = struct.unpack(">I", data[offset:offset+4])[0]
    offset += 4

    strings = []
    for _ in range(string_count):
        str_len = struct.unpack(">I", data[offset:offset+4])[0]
        offset += 4
        if str_len != 0xFFFFFFFF:  # Not null QString
            strings.append(data[offset:offset+str_len].decode('utf-16-be'))
            offset += str_len

    # Parse QByteArray (encrypted firmware)
    fw_len = struct.unpack(">I", data[offset:offset+4])[0]
    offset += 4
    encrypted = data[offset:offset+fw_len]

    # Decrypt with AES-128-ECB
    key = b"Lh2yfB7n6X7d9a5Z"
    # Align to 16-byte blocks
    encrypted = encrypted[:len(encrypted) // 16 * 16]
    cipher = AES.new(key, AES.MODE_ECB)
    decrypted = cipher.decrypt(encrypted)

    metadata = {
        "magic": strings[0] if len(strings) > 0 else None,
        "vendor": strings[1] if len(strings) > 1 else None,
        "format_version": strings[2] if len(strings) > 2 else None,
        "device": strings[3] if len(strings) > 3 else None,
        "version": strings[4] if len(strings) > 4 else None,
        "date": strings[5] if len(strings) > 5 else None,
        "checksum": strings[6] if len(strings) > 6 else None,
        "size": strings[7] if len(strings) > 7 else None,
    }

    return metadata, decrypted

# Usage
metadata, firmware = decrypt_mencrypt(Path("KM003C_V1.9.9.mencrypt"))
Path("firmware.bin").write_bytes(firmware)
```

## Verification

### Automated Checks

```python
import struct

def verify_firmware(data: bytes) -> bool:
    """Verify decrypted firmware is valid ARM Cortex-M."""
    if len(data) < 8:
        return False

    sp = struct.unpack("<I", data[0:4])[0]
    reset = struct.unpack("<I", data[4:8])[0]

    # Check SP is in SRAM range (0x20000000 - 0x20100000)
    if not (0x20000000 <= sp <= 0x20100000):
        return False

    # Check reset vector is odd (Thumb mode) and reasonable
    if reset & 1 == 0:  # Must be Thumb
        return False
    if reset > len(data):  # Must point within firmware
        return False

    return True
```

### Manual Verification

1. **`file` command**: Should identify as "ARM Cortex-M firmware"
   ```
   $ file firmware.bin
   firmware.bin: ARM Cortex-M firmware, initial SP at 0x200067b0, reset at 0x00004294
   ```

2. **`strings` command**: Should show expected device strings
   ```
   $ strings -n 10 firmware.bin | grep -i "charger\|km003\|ufcs"
   Find PD charger
   Find UFCS
   ```

3. **Checksum**: Compare metadata field 6 with computed CRC32 (if applicable)

## Related Documentation

- [unknown76_authentication.md](unknown76_authentication.md) - Key 3 usage for streaming auth
- [offline_log_protocol.md](offline_log_protocol.md) - Key 0 usage for memory download
- [protocol_specification.md](protocol_specification.md) - Overall protocol overview
