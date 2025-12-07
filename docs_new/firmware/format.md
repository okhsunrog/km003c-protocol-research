# Firmware File Format (.mencrypt)

Encrypted firmware file format used by ChargerLAB Mtools.

---

## File Structure

| Offset | Size | Description |
|--------|------|-------------|
| 0 | 4 | String count (big-endian u32) |
| 4 | var | QString array (metadata) |
| var | 4 | Firmware length (big-endian u32) |
| var+4 | var | AES-128-ECB encrypted firmware |

### Qt QString Format

Each QString is serialized as:
- 4-byte big-endian length (bytes, not characters)
- UTF-16BE encoded string data
- Null QString has length 0xFFFFFFFF

---

## Metadata Fields

| Index | Field | Example |
|-------|-------|---------|
| 0 | Magic | "Firmware file" |
| 1 | Vendor | "ChargerLab" |
| 2 | Format version | "V1.0" |
| 3 | Device model | "KM003C" |
| 4 | Firmware version | "1.9.9" |
| 5 | Release date | "2025.9.22" |
| 6 | Checksum | "E7A75D5B" |
| 7 | Firmware size | "453612" |
| 8 | Changelog (CN) | Chinese notes |
| 9 | Changelog (EN) | English notes |

---

## Encryption

### Algorithm

- **Mode:** AES-128-ECB
- **Key:** `Lh2yfB7n6X7d9a5Z` (key index 0)
- **Padding:** None (align to 16 bytes)

ECB mode encrypts each 16-byte block independently.

### Key Extraction from Mtools.exe

`get_crypto_key` at `0x1400735e0`:

| Index | Key | Usage |
|-------|-----|-------|
| 0 | `Lh2yfB7n6X7d9a5Z` | Firmware, memory read |
| 1 | `sdkW78R3k5dj0fHv` | Unused |
| 2 | `Uy34VW13jHj3598e` | Unused |
| 3 | `Fa0b4tA25f4R038a` | Streaming auth |

Keys are embedded as substrings in obfuscation strings at 0x140184ac8-0x140184b60.

---

## Decrypted Firmware

### Vector Table

| Offset | Value | Handler |
|--------|-------|---------|
| 0x000 | 0x200067b0 | Initial SP |
| 0x004 | 0x00004295 | Reset_Handler |
| 0x008 | 0x0000a459 | NMI_Handler |
| 0x00C | 0x00006cad | HardFault_Handler |
| 0x010 | 0x00009491 | MemManage_Handler |
| 0x014 | 0x00005b59 | BusFault_Handler |
| 0x018 | 0x000115b7 | UsageFault_Handler |
| 0x02C | 0x0000e815 | SVCall_Handler |
| 0x038 | 0x00004377 | PendSV_Handler |
| 0x03C | 0x0000f64d | SysTick_Handler |

All addresses are odd (Thumb mode bit set).

### Memory Layout

| Region | Address | Size |
|--------|---------|------|
| Flash/ROM | 0x00000000 | ~450KB |
| SRAM | 0x20000000+ | ~26KB |

---

## Decryption Script

```python
from Crypto.Cipher import AES
from pathlib import Path
import struct

def decrypt_mencrypt(filepath: Path) -> tuple[dict, bytes]:
    data = filepath.read_bytes()

    # Parse QString metadata
    offset = 0
    string_count = struct.unpack(">I", data[offset:offset+4])[0]
    offset += 4

    strings = []
    for _ in range(string_count):
        str_len = struct.unpack(">I", data[offset:offset+4])[0]
        offset += 4
        if str_len != 0xFFFFFFFF:
            strings.append(data[offset:offset+str_len].decode('utf-16-be'))
            offset += str_len

    # Parse encrypted firmware
    fw_len = struct.unpack(">I", data[offset:offset+4])[0]
    offset += 4
    encrypted = data[offset:offset+fw_len]

    # Decrypt
    key = b"Lh2yfB7n6X7d9a5Z"
    encrypted = encrypted[:len(encrypted) // 16 * 16]
    cipher = AES.new(key, AES.MODE_ECB)
    decrypted = cipher.decrypt(encrypted)

    metadata = {
        "magic": strings[0] if len(strings) > 0 else None,
        "vendor": strings[1] if len(strings) > 1 else None,
        "device": strings[3] if len(strings) > 3 else None,
        "version": strings[4] if len(strings) > 4 else None,
        "date": strings[5] if len(strings) > 5 else None,
    }

    return metadata, decrypted

# Usage
metadata, firmware = decrypt_mencrypt(Path("KM003C_V1.9.9.mencrypt"))
Path("firmware.bin").write_bytes(firmware)
```

---

## Verification

```python
import struct

def verify_firmware(data: bytes) -> bool:
    if len(data) < 8:
        return False

    sp = struct.unpack("<I", data[0:4])[0]
    reset = struct.unpack("<I", data[4:8])[0]

    # SP must be in SRAM
    if not (0x20000000 <= sp <= 0x20100000):
        return False

    # Reset must be Thumb mode (odd) and within firmware
    if reset & 1 == 0:
        return False
    if reset > len(data):
        return False

    return True
```

### Manual Checks

```bash
# Should identify as ARM firmware
file firmware.bin

# Should show device strings
strings -n 10 firmware.bin | grep -i "charger\|km003\|ufcs"
```
