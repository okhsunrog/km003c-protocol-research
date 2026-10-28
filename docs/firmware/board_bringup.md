# KM003C HW2.1 board bring-up

## Verified button inputs and recovery

On 2026-10-28, the owner held each named key while GPIO.PIDRB at
`0x40053810` was read through the stock firmware. All four inputs are active-low
with pull-ups. The button mask is `0x0b80`; other port bits changed independently.

| Button | GPIO | LQFP48 pad | Pressed PIDRB |
|--------|------|------------|---------------|
| Exit | PB7 | 43 | `0xef06` |
| OK | PB11 | 44 | `0xc78e` |
| Left | PB8 | 45 | `0xce86` |
| Right / lightning | PB9 | 46 | `0xcd86` |

Released samples were `0xcf86`. With the back face visible, male USB plug up
and HID connector right, these buttons are arranged top to bottom as listed.
The owner then powered the unit down and reconnected its HID USB port while
holding Exit. USB descriptor 2 reported DFU and the Rust updater read its
HW2.1 identity. Sending native JumpAprom returned to application 1.9.9 without
writing flash. Thus physical recovery through Exit is verified on this unit.
It still depends on a working, unchanged bootloader.

## Right / lightning and CC mode

The owner reports that holding Right during power connection enables CC
pull-down. The application participates in this behavior: startup `0x1e8a4`
samples PB9 and passes its active-low result to `0xa5a8`. That function sets
state bit 2 at `0x20004045` and calls `0x43610` with mode 0 or 1.

| Mode at `0x43610` | PB6 output | AW9523B P0_3 |
|------------------|------------|-------------|
| 0 | Low | Input / high impedance |
| 1 | High | Unchanged by this call |
| 2 | Unchanged | Output low |
| 3 | High | Output low |

AW9523B helper `0x1a9c8` writes output register 2 and direction register 4.
The startup pressed path selects mode 1. This establishes software involvement;
the actual resistor/switch network and independent passive effects still need
continuity measurements. Do not assume PB6 alone is the complete Rd circuit.
These function addresses are runtime addresses in the repository's older
1.9.9 image, rather than file offsets or proof of the installed build's layout.

## Live peripheral configuration

The raw register samples and selected decompilations are preserved under
[evidence/hw2.1_bringup](evidence/hw2.1_bringup/README.md).

- I2C3: PC13 AF48 SDA, PH2 AF49 SCL. AW9523B is at `0x5b`;
  orientation-related sensor at `0x19` remains unidentified.
- SPI2: PA8 AF47 SCK, PA10 AF44 MOSI, PB0 AF45 MISO; PA7 is a manual
  active-low chip select. Its external target has not been identified.
- QSPI: PB1 CS0, PB2 IO3, PB10 IO2, PB12 IO1, PB13 IO0, PB14 SCK,
  all AF7. LCD transfers temporarily switch PB1 to GPIO to deselect flash,
  drive PB15 low, use the QSPI direct-command port, then restore flash selection.
  The display and external flash share this controller/bus.
- USB: PA9 VBUS, PA11 DM, PA12 DP, all AF10. PA10 is used by SPI2.
- The photo identification of INA228 does not establish which of these buses
  carries its traffic. SPI2 activity alone is insufficient to relabel it INA229.

Live CMU SCFGR was `0x00212211`; PLLCFGR at `0x40054100` was
`0x01300b00` and UPLLCFGR at `+4` was `0x11101300`. The MPLL source bit
selects XTAL. With the firmware's assumed 16 MHz oscillator, M=1, N=12,
P=1, Q=2 and R=4 give HCLK 192 MHz, PCLK0/1/4 96 MHz, PCLK2/3 48 MHz
and EXCLK 48 MHz. USBCKCFGR `0xa0` selects PLLR / 48 MHz. These frequencies
are register-derived, not oscilloscope measurements.

## USB driver integration

Live reads at `0x400c0040` returned:

| Register | Value | Interpretation |
|----------|-------|----------------|
| GSNPSID | `0x4f54330a` | Synopsys OTG revision 3.30a |
| GHWCFG1 | `0x00000000` | Endpoint direction configuration |
| GHWCFG2 | `0x228ed530` | 5 device endpoints plus EP0; dedicated FS PHY |
| GHWCFG3 | `0x013400e8` | FIFO depth 308 words / 1232 bytes |
| GHWCFG4 | `0x17f08030` | Dedicated TX FIFOs; 5 IN endpoints plus EP0 |

