# KM003C Firmware Analysis

Reverse engineering notes for the decrypted KM003C firmware (v1.9.9).

## Firmware Overview

| Property | Value |
|----------|-------|
| File | `KM003C_V1.9.9_key0_ecb.bin` |
| Size | 453,616 bytes |
| Architecture | ARM Cortex-M (Thumb mode) |
| Language | ARM:LE:32:Cortex |
| Functions | 1,580 |
| Strings | 475 |
| Initial SP | 0x200067b0 |
| Reset Vector | 0x00004295 |

## Memory Layout

| Region | Start | End | Size | Description |
|--------|-------|-----|------|-------------|
| RAM | 0x00000000 | 0x0006ebef | 453,616 | Firmware code/data |
| SRAM | 0x20000000+ | - | ~26KB | Stack, heap, variables |

## RTOS Tasks

The firmware uses an RTOS with the following identified tasks:

| Task Name | Address | Purpose |
|-----------|---------|---------|
| `PD_PHY` | 0x00006460 | USB PD physical layer |
| `PD_TASK` | 0x0000660c | USB PD protocol logic |
| `TASK_CHARGE` | 0x00009088 | Charging protocol handling |
| `TASK_GUI` | 0x0000d5fc | Display/UI management |
| `TASK_USER` | 0x0001a944 | User input handling |
| `TASK_ADC` | 0x000473c0 | ADC measurements |
| `TASK_USB` | 0x0004d198 | USB host communication |

## Supported Charging Protocols

### USB Power Delivery
- PD 2.0, PD 3.0 (SPR)
- PD 3.1 (EPR - Extended Power Range)
- PD 3.2
- PPS (Programmable Power Supply)
- AVS (Adjustable Voltage Supply)

### Qualcomm Quick Charge
- QC 2.0 (5V/9V/12V/20V)
- QC 3.0 / QC 3+
- QC 4 / QC 5

### Proprietary Protocols
| Protocol | Vendor | Notes |
|----------|--------|-------|
| AFC | Samsung | Adaptive Fast Charging |
| FCP | Huawei | Fast Charge Protocol |
| SCP | Huawei | Super Charge Protocol |
| SFCP | Huawei | Super Fast Charge Protocol |
| TFCP | Huawei | Turbo Fast Charge Protocol |
| VFCP | Huawei/vivo | |
| UFCS | China | Universal Fast Charging Specification |
| VOOC | OPPO | |
| SVOOC | OPPO | Super VOOC |
| WARP+ | OnePlus | (via SVOOC) |
| MTK PE+ | MediaTek | Pump Express |
| MTK PE+ 2.0 | MediaTek | Pump Express 2.0 |
| Apple 2.4A | Apple | USB-C identification |
| Samsung 2.0A | Samsung | Legacy detection |
| BC 1.2 | USB-IF | Battery Charging spec |

## Protocol Detection Function

The protocol detection logic is implemented in `FUN_00016040` (1,534 bytes). It uses a switch statement on a protocol identifier to display detection status:

```c
// Protocol detection switch (param_3[0] values)
switch(*param_3) {
    case 3:  pcVar3 = "qc2.0:";    break;  // 0x03
    case 4:  pcVar3 = "qc3.0:";    break;  // 0x04
    case 5:  pcVar3 = "afc:";      break;  // 0x05
    case 6:  pcVar3 = "fcp:";      break;  // 0x06
    case 7:  pcVar3 = "scp:";      break;  // 0x07
    case 8:  pcVar3 = "vfcp:";     break;  // 0x08
    case 9:  pcVar3 = "sfcp:";     break;  // 0x09
    case 10: pcVar3 = "tfcp:";     break;  // 0x0a
    case 11: pcVar3 = "svooc:";    break;  // 0x0b
    case 12: pcVar3 = "vooc:";     break;  // 0x0c
    case 14: pcVar3 = "mtkpe:";    break;  // 0x0e
    case 15: pcVar3 = "mtkpe2.0:"; break;  // 0x0f
    case 16: pcVar3 = "ufcs:";     break;  // 0x10
    case 17: pcVar3 = "bc1.2:";    break;  // 0x11
    case 18: pcVar3 = "detection pd"; break;  // 0x12
    case 19: pcVar3 = "done";      break;  // 0x13
}
```

### Protocol Data Structures (FUN_00016040)

Each protocol type has a specific data structure accessed via offsets in param_3:

| Protocol ID | Offset | Data Description |
|-------------|--------|------------------|
| 3 (QC2.0) | 0x0c | Voltage list (count + values) |
| 4 (QC3.0) | 0x0c | Current voltage + flags |
| 5 (AFC) | 0x18 | Voltage list |
| 6 (FCP) | 0x10 | Voltage list |
| 7 (SCP) | 0x14 | Array of 5 ushorts (voltage/current params) |
| 8 (VFCP/UFCS) | 0x20 | Similar to SCP with UFCS voltage call |

