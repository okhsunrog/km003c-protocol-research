# Device Firmware Command Handlers

Ghidra analysis of device firmware USB command processing. All addresses and
firmware behavior on this page refer specifically to reverse engineering of
KM003C V1.9.9, decrypted image `KM003C_V1.9.9_key0_ecb.bin` (SHA-256
`9ce6125da454585fde1b5744018f94edc697a23941292cbf55d2a411d4df7517`).
Other firmware versions may differ.

For Mtools.exe (Windows app) analysis, see [Mtools Analysis](mtools_analysis.md).

---

## Main Dispatcher: FUN_0004eaf0

The main USB command processor at `0x0004eaf0` uses a switch on `command_type & 0x7F`:

| Command | Hex | Handler | Notes |
|---------|-----|---------|-------|
| Connect | 0x02 | Inline | Returns Accept (0x05) |
| GetData | 0x0C | `handle_get_data` | Builds ADC/PD/Settings responses |
| GetFile | 0x0D | FUN_00042c4a | File-transfer command |
| StartGraph | 0x0E | Inline | Starts streaming |
| StopGraph | 0x0F | Inline | Stops streaming |
| PdEnable | 0x10 | Inline | Enable PD monitoring |
| PdDisable | 0x11 | Inline | Disable PD monitoring |
| MemoryRead | 0x44 | `handle_memory_read` | Memory read with validation |
| SettingsBatch | 0x48 | `handle_settings_batch` | Executes nested settings operations |
| FlashWrite | 0x4A | Inline | Requires auth level > 0 |
| Command 0x4B | 0x4B | `handle_memory_read` | Memory-style read with 0x98000000 offset |
| StreamingAuth | 0x4C | `aes128_ecb_decrypt` | AES authentication |
| PrivilegedSettingsBatch | 0x4D | `handle_settings_batch` | Same payload as 0x48; requires auth level 2 |

---

## Hardware Crypto Functions

| Function | Address | Purpose | Control Bit |
|----------|---------|---------|-------------|
| `aes128_ecb_decrypt` | 0x00000fb0 | AES decrypt of incoming protocol data | uRam42100004 = 1 |
| `aes128_ecb_encrypt` | 0x00001090 | AES encrypt of outgoing memory data | uRam42100004 = 0 |

### Hardware Registers

| Address | Purpose |
|---------|---------|
| 0x40008010 | AES input data register |
| 0x40008020 | AES key register |

### Usage Pattern

```c
// aes128_ecb_encrypt (0x00001090) - encrypt memory for transport
undefined4 aes128_ecb_encrypt(uint *source, uint size, uint *key, uint *output) {
    // Validate: size 16-byte aligned, pointers 4-byte aligned
    if (((size & 0xf) == 0) && (((uint)source | (uint)key | (uint)output) & 3) == 0) {
        // Write key to hardware
        for (i = 0; i < 4; i++) DAT_40008020[i] = key[i];
        // Read source to hardware (can fault!)
        for (i = 0; i < 4; i++) DAT_40008010[i] = source[i];
        // Wait and return encrypted/decrypted
    }
}
```

---

## Authentication System

### Authentication Level (DAT_20004041)

| Level | Value | Access |
|-------|-------|--------|
| None | 0 | Basic ADC/PD only |
| Device | 1 | Flash write, extended attributes |
| Calibration | 2 | Factory/calibration commands |

### Level Determination (case 0x4C)

```c
// Decrypt payload with AES key Fa0b4tA25f4R038a
// Check bytes 8-19 against HardwareID (0x40010450, 12 bytes)
if (memcmp(&decrypted[8], (void*)0x40010450, 12) == 0) {
    DAT_20004041 = 1;  // Level 1 - device authenticated
}
// Or check bytes 8-19 against the first 12 bytes of the selected
// calibration record. Prefer 0x03000d80 when it is not erased;
// otherwise use 0x03000c00.
else if (memcmp(&decrypted[8], selected_calibration_record, 12) == 0) {
    DAT_20004041 = 2;  // Level 2 - calibration authenticated
}
```

The response attribute contains the actual level in bits 1-2:
`auth_level = (attribute >> 1) & 0x03`. Consequently level 1 produces
attribute `0x0203`, while level 2 produces `0x0205`; both values have now been
observed on firmware V1.9.9 hardware. Testing only bit 1 incorrectly treats a
level-2 response as failure.

### Level Enforcement Examples

```c
// Flash Write (0x4A) - requires level > 0
if (DAT_20004041 == 0) goto REJECT;

// GetData handler - limits attributes at level 0
if (auth_level == 0) {
    param_2 = param_2 & 0x19;  // Basic attributes only
}

// Command 0x4D - requires level 2
if (DAT_20004041 != 2) goto REJECT;
```

## Settings Batch Commands (0x48 and 0x4D)

Both commands enter the same handler, `FUN_00042df4`. Command `0x4D` first
requires authentication level 2; command `0x48` has no additional dispatcher
check. They are therefore two authorization paths for one nested operation
format, not two unrelated protocols.

