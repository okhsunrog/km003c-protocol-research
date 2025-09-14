# Protocol Research Findings (WIP)

Purpose: Validate correlations between extended header fields (attribute, next, chunk, size) and main header fields (type, extend, id, obj_count) against the master dataset.

Dataset and method
- Source: `data/processed/usb_master_dataset.parquet` (12,008 rows)
- Focus: USB application-layer PutData packets (`type == 65` from main header)
- Parsed fields:
  - Main header (little-endian 32-bit):
    - `type` = bits [0..6]
    - `extend` = bit [7] (observed)
    - `id` = bits [8..15]
    - `obj_count` = bits [22..31]
  - Extended header (always present for PutData, 32-bit little-endian):
    - `attribute` = bits [0..14]
    - `next` = bit [15]
    - `chunk` = bits [16..21]
    - `size_bytes` = bits [22..31] (interpreted as BYTES, not words)

Key counts (PutData only)
- Total PutData packets: 2,836
- Attribute distribution:
  - `1` (ATT_ADC): 1,877
  - `16` (ATT_PdPacket): 657
  - `2` (ATT_AdcQueue): 288
  - `8` (ATT_Settings): 7
  - `512` (other/unknown): 7

Confirmed correlations
- next vs size (ADC only):
  - `attribute == 1` always has `size_bytes == 44`.
  - `next == 0` → total length exactly 52 bytes (4 main + 4 ext + 44 ADC). Count: 1,825. No counterexamples.
  - `next == 1` → total length > 52 bytes (ADC + PD extension). Sizes observed: 68, 84, 96, 836, 856, 876 bytes. Count: 52. No counterexamples.
- chunk:
  - `attribute == 1` (ADC): `chunk == 0` for all 1,877 packets.
  - `attribute == 16` (PD): `chunk == 0` for all 657 packets.
  - `attribute == 2` (AdcQueue): `chunk` varies widely (e.g., 1,2,5,32–48 seen), consistent with queued-chunk semantics.
- size_bytes by attribute:
  - ADC (`attr=1`): always 44 bytes.
  - PD (`attr=16`): commonly 12 bytes (647), plus 18 (4), 44 (1), 76 (1), 88 (2), 108 (1), 28 (1) — aligns with multiple PD inner structures.
  - AdcQueue (`attr=2`): always 20 bytes (header of queued item), payload follows via chunking.
- obj_count vs total size (PutData):
  - Strong pattern across almost all PutData: `obj_count * 4 == total_len - 12` (i.e., obj_count counts 4-byte words after subtracting both headers = 8 bytes and one additional 4-byte unit).
  - Match rates by attribute:
    - ADC (`attr=1`): 1,876/1,877 match (99.9%). One exception off by +4 bytes.
    - PD (`attr=16`): 651/657 match (99.1%). A few cases off by +4 bytes.
    - AdcQueue (`attr=2`): 251/288 match (87.2%). Several cases off by +4 bytes.
  - Interpretation: For PutData, `obj_count` measures the number of payload words excluding the two 4-byte headers and excluding one additional 4-byte unit of the first object. Equivalently, for most packets:
    - `obj_count_words ≈ (total_len/4) - 3`
    - For ADC specifically: `obj_count_words = (44 - 4)/4 + (pd_extension_bytes / 4)` → `10 + (pd_extension_bytes/4)`

Other observations
- Main header `extend` bit:
  - Observed `extend == 0` for all PutData in this dataset. Extended header is nevertheless always present for PutData; thus `extend` does not signal the extended header here.
- ID field (`id`):
  - Not fully analyzed in this pass; appears to roll over 0–255. Future work: verify monotonicity within flows and any reuse across attributes.

Exceptions and edge cases
- Small subset of packets show `obj_count * 4 == total_len - 16` (off by exactly 4 bytes from the dominant `-12` rule), e.g. `(obj_count=188, total_len=768)`, `(228, 928)`, `(20, 96)`, `(3, 26)`. These occur across PD and AdcQueue and once in ADC.
  - Hypotheses: alignment/padding, header variant, or attribute-specific accounting nuance.
  - Action: flag these in deeper packet-level parsing to pinpoint the extra 4-byte field.

Quick reference values (empirical)
- ADC (`attr=1`):
  - `size_bytes=44`, `chunk=0`
  - `next=0` → 52 bytes total; `next=1` → 52 + PD extension bytes
  - `obj_count_words = 10 + (PD_ext_bytes/4)`
