# Transaction Correlation Analysis

Bitmask and latency validation across `usb_master_dataset.parquet` (4,789
GetData/PutData pairs from 13 source captures).

## Key Findings

- 100% correlation: each GetData attribute bit maps to a logical packet in PutData.
- Response ID always matches request ID (8-bit rollover).
- Empty PutData (obj_count_words=0) is valid when AdcQueue buffer is empty.

### Bitmask Mapping

| Request Mask | Response Attributes | Occurrences |
|--------------|--------------------|-------------|
| 0x0001 | [ADC] | 2,752 |
| 0x0010 | [PdPacket] | 1,213 |
| 0x0011 | [ADC, PdPacket] | 65 |
| 0x0003 | [ADC, AdcQueue] | 44 |
| 0x0002 | [AdcQueue] | 688 |
| 0x0002 | [] | 4 |
| 0x0008 | [Settings] | 11 |
| 0x0200 | [LogMetadata] | 12 |

### Timing (median)

| Request Type | Median Latency |
|--------------|----------------|
| ADC (0x0001) | 164 µs |
| PD (0x0010) | 123 µs |
| ADC+PD (0x0011) | 171 µs |
| AdcQueue (0x0002) | 510 µs |

### Per-Capture Highlights

- `orig_adc_1000hz.6`: 291 pairs, AdcQueue-heavy (220 requests) for high-rate sampling.
- `pd_capture_new.9`: 1,729 pairs, mixed ADC (1,401) + PD (310); ADC ~200 ms, PD ~40 ms cadence.
- `orig_with_pd.13`: 495 pairs, PD-dominant (347) alongside power monitoring.

## Rules Confirmed

1. Bitmask → attributes: bits 0,1,3,4,9 map to 1,2,8,16,512.
2. Chained logical packets use `next` flag; zero violations in dataset.
3. Transaction IDs match request/response (100%).
4. Empty PutData is normal when no AdcQueue data is ready.

---

## Validation & Tooling

- **Dataset:** `data/processed/usb_master_dataset.parquet` (20,862 USB rows from 14 source captures; 4,789 GetData/PutData pairs from 13 sources).
- **Parser:** the correlation generator uses the pinned Rust `km003c` parser and rejects MemoryRead request/confirmation traffic before attribute analysis.
- **Exports:** `data/processed/transaction_pairs.parquet`, `request_response_analysis.json`, `bitmask_correlation_validation.json`, `rust_lib_analysis.json`.
- **Scripts:** `scripts/parquet/analyze_request_response_correlation.py`, `scripts/parquet/analyze_with_km003c_lib.py`, `scripts/parquet/validate_bitmask_correlation.py`, `scripts/parquet/visualize_request_response.py`.

## Implementation Notes

- Treat `obj_count_words=0` as “no data yet”, not an error.
- For high-rate polling, prefer Interface 0 (bulk) for ~0.6 ms latency; HID is ~3.8 ms.
- When requesting multiple attributes, expect one logical packet per set bit and follow the `next` chain until 0.
- High-frequency ADC: poll only attr 0x0001; avoid frequent AdcQueue if latency-sensitive.
- Compatibility: HID (IF3) works without driver install but is slower; bulk (IF0) is fastest.

## Files and Scripts

- Dataset: `data/processed/usb_master_dataset.parquet`
- Scripts: `scripts/parquet/analyze_request_response_correlation.py`, `scripts/parquet/analyze_with_km003c_lib.py`, `scripts/parquet/validate_bitmask_correlation.py`
