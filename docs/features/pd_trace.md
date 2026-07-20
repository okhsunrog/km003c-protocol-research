# USB PD State Trace

Attribute `0x0020` exposes two internal USB PD trace queues. The layout and
producers described here were reverse engineered from KM003C firmware V1.9.9.
They must not be assumed to apply unchanged to other firmware versions.

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

## Protocol Event Queue

The second queue records protocol and message-processing events. Its producer
is called from more than 100 sites and accepts a raw byte code. Codes `0x82` and
`0x83` are emitted while processing extended messages, but a complete name
table has not been found. Consumers should preserve unknown codes rather than
assigning names based only on individual call sites.

## Firmware Locations

| Address | Name | Purpose |
|---------|------|---------|
| `0x0004286C` | `handle_get_data` | Serializes attribute `0x0020` |
| `0x00002C30` | `drain_5_byte_record_queue` | Drains a queue into the response |
| `0x00002C9E` | `queued_5_byte_record_bytes` | Returns `record_count * 5` |
| `0x0000DFDA` | `enqueue_pd_trace_event` | Appends one code/timestamp record |
| `0x0000ABB8` | `trace_pd_state_event` | Produces Type-C state transitions |
| `0x0000A81C` | `update_and_trace_pd_event` | Produces protocol events |
| `0x0006A6A2` | Type-C name table | Ordered state names beginning with `Disabled = 0` |

## Remaining Validation

- Preserve framed USB request/response pairs from real hardware.
- Exercise both empty and non-empty queues.
- Capture a chained response to confirm the zero-size extended-header handling.
- Identify the protocol-event enumeration without guessing from isolated uses.
