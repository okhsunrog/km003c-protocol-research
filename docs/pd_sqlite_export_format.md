# KM003C PD SQLite Export Format

This document describes the SQLite schema and binary blob layout used by the official Windows application for the ChargerLAB POWER‑Z KM003C when exporting PD captures. The database stores time‑series charts and a stream of PD events in compact binary form. Findings here are validated against the consolidated protocol spec in `docs/protocol_specification.md` and one‑to‑one correlated to the USB capture Parquet (e.g., `pd_capture_new.9`).

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

Each `Raw` BLOB encodes one (occasionally more) inner PD event(s). Two top‑level event kinds appear in practice:

1) Connection/Status Event (6 bytes)
- Marker: first byte `0x45`
- Layout (total 6 bytes):
  - `0x45` (type_id)
  - `timestamp_le24` (3 bytes, little‑endian)
  - `reserved` (1 byte)
  - `event_code` (1 byte)
- Examples (hex):
  - `45 82 17 00 00 11` (observed)
  - `45 D4 F8 12 00 11`, `45 CC 0D 13 00 12` (observed in USB PD‑only streams; codes `0x11/0x12` correlate with connect/disconnect states)

Connection/status event codes:
- `event_code = 0x11` → Connect (observed at the beginning of capture)
- `event_code = 0x12` → Disconnect (observed after the PD transfer sequence)

2) Wrapped PD Message Event (variable length)
- Marker: first byte in `0x80..0x9F` (size_flag)
- Event header (6 bytes):
  - `size_flag` (1 byte)
    - bit7: SOP present/valid indicator (observed set when PD data follows)
    - bits[5:0]: size code
  - `timestamp_le32` (4 bytes, little‑endian)
  - `sop` (1 byte)
- PD wire message length: `wire_len = (size_flag & 0x3F) - 5` bytes
  - After the 6‑byte event header, read exactly `wire_len` bytes and feed to a PD parser (e.g., `usbpdpy.parse_pd_message`).
- Example (hex, 1 event per row):
  - `9F 99 18 00 00 00 A1 61 2C 91 01 08 2C D1 02 00 2C C1 03 00 2C B1 04 00`
  - Here `size_flag=0x9F` → size code 31 → `wire_len = 31 − 5 = 26` bytes PD wire.

Notes
- Some rows include only a single event per `Raw`, but parsers should iterate defensively in case of multiple back‑to‑back events.
- The PD wire content is a standard USB PD message (2‑byte header + optional 4‑byte data objects). Use a USB PD parser (e.g., `usbpdpy`) to decode.
- Do not confuse these event headers with the 12‑byte “PD status” block used in KM003C ADC+PD combo packets; that 12‑byte status block is not present in this SQLite format.
- Direction is not stored in the wrapper header; it is derived from the PD wire header (power role bit). With updated `usbpdpy`, you can read `pd_power_role` (Source/Sink) and `pd_data_role` (Dfp/Ufp) from the decoded header.

## PD Event Kinds and Decoding

Two event kinds appear in both USB PD‑only payloads (after the 12‑byte preamble) and in SQLite `Raw` blobs (without a preamble):

- Connection/Status event
  - Header: 6 bytes, first byte = `0x45`
  - Fields: `[0]=0x45`, `[1..3]=timestamp_le24`, `[4]=reserved`, `[5]=event_code`
  - Codes observed: `0x11` (Connect), `0x12` (Disconnect)
  - No PD wire bytes follow.

- Wrapped PD message event
  - Header: 6 bytes, first byte `size_flag ∈ [0x80..0x9F]`
  - Fields: `[0]=size_flag`, `[1..4]=timestamp_le32`, `[5]=sop`
  - Computed: `wire_len = (size_flag & 0x3F) − 5`
  - Followed by exactly `wire_len` bytes of PD wire data.

PD wire messages are standard USB Power Delivery frames:
- PD Header: 2 bytes (little‑endian) containing `message_type`, `num_data_objects`, `message_id`, `power_role`, `data_role`, `spec_revision`.
- Data Objects: `num_data_objects * 4` bytes following the header.
- Decoding: use `usbpdpy.parse_pd_message(wire)` and read fields from `msg.header` and the returned object list.

Typical message types seen (pd_capture_new.9):
- `GoodCRC` (control) — header only, no data objects (2 wire bytes total)
- `Source_Capabilities` (data) — 6 PDOs observed (26 wire bytes total)
- `Request` (data) — 1 RDO (6 wire bytes total)
- `Accept` (control) — header only (2 wire bytes total)
- `PS_RDY` (control) — header only (2 wire bytes total)