[Embassy's Synopsys driver](https://docs.embassy.dev/embassy-usb-synopsys-otg/git/default/index.html)
is the intended core driver. It requires chip-specific initialization. Use
6 endpoint states and 308 FIFO words, rather than copying an STM32's capacities.
The stock app initialization at runtime `0x51140` sets AF10, routes INTC event
`0x113` to IRQ0 via `0x4005105c`, and ungates USB through PWC.FCG1 bit 8.
It configures NVIC IRQ0 priority `0xf0`. A Rust handler must forward IRQ0 to
`embassy_usb_synopsys_otg::on_interrupt`; INTC route ownership must remain alive.

The [HC32 HAL](https://github.com/okhsunrog/hc32f460-embassy-rs) at
`08a2603185d5acd05fda156e9cef468d47526be1` supplies the PAC, routing, GPIO and
clock support. The KM003C USB adapter and application now live in the separate
[custom firmware repository](https://github.com/okhsunrog/km003c-firmware).

**Embassy CDC enumeration and echo were verified on HW2.1 on 2026-10-28.**
The unmodified Synopsys driver from Embassy revision
`c2413d5994bbd8b7e6d5975fd49e6427cb903a02` worked after correcting the port's
RX FIFO reserve. Two 64-byte OUT payload allocations contribute 32 words;
`extra_rx_fifo_words=32` brings the RX FIFO to the native loader's 64 words.
Leaving the reserve at zero stalled EP0 status handling. Trial EP0 patches and
an alternate USB stack were removed from the final image.

The firmware configures its own HRC/MPLL and SRAM timing: nominal HCLK 192 MHz
and USB PLLR 48 MHz. The loader jumps to the application before executing its
DFU clock/USB initialization; that configuration cannot be inherited at normal
application entry. Separate RX/TX futures with an eight-packet queue passed
byte-for-byte CDC echo for 1, 23, 64, 7, 64, 17, 128, 256 and 512 bytes.

A SysTick deadline returned the experimental image to native DFU after about
20 seconds. It is a software deadline, not an independently running watchdog;
a permanently masked-interrupt or stuck-critical-section failure may prevent it.
Trace logs, panic locations and register snapshots use retention RAM and are
read through the native loader after reset. Full power-loss retention is not
claimed. The exact original 1.9.9 was restored with complete application
readback and unchanged loader bytes. See the
[archived hardware acceptance](https://github.com/okhsunrog/km003c-firmware/tree/main/hardware/usb-cdc)
for hashes, test results and recovery limits.

## Official SDK comparison

Sources used are the official
[DDL Rev3.3.0](https://oss-nc-beijing-2.cecloudcs.com/doc-hc/HC32F460_DDL_Rev3.3.0.zip),
[device pack](https://raw.githubusercontent.com/hdscmcu/pack/master/HDSC.HC32F460.1.0.11.pack)
and [datasheet Rev1.61](https://oss-nc-beijing-2.cecloudcs.com/doc-ds/DS_HC32F460SeriesDatasheet_Rev1.61.pdf).
The datasheet pinout/function tables were extracted with the owner's
`mistral_ocr` CLI, with the LQFP48 diagram also checked visually.

The SDK confirms the GPIO/CMU/PWC/EFM/USB register definitions, AF numbering,
INTC event and native USB global/device/FIFO layout. Its `hc32_ll_usb.c` selects
GCCTL at USB base + `0xe00` and the same core-reset/FIFO programming mechanisms.
This supports using the SDK as a porting reference. It does not prove which
SDK release or library source the manufacturer compiled. For example, current
DDL's `usb_coresoftrst` has a first AHB-idle wait which continues looping after
setting an error flag; a superficial timeout counter is not a bounded wait.
Review actual control flow before borrowing routines.

For a standalone USB application, initialize or explicitly verify:

1. Vectors at `0x4000`, stack in permitted SRAM, `.data` / `.bss`, metadata
   at image offset `0x420`, and VTOR. Stop inherited interrupts before RAM init.
2. SRAM/flash timing and power mode before changing HCLK; clock dividers and
   a valid USB 48 MHz source. Do not assume the main application's clock state
   exists when entered directly from the bootloader.
3. USB gate, pin mux, PHY/core reset, device mode, VBUS behavior and FIFO layout.
4. INTC event routing, vector handler and asynchronous USB task polling.
5. A recovery policy: preserve the original loader/ICG, provide Reset-to-DFU,
   and keep Exit hardware entry. A watchdog needs deliberate configuration;
   it is not automatically enabled by the current loader's ICG.

Neither display, ADC/INA228, sensor, external flash nor PD/CC configuration is
required for the initial Rust execution test or maintenance USB enumeration.

## LQFP48 pad inventory

This is a complete MCU-pad inventory, not a fully traced board schematic.
Unknown nets remain explicitly unresolved. PCR/PFSR are live snapshots.

| LQFP48 pad | Signal | Live PCR / PFSR | Role and evidence limits |
|------------|--------|-----------------|--------------------------|
| 1 | PH2 | `0x0100` / `0x0031` | I2C3_SCL (AF49); group-2 alternate mapping |
| 2 | PC13 | `0x0100` / `0x0030` | I2C3_SDA (AF48); group-2 alternate mapping |
| 3 | PC14 | `0x0000` / `0x0000` | XTAL32_OUT-capable pad; board connection unresolved |
| 4 | PC15 | `0x0000` / `0x0000` | XTAL32_IN-capable pad; board connection unresolved |
| 5 | PH0 | `0x0000` / `0x0000` | Main oscillator pad XTAL_OUT; board crystal connection not continuity-tested |
| 6 | PH1 | `0x0000` / `0x0000` | Main oscillator pad XTAL_IN; board crystal connection not continuity-tested |
| 7 | NRST | - | Active-low reset; board routing unresolved |
| 8 | AVSS/VREFL | - | Analog ground / low reference |
| 9 | AVCC/VREFH | - | Analog supply / high reference |
| 10 | PA0 | `0x0000` / `0x0000` | ADC-capable pin; board net unresolved |
| 11 | PA1 | `0x0000` / `0x0000` | ADC-capable pin; board net unresolved |
| 12 | PA2 | `0x8100` / `0x0000` | Analog-capable; dynamic GPIO manipulation in application; board net unresolved |
| 13 | PA3 | `0x8100` / `0x0000` | Analog-capable; dynamic GPIO manipulation in application; board net unresolved |
| 14 | PA4 | `0x0000` / `0x0000` | Board net unresolved |
| 15 | PA5 | `0x0000` / `0x0000` | Board net unresolved |
| 16 | PA6 | `0x0000` / `0x0000` | Board net unresolved |
| 17 | PA7 | `0x0103` / `0x0000` | SPI2 peripheral chip-select GPIO (active-low in helper 0x7118); external target unresolved |
| 18 | PB0 | `0x0000` / `0x002d` | SPI2_MISO (AF45) |
| 19 | PB1 | `0x0140` / `0x0007` | QSPI_CS0 (AF7); temporarily switched to GPIO for display transfers |
| 20 | PB2 | `0x0100` / `0x0007` | QSPI_IO3 (AF7) |
| 21 | PB10 | `0x0100` / `0x0007` | QSPI_IO2 (AF7) |
| 22 | VCAP_1 | - | Core-regulator capacitor pin |
| 23 | VSS | - | Ground |
| 24 | VCC | - | MCU supply |
| 25 | PB12 | `0x0000` / `0x0007` | QSPI_IO1 (AF7) |
| 26 | PB13 | `0x0000` / `0x0007` | QSPI_IO0 (AF7) |
| 27 | PB14 | `0x0100` / `0x0007` | QSPI_SCK (AF7) |
| 28 | PB15 | `0x0103` / `0x0000` | Display-select GPIO; boot command routine 0xed4 drives it low/high |
| 29 | PA8 | `0x0000` / `0x002f` | SPI2_SCK (AF47) |
| 30 | PA9 | `0x0100` / `0x000a` | USBFS_VBUS (AF10) |
| 31 | PA10 | `0x0000` / `0x002c` | SPI2_MOSI (AF44) |
| 32 | PA11 | `0x0000` / `0x000a` | USBFS_DM (AF10) |
| 33 | PA12 | `0x0000` / `0x000a` | USBFS_DP (AF10) |
| 34 | PA13 | `0x0100` / `0x0000` | SWDIO-capable; debug availability not established |
| 35 | VSS | - | Ground |
| 36 | VCC | - | MCU supply |
| 37 | PA14 | `0x0100` / `0x0000` | SWCLK-capable; debug availability not established |
| 38 | PA15 | `0x0000` / `0x0000` | Board net unresolved |
| 39 | PB3 | `0x0000` / `0x0005` | Timer alternate function 5; exact board net/channel unresolved |
| 40 | PB4 | `0x0000` / `0x0000` | Board net unresolved |
| 41 | PB5 | `0x0000` / `0x0000` | Board net unresolved |
| 42 | PB6 | `0x0002` / `0x0000` | CC-mode control GPIO in startup Right-button path; Rd circuit not continuity-tested |
| 43 | PB7 | `0x0140` / `0x0000` | Exit button; active-low; bootloader stay-in-DFU input |
| 44 | PB11 | `0x0140` / `0x0000` | OK button; active-low; also MCU MD pin |
| 45 | PB8 | `0x0140` / `0x0000` | Left button; active-low |
| 46 | PB9 | `0x0140` / `0x0000` | Right/lightning button; active-low; sampled at application startup |
| 47 | VSS | - | Ground |
| 48 | VCC | - | MCU supply |