Voltage values are stored as raw ADC counts and converted:
- `(voltage_raw >> 3) / 0x7d` for fixed point to display volts

## Charging Mode Initialization

The TASK_CHARGE creator (`FUN_00008f8c`) initializes different charging modes based on a mode parameter:

```c
// Charging mode initialization (from FUN_00008f8c)
switch(param_1) {
    case 0:  mode = 8;  // Unknown mode
    case 1:  DAT_200046c5 = 2;  // Fall through
    case 2:  mode = 9;  // QC detection mode?
    case 3-4: mode = 1;  // Basic charging
    case 5:  _DAT_200046dc = 0x20002610;  mode = 1;  // Protocol A
    case 6:  _DAT_200046d4 = 0x20003b64;  mode = 1;  // Protocol B
    case 7:  _DAT_200046d8 = 0x2000479c;  mode = 1;  // Protocol C
    case 9:  mode = 2;  // AFC mode?
    case 10: mode = 3;  // FCP mode?
    case 11-13: mode = 4;  // VOOC/SVOOC mode?
    case 14-15: mode = 5;  // MTK PE mode?
    default: mode = 0;
}
```

Each mode configures protocol-specific data structures and handlers for voltage/current negotiation.

## USB-C Type-C State Machine

The firmware implements a complete USB Type-C state machine with the following states:

### Source States
| State | Description |
|-------|-------------|
| `UnattachedSource` | No connection detected |
| `AttachWaitSource` | Waiting for attachment |
| `AttachedSource` | Connected as source |
| `TrySource` | Attempting source role |
| `TryWaitSource` | Waiting in try.SRC |
| `AttachedDebSource` | Debug accessory source attached |
| `UnattachedDebSource` | Debug accessory source unattached |
| `DebugAccessorySource` | Debug accessory mode (source) |

### Sink States
| State | Description |
|-------|-------------|
| `AttachedSink` | Connected as sink |
| `AttachWaitSink` | Waiting for sink attachment |
| `TrySink` | Attempting sink role |
| `TryWaitSink` | Waiting in try.SNK |
| `AttachedDebSink` | Debug accessory sink attached |
| `DebugAccessorySink` | Debug accessory mode (sink) |

### Cable/Accessory States
| State | Description |
|-------|-------------|
| `AttachedCable` | Cable detected |
| `AttachWaitCable` | Waiting for cable |
| `IllegalCable` | Invalid cable detected |
| `CablePlugShortCircuit` | Short circuit on cable plug |
| `AttachedLightningPlug` | Lightning adapter detected |
| `AttachWaitLightningPlug` | Waiting for Lightning adapter |
| `AttachedMonitor` | Monitor/display attached |
| `AttachWaitMonitor` | Waiting for monitor |
| `AttachWaitAccessory` | Waiting for accessory |

## Cable Detection

The device supports comprehensive cable analysis:

### Thunderbolt/USB4 Cables
| Cable Type | String |
|------------|--------|
| `Passive TBT3 Cable` | Thunderbolt 3 passive |
| `Active TBT3 Cable` | Thunderbolt 3 active |
| `Passive TBT4 Cable` | Thunderbolt 4 passive |
| `Active TBT4 Cable` | Thunderbolt 4 active |
| `Passive TBT5 Cable` | Thunderbolt 5 passive |
| `Active TBT5 Cable` | Thunderbolt 5 active |

### General Cable Types
- `Passive Cable` / `Active Cable`
- `USB-C eMarker` - Electronic marker chip
- `USB-C to C Cable`
- `Cable Resistance` - Measures cable resistance
- `Cable vendor` - Reads VDO manufacturer info
- `Cable Simulation` - Cable simulation mode

## PDM Mode (USB Communication)

The firmware supports a "PDM mode" for host communication:
- Entry string: `"pdm mode entry\nver1.0\n"`
- Busy response: `"pdm mode entry\nver1.0\nbusy\n"`

This appears to be the protocol used for USB bulk transfers documented in the protocol specification.

## Hardware Info

| Component | Details |
|-----------|---------|
| Brand | POWER-Z |
| Display | IPS 1.5" 240x240 |
| Connectivity | USB-C |
| ROM | 4MB (external flash at 0x03000xxx) |

## MCU Identification

Based on comprehensive peripheral register and vector table analysis, the MCU is likely an **NXP Kinetis K series** with external memory interface:

### Architecture Confirmation
- **ARM Cortex-M3 or M4** (confirmed by presence of MemManage, BusFault, UsageFault handlers in vector table - these are absent in Cortex-M0/M0+)
- **Initial Stack Pointer**: 0x200067b0 (~26KB stack, suggesting 32-64KB SRAM)
- **Reset Vector**: 0x00004295 (Thumb mode)