- PD (`attr=16`):
  - `size_bytes` varies (12 common), `chunk=0`, `next=0`
  - `obj_count_words ≈ (total_len/4) - 3` (with rare +4B exceptions)
- AdcQueue (`attr=2`):
  - `size_bytes=20`, `chunk` varies; `next=0`
  - Same `obj_count` relation with more exceptions to review

Open questions
- Why `extend` is always 0 in main header for PutData while extended header is always present.
- Root cause of the rare +4B exception in `obj_count` accounting across several attributes.
- Formal spec for how `obj_count` is defined per attribute (vs. our empirical formulas).

Reproduction
- Scripts were run via `.venv/bin/python` using Polars to parse `payload_hex`, with header decoding matching the layouts above.

Source files in dataset
- orig_adc_1000hz.6: 1240
- orig_adc_50hz.6: 570
- orig_adc_record.6: 420
- orig_new_adcsimple0.12: 494
- orig_open_close.16: 152
- orig_with_pd.13: 2056
- pd_capture_new.9: 6930
- rust_simple_logger.16: 146

Per-capture analysis
- pd_capture_new.9
  - Method (transaction-level, reusing app pipeline):
    - Filter `source_file == "pd_capture_new.9"`
    - Split into transactions via `km003c_analysis.usb_transaction_splitter.split_usb_transactions`
    - Tag via `km003c_analysis.transaction_tagger.tag_transactions`
    - For each transaction, extract first OUT `payload_hex` as request and first IN `payload_hex` as response
    - Decode response PutData headers (main/extended) to collect `attribute`, `next`, `size_bytes`, total length
    - Script: `notebooks/analyze_pd_capture_new9.py` (run with `.venv/bin/python notebooks/analyze_pd_capture_new9.py`)
  - Results summary:
    - Transactions: 1,734 total
    - Tags: BULK_COMMAND_RESPONSE=1,731; BULK_ONLY=1,731; CONTROL_ONLY=3; ENUMERATION=3
    - Response types: PutData=1,729; UNPARSED=2
    - PutData attributes: ADC (attr=1)=1,419; PD (attr=16)=310
    - ADC next: next=0 → 1,401; next=1 → 18; all next=1 had +16B appended (total_len=68)
    - PD size_bytes distribution: 12→305, 18→2, 28→1, 88→1, 108→1
  - Notes/discoveries:
    - Confirms earlier correlation: for ADC, `next=1` implies PD extension appended; in this capture, extension size consistently +16B
    - PD PutData entries mostly `size_bytes=12`, with a few larger PD structures (18/28/88/108B) indicating varied PD event/message payloads
    - Transaction structure dominated by clean BULK command-response cycles; minimal control-only enumeration interspersed
    - ADC packet lengths vs PD mode window:
      - Before PD enable and after PD disable: all ADC responses are exactly 52 bytes (no extensions observed).
      - Inside PD-active window: ADC with PD extension appear (next=1). In this capture, +16B extensions only (total 68B).
  - Mode switch detection:
    - First enable (pd_capture_new.9):
      - Continuous ADC_52 stream breaks at transaction index 39→40 (by start_time ordering).
      - tx=40 request `10f40200` → `Unknown(16)`; response `05f40000` → `Accept`.
      - Immediately after (tx=41+), host issues `CmdGetPdData` with PD `PutData` (attr=16, size_bytes=12) interleaved with `CmdGetSimpleAdcData` ADC.
    - First disable (pd_capture_new.9):
      - Last PD occurs at tx=409; at tx=411 request `11680000` → `Unknown(17)`; response `05...` → `Accept`.
      - Subsequent transactions revert to pure ADC_52-only stream.
    - Cross-capture confirmation (orig_with_pd.13):
      - Enable: tx=40 request `101b0200` → `Unknown(16)`; response `051b0000` → `Accept`; PD begins immediately after.
      - Disable: tx=455 request `11ba0000` → `Unknown(17)`; response `05ba0000` → `Accept`; ADC_52 resumes thereafter.
    - Interpretation: `Unknown(16)` likely enables PD capture/dual-mode; `Unknown(17)` likely disables it. Both are acknowledged by `Accept` and bracket periods of PD activity.
    - Cross-check (orig_with_pd.13): ADC+PD extensions occur only within the PD-active window as well; extensions are mostly +16B with one +32B instance observed.

  - ADC request variants (request→response correlation):
    - Standard ADC (52B response): request is 4 bytes `0x0C [id] 0x02 0x00`.
      - Parsed type: `GetData` / `CmdGetSimpleAdcData`.
      - Response: `PutData` with `attribute=1` (ADC), `next=0`, `size=44`, total 52B.
    - ADC with PD extension (68B or more): request is 4 bytes `0x0C [id] 0x22 0x00`.
      - Parsed type: also `GetData` (same command family), but attribute byte differs.
      - Response: `PutData` with `attribute=1`, `next=1`, base 52B + extension (in this capture +16B, total 68B).
    - PD-only fetch: request is `0x0C [id] 0x20 0x00` (for context).
      - Response: `PutData` with `attribute=16` (PD), sizes commonly 12B.
    - Observed consistently in both `pd_capture_new.9` and `orig_with_pd.13`:
      - `0x.. 02 00` → ADC_52; `0x.. 22 00` → ADC_PD; `0x.. 20 00` → PD.