The outer data header is followed by one or more ordinary 4-byte extended
headers and their payloads:

```text
[outer 0x48/0x4D header]
  [operation:15 | next:1 | reserved:6 | size_bytes:10]
  [payload, size_bytes]
  ...
```

The handler uses `operation` as a switch value, advances by `size_bytes`, and
continues only while `next` is set. Operations that consume arrays use
`size_bytes / 4` little-endian `u32` values. On completion the device sends a
four-byte `Finished` (`0x07`) response with the request transaction ID. The
six reserved/chunk bits are not interpreted by this handler.

### Confirmed operations

The operation names below describe the firmware effect. User-facing meanings
are left unnamed unless corroborated by the device UI or a host capture.

| Operation | Auth checked in handler | Effect |
|-----------|-------------------------|--------|
| `0x01` | none | Set language selection in settings-A word 0 bit 0 |
| `0x02` | none | Clear the uncalibrated/calibration-required flag in settings-A word 0 bit 2 |
| `0x03` | none | Set display brightness percentage in settings-A word 0 bits 3-9 |
| `0x04` | none | Set settings-A word 0 bits 10-11 |
| `0x05` | none | Set settings-A word 0 bits 12-13 |
| `0x06`, `0x1C` | none | Set settings-A word 0 bits 14-15, then apply runtime state |
| `0x07` | none | Set settings-A word 0 bits 16-18 |
| `0x08` | none | Reset/reinitialize system state |
| `0x09` | none | Reset both settings blocks, then perform operation `0x08` |
| `0x0A` | level 2 | Write `u32[]` at settings-A offset `0x1C`; update calibration state and persist |
| `0x0B`, `0x0C` | level 2 | Write `u32[]` at settings-A offset `0x30`; persist |
| `0x0D` | level 2 | Write `u32[]` at settings-A offset `0x44`; force the 7-bit field above to 50; persist |
| `0x0E` | level 1 or 2 | Invoke a low-level signed-byte control; exact device effect remains unknown |
| `0x0F` | level 2 | Set settings-A offset `0x58`; persist |
| `0x14` | none | Set screen orientation in settings-B word 0 bits 0-1; persist |
| `0x15` | none | Set settings-B word 0 bits 2-3 and apply it immediately; persist |
| `0x16` | none | Set settings-B word 0 bits 4-5; persist |
| `0x17` | none | Set the persisted main-page selection in settings-B word 0 bits 6-9; persist |
| `0x28` | none | Append consecutive 48-byte LogMetadata catalog entries, stopping before catalog offset `0x780` (40 entries) |
| `0x7FFF` | none | Persist settings-A without changing a field |

Operations `0x10`-`0x13`, `0x18`-`0x1B`, `0x1D`-`0x27` currently fall
through without a setting change. This is firmware-derived behavior; no write
operation should be sent to hardware until its user-facing meaning and safe
range have been established.

---

## Memory Read Handler (FUN_00042cac)

### Firmware Validation

```c
// Must pass all checks
if ((param_3 == -1) &&           // Magic: 0xFFFFFFFF
    (param_2 < 0x3d0901) &&      // Size < ~4MB
    (param_1 < 0x983d0901)) {    // Address < ~2.5GB
    // Allow read
} else {
    // Send REJECT (0x06)
}
```

| Parameter | Constraint | Hex Value |
|-----------|------------|-----------|
| param_3 | Must equal -1 | 0xFFFFFFFF |
| param_2 | Size < | 0x3d0901 (~4MB) |
| param_1 | Address < | 0x983d0901 (~2.5GB) |

### Two-Stage Access Control

1) **Firmware gate (above):** Enforces magic, size, and address ceilings; failures return REJECT (0x06).
2) **Hardware encryption (`aes128_ecb_encrypt` @ 0x00001090):** Reads the requested memory through the AES engine at `0x40008010/0x40008020` and encrypts it for transport. Requirements: size 16-byte aligned and pointers 4-byte aligned. Bus faults during the read map to error code 8 -> NOT_READABLE (0x27).

### Response Types

| Response | Hex | Cause |
|----------|-----|-------|
| REJECT | 0x06 | Firmware validation failed |
| NOT_READABLE | 0x27 | Hardware bus fault |
| DATA | (encrypted) | Successful read - 16-byte AES-ECB encrypted blocks |

### Address Blocking

| Address | Result | Notes |
|---------|--------|-------|
| 0xE000ED00 | REJECT | ARM CPUID > 0x983d0901 |
| 0x40048024 | NOT_READABLE | SIM_SDID protected |
| 0x00000420 | DATA (0x1A) | Device info readable |
| 0x40010450 | DATA (0x75) | Hardware ID readable |

### Special Calibration Handling

```c
// Special handling for 0x3000C00 region
if ((uint)(address - 0x3000c00) >> 7 < 3) {  // 0x3000c00-0x3000dff
    int *ptr = &DAT_03000c00;
    while (*ptr != -1 && ptr < &DAT_03000d80) {
        ptr += 0x10;  // 64-byte entries
    }
    if (ptr > (int *)0x3000d40) {
        address = &DAT_03000d80;  // Redirect to end
    }
}
```