### Complete Peripheral Map
| Address Range | Peripheral | Notes |
|---------------|------------|-------|
| 0x40008c00 | Unknown | Written with 0x1e during init |
| 0x40010804 | Unknown | Written with 0x105 |
| 0x40015400 | Timer/TPM 0 | FlexTimer/TPM peripheral |
| 0x40016400 | Timer/TPM 1 | Second timer instance |
| 0x4001dxxx | LPUART/FlexIO | UFCS single-wire communication |
| 0x40024xxx | Unknown (CMP/DAC?) | Used by UFCS |
| 0x40040000 | USB FS Controller | USB device/host controller |
| 0x40040400 | USB Endpoint | Endpoint buffers |
| 0x40048000 | SIM SCGC | Clock gating register 1 |
| 0x4004800c | SIM SCGC | Clock gating register 2 |
| 0x40048010 | SIM Unlock | Magic 0xa5a50000 required |
| 0x40049000 | WDOG | Watchdog timer (0x800100b3 config) |
| 0x40049008 | WDOG Handler | ISR pointer |
| 0x4004a000 | CMP 0 | Analog comparator 0 |
| 0x4004a100 | CMP 1 | Analog comparator 1 |
| 0x4004e800 | I2C Control | I2C peripheral base |
| 0x4004e808 | I2C Config | I2C configuration |
| 0x4004e818 | I2C Timing | Baud rate/timing |
| 0x4004e81c | I2C Status | Transfer status |
| 0x4004e820 | I2C Control | Interrupt acknowledge |
| 0x4004e82c | I2C Filter | Glitch filter config |
| 0x4004e830 | I2C Baud | Baud rate register |
| 0x40052000 | Unknown | Written with 0xb |
| 0x4005200c | Unknown | Written with 0x1 |
| 0x40053000 | DMA Controller | eDMA base |
| 0x40053400 | DMA Channel 1 | Channel configuration |
| 0x40053bfc | DMA Unlock | Magic 0xa500 required |
| 0x40053c46+ | DMA Channels | Channel priority registers |
| 0x40054000 | DMAMUX | DMA channel multiplexer |
| 0x400540c0 | DMAMUX Status | Status/control |
| 0x400543fe | DMAMUX Unlock | Magic 0xa500 required |
| 0x9c000000 | External Memory | LCD controller or QSPI (102 refs) |
| 0x42a7xxxx | Bit-band Alias | Atomic bit manipulation |
| 0x1fff8xxx | Bootloader ROM | Thunk calls to 0x1fff8184 |
| 0xe000exxx | ARM NVIC | Standard Cortex-M addresses |

### Magic Unlock Values
The firmware uses distinctive unlock patterns for certain peripherals:

| Address | Magic Value | Purpose |
|---------|-------------|---------|
| 0x40048010 | 0xa5a50000 | SIM/System unlock |
| 0x40053bfc | 0xa500 | DMA controller unlock |
| 0x400543fe | 0xa500 | DMAMUX unlock |

These unlock patterns are characteristic of NXP Kinetis SIM and DMA peripherals.

### External Memory Region (0x9c000000)
A significant memory-mapped region at 0x9c000000 with 102 cross-references:
- Registers at 0x9c000000, 0x9c000004, 0x9c000008, 0x9c000010, 0x9c000014
- Used with read-modify-write bit operations (e.g., `& 0xffffffdf` to clear bit 5)
- Likely an **LCD controller** (given LVGL graphics usage and 240x240 display)
- Could also be QSPI/FlexSPI external memory interface

### Clock Gating Functions
Two distinct clock gating functions identified:

```c
// FUN_00006900 - Controls 0x40048000 with unlock
void clock_gate_1(uint mask, int enable) {
    if (enable == 1)
        _DAT_40048000 &= ~mask;
    else
        _DAT_40048000 |= mask;
    _DAT_40048010 = 0xa5a50000;  // Unlock
}

// FUN_00006942 - Controls 0x4004800c (no unlock needed)
void clock_gate_2(uint mask, int enable) {
    if (enable == 1)
        _DAT_4004800c &= ~mask;
    else
        _DAT_4004800c |= mask;
}
```

Clock gate bits used: 0x1, 0x2, 0x10, 0x100, 0x8000, 0x20000

### MCU Candidate Analysis
**Most Likely: NXP Kinetis K series with FlexBus or QSPI**

Evidence supporting Kinetis:
1. SIM peripheral layout at 0x40048xxx with unlock pattern
2. eDMA at 0x40053xxx with DMAMUX at 0x40054xxx
3. Watchdog at 0x40049xxx
4. USB FS at 0x40040xxx
5. I2C at 0x4004e8xx
6. Bootloader ROM at 0x1fff8xxx
7. Bit-band aliasing at 0x42xxxxxx

Possible models:
- **Kinetis K22** (Cortex-M4, USB FS, FlexBus)
- **Kinetis K24** (Cortex-M4, USB FS, external memory)
- **Kinetis K64/K66** (Cortex-M4, USB FS/HS, external memory)

The 0x9c000000 region suggests either FlexBus or QSPI interface for external memory/LCD.

### Ruled Out: Nuvoton M480 Series

