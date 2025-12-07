# Firmware Overview

Reverse engineering notes for the decrypted KM003C firmware (v1.9.9).

---

## Firmware Properties

| Property | Value |
|----------|-------|
| File | `KM003C_V1.9.9_key0_ecb.bin` |
| Size | 453,616 bytes |
| Architecture | ARM Cortex-M (Thumb mode) |
| Language ID | ARM:LE:32:Cortex |
| Functions | 1,580 |
| Strings | 475 |
| Initial SP | 0x200067b0 |
| Reset Vector | 0x00004295 |

---

## Memory Layout

| Region | Start | End | Size | Description |
|--------|-------|-----|------|-------------|
| ROM | 0x00000000 | 0x0006ebef | 453,616 | Firmware code/data |
| SRAM | 0x20000000+ | - | ~26KB | Stack, heap, variables |
| External | 0x03000xxx | - | 4MB | External flash |
| Peripherals | 0x40000000+ | - | - | MCU peripherals |

---

## RTOS Tasks

The firmware uses a custom RTOS (not FreeRTOS/ThreadX):

| Task Name | Address | Priority | Stack | Purpose |
|-----------|---------|----------|-------|---------|
| PD_PHY | 0x00006460 | 2 | 512B | USB PD physical layer |
| PD_TASK | 0x0000660c | - | - | USB PD protocol logic |
| TASK_CHARGE | 0x00009088 | 2 | 2KB | Charging protocol handling |
| TASK_GUI | 0x0000d5fc | 6 | 4KB | Display/UI management |
| TASK_USER | 0x0001a944 | - | - | User input handling |
| TASK_ADC | 0x000473c0 | 5 | 1KB | ADC measurements |
| TASK_USB | 0x0004d198 | 2 | - | USB host communication |
| TASK_UFCS | 0x0004b14c | 2 | - | UFCS protocol |

### RTOS Primitives

| Function | Address | Purpose |
|----------|---------|---------|
| Task Create | 0x00049c6c | Create new task (magic 0xDAD8) |
| Semaphore Init | 0x00049580 | Initialize semaphore/mutex |
| Queue Init | 0x000499fe | Initialize message queue |
| Delay | 0x00002608 | Task delay (ms) |
| Critical Enter | 0x000002f4 | Enter critical section |
| Critical Exit | 0x000002fc | Exit critical section |

Task creation signature: `(handle, name, entry_point, param, priority 0-9, stack_base, stack_size, config)` with magic `0xDAD8`. GUI runs at priority 6; ADC at 5; PD_PHY/CHARGE/USB/UFCS at 2; idle at 9.

---

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

| Protocol | Vendor | ID |
|----------|--------|-----|
| AFC | Samsung | 5 |
| FCP | Huawei | 6 |
| SCP | Huawei | 7 |
| VFCP | Huawei/vivo | 8 |
| SFCP | Huawei | 9 |
| TFCP | Huawei | 10 |
| SVOOC | OPPO | 11 |
| VOOC | OPPO | 12 |
| MTK PE | MediaTek | 14 |
| MTK PE+ 2.0 | MediaTek | 15 |
| UFCS | China | 16 |
| BC 1.2 | USB-IF | 17 |

Protocol detection switch at `FUN_00016040` (1,534 bytes):

```c
switch(*param_3) {
    case 3:  pcVar3 = "qc2.0:";    break;
    case 4:  pcVar3 = "qc3.0:";    break;
    case 5:  pcVar3 = "afc:";      break;
    case 6:  pcVar3 = "fcp:";      break;
    case 7:  pcVar3 = "scp:";      break;
    case 8:  pcVar3 = "vfcp:";     break;
    case 9:  pcVar3 = "sfcp:";     break;
    case 10: pcVar3 = "tfcp:";     break;
    case 11: pcVar3 = "svooc:";    break;
    case 12: pcVar3 = "vooc:";     break;
    case 14: pcVar3 = "mtkpe:";    break;
    case 15: pcVar3 = "mtkpe2.0:"; break;
    case 16: pcVar3 = "ufcs:";     break;
    case 17: pcVar3 = "bc1.2:";    break;
    case 18: pcVar3 = "detection pd"; break;
    case 19: pcVar3 = "done";      break;
}
```

---

## MCU Identification

**Most Likely:** NXP Kinetis K series (K22/K24/K64/K66)

### Evidence

| Feature | Address/Value |
|---------|---------------|
| SIM unlock magic | 0xa5a50000 @ 0x40048010 |
| DMA unlock magic | 0xa500 @ 0x40053bfc |
| eDMA | 0x40053xxx |
| DMAMUX | 0x40054xxx |
| USB FS | 0x40040xxx |
| I2C | 0x4004e8xx |
| Watchdog | 0x40049xxx |
| Bootloader ROM | 0x1fff8xxx |
| Bit-band alias | 0x42xxxxxx |

### Clock Configuration

