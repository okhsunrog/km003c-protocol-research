# KM003C PD SQLite Export Format

This document describes the SQLite schema and binary blob layout used by the official Windows application for the ChargerLAB POWER‑Z KM003C when exporting PD captures. The database stores time‑series charts and a stream of PD events in compact binary form.

## Schema Overview

A typical export contains these tables (observed):

- `pd_chart(Time real, VBUS real, IBUS real, CC1 real, CC2 real)`
  - Regular time‑series samples for voltage, current, and CC pins
- `pd_table(Time real, Vbus real, Ibus real, Raw blob)`
  - Event stream with per‑row binary `Raw` records (see Wire Format)
- `pd_table_key(key integer)`
  - Auxiliary key (purpose not required for parsing)

Example schema dump:

```
CREATE TABLE pd_chart(Time real, VBUS real, IBUS real, CC1 real, CC2 real);
CREATE TABLE pd_table(Time real, Vbus real, Ibus real, Raw Blob);
CREATE TABLE pd_table_key(key integer);
```

## Wire Format (pd_table.Raw)

Each `Raw` BLOB encodes one (occasionally more) inner PD event(s). Two top‑level event markers appear in practice:

1) Connection/Status Event (6 bytes)
- Marker: first byte `0x45`
- Layout (total 6 bytes):
  - `0x45` (type_id)
  - `timestamp_le24` (3 bytes, little‑endian)
  - `reserved` (1 byte)
  - `event_data` (1 byte)
- Example (hex): `45 82 17 00 00 11`
  - type_id=0x45, timestamp=0x001782, event_data=0x11

2) Wrapped PD Message Event (variable length)
- Marker: first byte in `0x80..0x9F`
- Event header (6 bytes):
  - `size_flag` (1 byte)
    - bit7: SOP valid indicator (observed set when PD present)
    - bits[5:0]: size code
  - `timestamp_le32` (4 bytes, little‑endian)
  - `sop` (1 byte)
- PD wire message length: `(size_flag & 0x3F) - 5` bytes
  - After the 6‑byte event header, read exactly this many bytes and pass them to a PD parser (e.g., `usbpdpy.parse_pd_message`)
- Example (hex, 1 event per row):
  - `9F 99 18 00 00 00 A1 61 2C 91 01 08 2C D1 02 00 2C C1 03 00 2C B1 04 00`
  - Here `size_flag=0x9F` → size code 31 → wire_len = 31 − 5 = 26 bytes PD wire

Notes
- Some rows appear to include only a single event per `Raw`, but parsers should be defensive and iterate in case of multiple back‑to‑back events.
- The PD wire content is a standard USB PD message (2‑byte header + optional 4‑byte data objects). Use a USB PD parser (e.g., `usbpdpy`) to decode.
- Do not confuse these event headers with the 12‑byte “PD status” block used in KM003C ADC+PD combo packets; that 12‑byte status block is not present in this SQLite format.

## Parsing Example (Python)

The repo includes a reference parser that decodes `pd_table.Raw` and feeds PD wire messages to `usbpdpy`:

- Script: `notebooks/parse_pd_sqlite.py`
- Usage: `.venv/bin/python notebooks/parse_pd_sqlite.py`
- Output example on a sample DB:
  - Rows: 13
  - PD messages parsed: 11
  - Types: GoodCRC×8, GotoMin×1, Accept×1, PS_RDY×1

Core logic sketch:

```
# Pseudocode
for each row in pd_table:
    b = Raw
    i = 0
    while i < len(b):
        t0 = b[i]
        if t0 == 0x45:
            # 6-byte connection/status
            i += 6
        elif 0x80 <= t0 <= 0x9F:
            size_flag = b[i]
            ts = LE32(b[i+1:i+5])
            sop = b[i+5]
            i += 6
            wire_len = (size_flag & 0x3F) - 5
            wire = b[i:i+wire_len]
            i += wire_len
            # parse wire with a PD parser
        else:
            break
```

## Chart Table (pd_chart)

- `Time` is a float (seconds since start of capture, observed)
- `VBUS` (volts), `IBUS` (amps), `CC1`/`CC2` (volts)
- Sampling cadence depends on the app and device state

## Known Limitations

- Source Capabilities messages were not present in the sample DB used for testing; we did observe control/handshake (GoodCRC, GotoMin, Accept, PS_RDY). Other DBs may contain richer PD traffic.
- Some rows may embed trailing bytes that are not separate events; parsers should avoid over‑eager scanning beyond the computed `wire_len`.

## Provenance

- This SQLite layout originates from the official KM003C Windows application’s PD export feature. The above structure was reverse‑engineered empirically from multiple captures.

