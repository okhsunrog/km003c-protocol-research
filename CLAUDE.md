# CLAUDE.md (Agent Guide)

Concise, AI‑oriented guidance for working in this repo. Optimize for correctness, reuse, and speed by using the existing library and tools.

## Environment Quickstart

```bash
# Install runtime deps
uv sync

# Dev deps (ruff/maturin/etc.)
uv sync -E dev

# Build Rust Python extension (km003c_lib)
just rust-ext
```

## Core Commands

```bash
# Validate before shipping changes
just test     # Run tests
just lint     # Ruff lint
just format   # Ruff format

# Direct invocations
uv run pytest -q
uv run mypy km003c_analysis/
uv run ruff check km003c_analysis scripts
uv run ruff format km003c_analysis scripts

# Streamlit app
just app
```

## AI Quickstart

Preferred path: use the library for parsing/splitting/tagging; avoid re‑implementing low‑level parsing unless absolutely required.

```python
import polars as pl
from pathlib import Path
from km003c_analysis.core import split_usb_transactions, tag_transactions
from km003c_lib import parse_packet, parse_raw_packet
from scripts.km003c_helpers import get_packet_type, get_adc_data, get_pd_status, get_pd_events

DATASET = Path("data/processed/usb_master_dataset.parquet")
df = pl.read_parquet(DATASET)

# Work on bulk traffic; split into transactions; add tags
bulk = df.filter(pl.col("transfer_type") == "0x03")
tx = split_usb_transactions(bulk)
tx_tagged = tag_transactions(tx)

# Example: focus on IN completions with payload (PutData candidates)
pd_candidates = tx_tagged.filter(
    (pl.col("endpoint_address") == "0x81")
    & (pl.col("urb_type") == "C")
    & pl.col("payload_hex").is_not_null()
)
```

### Parsing Protocol Correctly

- Use `km003c_lib` for all KM003C protocol parsing. Avoid manual bit/byte parsing in Python. This ensures consistent attribute masks and header semantics across scripts.
- Control header bits (wire): `type:7 | reserved_flag:1 | id:8 | (unused):1 | att:15`. The `att` field is a 15‑bit value that directly equals the attribute (ADC=0x0001, AdcQueue=0x0002, Settings=0x0008, PdPacket=0x0010). Do not apply extra shifts.
 - Byte layout gotcha: `att` starts at bit 17 of the 32‑bit little‑endian header. For `att=0x0001` (ADC), the third byte often shows `0x02`. This is expected; do not reinterpret it as `0x0002`. Prefer `km003c_lib` to avoid such mistakes.
- `reserved_flag` is vendor‑specific and is not an extended header indicator. PutData (0x41) always carries extended logical packets.
- Extended header (per logical packet): `att:15 | next:1 | chunk:6 | size:10`.

Recommended patterns:
- High‑level: `parse_packet()` then use helpers: `get_packet_type`, `get_adc_data`, `get_pd_status`, `get_pd_events`.
- Low‑level: `parse_raw_packet()` to inspect `header` and `logical_packets` in the `"Data"` variant.

Example:
```python
pkt = parse_packet(packet_bytes)
if get_packet_type(pkt) == "DataResponse":
    adc = get_adc_data(pkt)
    pdst = get_pd_status(pkt)
    pdev = get_pd_events(pkt)

raw = parse_raw_packet(packet_bytes)
if isinstance(raw, dict) and "Data" in raw:
    hdr = raw["Data"]["header"]
    for lp in raw["Data"]["logical_packets"]:
        attr = lp.get("attribute")
```

## Common Analysis Recipes

- Map GetData masks → PutData categories (use transactions)
  - Load master dataset, split transactions as above.
  - For each transaction, parse first OUT Submit with data as GetData; parse IN Complete as PutData and classify segments.
  - See docs/protocol_specification.md for bitmask semantics and attributes.

- Extract ADC payloads
  - Parse PutData logical packets with attribute=1 (ADC) and size=44; use the byte offsets from docs/protocol_specification.md.

- Parse PD event streams
  - For PdPacket attribute=16 with size>12: preamble (12B) + repeated 6B event headers + PD wire bytes.
  - Full details and SQLite parity: docs/pd_sqlite_export_format.md.

- Correlate to SQLite export
  - Use km003c_analysis.tools.pd_sqlite_analyzer to load and compare PD streams; export to Parquet/JSON if needed.

## Tests You Should Use

- Transaction logic: tests/test_transaction_splitter.py
- Tagging semantics: tests/test_transaction_tagger.py

Recommended loop:
```bash
just test         # Run all tests
uv run pytest -q  # Quick iteration
```

## Data + Invariants

- Master Parquet: `data/processed/usb_master_dataset.parquet` (≈11.5k packets).
- GetData attribute_mask is a 15‑bit bitmask; combine with bitwise OR to request multiple classes.
  - Bits → attributes: 0x0001 ADC(1), 0x0002 AdcQueue(2), 0x0008 Settings(8), 0x0010 PdPacket(16), 0x0200 Unknown512(512)
  - Examples: 0x0011 = ADC|PD, 0x0003 = ADC|AdcQueue
- PutData uses chained logical packets; continue until `next=0`.
- Response `id` matches request `id` (8‑bit roll‑over).
- Do NOT group by URB ID (kernel address, reused). Use split_usb_transactions.

## Tools and Entry Points

- Library
  - `km003c_analysis.core.split_usb_transactions` — robust transaction grouping
  - `km003c_analysis.core.tag_transactions` — structural tags (BULK_COMMAND_RESPONSE, etc.)

- Tools
  - `km003c_analysis.tools.pd_sqlite_analyzer` — analyze/convert official SQLite PD exports

- Scripts (examples)
  - `scripts/analyze_km003c_protocol.py` — end‑to‑end protocol analysis
  - `scripts/parse_pd_wrapped.py` — PD wrapped event parsing
  - `scripts/export_complete_pd_analysis.py` — full PD analysis export
  - `scripts/summarize_pd_messages.py` — quick PD summary

## Documentation Map (read, don’t duplicate)

- Protocol: `docs/protocol_specification.md` — application‑layer headers, bitmasks, ADC payload offsets, flows
- Transport: `docs/usb_transport_specification.md` — endpoints, URB/ZLP handshakes, timings
- PD SQLite: `docs/pd_sqlite_export_format.md` — PD preamble/events, SQLite schema and parity with USB

## When to Extend vs. Reuse

- Prefer using existing helpers (splitter/tagger) and tools before writing custom parsers.
- If adding parsing, keep it small, tested, and colocated near existing patterns (scripts/ or km003c_analysis/tools/).

## Known Gotchas

- URB IDs are not transaction IDs; never group by URB ID.
- The reserved flag in headers is vendor‑specific and not an indicator of extended headers.
- AdcQueue (attr 2) frames include a header; sizes vary with sample count.

## Apps

```bash
just app  # Launch Streamlit dashboards
```