- Base oscillator: 16 MHz
- Core frequency: 192 MHz (PLL multiplier 12)
- NVIC registers seen at `0xe000e100` (ISER), `0xe000e280` (ICPR), `0xe000e400` (IPR).

---

## Peripheral Map

| Address | Peripheral | Notes |
|---------|------------|-------|
| 0x40008010 | Hardware AES input | Crypto engine |
| 0x40008020 | Hardware AES key | Key register |
| 0x40015400 | Timer/TPM 0 | FlexTimer |
| 0x40016400 | Timer/TPM 1 | FlexTimer |
| 0x4001dxxx | LPUART/FlexIO | UFCS single-wire |
| 0x40024xxx | CMP/DAC | UFCS support |
| 0x40040000 | USB FS Controller | Device/host |
| 0x40048xxx | SIM SCGC | Clock gating |
| 0x40049xxx | Watchdog | 0x800100b3 config |
| 0x4004a0xx | CMP 0/1 | Analog comparators |
| 0x4004e8xx | I2C | External ADC/sensors |
| 0x40053xxx | eDMA | DMA controller |
| 0x40054xxx | DMAMUX | DMA multiplexer |
| 0x9c000000 | External Memory | LCD controller or QSPI |

---

## I2C Devices

| Address | Device | Notes |
|---------|--------|-------|
| 0x5B (91) | Hynetek PD PHY | CC lines, BMC, VBUS sensing |
| 0x19 (25) | Unknown sensor | Status read at reg 0x31 |

The Hynetek chip (likely HUSB238) handles physical layer; PD protocol stack is in firmware.

---

## USB Stack Initialization

- Init entry: `FUN_000507e8` at base `0x400c0000`.
- Steps: clear pending state → configure FIFO sizes/addresses → set up EP0 (control) → configure bulk endpoints → enable USB interrupts.
- Registers observed: control/status (+0x008..0x018), FIFO (+0x024/+0x028), DFIFO (+0x038), endpoint config (+0x104..0x110), OTG control/status (+0x800+).

## Graphics Library

The firmware uses **LVGL v7.x**:

### Widgets Used

| Widget | Address | Purpose |
|--------|---------|---------|
| lv_bar | 0x000258ec | Progress bars |
| lv_btn | 0x00025c04 | Buttons |
| lv_chart | 0x00027c1c | Graph display |
| lv_img | 0x0002f084 | Image display |
| lv_label | 0x00030470 | Text labels |
| lv_list | 0x00030f38 | Scrollable list |
| lv_table | 0x00037764 | Data table |
| lv_tabview | 0x0003801c | Tabbed interface |

### Display

- Resolution: 240x240 pixels
- Type: IPS LCD 1.5"
- Interface: Likely SPI

---

## USB Type-C State Machine

### Source States

| State | Description |
|-------|-------------|
| UnattachedSource | No connection |
| AttachWaitSource | Waiting for attachment |
| AttachedSource | Connected as source |
| TrySource | Attempting source role |

### Sink States

| State | Description |
|-------|-------------|
| AttachedSink | Connected as sink |
| AttachWaitSink | Waiting for attachment |
| TrySink | Attempting sink role |

### Cable/Accessory States

| State | Description |
|-------|-------------|
| AttachedCable | Cable detected |
| IllegalCable | Invalid cable |
| AttachedLightningPlug | Lightning adapter |
| AttachedMonitor | Display attached |

---

## Cable Detection

### Thunderbolt/USB4

- Passive TBT3/4/5 Cable
- Active TBT3/4/5 Cable
- USB-C eMarker
- Cable Resistance measurement
- VDO manufacturer info

### General Cable Types
- Passive/Active cable detection
- USB-C to C cables
- Cable simulation mode

## Peripheral Map and Unlocks

| Address / Range | Purpose | Notes |
|-----------------|---------|-------|
| 0x40048010 | SIM unlock | Magic `0xa5a50000` |
| 0x40053bfc / 0x400543fe | DMA / DMAMUX unlock | Magic `0xa500` |
| 0x40015400 / 0x40016400 | Timer/TPM 0/1 | FlexTimer |
| 0x4001dxxx | LPUART/FlexIO | UFCS single-wire |
| 0x4004e8xx | I2C | External ADC / sensors / PD PHY |
| 0x40040000 | USB FS controller | Device/host |
| 0x9c000000 | External memory/LCD | Heavily referenced (LCD or QSPI) |
| 0x1fff8xxx | Bootloader ROM | Thunk at 0x1fff8184 |
| 0x42xxxxxx | Bit-band alias | Atomic bit ops |

Magic unlock values and register layout match NXP Kinetis parts. The 0x9c000000 region is accessed with bit masking and likely backs the 240x240 LCD (or external QSPI storage).

### Clock Gating Functions

Two gate helpers mirror the Kinetis SIM layout:

