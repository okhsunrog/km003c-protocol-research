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
| Commands `0x48` / `0x4D` | V1.9.9 `handle_settings_batch` (0x00042df4) | Nested operations mutate settings; language, uncalibrated flag, brightness, orientation, device mode, selected page, and LogMetadata append are identified; `0x4D` requires auth level 2 | Name the remaining bitfields and capture safe read/write exchanges |
| Command `0x4B` | Shares the memory handler with a `0x98000000` offset | Appears related to stored data | Confirm framing and relation to offline logs |
| Attribute `0x0020` | V1.9.9 PD trace producers and `handle_get_data` | Two length-prefixed PD state-machine queues; records are event code plus uptime seconds | Map event-code enums and confirm in framed USB traffic |
| Attribute `0x0040` | V1.9.9 `TASK_UFCS`, RX/TX producers, and `handle_get_data` | UFCS measurement preamble and variable RX/TX/state event stream | Name four measurements, map all event kinds, and confirm in framed USB traffic |
| Attribute `0x0004` | Public/vendor naming and host UI | Not used by captured 1000 SPS traffic | Determine whether any firmware implements it |

Settings (`0x0008`) is confirmed to concatenate independently checksummed
96-byte and 84-byte firmware structures. Its storage boundaries, calibration
arrays, checksums, and several bitfield locations are known, but most
user-facing names still need independent confirmation. The public library now
uses a lossless read-only wrapper: it validates both CRCs, exposes only the
confirmed fields semantically, and preserves everything else as raw block
data. LogMetadata (`0x0200`) is verified as a catalog of 48-byte entries, and
settings operation `0x28` appends records to that same catalog. The field at
`0x10` and final eight reserved bytes remain opaque.

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
- Decode the LogMetadata field at `0x10`; it changed from `0x0A00` during an
  active recording to `0x0A45` after finalization.

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
