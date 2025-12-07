# Firmware Documentation

Reverse engineering documentation for the KM003C device firmware and official Windows application.

---

## Documents

| Document | Description |
|----------|-------------|
| [Overview](overview.md) | MCU identification, RTOS, charging protocols, memory layout |
| [Format](format.md) | .mencrypt firmware file decryption |
| [Handlers](handlers.md) | Device firmware command handlers (Ghidra analysis) |
| [Mtools Analysis](mtools_analysis.md) | Official Windows app reverse engineering |

---

## Ghidra Projects

Two binaries have been analyzed:

### Device Firmware

- **File:** `KM003C_V1.9.9_key0_ecb.bin` (decrypted)
- **Size:** 453,616 bytes
- **Architecture:** ARM Cortex-M (Thumb mode)
- **Functions:** 1,580
- **Strings:** 475

### Mtools.exe

- **File:** `Mtools.exe` (official Windows application)
- **Framework:** Qt5 (x64)
- **Focus:** Protocol implementation, cryptography

---

## Quick Reference

### Key Firmware Addresses

| Address | Purpose |
|---------|---------|
| FUN_0004eaf0 | Main USB command dispatcher |
| FUN_00042cac | Memory read handler |
| FUN_00000fb0 | AES encrypt (hardware) |
| FUN_00001090 | AES decrypt (hardware) |
| DAT_20004041 | Authentication level (0/1/2) |

### Key Mtools.exe Addresses

| Address | Purpose |
|---------|---------|
| 0x14006e9e0 | send_auth_packet_and_verify |
| 0x14006d1b0 | handle_response_packet |
| 0x14006ef10 | manage_data_stream |
| 0x1400735e0 | get_crypto_key |
| 0x140184b60 | AES key strings |

### AES Keys

| Key | Usage |
|-----|-------|
| `Lh2yfB7n6X7d9a5Z` | Memory download, firmware, logs |
| `Fa0b4tA25f4R038a` | Streaming auth (encrypt) |
| `FX0b4tA25f4R038a` | Streaming auth (decrypt) |

See [Protocol Reference](../protocol_reference.md) for the canonical key list.