PD data object quick reference (common cases):
- Fixed Supply PDO (Source_Capabilities): 32‑bit field encoding supply type, voltage (50 mV units), maximum current (10 mA units), and capability flags (e.g., dual‑role power, USB communications capable). Multiple PDOs enumerate available rails.
- Request Data Object (Request): 32‑bit field encoding the selected PDO index, operating current, maximum current, and flags (e.g., no USB suspend, USB communications capable, capability mismatch).

Note: For full semantics of PDO/RDO bits, refer to the USB Power Delivery specification. The usbpdpy library exposes parsed fields for convenience.

### Timestamp Semantics and Alignment
- Wrapper event timestamps (`timestamp_le32`) use a millisecond base and align with USB PD event `ts32` from PD‑only payloads.
- KM003C’s 12‑byte PD status block in USB (chained after ADC) uses a separate 24‑bit counter at ~40 ms/tick; it does not appear in SQLite exports and should not be conflated with wrapper timestamps.
- In USB PD‑only payloads, the 12‑byte preamble `ts32` is an end‑of‑burst anchor; the inner per‑event timestamps are less than or equal to this preamble timestamp by a few milliseconds. SQLite rows store only the per‑event timestamps; there is no preamble in `Raw`.

## Parsing Example (Python)

The repo includes a reference parser that decodes `pd_table.Raw` and feeds PD wire messages to `usbpdpy`. With the updated library, `Source_Capabilities` parses cleanly and exposes roles:

- Example (from data/processed/complete_pd_analysis.parquet):
  - Types observed: Source_Capabilities, Request, Accept, PS_RDY, GoodCRC
  - Roles extracted: `pd_power_role ∈ {Source, Sink}`, `pd_data_role ∈ {Dfp, Ufp}`
  - Connection/status events (0x45…) appear as 6‑byte rows with no PD type

Core logic sketch:

```
# Pseudocode
for each row in pd_table:
    b = Raw
    i = 0
    while i < len(b):
        t0 = b[i]
        if t0 == 0x45:
            # 6-byte connection/status (connect/disconnect/CC state)
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

## Correlation With USB Capture (Parquet)

- One‑to‑one correlation validated: PD events from SQLite map to matching PD events in `pd_capture_new.9`.
- Connection/status events appear in the USB PD‑only streams as 12‑byte preamble + 6‑byte `0x45 …` blocks (payload size 18). Examples:
  - `preamble: e5 e8 5b 00 00 00 00 00 76 06 03 00` + `event: 45 e2 e8 5b 00 11`
  - `preamble: 07 f4 5b 00 fa 13 00 00 a5 0c 7d 00` + `event: 45 fc f3 5b 00 12`
- Wrapped PD messages appear identically (aside from the absence of the 12‑byte preamble in the SQLite rows).

Observed distribution (pd_capture_new.9):
- All wrapped PD events are SOP (sop=0) in this capture.
- Message counts: GoodCRC=4, Source_Capabilities=4, Request=1, Accept=1, PS_RDY=1.

Empty PD responses (no new messages):
- USB may return a minimal 18‑byte PdPacket (12‑byte preamble + an empty 6‑byte event header with `wire_len=0`). These indicate “no wire data this tick” and typically do not produce a corresponding SQLite event row unless a separate `0x45` status event is emitted.

Direction and connect/disconnect applicability to Parquet:
- PD message direction (Source→Sink or Sink→Source) is inferred from the PD wire header (roles), identical for SQLite and Parquet.
- Connect (`0x11`) and disconnect (`0x12`) events are present in the USB capture as preamble+0x45 events and align with the first/last status markers in the SQLite export.

## Known Notes

- `Source_Capabilities` now parses without issues with the updated `usbpdpy` library; PDOs and roles are available for analysis.
- Some rows may embed trailing bytes that are not separate events; parsers should avoid over‑eager scanning beyond the computed `wire_len`.

## Direction and Roles

- Direction is determined from the PD wire message header (power role = Source/Sink, data role = Dfp/Ufp). The wrapper event header’s `sop` indicates SOP type, not direction.
- These roles and message types are exported in `data/processed/complete_pd_analysis.parquet` as `pd_message_type`, `pd_power_role`, and `pd_data_role`.

## Provenance

- This SQLite layout originates from the official KM003C Windows application’s PD export feature. The above structure was reverse‑engineered empirically from multiple captures.
