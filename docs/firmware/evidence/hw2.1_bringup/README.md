# HW2.1 live bring-up evidence

Captured on 2026-10-28 using the installed 1.9.9 application. The owner held
each key separately while the existing Rust CLI read GPIO input registers.
Raw samples and `live_verification.json` identify Exit PB7, OK PB11, Left PB8
and Right PB9. Released samples confirm all four returned high.

Other binary files are live snapshots of GPIO mux, CMU clocks, peripheral
gates, SPI2, I2C3 and USB core configuration. They are not a complete reset
configuration or a traced electrical schematic.

The `000*.c` files are selected Ghidra exports from the repository's older
1.9.9 application loaded at `0x4000`; their names use runtime addresses.
The `boot-*.c` files are additional exports from the separately acquired HW2.1
bootloader. Decompiled types and local names are inferred, not original source.
Interpretation and confidence limits are in [board bring-up](../../board_bringup.md).

`SHA256SUMS` covers the evidence files in this directory. Check from repository
root with `sha256sum --check docs/firmware/evidence/hw2.1_bringup/SHA256SUMS`.
