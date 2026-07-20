# PD Analysis

USB Power Delivery capture and SQLite export format.

For packet headers and general protocol, see [Protocol Reference](../protocol_reference.md).

---

## Overview

The KM003C can capture USB PD messages and export them to SQLite. PD data appears in two contexts:

1. **USB protocol:** PdPacket attribute (0x0010) in PutData responses
2. **SQLite export:** Official app exports to `.db` files

---

## PD Measurement Block (12 bytes)

Standalone PD status, the PD part of a chained ADC+PD response, and the
preamble of a PD event stream all use the same layout:

- `[0..3] timestamp_ms (u32 LE, monotonic device time)`
- `[4..5] vbus_mV (u16)`
- `[6..7] ibus_mA (i16, signed)`
- `[8..9] cc1_mV (u16)`
- `[10..11] cc2_mV (u16)`

This was checked across 1,278 captured PD blocks: 1,182 standalone/chained
12-byte blocks and 96 event streams. Within each capture the counter was
monotonic, and its delta tracked host elapsed milliseconds at a median ratio
of approximately 1.00005.

When no event is queued, the PdPacket payload is just this 12-byte block.
Observed 18-byte payloads contain a real 6-byte `0x45` connection/disconnection
event; they are not empty-event sentinels.

---

## PD Event Stream Format

Two event kinds appear in PD payloads:

### Connection/Status Event (6 bytes)

| Offset | Size | Field |
|--------|------|-------|
| 0 | 1 | Marker: `0x45` |
| 1 | 3 | Timestamp (LE24) |
| 4 | 1 | Reserved |
| 5 | 1 | Event code |

**Event codes:**

- `0x21` - Connect (33 decimal)
- `0x22` - Disconnect (34 decimal)

### Wrapped PD Message Event (variable)

| Offset | Size | Field |
|--------|------|-------|
| 0 | 1 | Size flag (`0x80..0x9F`) |
| 1 | 4 | Timestamp (LE32) |
| 5 | 1 | SOP type |
| 6 | N | PD wire bytes |

**Wire length:** `(size_flag & 0x3F) - 5` bytes

The wire bytes are standard USB PD messages (2-byte header + data objects).

---

## Examples & Correlation

- **Preamble+event sample:** `preamble: e5 e8 5b 00 00 00 00 00 76 06 03 00` + `event: 45 e2 e8 5b 00 21` (connect). Disconnect uses code `0x22`.
- **Wrapped message sample:** size_flag `0x9F` → `wire_len=21`; parsed messages observed: GoodCRC, Source_Capabilities, Request, Accept, PS_RDY.
- **USB ↔ SQLite:** PD events in `pd_table.Raw` match USB PD-only payloads minus the 12-byte measurement preamble; timestamps align with the same millisecond timebase.

## SQLite Export Format

### Schema

```sql
CREATE TABLE pd_chart(Time real, VBUS real, IBUS real, CC1 real, CC2 real);
CREATE TABLE pd_table(Time real, Vbus real, Ibus real, Raw Blob);
CREATE TABLE pd_table_key(key integer);
```

### pd_chart Table

Time-series ADC samples during PD capture:

- `Time` - seconds since capture start
- `VBUS` - volts
- `IBUS` - amps
- `CC1`, `CC2` - volts

### pd_table Table

PD events with binary payload:

- `Time` - event timestamp
- `Vbus`, `Ibus` - instantaneous readings
- `Raw` - binary blob with PD event(s)

### Raw Blob Format

Same as PD event stream format above (without 12-byte preamble):

```python
# Parsing pseudocode
i = 0
while i < len(raw):
    if raw[i] == 0x45:
        # Connection/status event (6 bytes)
        event_code = raw[i + 5]
        i += 6
    elif 0x80 <= raw[i] <= 0x9F:
        # Wrapped PD message
        size_flag = raw[i]
        timestamp = LE32(raw[i+1:i+5])
        sop = raw[i + 5]
        wire_len = (size_flag & 0x3F) - 5
        wire = raw[i+6:i+6+wire_len]
        i += 6 + wire_len
        # Parse wire with usbpdpy
    else:
        break
```

