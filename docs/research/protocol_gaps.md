# Protocol Gaps

Tracked gaps in the KM003C protocol research. The main
[Protocol Reference](../protocol_reference.md) contains interoperable behavior;
this page records confirmed but incomplete areas and hypotheses that still need
evidence.

## Application Protocol

| Area | Evidence | What Is Known | Missing Work |
|------|----------|---------------|--------------|
| EnablePdMonitor (`0x10`) | Captured request/Accept pairs | PD polling also works without it | Determine the state it changes |
| DisablePdMonitor (`0x11`) | Captured request/Accept pairs | Paired with `0x10` | Determine observable effects |
| Command `0x48` | Firmware dispatcher case at `FUN_00042df4` | Dedicated handler exists | Identify request layout and purpose |
| Command `0x4B` | Shares the memory handler with a `0x98000000` offset | Appears related to stored data | Confirm framing and relation to offline logs |
| Command `0x4D` | Firmware dispatcher and auth-level check | Requires authentication level 2 | Identify payload and factory use |
| Authentication level 2 | Firmware state and checks | Distinct from HardwareID-based level 1 | Reproduce the accepted challenge |
| Attribute `0x0020` | Firmware-derived | Separate PD-related handler exists | Confirm in framed USB traffic |
| Attribute `0x0040` | Firmware-derived | Quick Charge-related handler exists | Confirm layout in framed USB traffic |
| Attribute `0x0004` | Public/vendor naming and host UI | Not used by captured 1000 SPS traffic | Determine whether any firmware implements it |

Settings (`0x0008`) has a partially verified layout and should remain raw until
its fields are independently confirmed. LogMetadata (`0x0200`) is verified as a
catalog of 48-byte entries; only its final eight reserved bytes remain opaque.

## Bootloader and Firmware Update

The `updating_firmware.*` captures contain a separate update flow. The following
named operations are supported by host/firmware evidence, but the complete state
machine and payload framing are not documented:

| Hex | Name | Current Evidence |
|-----|------|------------------|
| `0x01` | Sync | Repeated in update traffic |
| `0x04` | Reset | Named dispatcher operation |
| `0x07` | Finished | Named completion operation |
| `0x08` | JumpAprom | Named application jump |
| `0x09` | JumpDfu | Named DFU jump |
| `0x0B` | Error | Named error response |
| `0x0D` | GetFile | Named file-transfer operation |

Arbitrary bytes inside firmware payloads are not command evidence. Add an
operation here only when it has a framed request/response pair, a matching
dispatcher case, or both.

## Offline Logs

- Identify the log deletion/clear command.
- Test MemoryRead transfer segmentation on HID and non-Linux host stacks.
- Determine whether the final eight LogMetadata bytes are always reserved.

## Hardware and Firmware

- Confirm external ADC identity at I2C address `0x19`.
- Confirm the PD PHY identity from chip markings or a matching register map.
- Document the external flash layout.
- Document the display-controller command set.

## Evidence Required to Close a Gap

1. Preserve a request and response with source capture and frame numbers.
2. Separate framed protocol bytes from raw encrypted or file-transfer data.
3. Match transaction ID and command/attribute semantics where applicable.
4. Cross-check the relevant firmware or host handler.
5. Add a capture-backed regression test before promoting the behavior to the
   protocol reference.
