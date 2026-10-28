# Firmware Overview

Reverse engineering notes for the decrypted KM003C firmware (v1.9.9).

Code and string locations below retain the original image-offset labels unless
explicitly identified as runtime addresses. The application is loaded at
`0x00004000`; add `0x4000` to an image offset to obtain its flash address.
Register addresses and raw vector-table values are already runtime addresses.
See [HC32F460 Register Analysis](hc32f460_analysis.md) for the verified mapping.

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
| Application image | 0x00004000 | 0x00072bef | 453,616 bytes | File mapped into internal flash |
| Main SRAM | 0x1fff8000 | 0x20026fff | 188 KiB | Includes RAM-resident code and application data |
| Retention SRAM | 0x200f0000 | 0x200f0fff | 4 KiB | Separate retained RAM bank |
| OTP/calibration | 0x03000c00 | 0x03000ffb | 1,020 bytes | Internal OTP region in the vendor device pack |
| QSPI registers | 0x9c000000 | - | - | Controller registers, not the external flash contents |
| Peripherals | 0x40000000+ | - | - | MCU peripherals |

---

## RTOS Tasks

The native firmware uses **TencentOS tiny / derivative**. The exact release or
commit has not been established. The task and primitive mappings below remain
reverse-engineered binary observations, not symbols from a version-matched source
build.

This identification is useful for matching task creation, synchronization objects,
timeouts and scheduler behavior against TencentOS tiny. Structure layouts, tick
rate and configuration-dependent behavior still need verification against the
particular firmware; do not infer them from an arbitrary upstream release.
The custom Rust firmware uses Embassy and does not depend on this native kernel.

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

