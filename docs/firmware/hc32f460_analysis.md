# HC32F460 Register Analysis

Reinterpretation of the KM003C application and bootloader using the identified
HC32F460 MCU. This page distinguishes register definitions, instructions in the
binaries, and conclusions that still require hardware measurements.

## Sources and Inputs

- [tomoca2's KM003C teardown, January 6, 2024](https://tomoca2.hatenablog.com/entry/2024/01/06/091942):
  physical chip identification; specifications and photograph are summarized in
  the [firmware overview](overview.md#mcu-identification).
- [HDSC HC32F460 device pack 1.0.11](https://www.keil.arm.com/packs/hc32f460-hdsc/versions/),
  distributed through Arm Keil. The
  [vendor-hosted pack](https://raw.githubusercontent.com/hdscmcu/pack/master/HDSC.HC32F460.1.0.11.pack)
  supplies `Device/Include/HC32F460.h`, `SVD/HC32F460.svd`,
  `Device/Source/system_hc32f460.c`, and `HDSC.HC32F460.pdsc`.
  Downloaded pack SHA-256:
  `43ed3801ae30013f1c0008e7be7b70f19acb14cf78cd7233c3e2edcdfebc8173`.
- Application: repository file `fw/KM003C_V1.9.9_key0_ecb.bin`, 453,616 bytes,
  SHA-256 `9ce6125da454585fde1b5744018f94edc697a23941292cbf55d2a411d4df7517`.
- Bootloader: locally preserved read of addresses `0x00000004–0x00003fff`
  from KM003C HW 2.1 / FW 1.9.9, 16,380 bytes, SHA-256
  `17d51eeff9fb6abe1a7024a108006248e0aaebdaae52de69a3e26c000565d4bf`.
  Its acquisition metadata records two identical reads and independent prefix
  checks. Bytes `0x00000000–0x00000003` are missing; this is not a complete
  bootloader image. The acquired bytes are now preserved as
  [a partial binary](../../fw/bootloader_hw2.1_00000004-00003fff.bin), with
  [detailed bootloader logic](bootloader.md) and supporting exports.

The audit used Capstone 5.0.9 in Thumb/M-class mode, decoding instructions and
following literal loads and `MOVW`/`MOVT` address construction. Linear scans
only located candidates: the sequences below were inspected individually.
Floating-point constants, jump tables, and arbitrary words resembling peripheral
addresses are not evidence of register accesses.

## Application Load Address and Existing Labels

**The application file starts at flash address `0x4000`, not zero.** Its first
two words are initial SP `0x200067b0` and reset vector `0x00004295`.
The reset instruction is at file offset `0x294`, hence runtime `0x4294`.

The bootloader independently confirms the mapping:

| Bootloader runtime address | Instruction or action |
|----------------------------|-----------------------|
| `0x1a02–0x1a08` | Read `0x4420`; require application metadata value `0x4000` |
| `0x1a16–0x1a2a` | Validate application SP at `0x4000` against the main SRAM range |
| `0x1a2c–0x1a36` | Read reset vector from `0x4004`; write `0x4000` to SCB.VTOR |
| `0x1a3a–0x1a40` | Load application MSP and branch to its reset vector |

Older Ghidra `FUN_...` code labels in this repository use image offsets.
For those labels, `runtime = image_offset + 0x4000`. Literal register, RAM,
pointer, and vector-table values must **not** have this offset added.

| Function | Existing image-offset label | Runtime address |
|----------|-----------------------------|-----------------|
| AES decrypt | `0x00000fb0` | `0x00004fb0` |
| AES encrypt | `0x00001090` | `0x00005090` |
| MemoryRead | `0x00042cac` | `0x00046cac` |
| USB dispatcher | `0x0004eaf0` | `0x00052af0` |

For example, the dispatcher at runtime `0x52b16` masks the command with
`0x7f`. Loading the binary at zero instead gives incorrect branch targets and
misaligns absolute flash pointers with their contents.

## Register Identities and Instruction Evidence

All instruction addresses in the following table are **runtime addresses**.
An address passed to a driver identifies its target peripheral, but does not
by itself identify the external component attached to it.

| Register/block | Vendor identity | Binary evidence |
|----------------|-----------------|-----------------|
| `0x40048010` | `PWC.FCG0PC`, clock-gating protection | Application `0x5dfc` writes `0xa5a50001`; `0x5e10` writes `0xa5a50000`. Bootloader `0x1ac2` / `0x1acc` does the same unlock/lock sequence. |
| `0x40053bfc` | `GPIO.PWPR`, pin write protection | Application `0x61ba` / `0x61ca` writes `0xa501` / `0xa500` around a pin-configuration change. Bootloader `0x19e4` / `0x19ee` repeats this pattern. |
| `0x40040000` | `ADC1.STR` | Application `0x690e` clears the start register; `0x54ba–0x54e4` accesses analog-watchdog registers `AWDSR`, `AWDCHSR`, and `AWDCR` in the same block. |
| `0x40054020` | `CMU.SCFGR` | Application clock setup at `0x602c` programs bus dividers; bootloader `0x1a50` writes `0x00212211`. |
| `0x40054100` | `CMU.PLLCFGR` | Application `0x6124–0x6152` programs PLL multipliers/dividers; bootloader `0x1a54` writes `0x13702f81`. |
| `0x40016400` | `TMRA6` | Application `0x5e58` constructs the peripheral address; subsequent calls pass it to timer drivers. |
| `0x40024000` | `TMR01` | Application `0x4f662` constructs the address and passes it to timer setup calls at `0x4f66c` and `0x4f676`. |
| `0x4001d004` | `USART1.TDR` | Application `0x4f3e8–0x4f3ec` puts this address into `DMA1.DAR0` at `0x40053044`, connecting the UFCS transmit path to USART1. |
| `0x4004e800` | `I2C3` | Application `0x6e0c–0x6e6c` configures the controller; bootloader `0x60c–0x632` also initializes it. |
| `0x400c0000` | `USBFS` | Application `0x5119e` constructs the controller base; bootloader `0x1d62` loads it and then accesses the USB global register block. |
| `0x9c000000` | `QSPI` | Application `0xd6e2–0xd6f4` configures `CR`, `CSCR`, `FCR`, and `CCMD`. `0xd51a` writes `0x05` to `DCOM`; `0xd51c` reads it back. |

Other vendor-defined blocks include TimerA2 (`0x40015400`), DMA1/DMA2
(`0x40053000` / `0x40053400`), GPIO (`0x40053800`), and CMU (`0x40054000`).
The `0x40053xxx` range contains both DMA and GPIO; it cannot be assigned one
peripheral name as a whole.

## SRAM, RAM Code, and OTP

The vendor pack declares these memories for its 512 KiB variants, including
the photographically identified `HC32F460JETA`:

| Memory | Start | Length | Exclusive end |
|--------|-------|--------|---------------|
| Internal flash | `0x00000000` | `0x80000` (512 KiB) | `0x00080000` |
| Main SRAM | `0x1fff8000` | `0x2f000` (188 KiB) | `0x20027000` |
| Retention SRAM | `0x200f0000` | `0x1000` (4 KiB) | `0x200f1000` |
| OTP | `0x03000c00` | `0x3fc` (1,020 bytes) | `0x03000ffc` |

The application contains an initialization-table record at file offset
`0x6de58` (runtime `0x71e58`):

```text
source flash address = 0x00071eb8  (file offset 0x6deb8)
destination          = 0x1fff8000
length               = 0x00000684
initialization helper= 0x000549c8
```

The startup walker at `0x4c5c–0x4c74` dispatches these records; helper
`0x549c8–0x549d4` copies words from the source to the destination. The thunks at
runtime `0x4460` and `0x446a` branch to Thumb pointers `0x1fff8185` and
`0x1fff826f`. Their targets lie inside that SRAM initialization region;
decoding the corresponding bytes in the image yields Thumb functions.
These are application RAM-code targets, not evidence of a ROM bootloader.

The separate bootloader also writes variables in this SRAM: `0x1abc` stores
its clock-frequency value at `0x1fff8090`. Its reset startup at `0x48` loads
SP `0x1fffb908`. Thus an address below `0x20000000` is not necessarily ROM.

The calibration records at `0x03000c00` and `0x03000d80` are within the
vendor-declared internal OTP region. They must not be described as a 4 MB
external-flash allocation. The external flash's full layout and device identity
still require separate analysis.

## Clock Setup

Application initialization at runtime `0x602c` (file offset `0x202c`) performs:

1. Unlock `PWC.FPRC` at `0x400543fe` with `0xa501`.
2. Configure bus dividers in `CMU.SCFGR` and enable/check the external oscillator.
3. Select external oscillator input for MPLL if the oscillator-stop status is
   clear; otherwise select the internal high-speed RC input (`PLLSRC`, bit 7).
4. Program `MPLLN=11`, `MPLLP=0`, `MPLLQ=1`, `MPLLR=3` in `CMU.PLLCFGR`.
   This routine leaves `MPLLM` unchanged; its vendor reset value is zero.
5. Enable MPLL, wait for its stable flag, select clock source 5 in `CMU.CKSWR`,
   and relock `PWC.FPRC`.
6. Store `0x0b71b000` (`192000000`) at RAM address `0x200000c4` at `0x621e`.

For a 16 MHz input and `MPLLM=0`, the vendor clock formula gives:

```text
MPLL P output = input / (MPLLM + 1) * (MPLLN + 1) / (MPLLP + 1)
              = 16 MHz / 1 * 12 / 1 = 192 MHz
```

The application's clock calculation at `0x5b80–0x5bb2` independently reads
`PLLCFGR`, extracts these fields, and uses the constant `16000000`.
The bootloader programs a different PLL configuration and stores
`0x0a037a00` (`168000000`) at `0x1fff8090`.
Configured values and frequency constants establish firmware intent; they
do not measure the active clock or prove which oscillator path a particular
device took.

## Crypto and Unique ID

The vendor map confirms the existing AES data/key interpretation:

| Address | Register | Firmware use |
|---------|----------|--------------|
| `0x40008000` | `AES.CR` | Start and direction control |
| `0x40008010–0x4000801c` | `AES.DR0–DR3` | Four data words, read and written |
| `0x40008020–0x4000802c` | `AES.KR0–KR3` | Four key words |
| `0x40010450–0x40010458` | `EFM.UQID0–UQID2` | Vendor-defined 96-bit unique-ID registers |

At runtime `0x4fdc–0x4ff6`, the decrypt routine constructs data address
`0x40008010`, adds `0x10` to obtain the key address, and writes the four key
words. Bit-band addresses `0x42100000` and `0x42100004` access `AES.CR`
bits 0 and 1. Decrypt writes direction 1 at `0x5030`; encrypt writes direction
0 at `0x5110`. The same data/key addresses occur in the bootloader's AES code.

The failed MemoryRead at `0x40048024` does not identify a chip-ID register or
prove a security restriction. This address is not a named register in the
vendor PWC SVD. Keep the observed failure separate from its unproven cause.

## AW9523B at I2C Address 0x5B

The teardown photograph shows an AWINIC `AW9523B` marking. The
[manufacturer's product page](https://www.awinic.com/en/productDetail/AW9523BTQR)
identifies it as a 16-port GPIO/LED controller. Its
[manufacturer-authored datasheet, V1.1.1](https://download.kamami.pl/p587253-AW9523%2BEnglish%2BDatasheet.pdf)
defines address bits `10110 AD1 AD0`, permitting 7-bit addresses `0x58–0x5B`.
The following application sequences match its register map, not just its address.
All code locations here are runtime addresses.

The write wrapper at `0x1ab28` preserves its register argument, sets device
address `0x5b` at `0x1ab3e`, and calls the I2C write routine at `0x21e54`.
The read wrapper at `0x1a95c` sets the same device address at `0x1a972` and
calls `0x21b8c`. Both wrappers retry after I2C recovery on an error.

| Application instruction/call | Operation through the 0x5B wrapper | AW9523B meaning |
|------------------------------|-----------------------------------|-----------------|
| `0x1a884–0x1a888` | Write `0x00` to register `0x7f` | Software reset |
| `0x1a894–0x1a898` | Read register `0x10` | Device ID (datasheet value `0x23`; this sequence alone does not establish the returned value) |
| `0x1a8aa–0x1a8b4` | Write bytes `c0 ed` starting at `0x02` | P0/P1 output latches |
| `0x1a8c0–0x1a8c8` | Write bytes `0f 00` starting at `0x04` | P0/P1 directions |
| `0x1a8ce–0x1a8d6` | Write `0x0f` to `0x12` | P0 GPIO/LED selection |
| `0x1a8da–0x1a8e6` | Write `0xf3` to `0x13` | P1 GPIO/LED selection |
| `0x1a8ec–0x1a8f4` | Write `0x10` to `0x11` | Global control |
| `0x1a900–0x1a904` | Write two zero bytes starting at `0x22` | P1_2/P1_3 dimming |
| `0x1a90e–0x1a912` | Write four bytes starting at `0x28` | P0_4–P0_7 dimming |

The bootloader independently uses address `0x5b` in its write wrapper at
`0x122e`, reads ID register `0x10` at `0x1138–0x113c`, and writes
`0x12=0x0f`, `0x13=0xf3`, and `0x11=0x10` at `0x1166–0x1176`.

The application values resolve some logical pin roles: P0_0–P0_3 are GPIO
inputs, P0_4–P0_7 are LED-current outputs, and P1_2/P1_3 are LED-current
outputs. The remaining P1 pins are GPIO outputs. These mode settings do not
identify the PCB nets, keys, LEDs, reset lines, or control signals attached to
each pin. In particular, identifying AW9523B does not identify an external
PD transceiver.

## Sensor at I2C Address 0x19

The application read wrapper at `0xd9d2` and write wrapper at `0xda20` use
the same I2C routines as AW9523B but set the device address to `0x19`.
At `0x47f98–0x47fbe`, firmware reads register `0x31`, masks its low nibble,
and maps values 1–8 through a small lookup table. Initialization at `0x47fea`
writes `0x20=0x1f`, then `0x20=0x27`, `0x21=0xc0`, `0x23=0x10`,
`0x30=0xff`, and `0x32=0x0f`. This is consistent with the orientation-sensor
role. Subsequent HW2.1 reads returned WHO_AM_I `0x11`; XYZ and 6D operation
identify the SC7A20 family. The exact suffix/revision remains unconfirmed. The
custom driver and four-way display rotation are now hardware-accepted; see
[board bring-up](board_bringup.md#accelerometer-and-automatic-display-rotation-2026-10-28).

This is distinct from the photographed INA228: TI's
[address table](https://www.ti.com/document-viewer/INA228/datasheet/GUID-E4E4E716-7FF4-403D-AA16-CF0C7187D9F5)
permits addresses `0x40–0x4f`. The photo's `228I` marking matches TI's
[official marking information](https://www.ti.com/ods/sysadd/oa/symlink/ina228_oa.pdf).

On the tested HW2.1 device, the measurement target is now confirmed as INA229:
SPI2 manufacturer/device reads returned `0x5449` / `0x2291`. It is separate
from the sensor at `0x19`. See [hardware acceptance](board_bringup.md#ina229-acceptance-against-stock-207-2026-10-28).

## Remaining Hardware Questions

- Validate current calibration across ranges and resolve the exact SC7A20 suffix/revision at `0x19`.
- Map AW9523B ports to PCB signals, including any display or PD-control lines.
- Recover the external-flash part number, capacity, and complete storage layout.
- Trace display commands and pin routing independently of the QSPI register block.
- Validate actual clocks and oscillator fallback on hardware if needed.
- Recheck other firmware versions and board revisions before generalizing these results.