Comparative analysis rules out Nuvoton M480/M483/M487:

| Check | Expected (Nuvoton M480) | Actual | Match? |
|-------|-------------------------|--------|--------|
| SYS base | 0x40000000 | No refs | ❌ |
| CLK base | 0x40000200 | No refs | ❌ |
| GPIO | 0x40004000 | No refs | ❌ |
| PDMA | 0x40008000 | No refs | ❌ |
| USB | 0x40019000/0x400C0000 | 0x40040000 | ❌ |
| I2C | 0x40020xxx | 0x4004e8xx | ❌ |
| Base crystal | 12 MHz typical | 16 MHz | ❌ |
| Unlock pattern | None | 0xa5a50000 (Kinetis) | ❌ |

The magic unlock values (0xa5a50000 for SIM, 0xa500 for DMA) are characteristic of NXP Kinetis and not used by Nuvoton.

### Live Device Memory Probing

Using the Unknown68 (0x44) memory download command, we tested readability of various addresses:

| Address | Result | Notes |
|---------|--------|-------|
| 0xE000ED00 | REJECTED | ARM CPUID blocked |
| 0x40048024 | NOT READABLE | SIM_SDID blocked |
| 0x40010450 | **READABLE** | Returns 12 bytes |
| 0x00000420 | **READABLE** | Device info (encrypted) |
| 0x00004420 | **READABLE** | Device info (encrypted) |
| 0x40040000 | CONFIRM ONLY | USB controller |
| 0x1FFF0000 | NOT READABLE | ROM area blocked |

The device restricts access to MCU identification registers (ARM core, SIM) via the memory download command, but allows reading from specific flash/info areas.

Data from 0x40010450 (12 bytes): `af0469d71a17914910f8c607`

### Clock Frequency Analysis

**Device Info Screen reports: 192 MHz**

With a 16 MHz crystal (confirmed from firmware PLL calculation), 192 MHz is achievable with PLL multiplier of 12:
- 16 MHz × 12 = 192 MHz

This is within the capability of:
- NXP Kinetis K64/K66 (up to 180 MHz typical, some parts to 200 MHz)
- Nuvoton M480 (up to 192 MHz) - but peripheral layout doesn't match
- High-speed Kinetis variants or derivatives

### I2C Bus (External ADC/Sensors)
The I2C peripheral at 0x4004e8xx is used for external sensor communication:
- **Status Register**: 0x4004e81c - Bit 6 indicates busy, Bit 17 indicates transfer complete
- **Control Register**: 0x4004e820 - Used to acknowledge/clear interrupts
- 23 references found in I2C driver functions (0x0001db8c - 0x0001de54)
- Used by TASK_ADC for reading external ADC/power measurement ICs

#### I2C Devices Identified
| Address | Purpose | Key Registers |
|---------|---------|---------------|
| 0x5b (91) | Hynetek USB PD PHY chip | 0x02 (ctrl), 0x04 (mask), 0x10 (status), 0x7f (reset) |
| 0x19 (25) | Unknown sensor/IC | 0x31 (status read) |

The 0x5b device is a **Hynetek PD PHY chip** (likely HUSB238 or similar) - string "Hynetek" found at 0x0006aa54. Handles:
- CC line monitoring and BMC encoding/decoding
- VBUS sensing
- Physical layer signaling

The actual PD protocol stack (state machine, PDO negotiation) is implemented in firmware (PD_PHY, PD_TASK tasks).
- `FUN_00016b28`: I2C write to address 0x5b
- `FUN_0001695c`: I2C read from address 0x5b
- Initialization writes 0xedc0 to reg 0x02, 0x0f to reg 0x04

### Clock Configuration

The MCG (Multipurpose Clock Generator) uses a **16 MHz** base oscillator:

```c
// Clock calculation from FUN_00001b60
freq = (((PLL_CONFIG << 15) >> 23) + 1) * (16000000 / ((PLL_CONFIG & 0x1f) + 1))
       / ((PLL_CONFIG >> 28) + 1);
```

### NVIC Configuration (ARM Standard)
| Address | Register | Purpose |
|---------|----------|---------|
| 0xe000e100 | NVIC_ISER | Interrupt Set Enable |
| 0xe000e280 | NVIC_ICPR | Interrupt Clear Pending |
| 0xe000e400 | NVIC_IPR | Interrupt Priority |

## USB Stack Analysis

The USB stack initializes via `FUN_000507e8` with peripheral base `0x400c0000`:

### USB OTG Register Offsets (from decompilation)
| Offset | Purpose |
|--------|---------|
| +0x008 | Control register |
| +0x00C | Configuration |
| +0x010 | Status register |
| +0x014-0x18 | Interrupt registers |
| +0x024, 0x028 | FIFO configuration |
| +0x038 | DFIFO address |
| +0x104-0x110 | Endpoint configuration |
| +0x800 | OTG control/status |
| +0x804 | OTG mode register |
| +0x810-0x81C | OTG config registers |
| +0xE00 | Endpoint 0 control |

