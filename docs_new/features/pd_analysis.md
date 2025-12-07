# PD Analysis

USB Power Delivery capture and SQLite export format.

For packet headers and general protocol, see [Protocol Reference](../protocol_reference.md).

---

## Overview

The KM003C can capture USB PD messages and export them to SQLite. PD data appears in two contexts:

1. **USB protocol:** PdPacket attribute (0x0010) in PutData responses
2. **SQLite export:** Official app exports to `.db` files

---

## PD Status vs Preamble (12 bytes)

PD data shows up in two distinct 12-byte forms. They are not interchangeable:

- **PD Status (ADC+PD combo, 68B total):**
  - `[0] type_id (u8)`
  - `[1..3] timestamp24 (u24, ~40ms/tick)`
  - `[4..5] vbus_mV (u16)`
  - `[6..7] ibus_mA (u16)`
  - `[8..9] cc1_mV (u16)`
  - `[10..11] cc2_mV (u16)`
  - Follows an ADC logical packet; no PD events follow in the common 68B packets.

- **PD Preamble (PD-only/event streams):**
  - `[0..3] timestamp_ms (u32, ms base)`
  - `[4..5] vbus_mV (u16)`
  - `[6..7] ibus_mA (i16, signed)`
  - `[8..9] cc1_mV (u16)`
  - `[10..11] cc2_mV (u16)`
  - Immediately followed by repeated 6-byte event headers + PD wire bytes.

**Empty PD response:** When no new PD data is available, the device returns an 18-byte PdPacket: 12-byte preamble + a single empty 6-byte event header (`wire_len=0`).

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
- `0x11` - Connect
- `0x12` - Disconnect

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

**Timestamp alignment:** SQLite `timestamp_ms` aligns with the 32-bit preamble timestamps in USB PD-only payloads. The 24-bit PD status timestamp from ADC+PD packets is a coarse counter (~40 ms/tick) and should not be conflated with the SQLite timestamps.

**Empty PD rows:** The empty 18-byte PD USB response normally produces no SQLite row unless accompanied by a separate `0x45` status event.

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

### Enable PD Monitor (0x10)

```
10 TID 00 00  # Enable PD capture
```

### Disable PD Monitor (0x11)

```
11 TID 00 00  # Disable PD capture
```

### Request PD Data

Include attribute 0x0010 in GetData:

```
0C TID 20 00  # GetData attr=0x0010 (PD only)
0C TID 22 00  # GetData attr=0x0011 (ADC + PD)
```

---

## Correlation: USB to SQLite

- USB PdPacket (18+ bytes) = 12-byte preamble + events
- SQLite Raw blob = events only (no preamble)
- Timestamps align between sources
- Connect/disconnect events present in both

**Empty PD responses:** USB may return 18-byte packet (12B preamble + 6B empty event header) indicating no new PD data.

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

All observed wrapped events were SOP (sop=0). Connect (`0x11`) and disconnect (`0x12`) status events in USB captures align with the first/last markers in the SQLite export.

All messages observed were SOP (sop=0).