---

## Response Building

### Error Code Mapping (FUN_0000ced4)

```c
switch(error_code & 0x1f) {
    case 7:  response = 0x26; break;
    case 8:  response = 0x27; break;  // NOT_READABLE
    case 9:  response = 0x29; break;
    // ...
}
```

### MemoryRead Data

After the framed `0xC4` confirmation, the device sends unframed AES-128-ECB
ciphertext with no application packet header.

---

## GetData Handler (FUN_0004286c)

### Attribute Mask Processing

```c
// At auth level 0, mask is limited
if (auth_level == 0) {
    attribute_mask = attribute_mask & 0x19;  // Only bits 0,3,4
}
```

This limits unauthenticated access to:

- 0x01 (ADC)
- 0x08 (Settings)
- 0x10 (PdPacket)

Higher attributes (AdcQueue 0x02, etc.) require authentication.

### Firmware-only extra attributes

The V1.9.9 handler also builds attributes `0x0020` and `0x0040`. Attribute
`0x0020` is now confirmed by framed hardware responses; `0x0040` remains
firmware-derived because no framed UFCS trace capture is available.

Attribute `0x0020` drains two USB PD state-machine trace queues. Each queue is
encoded as one byte containing its following byte length, then zero or more
fixed five-byte records:

```text
[queue_1_bytes: u8][event_code: u8][uptime_seconds: u32 LE]...
[queue_2_bytes: u8][event_code: u8][uptime_seconds: u32 LE]...
```

The firmware caps each copied queue at 200 bytes. Producers show the first
queue receiving PD state-transition codes. The second queue mixes internal
protocol-engine state transitions with direct receive markers. State `0x00` is
the detached/disabled protocol reset state; `0x82` records completion of
received-message processing, while `0x83` records construction and scheduling
of an extended-message chunk request. The first queue's codes
`0x00..0x24` are mapped by an ordered name table embedded in the firmware; code
`0x25` is emitted by an attached-source CC recheck path but remains unnamed.
See [USB PD State Trace](../features/pd_trace.md) for the complete table. The
timestamp is the firmware millisecond uptime counter divided by 1000.

The logical extended header leaves its size field at zero. A host must derive
the payload boundary from both queue-length prefixes instead of treating the
payload as empty or consuming the remainder of a chained response.

Attribute `0x0040` is the UFCS trace attribute. This is confirmed by the owning
state object, its `TASK_UFCS` initializer, and the RX/TX producers of the event
ring. It starts with a 12-byte preamble followed by variable records:

```text
[uptime_ms_low32: u32]
[measurement_1: u16][measurement_2: u16]
[measurement_3: u16][measurement_4: u16]
[event descriptor: 8 bytes][optional frame bytes]...
```

Each descriptor is `[timestamp_ms: u32][offset_or_value: u8][end_or_value: u8]`
`[payload_len: u8][kind: u8]`. Kind `0` records a received UFCS frame and kind
`1` a transmitted UFCS frame; these descriptors are immediately followed by
`payload_len` frame bytes. Kind `0x40` records a UFCS state event and carries no
trailing frame. Kinds `2` and `3` are supported by the ring code but have no
identified producer in V1.9.9. The four measurement fields are still unnamed.
No framed `0x0040` capture is available, so this exact layout remains
firmware-derived.

---

## Key Addresses Summary

### Functions

| Address | Name | Purpose |
|---------|------|---------|
| 0x0004eaf0 | `dispatch_usb_command` | Main command switch |
| 0x0004286c | `handle_get_data` | GetData handler |
| 0x00042cac | `handle_memory_read` | Memory read with validation |
| 0x00042df4 | `handle_settings_batch` | Shared 0x48/0x4D nested settings handler |
| 0x00000fb0 | `aes128_ecb_decrypt` | Decrypt incoming protocol data |
| 0x00001090 | `aes128_ecb_encrypt` | Encrypt outgoing memory data |
| 0x00017c88 | `crc32_hardware` | Hardware CRC-32/ISO-HDLC |
| 0x0000ced4 | error_map | Error code to response |

### Data

| Address | Purpose |
|---------|---------|
| 0x20003598 | Settings-B runtime block (84 bytes) |
| 0x20004041 | Auth level (0/1/2) |
| 0x200047d4 | Settings-A runtime block (96 bytes) |
| 0x40010450 | Hardware device ID (12 bytes) |
| 0x03000c00 | Calibration table |
| 0x40008010 | AES input register |
| 0x40008020 | AES key register |

---

## Command 0x4B: Offset Memory Read

Similar to 0x44 but adds base offset:

```c
case 0x4b:
    address = requested_address + 0x98000000;
    FUN_00042cac(address, size, param3, param4);
```

Maps 0x00000000 → 0x98000000, likely for specific memory region access.