### Packet Samples: pd_capture_new.9

#### ADC+PD responses (attribute=1, next=1) — 18 total
- tx 57 | start=8.118736 | len=68 | size_bytes=44 | chunk=0
  - request: 0c 06 22 00
  - response: 41 06 82 03 01 80 00 0b a1 0f 00 00 da ff ff ff 76 0f 00 00 f6 ff ff ff da 0f 00 00 54 00 00 00 a6 0d 71 7e cf 04 30 01 01 01 79 7e 00 80 7a 00 1e 00 19 00 10 00 00 03 31 d4 5b 00 04 00 00 00 a5 0c 7c 00
- tx 69 | start=8.528716 | len=68 | size_bytes=44 | chunk=0
  - request: 0c 12 22 00
  - response: 41 12 82 03 01 80 00 0b a1 0f 00 00 1a 00 00 00 4f 0f 00 00 d5 ff ff ff b3 0f 00 00 33 00 00 00 a6 0d 71 7e cf 04 30 01 01 01 79 7e 00 80 7a 00 1e 00 19 00 10 00 00 03 cb d5 5b 00 04 00 00 00 a3 0c 7b 00
- tx 87 | start=9.158670 | len=68 | size_bytes=44 | chunk=0
  - request: 0c 24 22 00
  - response: 41 24 82 03 01 80 00 0b a1 0f 00 00 2a 00 00 00 4f 0f 00 00 d5 ff ff ff b3 0f 00 00 33 00 00 00 a7 0d 76 7e d0 04 31 01 01 01 7e 7e 00 80 7a 00 1e 00 19 00 10 00 00 03 41 d8 5b 00 03 00 00 00 a3 0c 79 00
- tx 125 | start=10.424810 | len=68 | size_bytes=44 | chunk=0
  - request: 0c 4a 22 00
  - response: 41 4a 82 03 01 80 00 0b de 0e 00 00 f6 ff ff ff 74 0f 00 00 1e 00 00 00 d8 0f 00 00 7c 00 00 00 a8 0d 71 7e cf 04 57 01 2b 01 79 7e 00 80 7a 00 1b 00 15 00 10 00 00 03 33 dd 5b 00 04 00 00 00 a3 0c 7e 00
- tx 156 | start=11.458509 | len=68 | size_bytes=44 | chunk=0
  - request: 0c 69 22 00
  - response: 41 69 82 03 01 80 00 0b a1 0f 00 00 0e 00 00 00 87 0f 00 00 f8 ff ff ff eb 0f 00 00 56 00 00 00 a8 0d 75 7e ce 04 1a 01 da 00 7d 7e 00 80 7a 00 1b 00 15 00 10 00 00 03 3d e1 5b 00 03 00 00 00 9c 0c 7a 00
- tx 175 | start=12.098521 | len=68 | size_bytes=44 | chunk=0
  - request: 0c 7c 22 00
  - response: 41 7c 82 03 01 80 00 0b a1 0f 00 00 ea ff ff ff 87 0f 00 00 f8 ff ff ff eb 0f 00 00 56 00 00 00 a8 0d 73 7e d0 04 18 01 d9 00 7b 7e 00 80 7a 00 1b 00 15 00 10 00 00 03 bd e3 5b 00 04 00 00 00 a3 0c 7c 00