### USB Initialization Sequence
1. Clear pending state, set control registers
2. Configure FIFO sizes and addresses
3. Set up endpoint 0 (control)
4. Configure bulk endpoints for data transfer
5. Enable USB interrupts

## RTOS Analysis

The RTOS appears to be a **custom/proprietary implementation** (not FreeRTOS/ThreadX):

### Task Creation Function (`FUN_00049c6c`)
```c
// Signature pattern
undefined4 FUN_00049c6c(
    undefined4 *taskHandle,   // Task control block
    char *taskName,           // Task name string
    int entryPoint,           // Task function
    undefined4 param,         // Task parameter
    uint priority,            // 0-9, 9 = highest
    int stackBase,            // Stack memory
    uint stackSize,           // Stack size in bytes
    int param8                // Additional config
);

// Task signature magic: 0xDAD8
// Priority levels: 0-9 (9 = system level)
```

### RTOS Primitives
| Function | Address | Purpose |
|----------|---------|---------|
| Task Create | 0x00049c6c | Create new task |
| Semaphore Init | 0x00049580 | Initialize semaphore/mutex |
| Queue Init | 0x000499fe | Initialize message queue |
| Delay | 0x00002608 | Task delay (ms) |
| Critical Section | 0x000002f4, 0x000002fc | Enter/exit critical |

### Task Priority Assignments
| Priority | Tasks |
|----------|-------|
| 9 | System idle |
| 6 | TASK_GUI |
| 5 | TASK_ADC |
| 2 | PD_PHY, TASK_CHARGE, TASK_USB, TASK_UFCS |

### Task Entry Points
| Task | Creator | Entry Point | Stack Size |
|------|---------|-------------|------------|
| TASK_ADC | 0x00047384 | 0x0001dc1d | 0x400 (1KB) |
| TASK_CHARGE | 0x00008f8c | 0x0001e109 | 0x800 (2KB) |
| TASK_GUI | 0x0000d5c0 | 0x0001e8a5 | 0x1000 (4KB) |
| PD_PHY | 0x00006460 | 0x0001ea91 | 0x200 (512B) |
| TASK_UFCS | 0x0004b14c | - | - |
| TASK_USB | 0x0004d198 | - | - |

## Graphics Library (LVGL)

The firmware uses **LVGL v7.x** based on widget naming:

### LVGL Widgets Used
| Widget | Address | Purpose |
|--------|---------|---------|
| lv_bar | 0x000258ec | Progress bars |
| lv_btn | 0x00025c04 | Buttons |
| lv_btnmatrix | 0x00026b30 | Button matrix (menu) |
| lv_chart | 0x00027c1c | Chart/graph display |
| lv_cont | 0x0002896c | Container |
| lv_img | 0x0002f084 | Image display |
| lv_label | 0x00030470 | Text labels |
| lv_line | 0x0003073c | Line drawing |
| lv_list | 0x00030f38 | Scrollable list |
| lv_msgbox | 0x00032a78 | Message dialogs |
| lv_obj | 0x00034b58 | Base object |
| lv_page | 0x00035a58 | Scrollable page |
| lv_slider | 0x00036674 | Slider control |
| lv_switch | 0x00036cc0 | Toggle switch |
| lv_table | 0x00037764 | Data table |
| lv_tabview | 0x0003801c | Tabbed interface |
| lv_win | 0x0003b468 | Window |

### Display Driver
- Resolution: 240x240 pixels
- Type: IPS LCD
- Interface: Likely SPI (based on typical designs)

## ADC/Measurement System

### Ripple Voltage Analysis (FUN_000442e8)
High-speed ADC sampling for voltage ripple measurement:
- **Sample Rate**: 2MHz+ (controlled by `uVar8 > 2000000` check)
- **Buffer Size**: 512 samples (0x200)
- **Processing**: Averaging, min/max detection, FFT for frequency
- **Output**: kHz frequency, mV ripple voltage, V/A measurements

### Voltage Conversion
Raw ADC values are converted using:
```c
// Protocol voltage display
voltage_volts = (raw_value >> 3) / 0x7d;  // 125 divisor

// Ripple measurement
ripple_mv = (v_max - v_min) * 9 / 10;
frequency_khz = (peak_index * sample_rate) >> 9 / 1000.0;
```

### Key Measurement Functions
| Function | Purpose |
|----------|---------|
| FUN_000442e8 | Ripple voltage/frequency analysis |
| FUN_0003366a | Get ADC data structure |
| FUN_0004340c | Check measurement ready |
| FUN_000433b8 | Get sample rate |
| FUN_0001504c | FFT/signal processing |
| FUN_000157d0 | Data transformation |

## Device Info Screen Data