**Teardown evidence:** The author identifies the MCU in the photographed KM003C
as a Huada/HDSC **HC32F460**. The article does not specify its ordering suffix.
The component photograph resolves the marking as `F460JETA`, consistent with
**HC32F460JETA** in LQFP48 (12 exposed leads on each side).
See tomoca2's
[January 6, 2024 teardown and repair article](https://tomoca2.hatenablog.com/entry/2024/01/06/091942)
and its [component-side photograph](https://cdn-ak.f.st-hatena.com/images/fotolife/t/tomoca2/20240105/20240105220534.jpg).

The article reports these MCU specifications:

| Property | Reported value |
|----------|----------------|
| Core | ARM Cortex-M4 with floating-point support |
| Clock capability | 200 MHz |
| Internal flash | 512 KB |
| SRAM | 192 KB, including 32 KB high-speed RAM |
| Retention RAM | 4 KB RRAM |

The article identifies the examined PCB as manufactured on September 12, 2022.
It also shows a KAMCAP 3.0 V, 0.35 F supercapacitor. These observations apply to
the photographed hardware; they do not establish the part fitted to every
KM003C revision. The V1.9.9 application and the separately captured HW 2.1
bootloader independently match the HC32F460 register map in the
[official HDSC device pack](https://www.keil.arm.com/packs/hc32f460-hdsc/versions/).

### Clock Configuration

- Firmware clock calculation uses a 16 MHz input.
- Initialization programs MPLLN=11, MPLLP=0 and selects MPLL. With MPLLM=0,
  this gives 192 MHz; the routine also stores `192000000` in RAM. This is
  firmware evidence, not a measurement of the physical clock. The teardown's
  200 MHz describes MCU capability, not the configured KM003C clock.
- NVIC registers seen at `0xe000e100` (ISER), `0xe000e280` (ICPR), `0xe000e400` (IPR).
- Architecture: ARM Cortex-M4F, supported by the chip identification and vendor pack.

---

## Peripheral Map (HC32F460)

Names below are matched against the vendor SVD/header and firmware accesses.
Detailed instruction locations and the evidence limits are recorded in
[HC32F460 Register Analysis](hc32f460_analysis.md).

| Address | Peripheral | Notes |
|---------|------------|-------|
| 0x40008010 | AES.DR0 | First of four data words |
| 0x40008020 | AES.KR0 | First of four key words |
| 0x40010450 | EFM.UQID0 | First of three unique-ID words |
| 0x40015400 | TMRA2 | TimerA instance 2 |
| 0x40016400 | TMRA6 | TimerA instance 6 |
| 0x4001d000 / 0x4001d400 | USART1 / USART2 | Serial peripherals used in UFCS code |
| 0x40024000 | TMR01 | Timer0 instance 1 |
| 0x40040000 | ADC1 | Internal ADC registers |
| 0x40048000 | PWC.FCG0 | Peripheral clock gating |
| 0x40048010 | PWC.FCG0PC | Clock-gating write protection |
| 0x40049000 | WDT | Watchdog |
| 0x4004a000 / 0x4004a010 / 0x4004a020 | CMP1 / CMP2 / CMP3 | Analog comparators |
| 0x4004e800 | I2C3 | I2C controller |
| 0x40053000 / 0x40053400 | DMA1 / DMA2 | DMA controllers |
| 0x40053800 | GPIO | GPIO and pin configuration |
| 0x40053bfc | GPIO.PWPR | Pin write protection |
| 0x40054000 | CMU | Clock management |
| 0x400c0000 | USBFS | USB full-speed controller |
| 0x9c000000 | QSPI | External-flash controller registers |
| 0x1fff8000+ | Main SRAM | Includes functions called through RAM thunks |
| 0x42000000–0x43ffffff | Peripheral bit-band aliases | ARM mechanism; not a chip-family identifier |

---

## External Components and I2C Devices

The same [component photograph](https://cdn-ak.f.st-hatena.com/images/fotolife/t/tomoca2/20240105/20240105220534.jpg)
provides additional component evidence:

| Component | Evidence | Limits |
|-----------|----------|--------|
| AWINIC AW9523B | Visible marking; the application and bootloader register sequences match its GPIO/LED register map | Individual PCB signal assignments remain to be recovered |
| TI INA228 (teardown specimen) | Visible `228I` marking and 10-pin package match TI's [package marking addendum](https://www.ti.com/ods/sysadd/oa/symlink/ina228_oa.pdf) | Our HW2.1 unit instead returned INA229 IDs over SPI2; see below |

| Address | Device | Notes |
|---------|--------|-------|
| 0x5B (91) | AW9523B GPIO/LED controller | Reset, ID, direction, GPIO/LED mode and dimming registers match the vendor map in both binaries |
| 0x19 (25) | SC7A20-family accelerometer (tested HW2.1: WHO_AM_I `0x11`) | Read of reg 0x31 and configuration of regs 0x20, 0x21, 0x23, 0x30 and 0x32 |

The [AW9523B product documentation](https://www.awinic.com/en/productDetail/AW9523BTQR)
describes 16 GPIO/LED outputs. The matching firmware evidence is detailed in
[HC32F460 Register Analysis](hc32f460_analysis.md#aw9523b-at-i2c-address-0x5b).
Address `0x5B` must not be used as evidence of an external PD PHY. The external
PD/CC circuitry remains to be reconstructed independently.

TI specifies INA228 addresses in the range `0x40–0x4F`; neither address listed
above is an INA228 address. Do not assign the photographed INA228 to the
sensor at `0x19`.

On the tested HW2.1 unit, SPI2 returned manufacturer/device IDs `0x5449` /
`0x2291`, confirming **INA229**. The Rust driver collected 360 samples and
passed concurrent USB echo. This runtime identification is separate from the
teardown photo. See [board acceptance](board_bringup.md#ina229-acceptance-against-stock-207-2026-10-28).

---

## USB Stack Initialization

- USBFS register base: `0x400c0000`. The earlier `FUN_000507e8` label points
  to USB task setup (image offset `0x507e8`, runtime `0x547e8`); it should not
  be treated as the entry of a single low-level hardware initialization routine.
- Steps: clear pending state → configure FIFO sizes/addresses → set up EP0 (control) → configure bulk endpoints → enable USB interrupts.
- Global control/status registers occupy `+0x008..+0x018`.
- `+0x024` is GRXFSIZ (RX FIFO depth); `+0x028` is the non-periodic TX /
  device EP0 TX FIFO size/start register, not a FIFO data port.
- `+0x038` is the generic Synopsys GGPIO location, not DFIFO. The HC32 vendor
  header leaves this slot reserved; STM32-specific GCCFG bit meanings must not
  be assumed to apply to HC32.
- `+0x104..+0x114` are DIEPTXF1..5 (TX FIFO size/start registers).
- Device control/status starts at `+0x800`; IN endpoint registers start at
  `+0x900`, OUT endpoint registers at `+0xb00`, each with stride `0x20`.
- FIFO data windows start at `+0x1000`, with stride `0x1000` per FIFO.

These offsets are relative to `0x400c0000`, cross-checked against the vendor
CMSIS header and the
[Synopsys register definitions in Linux DWC2](https://github.com/torvalds/linux/blob/master/drivers/usb/dwc2/hw.h).
They describe the register map; they do not establish that every listed register
is accessed by a particular firmware routine.

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

A [September 2025 replacement report](https://www.reddit.com/r/UsbCHardware/comments/1njcblc)
describes a working 1.54-inch, 240x240 SPI replacement advertised with an ST7789
driver. This is owner-reported compatibility evidence, not identification of
the original display controller. The firmware UI string rounds the display
size to 1.5 inches.

---

## USB Type-C State Machine

### Source States

| State | Description |
|-------|-------------|
| UnattachedSource | No connection |
| AttachWaitSource | Waiting for attachment |
| AttachedSource | Connected as source |
| TrySource | Attempting source role |
| TryWaitSource | Waiting in try.SRC |
| AttachedDebSource | Debug accessory source attached |
| UnattachedDebSource | Debug accessory source unattached |
| DebugAccessorySource | Debug accessory mode (source) |

### Sink States

| State | Description |
|-------|-------------|
| AttachedSink | Connected as sink |
| AttachWaitSink | Waiting for attachment |
| TrySink | Attempting sink role |
| TryWaitSink | Waiting in try.SNK |
| AttachedDebSink | Debug accessory sink attached |
| DebugAccessorySink | Debug accessory mode (sink) |

### Cable/Accessory States

| State | Description |
|-------|-------------|
| AttachedCable | Cable detected |
| IllegalCable | Invalid cable |
| AttachedLightningPlug | Lightning adapter |
| AttachedMonitor | Display attached |
| AttachWaitCable | Waiting for cable |
| CablePlugShortCircuit | Short circuit on cable plug |
| AttachWaitLightningPlug | Waiting for Lightning adapter |
| AttachWaitMonitor | Waiting for monitor |
| AttachWaitAccessory | Waiting for accessory |

## Charging Mode Initialization

`FUN_00008f8c` selects protocol/charging modes:

| Mode Param | Resulting Mode | Notes |
|------------|----------------|-------|
| 0 | 8 | Unknown mode |
| 1 | 2 | Falls through from case 1 to 2 |
| 2 | 9 | QC detection? |
| 3–4 | 1 | Basic charging |
| 5 | 1 | Sets `_DAT_200046dc = 0x20002610` (protocol A) |
| 6 | 1 | Sets `_DAT_200046d4 = 0x20003b64` (protocol B) |
| 7 | 1 | Sets `_DAT_200046d8 = 0x2000479c` (protocol C) |
| 9 | 2 | AFC mode? |
| 10 | 3 | FCP mode? |
| 11–13 | 4 | VOOC/SVOOC family |
| 14–15 | 5 | MTK PE family |
| default | 0 | |

Each mode configures protocol-specific data structures and handlers for voltage/current negotiation.

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

```text
"qc2.0:", "qc3.0:", "afc:", "fcp:", "scp:", "vfcp:",
"sfcp:", "tfcp:", "svooc:", "vooc:", "mtkpe:", "mtkpe2.0:",
"ufcs:", "bc1.2:", "detection pd", "done"
```

### PD Format Strings

```text
"PD3.2", "PD3.1", "%s EPR", "%s,AVS"
"%sPPS: %4.2f-%4.2fV%5.2fA"
"%sFixed: %8.2fV%5.2fA"
"%sAVS: 9-20V%3.2fA,%3.2fA"
```

### PDM Mode

```text
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