- tx 187 | start=12.518766 | len=68 | size_bytes=44 | chunk=0
  - request: 0c 88 22 00
  - response: 41 88 82 03 01 80 00 0b a1 0f 00 00 22 00 00 00 81 0f 00 00 02 00 00 00 e5 0f 00 00 60 00 00 00 a8 0d 73 7e d0 04 18 01 d9 00 7b 7e 00 80 7a 00 1b 00 15 00 10 00 00 03 61 e5 5b 00 04 00 00 00 a5 0c 7c 00
- tx 199 | start=12.938783 | len=68 | size_bytes=44 | chunk=0
  - request: 0c 94 22 00
  - response: 41 94 82 03 01 80 00 0b a1 0f 00 00 ea ff ff ff 81 0f 00 00 02 00 00 00 e5 0f 00 00 60 00 00 00 a5 0d 74 7e d1 04 16 01 d8 00 7c 7e 00 80 7a 00 1b 00 14 00 10 00 00 03 05 e7 5b 00 04 00 00 00 a1 0c 7d 00
- tx 217 | start=13.568639 | len=68 | size_bytes=44 | chunk=0
  - request: 0c a6 22 00
  - response: 41 a6 82 03 01 80 00 0b de f2 08 00 b6 ff ff ff c5 0f 00 00 04 00 00 00 29 10 00 00 62 00 00 00 a7 0d 74 7e ce 04 18 01 d6 00 7c 7e 00 80 02 00 25 00 26 00 10 00 00 03 7b e9 5b 00 e0 0f f4 ff 72 06 03 00
- tx 255 | start=14.818792 | len=68 | size_bytes=44 | chunk=0
  - request: 0c cc 22 00
  - response: 41 cc 82 03 01 80 00 0b ea 09 89 00 d4 1b ee ff da 00 45 00 ee 52 ff ff e0 00 45 00 4c 53 ff ff a9 0d c3 40 3c 00 b1 22 ef 22 7c 7e 00 80 12 00 46 03 4c 03 10 00 00 03 5d ee 5b 00 07 23 c3 fb 86 06 11 00
- tx 280 | start=15.658777 | len=68 | size_bytes=44 | chunk=0
  - request: 0c e5 22 00
  - response: 41 e5 82 03 01 80 00 0b 76 12 89 00 8d f7 eb ff 1d aa 89 00 70 0b f6 ff 23 aa 89 00 ce 0b f6 ff a9 0d 09 41 89 00 3b 21 7b 21 82 7e 00 80 0e 00 54 03 5b 03 10 00 00 03 a5 f1 5b 00 e3 22 b5 fa 85 06 12 00
- tx 305 | start=16.489449 | len=68 | size_bytes=44 | chunk=0
  - request: 0c fe 22 00
  - response: 41 fe 82 03 01 80 00 0b 90 0e 00 00 02 ff ff ff 29 f3 88 00 1a 47 f0 ff 2f f3 88 00 25 50 f0 ff ab 0d 2a 41 b0 00 80 20 be 20 82 7e 00 80 6a 00 3b 01 3c 01 10 00 00 03 e4 f4 5b 00 00 00 00 00 a5 0c 7e 00
- tx 323 | start=17.108956 | len=68 | size_bytes=44 | chunk=0
  - request: 0c 10 22 00
  - response: 41 10 82 03 01 80 00 0b 97 30 00 00 de ff ff ff 29 f3 88 00 1a 47 f0 ff 2f f3 88 00 25 50 f0 ff ab 0d 75 7e cf 04 f3 00 d8 00 7d 7e 00 80 7a 00 18 00 15 00 10 00 00 03 4f f7 5b 00 0c 00 00 00 a3 0c 79 00
- tx 348 | start=17.948546 | len=68 | size_bytes=44 | chunk=0
  - request: 0c 29 22 00
  - response: 41 29 82 03 01 80 00 0b a7 28 00 00 ae ff ff ff 17 e5 0f 00 4a ff ff ff 7b e5 0f 00 a8 ff ff ff ac 0d 74 7e d0 04 fd 00 de 00 7c 7e 00 80 7a 00 20 00 1d 00 10 00 00 03 97 fa 5b 00 08 00 00 00 a3 0c 75 00
- tx 360 | start=18.374480 | len=68 | size_bytes=44 | chunk=0
  - request: 0c 35 22 00
  - response: 41 35 82 03 01 80 00 0b b4 22 00 00 d2 ff ff ff a8 2c 00 00 d4 ff ff ff 0c 2d 00 00 32 00 00 00 ab 0d 72 7e cd 04 26 01 08 01 7a 7e 00 80 7a 00 1c 00 19 00 10 00 00 03 41 fc 5b 00 08 00 00 00 a5 0c 79 00
