# Unknown Commands

Tracker for partially understood or bootloader-specific commands.

For fully documented commands, see [Protocol Reference](../protocol_reference.md).

---

## Command Coverage

### Implemented / Known

| Type | Hex | Name | Status | Notes |
|------|-----|------|--------|-------|
| 0x02 | Connect | Implemented | Session start (optional for AdcQueue) |
| 0x03 | Disconnect | Implemented | Normal session end |
| 0x05 | Accept | Implemented | Ack |
| 0x06 | Reject | Implemented | Error response |
| 0x0C | GetData | Implemented | Attribute mask requests |
| 0x0E | StartGraph | Fully reversed | Rate index 0-3 |
| 0x0F | StopGraph | Fully reversed | |
| 0x10 | EnablePdMonitor | Partially understood | Purpose unclear - PD polling works without it |
| 0x11 | DisablePdMonitor | Partially understood | Purpose unclear - see EnablePdMonitor |
| 0x41 | PutData | Implemented | Data responses |
| 0x44 | MemoryRead | Fully reversed | Offline logs/calibration/firmware info |
| 0x4C | StreamingAuth | Fully reversed | Required for AdcQueue streaming |
| 0x34/0x4E/0x76/0x68 | LogDataChunk* | Documented | Offline log chunks |
| 0x1A/0x3A/0x40/0x75 | DeviceInfo/Firmware/Calibration/Serial | Fully reversed | MemoryRead responses |

### Bootloader/DFU Only

These appear only in firmware update captures (`updating_firmware.*`) and remain unsolved:

| Type | Hex | Count | Notes |
|------|-----|-------|-------|
| 0x00 | Unknown | - | Bootloader? |
| 0x01 | Sync | 113 | Likely firmware data chunks |
| 0x04 | Reset | - | Device-level reset? |
| 0x07 | Finished | - | Update complete? |
| 0x08 | JumpAprom | - | Jump to application? |
| 0x09 | JumpDfu | - | Jump to DFU mode? |
| 0x0B | Error | - | Error response? |
| 0x0D | GetFile | - | File download? |

### Firmware Update Only (0x14-0x7E)

Commands seen only during firmware updates:

```
0x14, 0x15, 0x1C, 0x1D, 0x1F, 0x20, 0x22, 0x23, 0x24, 0x26,
0x27, 0x28, 0x2B, 0x2E, 0x30, 0x32, 0x33, 0x36, 0x38, 0x39,
0x3C, 0x42, 0x46, 0x47, 0x4B, 0x4F, 0x50, 0x52, 0x54, 0x56,
0x58, 0x59, 0x5B, 0x5C, 0x5E, 0x60, 0x61, 0x63, 0x64, 0x67,
0x6D, 0x6E, 0x6F, 0x70, 0x73, 0x77, 0x78, 0x79, 0x7A, 0x7D, 0x7E
```

Type 0x01 appears 113 times - likely firmware chunk transfers.

## Attribute Coverage

| Attribute | Hex | Name | Status | Notes |
|-----------|-----|------|--------|-------|
| 0x0001 | ADC | Implemented | 44-byte snapshot |
| 0x0002 | AdcQueue | Implemented | 20 bytes/sample, streaming |
| 0x0004 | AdcQueue10k | Not implemented | Documented but unused |
| 0x0008 | Settings | Fully reversed | 180 bytes |
| 0x0010 | PdPacket | Implemented | Status (12B) or events (>12B) |
| 0x0020 | PdStatus | Listed | Status only |
| 0x0040 | QcPacket | Listed | Quick Charge data |
| 0x0200 | LogMetadata | Fully reversed | Offline log info |
| 0x0649 | Unknown1609 | Unknown | Seen with Unknown26 |
| 0x564D | Unknown22093 | Data response | Unknown44 response attribute |
| 0x68C1 | Unknown26817 | Unknown | Seen with Unknown58 |

---

## Unknown Attributes

| Attribute | Hex | Seen With | Notes |
|-----------|-----|-----------|-------|
| 0x0649 | 1609 | Unknown26 | Device info related? |
| 0x564D | 22093 | Unknown44 | Alternative firmware info |
| 0x68C1 | 26817 | Unknown58 | Firmware info related? |

---

## Partially Understood Commands

### Command 0x48 (72)

- Handled by FUN_00042df4 in firmware
- Purpose unknown
- Appears in some captures

### Command 0x4D (77)

- Requires auth level 2 (calibration)
- Likely factory/calibration command
- Not accessible without special authentication

---

## Log Data Chunk Types

Sequential chunk markers for large data transfers:

| Type | Hex | Order | Size |
|------|-----|-------|------|
| 0x34 | 52 | 1st | 2544B |
| 0x4E | 78 | 2nd | 2544B |
| 0x76 | 118 | 3rd | 2544B |
| 0x68 | 104 | Final | Variable |

**Question:** Is the sequence fixed, or does it depend on total data size?

---

## Open Questions

### Protocol

- [ ] Full bootloader/DFU protocol documentation
- [ ] What triggers different chunk types (0x34/0x4E/0x76/0x68)?
- [ ] Multiple log selection - how to download specific logs?
- [ ] Log deletion protocol

### Hardware

- [ ] External ADC IC identification (I2C address 0x19)
- [ ] Complete display controller command set
- [ ] External flash memory layout

### Authentication

- [ ] What validates to auth level 2?
- [ ] Calibration data structure at 0x03000C00

---

## Contributing

When analyzing new commands:

1. Capture example packets (request + response)
2. Find handler in firmware (FUN_0004eaf0 switch)
3. Find handler in Mtools.exe if applicable
4. Document packet structure
5. Test minimal requirements
6. Add findings here or to appropriate doc
