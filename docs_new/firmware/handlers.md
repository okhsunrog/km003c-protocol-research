# Device Firmware Command Handlers

Ghidra analysis of device firmware USB command processing.

For Mtools.exe (Windows app) analysis, see [Mtools Analysis](mtools_analysis.md).

---

## Main Dispatcher: FUN_0004eaf0

The main USB command processor at `0x0004eaf0` uses a switch on `command_type & 0x7F`:

| Command | Hex | Handler | Notes |
|---------|-----|---------|-------|
| Connect | 0x02 | Inline | Returns Accept (0x05) |
| GetData | 0x0C | FUN_0004286c | Builds ADC/PD/Settings responses |
| Unknown | 0x0D | FUN_00042c4a | Data command |
| StartGraph | 0x0E | Inline | Starts streaming |
| StopGraph | 0x0F | Inline | Stops streaming |
| PdEnable | 0x10 | Inline | Enable PD monitoring |
| PdDisable | 0x11 | Inline | Disable PD monitoring |
| MemoryRead | 0x44 | FUN_00042cac | Memory read with validation |
| Unknown72 | 0x48 | FUN_00042df4 | Unknown purpose |
| FlashWrite | 0x4A | Inline | Requires auth level > 0 |
| Unknown75 | 0x4B | FUN_00042cac | Memory read + 0x98000000 offset |
| StreamingAuth | 0x4C | FUN_00000fb0 | AES authentication |

---

## Hardware Crypto Functions

| Function | Address | Purpose | Control Bit |
|----------|---------|---------|-------------|
| FUN_00000fb0 | 0x00000fb0 | AES Encrypt | uRam42100004 = 1 |
| FUN_00001090 | 0x00001090 | AES Decrypt/Read | uRam42100004 = 0 |

### Hardware Registers

| Address | Purpose |
|---------|---------|
| 0x40008010 | AES input data register |
| 0x40008020 | AES key register |

### Usage Pattern

```c
// FUN_00001090 - AES decrypt/memory read
undefined4 FUN_00001090(uint *source, uint size, uint *key, uint *output) {
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
// Check against hardware device ID (0x40010450-0x40010458)
if (decrypted matches device_id) {
    DAT_20004041 = 1;
}
// Or check against calibration data (0x03000c00)
else if (decrypted matches calibration_data) {
    DAT_20004041 = 2;
}
```

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

### Response Types

| Response | Hex | Cause |
|----------|-----|-------|
| REJECT | 0x06 | Firmware validation failed |
| NOT_READABLE | 0x27 | Hardware bus fault |
| DATA | 0x1A, 0x3A, 0x40, 0x75 | Successful read |

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

### Data Response Types

| Type | Hex | Memory Region |
|------|-----|---------------|
| Unknown26 | 0x1A | 0x420 (device info 1) |
| Unknown58 | 0x3A | 0x4420 (firmware info) |
| Head | 0x40 | 0x3000C00 (calibration) |
| Unknown117 | 0x75 | 0x40010450 (device ID) |

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

---

## Key Addresses Summary

### Functions

| Address | Name | Purpose |
|---------|------|---------|
| 0x0004eaf0 | dispatcher | Main command switch |
| 0x0004286c | get_data | GetData handler |
| 0x00042cac | memory_read | Memory read with validation |
| 0x00000fb0 | aes_encrypt | Hardware AES encrypt |
| 0x00001090 | aes_decrypt | Hardware AES decrypt |
| 0x0000ced4 | error_map | Error code to response |

### Data

| Address | Purpose |
|---------|---------|
| 0x20004041 | Auth level (0/1/2) |
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