- tx 378 | start=18.998691 | len=68 | size_bytes=44 | chunk=0
  - request: 0c 47 22 00
  - response: 41 47 82 03 01 80 00 0b f9 1d 00 00 0e 00 00 00 a8 2c 00 00 d4 ff ff ff 0c 2d 00 00 32 00 00 00 ae 0d 72 7e cd 04 1e 01 05 01 7a 7e 00 80 7a 00 1c 00 19 00 10 00 00 03 b1 fe 5b 00 07 00 00 00 a3 0c 7b 00
- tx 396 | start=19.618697 | len=68 | size_bytes=44 | chunk=0
  - request: 0c 59 22 00
  - response: 41 59 82 03 01 80 00 0b 4f 1a 00 00 0e 00 00 00 bf 1f 00 00 f1 ff ff ff 23 20 00 00 4f 00 00 00 ae 0d 72 7e ce 04 1a 01 05 01 7a 7e 00 80 7a 00 1b 00 19 00 10 00 00 03 1d 01 5c 00 07 00 00 00 a3 0c 7b 00
- tx 408 | start=20.038624 | len=68 | size_bytes=44 | chunk=0
  - request: 0c 65 22 00
  - response: 41 65 82 03 01 80 00 0b b3 19 00 00 1a 00 00 00 bf 1f 00 00 f1 ff ff ff 23 20 00 00 4f 00 00 00 ae 0d 72 7e ce 04 1a 01 05 01 7a 7e 00 80 7a 00 1b 00 19 00 10 00 00 03 c1 02 5c 00 06 00 00 00 a5 0c 7b 00

#### PD responses (attribute=16) — 10 examples
- tx 41 | start=7.586370 | len=20 | size_bytes=12 | chunk=0
  - request: 0c f6 20 00
  - response: 41 f6 82 00 10 00 00 03 1c d2 5b 00 03 00 00 00 a5 0c 7d 00
- tx 42 | start=7.608889 | len=20 | size_bytes=12 | chunk=0
  - request: 0c f7 20 00
  - response: 41 f7 82 00 10 00 00 03 33 d2 5b 00 04 00 00 00 a5 0c 78 00
- tx 43 | start=7.648707 | len=20 | size_bytes=12 | chunk=0
  - request: 0c f8 20 00
  - response: 41 f8 82 00 10 00 00 03 5b d2 5b 00 04 00 00 00 a5 0c 7c 00
- tx 44 | start=7.688760 | len=20 | size_bytes=12 | chunk=0
  - request: 0c f9 20 00
  - response: 41 f9 82 00 10 00 00 03 83 d2 5b 00 03 00 00 00 a3 0c 7c 00
- tx 46 | start=7.728763 | len=20 | size_bytes=12 | chunk=0
  - request: 0c fb 20 00
  - response: 41 fb 82 00 10 00 00 03 ab d2 5b 00 03 00 00 00 a5 0c 7d 00
- tx 47 | start=7.768790 | len=20 | size_bytes=12 | chunk=0
  - request: 0c fc 20 00
  - response: 41 fc 82 00 10 00 00 03 d3 d2 5b 00 04 00 00 00 a5 0c 7a 00
- tx 48 | start=7.808481 | len=20 | size_bytes=12 | chunk=0
  - request: 0c fd 20 00
  - response: 41 fd 82 00 10 00 00 03 fb d2 5b 00 02 00 00 00 a5 0c 79 00
- tx 49 | start=7.848691 | len=20 | size_bytes=12 | chunk=0
  - request: 0c fe 20 00
  - response: 41 fe 82 00 10 00 00 03 23 d3 5b 00 02 00 00 00 a1 0c 78 00
- tx 50 | start=7.888515 | len=20 | size_bytes=12 | chunk=0
  - request: 0c ff 20 00
  - response: 41 ff 82 00 10 00 00 03 4b d3 5b 00 04 00 00 00 a3 0c 7b 00
- tx 52 | start=7.928605 | len=20 | size_bytes=12 | chunk=0
  - request: 0c 01 20 00
  - response: 41 01 82 00 10 00 00 03 73 d3 5b 00 05 00 00 00 a5 0c 7c 00