**Timestamp alignment:** SQLite `timestamp_ms`, standalone/chained PD status,
and USB PD event-stream preambles use the same device-relative millisecond
timebase.

---

## PD Message Decoding

PD wire messages are standard USB PD frames:

**Header (2 bytes LE):**

- Message type (5 bits)
- Num data objects (3 bits)
- Message ID (3 bits)
- Power role (1 bit): Source/Sink
- Data role (1 bit): DFP/UFP
- Spec revision (2 bits)

**Data objects:** `num_objects × 4` bytes

### Common Message Types

| Type | Name | Objects |
|------|------|---------|
| Control | GoodCRC | 0 |
| Control | Accept | 0 |
| Control | PS_RDY | 0 |
| Data | Source_Capabilities | 1-7 PDOs |
| Data | Request | 1 RDO |

### Using usbpdpy

```python
from usbpdpy import parse_pd_message

msg = parse_pd_message(wire_bytes)
print(f"Type: {msg.header.message_type}")
print(f"Power role: {msg.header.pd_power_role}")
print(f"Data role: {msg.header.pd_data_role}")

if hasattr(msg, 'pdos'):
    for pdo in msg.pdos:
        print(f"  PDO: {pdo}")
```

---

## USB Protocol Commands

### Request PD Data

Include attribute 0x0010 in GetData:

```text
0C TID 20 00  # GetData attr=0x0010 (PD only)
0C TID 22 00  # GetData attr=0x0011 (ADC + PD)
```

The device buffers PD events and returns them via polling. No special enable command is required.

### Enable/Disable PD Monitor (0x10/0x11) - Optional

```text
10 TID 02 00  # Enable PD capture
11 TID 00 00  # Disable PD capture
```

**Note:** These commands are optional. PD data can be retrieved via GetData polling without explicitly enabling the monitor. The exact purpose of these commands is unclear and needs further investigation.

---

## Correlation: USB to SQLite

- USB PdPacket (>12 bytes) = 12-byte measurement preamble + one or more events
- SQLite Raw blob = events only (no preamble)
- Timestamps align between sources
- Connect/disconnect events present in both

---

## Python Example

```python
import sqlite3
from usbpdpy import parse_pd_message

def parse_pd_events(raw):
    events = []
    i = 0
    while i < len(raw):
        if raw[i] == 0x45:
            events.append({
                'type': 'status',
                'code': raw[i + 5],
            })
            i += 6
        elif 0x80 <= raw[i] <= 0x9F:
            size_flag = raw[i]
            ts = int.from_bytes(raw[i+1:i+5], 'little')
            sop = raw[i + 5]
            wire_len = (size_flag & 0x3F) - 5
            wire = raw[i+6:i+6+wire_len]
            i += 6 + wire_len

            msg = parse_pd_message(wire)
            events.append({
                'type': 'pd',
                'timestamp': ts,
                'sop': sop,
                'message': msg,
            })
        else:
            break
    return events

# Read SQLite export
conn = sqlite3.connect('pd_export.db')
cursor = conn.execute('SELECT Time, Raw FROM pd_table')

for time, raw in cursor:
    events = parse_pd_events(raw)
    for e in events:
        if e['type'] == 'pd':
            print(f"{time:.3f}s: {e['message'].header.message_type}")
```

---

## Observed Data (pd_capture_new.9)

| Message Type | Count |
|--------------|-------|
| GoodCRC | 4 |
| Source_Capabilities | 4 |
| Request | 1 |
| Accept | 1 |
| PS_RDY | 1 |

All observed wrapped events were SOP (sop=0). Connect (`0x21`) and disconnect (`0x22`) status events in USB captures align with the first/last markers in the SQLite export.

All messages observed were SOP (sop=0).
