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

| Task Name | Purpose |
|-----------|---------|
| `TASK_CHARGE` | Charging protocol handling |
| `TASK_GUI` | Display/UI management |
| `TASK_USER` | User input handling |
| `PD_PHY` | USB PD physical layer |
| `PD_TASK` | USB PD protocol logic |

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

## Hardware Info

| Component | Details |
|-----------|---------|
| Brand | POWER-Z |
| Display | IPS 1.5" 240x240 |
| Connectivity | USB-C |

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

## Key Functions to Analyze

| Address | Size | Notes |
|---------|------|-------|
| 0x00004294 | - | Reset handler |
| 0x00006608 | - | Referenced by thunk, likely PD-related |
| 0x00008f8c | - | Task-related |
| 0x00009094 | - | Task-related |
| 0x0000653c | - | Referenced by thunk |
| 0x0001bc88 | - | Referenced by thunk |
| 0x0001cd90 | - | Referenced by thunk |

## String Addresses

| Address | String |
|---------|--------|
| 0x0000043c | "1.9.9" (version) |
| 0x000064b0 | "PD_PHY" |
| 0x0000660c | "PD_TASK" |
| 0x00009088 | "TASK_CHARGE" |
| 0x0000d5fc | "TASK_GUI" |
| 0x0001a944 | "TASK_USER" |
| 0x000184d4 | "POWER-Z" |
| 0x00018500 | "IPS 1.5'' 240 x 240" |

## Notes

1. The firmware appears to use LVGL graphics library (`lv_bar` string found)
2. Multiple proprietary fast charging protocols are implemented
3. USB PD up to revision 3.2 with EPR support
4. Thunderbolt 3/4 cable detection capability
5. The base address 0x00000000 suggests this is loaded by a bootloader