From `FUN_00018334` (About/Info screen):
| Row | Label | Value Source |
|-----|-------|--------------|
| 0 | Brand | "POWER-Z" (static) |
| 1 | Model | Dynamic (from 0x4430?) |
| 2 | Clock freq. | Dynamic (MHz calculation) |
| 3 | ROM | "4MB" (static) |
| 4 | Screen | "IPS 1.5'' 240 x 240" |
| 5 | SN | Dynamic (serial number) |
| 6 | Date | Dynamic (build date) |
| 7 | HW | Dynamic (hardware version) |
| 8 | FW | Dynamic (firmware version) |

## Interesting Strings

### UI Messages
```
"Detecting AFC\nplease wait..."
"Detecting PD Protocol\nplease wait..."
"Find PD charger"
"Find apple USB-C charger"
"Find UFCS"
"USB mode is running"
```

### Protocol Detection
```
"detection pd"
"mtkpe2.0:"
"svooc:"
"vooc:"
"tfcp:"
"sfcp:"
"qc3.0:"
"qc2.0:"
"afc:"
"scp:"
"fcp:"
"vfcp:"
"ufcs:"
"bc1.2:"
```

### PD Messages
```
"PD3.2"
"PD3.1"
"%s EPR"
"%s,AVS"
"%sPPS: %4.2f-%4.2fV%5.2fA"
"%sFixed: %8.2fV%5.2fA"
"%sAVS: 9-20V%3.2fA,%3.2fA"
```

### VDO/Cable Info
```
"HW:%04x FW:%04x\nVDO:%1x v:%d"
"Vdo object hex"
"IdHead"
"CertStat"
"Cable"
"TBT3/4"
"Manufacturer Info"
```

### Measurements
```
"Vbus:%5.3fV\nCC1:%5.3fV CC2:%5.3fV"
"zDVoltage: %5.2f - %5.2fV\nCurrent: %5.2f - %5.2fA\n"
```

### Menu Items
```
"Chart"
"Tools"
"record"
"analyzer"
```

## Vector Table

| Offset | Handler | Address |
|--------|---------|---------|
| 0x000 | Initial SP | 0x200067b0 |
| 0x004 | Reset | 0x00004295 |
| 0x008 | NMI | 0x0000a459 |
| 0x00C | HardFault | 0x00006cad |
| 0x010 | MemManage | 0x00009491 |
| 0x014 | BusFault | 0x00005b59 |
| 0x018 | UsageFault | 0x000115b7 |
| 0x02C | SVCall | 0x0000e815 |
| 0x038 | PendSV | 0x00004377 |
| 0x03C | SysTick | 0x0000f64d |

## External References

The firmware references external functions in the bootloader/ROM area:
- `thunk_EXT_FUN_1fff8184` at 0x00000460 - Points to 0x1fff8184 (likely bootloader ROM)

## Key Functions

| Address | Size | Name/Purpose |
|---------|------|--------------|
| 0x00004294 | - | Reset handler (entry point) |
| 0x00006460 | 138 | PD_PHY task initialization |
| 0x0000ce04 | - | PD task caller (calls PD_PHY) |
| 0x00016040 | 1,534 | Protocol detection (switch statement) |
| 0x0001ba00 | - | PDO formatting (Fixed/PPS/AVS) |
| 0x0004d198 | 116 | TASK_USB initialization |
| 0x00049c6c | - | RTOS task creation |
| 0x00049580 | - | RTOS semaphore/mutex init |
| 0x000499fe | - | RTOS queue init |
| 0x0003db42 | - | Get PDO count |
| 0x0003dc6c | - | Check EPR capability |
| 0x0003dc90 | - | Check AVS capability |
| 0x0003db2c | - | Get PDO list pointer |
| 0x0001785a | - | Display string (UI output) |
| 0x000178e8 | - | Display formatted string (printf-like) |
| 0x00050964 | - | String formatting (sprintf-like) |

## String Addresses

### Task Names
| Address | String |
|---------|--------|
| 0x000064b0 | "PD_PHY" |
| 0x0000660c | "PD_TASK" |
| 0x00009088 | "TASK_CHARGE" |
| 0x0000d5fc | "TASK_GUI" |
| 0x0001a944 | "TASK_USER" |
| 0x000473c0 | "TASK_ADC" |
| 0x0004d20c | "TASK_USB" |

### Device Info
| Address | String |
|---------|--------|
| 0x0000043c | "1.9.9" (version) |
| 0x000184d4 | "POWER-Z" |
| 0x00018500 | "IPS 1.5'' 240 x 240" |
| 0x0003f0b4 | "pdm mode entry\nver1.0\n" |

### Protocol Strings
| Address | String |
|---------|--------|
| 0x00016698 | "mtkpe2.0:" |
| 0x000166a4 | "mtkpe:" |
| 0x000166ac | "svooc:" |
| 0x000166b4 | "vooc:" |
| 0x000166bc | "tfcp:" |
| 0x000166c4 | "sfcp:" |
| 0x000166cc | "qc3.0:" |
| 0x000166d4 | "qc2.0:" |
| 0x000166dc | "afc:" |
| 0x000166e4 | "scp:" |
| 0x000166ec | "fcp:" |
| 0x000166f4 | "vfcp:" |
| 0x000166fc | "ufcs:" |
| 0x00016704 | "bc1.2:" |

