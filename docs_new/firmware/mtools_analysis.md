# Mtools.exe Analysis

Ghidra reverse engineering of the official ChargerLAB Windows application.

For device firmware analysis, see [Handlers](handlers.md).

---

## Overview

| Property | Value |
|----------|-------|
| File | Mtools.exe |
| Framework | Qt5 (x64) |
| Purpose | Official KM003C control software |

---

## Key Functions

| Address | Name | Purpose |
|---------|------|---------|
| 0x14006e9e0 | send_auth_packet_and_verify | StreamingAuth (0x4C) handler |
| 0x1400735e0 | get_crypto_key | AES key selection by index |
| 0x14006b470 | build_command_header | Builds 4-byte control header |
| 0x14006b5f0 | build_download_request_packet | Memory read request packets |
| 0x14006b9b0 | build_data_packet_header | Data packet with extended header |
| 0x14006d1b0 | handle_response_packet | Response parsing dispatcher |
| 0x14006ec70 | send_simple_command | Generic command sender |
| 0x14006ef10 | manage_data_stream | StartGraph/StopGraph handler |
| 0x14006f870 | download_large_data | Memory download orchestration |

---

## Data Locations

| Address | Description |
|---------|-------------|
| 0x140184ac8 | Key 0 obfuscation string |
| 0x140184af8 | Key 1 obfuscation string |
| 0x140184b28 | Key 2 obfuscation string |
| 0x140184b60 | Key 3 obfuscation string |
| 0x140277089 | Transaction ID counter |
| 0x14017acb0 | Sample rate timing table |

---

## AES Key Extraction

### get_crypto_key (0x1400735e0)

```c
QByteArray* get_crypto_key(QByteArray* result, int key_index) {
    switch(key_index) {
        case 0: return mid(DAT_140184ac8, 0x14, 0x10);
        case 1: return mid(DAT_140184af8, 0x0e, 0x10);
        case 2: return mid(DAT_140184b28, 0x0d, 0x10);
        case 3: return mid(DAT_140184b60, 0x16, 0x10);
    }
}
```

### Obfuscation Strings

Keys are embedded within longer random-looking strings:

```
0x140184ac8: "NmR0R.uz3KgNOu4xufpWLh2yfB7n6X7d9a5ZBwLe/CZ.iz8"
                                ^^^^^^^^^^^^^^^^
                                offset 0x14 = Key 0

0x140184b60: "XwcPWtquq0yNVdaQjaFO7LFa0b4tA25f4R038azbeXoxQ41..."
                                    ^^^^^^^^^^^^^^^^
                                    offset 0x16 = Key 3
```

### Key Table

| Index | Key | Usage |
|-------|-----|-------|
| 0 | `Lh2yfB7n6X7d9a5Z` | Firmware decrypt, memory read, logs |
| 1 | `sdkW78R3k5dj0fHv` | Unused in analyzed paths |
| 2 | `Uy34VW13jHj3598e` | Unused in analyzed paths |
| 3 | `Fa0b4tA25f4R038a` | Streaming auth (encrypt) |
| 3' | `FX0b4tA25f4R038a` | Streaming auth (decrypt, byte[1]='X') |

---

## StreamingAuth Implementation

### send_auth_packet_and_verify (0x14006e9e0)

**Challenge construction:**

| Offset | Size | Content |
|--------|------|---------|
| 0 | 8 | Timestamp (QDateTime::toMSecsSinceEpoch) |
| 8 | 8 | Device-specific data |
| 16 | 8 | Random (QRandomGenerator64) |

This 24-byte plaintext is AES-128-ECB encrypted to 32 bytes.

**Verification flow:**
1. Build challenge with timestamp + device_id + random
2. Encrypt with key 3 (`Fa0b4tA25f4R038a`)
3. Send packet
4. Receive response
5. Decrypt response with modified key (`FX...`)
6. Verify timestamp and random match original

---

## Response Handling

### handle_response_packet (0x14006d1b0)

Switch on attribute value:

```c
switch(attribute) {
    case 0x01:  // ADC
        process_adc_packet();
        break;
    case 0x02:  // AdcQueue
        process_adc_data();
        break;
    case 0x08:  // Settings
        // Skip to offset 0x60, extract mode from bits 2-3
        mode = (byte_at_0x60 >> 2) & 3;
        break;
    case 0x10:  // PdPacket
        process_pd_packet();
        break;
    case 0x20:  // Debug log
        // ...
        break;
    case 0x40:  // QcPacket
        // ...
        break;
}
```

**Note:** Attribute 0x04 (AdcQueue10k) is NOT handled - falls through.

### AdcQueue10k Status (0x0004)

Despite being defined in code, this attribute was **never implemented**:

1. **String exists:** `"AttributeAdcQueue10K"` at 0x14022ddd8 (debug enum)
2. **UI buttons exist:** Sample rate buttons show "10KSPS" at FUN_140016940
3. **NO handler:** `handle_response_packet` doesn't process 0x04
4. **Conclusion:** Planned but never implemented

Sample rate is controlled via **StartGraph (0x0E)** rate_index, not via a separate attribute. All streaming uses AdcQueue (0x02).

---

## Streaming Control

### manage_data_stream (0x14006ef10)

```c
// Build StartGraph command
build_command_header(buffer, 0x0E, rate_index);

// Store polling interval from lookup table
// Table at 0x14017acb0: [1000, 100, 20, 1] ms
polling_ms = timing_table[rate_index & 7];
```

### Sample Rate Lookup Table

| Address | Values |
|---------|--------|
| 0x14017acb0 | [1000, 100, 20, 1] |

These are **host-side polling intervals** in milliseconds, not device sample rates:

| Index | Polling Interval | Device Rate |
|-------|-----------------|-------------|
| 0 | 1000 ms | 2 SPS |
| 1 | 100 ms | 10 SPS |
| 2 | 20 ms | 50 SPS |
| 3 | 1 ms | 1000 SPS |

---

## Memory Download

### build_download_request_packet (0x14006b5f0)

Builds 0x44 memory read request:
1. Create 16-byte plaintext: address + size + 0xFFFFFFFF + CRC32
2. Pad to 32 bytes with 0xFF
3. Encrypt with key 0
4. Prepend 4-byte header

### download_large_data (0x14006f870)

Orchestrates multi-chunk downloads:
1. Send 0x44 request
2. Receive 20-byte confirmation
3. Collect data chunks (0x34, 0x4E, 0x76, 0x68)
4. Decrypt chunks with key 0
5. Concatenate and return

---

## Settings Parsing

From handle_response_packet for attribute 0x08:

```c
// Skip to offset 0x60
QByteArray::remove(buffer, 0, 0x60);

// Read mode_flags byte
mode_flags = buffer[0];

// Extract mode from bits 2-3
device_mode = (mode_flags >> 2) & 3;

// Store in context
device_context[0x160] = device_mode;
```

---

## UI/Feature Mapping

| UI Feature | Function | Command |
|------------|----------|---------|
| Graph view | manage_data_stream | 0x0E/0x0F |
| Device info | download_large_data | 0x44 |
| PD capture | handle_response_packet | attr=0x10 |
| Settings | handle_response_packet | attr=0x08 |
| Auth | send_auth_packet_and_verify | 0x4C |

---

## AdcQueue10k Status

The attribute 0x0004 (AdcQueue10k) appears in code but is **not implemented**:

1. **String exists:** `"AttributeAdcQueue10K"` at 0x14022ddd8 (debug enum)
2. **UI buttons exist:** Sample rate buttons at FUN_140016940
3. **NO handler:** handle_response_packet doesn't process 0x04
4. **Conclusion:** Planned but never implemented; use 0x02 with rate index

---

## Transaction ID

Global counter at 0x140277089:
- Incremented per packet
- 8-bit rollover (0-255)
- Response ID should match request ID

---

## Header Building

### build_command_header (0x14006b470)

Builds 4-byte control packet header:

```c
void build_command_header(byte* buffer, byte type, byte param) {
    buffer[0] = type;
    buffer[1] = get_next_tid();  // From 0x140277089
    buffer[2] = param;
    buffer[3] = 0;
}
```

### build_data_packet_header (0x14006b9b0)

Builds data packet with extended header for logical packets.
