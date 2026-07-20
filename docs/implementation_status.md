# km003c-lib Implementation Status

This matrix compares the protocol documented in this repository with the Rust
implementation targeted for the next `km003c-lib` release. The research tools
remain pinned to the published `km003c` 0.2.0 package until that release is
available. “Raw” means framing is preserved but no typed semantic structure is
exposed yet.

| Protocol Area | Rust Library | Python Bindings | Notes |
|---------------|--------------|-----------------|-------|
| Control/Data/extended headers | Implemented | Implemented | Includes chained PutData and typed correlation |
| ADC (`0x0001`) | Implemented | Implemented | Typed `uom` quantities in Rust |
| AdcQueue (`0x0002`) | Implemented | Implemented | Four rates, 1 kHz sequence timebase, rate-dependent auxiliary units |
| PD 12-byte measurements | Implemented | Implemented | One layout/type for standalone, chained, and event preamble measurements |
| PD event stream framing | Implemented | Implemented | Connect/disconnect and raw PD wire frames |
| USB PD semantic decoding | Optional `usbpd` feature | Raw PD wire data | Shared typed decoder is used by km003c-egui and the CLI; Python receives SOP + wire bytes |
| Settings (`0x0008`) | Raw | Raw | Documented fields are not yet a stable typed API |
| LogMetadata (`0x0200`) | Implemented | Raw | Parses empty, single-entry, and multi-entry catalogs |
| MemoryRead (`0x44`) | Implemented | Parse helpers only | Rust validates confirmation and collects multi-transfer ciphertext |
| Offline log workflow | Implemented | Research script | Typed `uom` samples, per-entry offsets, CSV/JSON CLI export |
| StreamingAuth level 1 (`0x4C`) | Implemented | Crypto parsing helpers | HardwareID-based AdcQueue authentication |
| Authentication level 2 | Not implemented | Not implemented | Firmware-derived flow is not reproduced |
| Enable/Disable PD monitor | Implemented | Constants/parsing | Exact device-side effect remains unknown |
| QC/extra attributes | Not implemented | Not implemented | Firmware-derived, not confirmed in framed captures |
| Flash write / command `0x4B` / `0x48` / `0x4D` | Not implemented | Not implemented | Research-only until wire behavior is confirmed |
| Bootloader/firmware update | Not implemented | Not implemented | Separate protocol flow |
| CDC transport | Not implemented | Not implemented | Rust supports vendor bulk and HID interfaces |

The protocol reference is intentionally broader than the library. A documented
firmware capability is not considered implemented until the public API can
construct or parse it and a capture-backed or hardware test covers the path.

See [Protocol Gaps](research/protocol_gaps.md) for the unresolved research
items and [Protocol Reference](protocol_reference.md) for the wire format.
