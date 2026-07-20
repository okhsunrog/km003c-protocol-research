# USB PD State Trace

Attribute `0x0020` exposes two internal USB PD trace queues. The layout and
producers described here were reverse engineered from KM003C firmware V1.9.9
and verified against framed responses from a device running that version. They
must not be assumed to apply unchanged to other firmware versions.

## Payload Layout

The logical-packet extended header reports a size of zero. A parser must derive
the actual payload size from the two queue prefixes, including when another
logical packet follows in the same `PutData` response.

```text
[state_bytes: u8]
[state_code: u8][uptime_seconds: u32 LE]...
[protocol_bytes: u8]
[protocol_code: u8][uptime_seconds: u32 LE]...
```

Both byte counts must be multiples of five. Each firmware ring holds 40 records,
so each queue contains at most 200 record bytes. Reading the attribute drains
the returned records.

The timestamp is `get_uptime_ms() / 1000`, so its unit and resolution are whole
seconds even though the underlying device uptime has millisecond resolution.

## Type-C State Queue

Firmware contains the state names in numeric order from an explicit
`Disabled = 0` entry. All names through `0x24` are therefore mapped. A producer
also emits `0x25`, but no corresponding name is present; it remains unknown.

| Code | Firmware name | Code | Firmware name |
|------|---------------|------|---------------|
| `0x00` | Disabled | `0x13` | AttachWaitLightningPlug |
| `0x01` | DelayUnattached | `0x14` | AttachedDebSink |
| `0x02` | AttachedResistance | `0x15` | AttachWaitDebSink |
| `0x03` | TryResistance | `0x16` | TryWaitDebSink |
| `0x04` | AttachedDebSource | `0x17` | AttachedSink |
| `0x05` | UnattachedDebSource | `0x18` | AttachWaitSink |
| `0x06` | AttachWaitDebSource | `0x19` | TryWaitSink |
| `0x07` | TryDebSource | `0x1A` | TrySink |
| `0x08` | AttachedSource | `0x1B` | DebugAccessorySink |
| `0x09` | UnattachedSource | `0x1C` | AttachedMonitor |
| `0x0A` | AttachWaitSource | `0x1D` | AttachWaitMonitor |
| `0x0B` | TryWaitSource | `0x1E` | Cable Cross |
| `0x0C` | TrySource | `0x1F` | CablePlugShortCircuit |
| `0x0D` | DebugAccessorySource | `0x20` | ErrorRecovery |
| `0x0E` | AttachedCable | `0x21` | PoweredAccessory |
| `0x0F` | IllegalCable | `0x22` | UnsupportedAccessory |
| `0x10` | AttachWaitCable | `0x23` | AudioAccessory |
| `0x11` | AttachWaitMonitorDefective | `0x24` | AttachWaitAccessory |
| `0x12` | AttachedLightningPlug | `0x25` | Unknown |

The `Deb` spelling is preserved from the firmware strings rather than expanded
speculatively.

Code `0x25` is emitted by a short handler reached from the attached-source poll
path after a delayed CC ADC recheck. The handler toggles two low-level Type-C
controls, but neither the ordered string table nor another independent symbol
provides a semantic state name. Naming it from that behavior alone would be
speculative, so consumers must continue to preserve it as unknown.

## Protocol Event Queue

The second queue mixes internal protocol-engine state transitions with two
direct receive-path markers. The state transition helper stores its argument as
the current protocol-engine state and appends that same byte to the queue. It is
called from more than 100 sites, and no corresponding state-name table has been
found.

One state and two direct markers are independently identified:

| Code | Meaning | Evidence |
|------|---------|----------|
| `0x00` | Disabled | Set by the protocol reset path called as the Type-C state detaches; also present in the hardware disconnect trace |
| `0x82` | ReceivedMessage | Appended at the common completion path after processing a received PD message or extended-message chunk |
| `0x83` | ExtendedChunkRequest | Appended after constructing an extended header with the Chunked and Request Chunk bits and signalling the request to the protocol task |

`0x82` is also present throughout the V1.9.9 Pixel 8 Pro hardware capture. The
`0x83` meaning is firmware-confirmed but has not yet been observed in a trace
response. Other values, including observed states `0x52` and `0x76..0x78`, must
remain lossless unknown values until their complete state semantics can be
established rather than guessed from isolated transitions.

## Firmware Locations

| Address | Name | Purpose |
|---------|------|---------|
| `0x0004286C` | `handle_get_data` | Serializes attribute `0x0020` |
| `0x00002C30` | `drain_5_byte_record_queue` | Drains a queue into the response |
| `0x00002C9E` | `queued_5_byte_record_bytes` | Returns `record_count * 5` |
| `0x0000DFDA` | `enqueue_pd_trace_event` | Appends one code/timestamp record |
| `0x0000ABB8` | `trace_pd_state_event` | Produces Type-C state transitions |
| `0x0000A81C` | `update_and_trace_pd_event` | Produces protocol events |
| `0x00008900` | `process_received_pd_message` | Emits receive markers `0x82` and `0x83` |
| `0x0000CDB2` | `reset_pd_protocol` | Selects protocol state `0x00` while detaching |
| `0x0000CED4` | `run_pd_protocol_state_machine` | Dispatches internal protocol-engine states |
| `0x0006A6A2` | Type-C name table | Ordered state names beginning with `Disabled = 0` |

## Hardware Validation

The request uses logical attribute `0x0020`, encoded as `40 00` in GetData
header bytes 2-3. Tests on V1.9.9 covered all of these cases:

- an empty trace (`00 00` payload);
- a single protocol event in a 15-byte response whose top-level object count
  decodes to zero;
- a full 40-record protocol queue while a Pixel 8 Pro connected;
- Type-C state events on phone connection and disconnection;
- an empty trace followed by attribute `0x0080` in the same response.

The chained capture confirms that the trace's zero size is not a terminator:
both queue prefixes must be consumed before parsing the next extended header.

## Remaining Validation

- Recover names for the remaining protocol-engine states without guessing from
  isolated transitions.
- Capture an extended-message exchange that produces marker `0x83`.
- Check whether other firmware versions use the same state codes and framing.
