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
| Attribute `0x0020` | V1.9.9 firmware plus framed empty, active, connect/disconnect, and chained hardware responses | Two length-prefixed queues; Type-C states `0x00..0x24`, protocol disabled state `0x00`, receive marker `0x82`, and extended chunk-request marker `0x83` are identified; Type-C code `0x25` and the remaining protocol-engine states stay lossless and unnamed | Recover protocol state names, capture `0x83`, and compare other firmware versions |
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

The successful update flow, 64-byte descriptor, synchronous erase, raw AES
blocks, independent reply IDs, CRC check and final metadata patch are documented
in [km003c-firmware](https://github.com/okhsunrog/km003c-firmware), alongside
the partial loader dump, selected decompiler exports and hardware evidence. The
[updater implementation snapshot](../firmware/updater_implementation.md) also
records a completed HW 2.1 cycle from original 1.9.9 to 2.0.7 and back, with
full installed-image readback and an unchanged acquired bootloader extent.

Remaining work:

- Acquire the missing initial vector word `[0,4)` through a validated read path.
- Test recovery from interruption during erase, data writes and metadata commit.
- Test deliberate ACK loss on hardware; scripted host tests do not establish
  device-side duplicate/recovery behavior.
- Confirm behavior on other hardware/loader revisions and compatibility of older releases.

JumpDfu `0x09` is an application-side entry operation. It and GetFile `0x0d`
are not implemented cases in the acquired loader's dispatcher. Command names
in a host enum or arbitrary ciphertext bytes are not loader-command evidence.

## Offline Logs

- Identify the log deletion/clear command.
- Test MemoryRead transfer segmentation on HID and non-Linux host stacks.
- Determine whether the final eight LogMetadata bytes are always reserved.
- Decode the LogMetadata field at `0x10`; it changed from `0x0A00` during an
  active recording to `0x0A45` after finalization.

## Hardware and Firmware

Pin mapping, component identification, peripheral bring-up and remaining
hardware questions are maintained with the custom Rust firmware in
[km003c-firmware](https://github.com/okhsunrog/km003c-firmware).

## Evidence Required to Close a Gap

1. Preserve a request and response with source capture and frame numbers.
2. Separate framed protocol bytes from raw encrypted or file-transfer data.
3. Match transaction ID and command/attribute semantics where applicable.
4. Cross-check the relevant firmware or host handler.
5. Add a capture-backed regression test before promoting the behavior to the
   protocol reference.
