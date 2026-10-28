# Hardware and custom firmware

The connected KM003C HW2.1 uses the following hardware. Older photographed
revisions may contain different components.

| Component | Identified hardware |
| --- | --- |
| MCU | HC32F460, Cortex-M4F at 192 MHz; HC32F460JETA/LQFP48 identification supported by teardown markings and the register map |
| MCU memory | 512 KiB internal flash, 188 KiB main SRAM and 4 KiB retention SRAM |
| Measurement | TI INA229 on SPI2, confirmed by hardware IDs and stock initialization |
| Display | 240×240 ST7789-compatible IPS panel on the shared QSPI bus |
| GPIO and backlight | AW9523B at I²C `0x5b` |
| Orientation | SC7A20-family accelerometer at I²C `0x19`, WHO_AM_I `0x11` |
| Storage | 4 MiB external NOR; legacy ID `0x8515`, exact part unresolved |
| USB | Full Speed, Synopsys/DWC2-compatible OTG block with internal PHY |
| Power Delivery | CC comparator, timer and DMA with external analog circuitry; no dedicated PD peripheral identified |
| Buttons | Exit PB7, OK PB11, Left PB8, Right/lightning PB9; active low |

Board bring-up and development of custom Rust firmware using Embassy are in
progress. USB CDC, display/buttons, automatic rotation, INA229 measurement,
D+/D−/CC voltages and passive PD reception in both cable orientations have been
tested on this unit. Active PD transmission remains under development.

Detailed pinouts, peripheral configuration, bootloader/recovery analysis,
implementation and hardware evidence are maintained in
[km003c-firmware](https://github.com/okhsunrog/km003c-firmware).