### PD Format Strings
| Address | String |
|---------|--------|
| 0x00023b50 | "PD3.2" |
| 0x00023b60 | "PD3.1" |
| 0x00023b58 | "%s EPR" |
| 0x00023b68 | "%s,AVS" |
| 0x0001bbd0 | "%sPPS: %4.2f-%4.2fV%5.2fA" |
| 0x0001bbec | "%sFixed: %8.2fV%5.2fA" |
| 0x0001bb88 | "%sAVS: 9-20V%3.2fA,%3.2fA" |
| 0x0003cb0c | "PD%d.0 %dW" |
| 0x0003cb18 | "PD%d.1 %dW" |
| 0x0003cb24 | "PD%d.2 %dW" |
| 0x0003cb00 | "EPR Capable" |

### Measurement Strings
| Address | String |
|---------|--------|
| 0x00024290 | "Vbus:%5.3fV\nCC1:%5.3fV CC2:%5.3fV" |
| 0x000433a0 | "1M 50uS" (sampling rate) |

## Notes

1. The firmware appears to use LVGL graphics library (`lv_bar` string found)
2. Multiple proprietary fast charging protocols are implemented (17+ protocols)
3. USB PD up to revision 3.2 with EPR support (240W capable)
4. Thunderbolt 3/4/5 cable detection capability with active/passive differentiation
5. The base address 0x00000000 suggests this is loaded by a bootloader
6. PDM mode v1.0 is the USB communication protocol for host software
7. Complete USB Type-C state machine implementation per USB-IF spec
8. RTOS-based architecture with 7 identified tasks
9. External bootloader ROM functions called via thunk at 0x1fff8184
10. Lightning adapter detection capability (for testing Apple accessories)
11. Cable simulation mode for testing purposes
12. High voltage warning system for device protection
13. DPS (Dynamic Power Sharing) support indicated by "PD%d.2 %dW DPS:%2dW" format string
14. External ADC/power measurement IC accessed via I2C bus (0x4004e8xx peripheral)
15. FlexTimer/TPM peripheral at 0x40015400 used for timing and possibly CC line monitoring
16. Bit-band aliasing (0x42a7xxxx) used for atomic peripheral register bit manipulation
17. High-speed ADC sampling for ripple analysis (512 samples at 2MHz+, FFT for frequency detection)
18. Protocol-specific voltage capability structures with count + voltage array format

## Unknown68 (0x44) Memory Read Command - Access Control

The Unknown68 command allows reading memory from the device via USB. The firmware implements a **two-stage access control mechanism**:

### Stage 1: Firmware Validation (FUN_00042cac at 0x00042cac)

Before attempting to read memory, the firmware validates the request parameters:

```c
// Address validation in FUN_00042cac (line 11)
if (((param_3 == -1) && (param_2 < 0x3d0901)) && (param_1 < 0x983d0901)) {
    // Read allowed - proceed to hardware read
    DAT_20010b00 = 0xc4;  // Response type: confirm (0x44 | 0x80)
    // ... read data in 0x9f0 byte chunks via FUN_00001090
}
else {
    // Validation failed - send REJECT response
    local_24 = CONCAT11(transaction_id, 0x06);  // Response type: 0x06
    FUN_0004f080(&local_24, 4, 1000);  // Send 4-byte rejection
}
```

**Validation Rules:**
| Parameter | Constraint | Hex Value | Meaning |
|-----------|------------|-----------|---------|
| param_3 | Must equal -1 | 0xFFFFFFFF | Magic constant from protocol |
| param_2 | Must be < 0x3d0901 | 4,000,001 | Size limit (~4MB) |
| param_1 | Must be < 0x983d0901 | 2,554,759,425 | Address limit (~2.5GB) |

**Examples:**
| Address | Passes Validation? | Reason |
|---------|-------------------|--------|
| 0x00000420 | ✓ Yes | 0x420 < 0x983d0901 |
| 0x40048024 | ✓ Yes | 0x40048024 < 0x983d0901 |
| 0xE000ED00 | ✗ No | 0xE000ED00 > 0x983d0901 (ARM CPUID blocked) |
| 0xFFFFFFFF | ✗ No | 0xFFFFFFFF > 0x983d0901 |

### Stage 2: Hardware Read (FUN_00001090 at 0x00001090)

For addresses that pass validation, the firmware attempts the actual memory read via hardware:

```c
// Hardware crypto read function (FUN_00001090)
undefined4 FUN_00001090(uint *source_addr, uint size, uint *aes_key, uint *output) {
    // Validate alignment: size must be 16-byte aligned, pointers 4-byte aligned
    if (((size & 0xf) == 0) && (((uint)source_addr | (uint)aes_key | (uint)output) & 3) == 0) {
        // Write AES key to hardware crypto at 0x40008020
        for (i = 0; i < 4; i++) DAT_40008020[i] = aes_key[i];

        // Read source data to hardware crypto at 0x40008010
        for (i = 0; i < 4; i++) DAT_40008010[i] = source_addr[i];  // <-- Can fault here!

        // Wait for encryption and return
        // ...
    }
}
```