```c
// 0x40048000 with unlock at 0x40048010
clock_gate_1(mask, enable) { _DAT_40048000 = enable ? _DAT_40048000 & ~mask : _DAT_40048000 | mask; _DAT_40048010 = 0xa5a50000; }
// 0x4004800c (no unlock)
clock_gate_2(mask, enable) { _DAT_4004800c = enable ? _DAT_4004800c & ~mask : _DAT_4004800c | mask; }
```

Observed bits: 0x1, 0x2, 0x10, 0x100, 0x8000, 0x20000.

### I2C Bus (External ADC / PD PHY)

- Peripheral: 0x4004e8xx (status at 0x4004e81c, control/ack at 0x4004e820).
- Devices seen:
  - 0x5b: Hynetek PD PHY (likely HUSB238). Regs: 0x02 ctrl, 0x04 mask, 0x10 status, 0x7f reset. Init writes 0xedc0 → 0x02, 0x0f → 0x04.
  - 0x19: Unknown sensor/ADC (status read at reg 0x31).
- Used by TASK_ADC for external measurements.

### External Memory Region (0x9c000000)

Registers at 0x9c000000/4/8/10/14, manipulated with bit clear/set ops. Likely the LCD controller or FlexSPI-mapped external storage used by LVGL.

### Clock Frequency

- Base oscillator: 16 MHz (from PLL calculation)
- UI reports 192 MHz; achieved via PLL multiplier 12 (`16 MHz × 12 ≈ 192 MHz`).

### MCU Candidate / Ruled Out

- Evidence fits NXP Kinetis K-series (SIM unlock 0xa5a50000; eDMA+DMAMUX at 0x40053xxx/0x40054xxx; watchdog 0x40049xxx; USB FS 0x40040xxx; I2C 0x4004e8xx; boot ROM 0x1fff8xxx; bit-band alias 0x42xxxxxx).
- Nuvoton M480 ruled out: base addresses (SYS/CLK/GPIO/PDMA) do not appear; USB/I2C bases differ; no unlock patterns; typical 12 MHz crystal mismatched.

---

## ADC/Measurement System

### Ripple Analysis (FUN_000442e8)

- Sample rate: 2MHz+
- Buffer size: 512 samples
- Processing: Averaging, min/max, FFT

### Voltage Conversion

```c
// Protocol voltage display
voltage_volts = (raw_value >> 3) / 0x7d;  // 125 divisor

// Ripple measurement
ripple_mv = (v_max - v_min) * 9 / 10;
frequency_khz = (peak_index * sample_rate) >> 9 / 1000.0;
```

---

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

Presence of MemManage/BusFault/UsageFault confirms Cortex-M3 or M4 (not M0/M0+).

---

## Device Info Screen

From `FUN_00018334`:

| Row | Label | Value |
|-----|-------|-------|
| 0 | Brand | "POWER-Z" |
| 1 | Model | Dynamic |
| 2 | Clock freq. | 192 MHz |
| 3 | ROM | 4MB |
| 4 | Screen | IPS 1.5'' 240 x 240 |
| 5 | SN | Serial number |
| 6 | Date | Build date |
| 7 | HW | Hardware version |
| 8 | FW | Firmware version |

---

## Notable Strings

### Protocol Detection

```
"qc2.0:", "qc3.0:", "afc:", "fcp:", "scp:", "vfcp:",
"sfcp:", "tfcp:", "svooc:", "vooc:", "mtkpe:", "mtkpe2.0:",
"ufcs:", "bc1.2:", "detection pd", "done"
```

### PD Format Strings

```
"PD3.2", "PD3.1", "%s EPR", "%s,AVS"
"%sPPS: %4.2f-%4.2fV%5.2fA"
"%sFixed: %8.2fV%5.2fA"
"%sAVS: 9-20V%3.2fA,%3.2fA"
```

### PDM Mode

```
"pdm mode entry\nver1.0\n"
"pdm mode entry\nver1.0\nbusy\n"
```

This is the USB communication protocol for host software.

---

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

### Device Info

| Address | String |
|---------|--------|
| 0x0000043c | "1.9.9" (version) |
| 0x000184d4 | "POWER-Z" |
| 0x00018500 | "IPS 1.5'' 240 x 240" |
| 0x0003f0b4 | "pdm mode entry\nver1.0\n" |

---

## Key Functions

| Address | Size | Purpose |
|---------|------|---------|
| 0x00004294 | - | Reset handler (entry point) |
| 0x00006460 | 138 | PD_PHY task init |
| 0x00016040 | 1,534 | Protocol detection |
| 0x0001ba00 | - | PDO formatting (Fixed/PPS/AVS) |
| 0x0003db42 | - | Get PDO count |
| 0x0003dc6c | - | Check EPR capability |
| 0x0003dc90 | - | Check AVS capability |
| 0x000442e8 | - | Ripple voltage analysis |
| 0x0004d198 | 116 | TASK_USB init |
| 0x0004eaf0 | - | Main command dispatcher |