If the hardware read fails (e.g., accessing protected peripheral registers), the MCU generates a bus fault. This is caught by the error handling system:

**Error Code Mapping (FUN_0000ced4 at 0x0000ced4):**
```c
// Error code 8 → Response 0x27 (NOT_READABLE)
switch(error_code & 0x1f) {
    case 7:  response = 0x26; break;
    case 8:  response = 0x27; break;  // NOT_READABLE
    case 9:  response = 0x29; break;
    // ...
}
```

### Response Types Summary

| Response | Hex | Meaning | Cause |
|----------|-----|---------|-------|
| REJECT | 0x06 | Validation failed | Address > 0x983d0901 or size > 0x3d0901 |
| NOT_READABLE | 0x27 | Hardware read failed | Protected peripheral, unmapped memory |
| CONFIRM | 0x44 | Request received | Precedes data response |
| DATA | 0x1A, 0x2C, 0x3A, 0x75 | Memory data | Successful read |

### Tested Address Behavior

| Address | Description | Response | Notes |
|---------|-------------|----------|-------|
| 0x00000420 | Device info block 1 | DATA (0x1A) | ✓ Readable, encrypted |
| 0x00004420 | Device info block 2 | DATA | ✓ Readable, encrypted |
| 0x03000C00 | Calibration/config | DATA | ✓ Readable |
| 0x40010450 | Unknown peripheral | DATA (0x75) | ✓ Readable (12 bytes) |
| 0x40048024 | SIM_SDID | NOT_READABLE (0x27) | Hardware-protected |
| 0xE000ED00 | ARM CPUID | REJECT (0x06) | Address > 0x983d0901 |
| 0x1FFF0000 | Bootloader ROM | NOT_READABLE | Hardware-protected |

### Special Address Handling (0x3000C00 Region)

The dispatcher (FUN_0004eaf0) has special handling for the calibration area:

```c
// Case 0x44 special handling for calibration region
if ((uint)(address - 0x3000c00) >> 7 < 3) {  // Address in 0x3000c00-0x3000dff
    // Search for valid entry (not -1)
    int *ptr = &DAT_03000c00;
    while (*ptr != -1 && ptr < &DAT_03000d80) {
        ptr += 0x10;  // 64-byte entries
    }
    if (ptr > (int *)0x3000d40) {
        address = &DAT_03000d80;  // Redirect to end of table
    }
}
```

This allows reading calibration data stored in 64-byte entries, stopping at the first empty (0xFFFFFFFF) slot.

### AES Keys for Memory Read

The memory read uses hardware AES encryption. Keys are stored at 0x0006e8cc:

| Key Index | Value | Usage |
|-----------|-------|-------|
| 0 | `Lh2yfB7n6X7d9a4Z` | Default memory read |
| 1 | `Ea0b4tA25f4R038a` | Alternative mode |

**Note:** The Python scripts use key `Lh2yfB7n6X7d9a5Z` (with '5'), which appears to be a slight variation that also works. The firmware may accept both.

### Case 0x4B: Offset Memory Read

Command 0x4B is similar to 0x44 but adds an offset to the address:

```c
case 0x4b:
    address = requested_address + 0x98000000;  // Add offset
    FUN_00042cac(address, size, param3, param4);
```

This maps addresses like 0x00000000 → 0x98000000, potentially for reading from a specific memory region.

## Correlation with Protocol Research

The firmware analysis confirms several findings from the USB protocol research:

| Firmware Finding | Protocol Research Correlation |
|------------------|-------------------------------|
| TASK_ADC | ADC attribute (0x0001) data packets |
| TASK_USB | USB bulk transfer handling |
| PDM mode v1.0 | GetData/PutData command structure |
| Protocol switch IDs | Protocol detection attribute values |
| PD format strings | PdPacket attribute (0x0010) parsing |

## Future Analysis

### Completed
- [x] Decompile TASK_CHARGE to understand charging state machine
- [x] Analyze PD_TASK for USB PD message handling
- [x] Identify ADC peripheral register addresses (I2C at 0x4004e8xx)
- [x] Map peripheral registers (I2C, Timer, GPIO, Comparator)
- [x] Identify task entry points and stack sizes

### Remaining
- [ ] Map RTOS memory structures (queues, semaphores)
- [ ] Trace USB endpoint configuration in detail
- [ ] Identify external ADC IC model (via I2C address analysis)
- [ ] Reverse engineer PD voltage/current negotiation algorithm
- [ ] Analyze UFCS protocol implementation
- [ ] Map display controller command sequences
- [ ] Identify external flash memory chip and layout
