# AdcQueue Streaming

High-rate power measurement streaming via attribute 0x0002.

For packet headers and general protocol, see [Protocol Reference](../protocol_reference.md).

---

## Quick Start

```python
# 1. Connect
send([0x02, tid, 0x00, 0x00])

# 2. Auth (required for streaming)
send([0x4C, tid, 0x00, 0x02] + bytes(32))

# 3. Start Graph at 50 SPS (rate_index=2)
send([0x0E, tid, 0x04, 0x00])

# 4. Wait ~1 second for samples to accumulate

# 5. Request AdcQueue data
send([0x0C, tid, 0x04, 0x00])  # GetData attr=0x0002
response = read()  # Returns N × 20-byte samples

# 6. Stop when done
send([0x0F, tid, 0x00, 0x00])
```

**Key insight:** Authentication (0x4C) is required for AdcQueue - without it, StartGraph succeeds but returns 0 samples. However, payload content doesn't matter - any 32 bytes work.

---

## Sample Structure (20 bytes)

| Offset | Size | Type | Field | Units |
|--------|------|------|-------|-------|
| 0 | 2 | u16 | Sequence | Incrementing counter |
| 2 | 2 | u16 | Marker | Always 0x3C (60) |
| 4 | 4 | i32 | VBUS | µV (microvolts) |
| 8 | 4 | i32 | IBUS | µA (microamperes, signed) |
| 12 | 2 | u16 | CC1 | ×0.1mV (divide by 10000 for V) |
| 14 | 2 | u16 | CC2 | ×0.1mV |
| 16 | 2 | u16 | D+ | ×0.1mV |
| 18 | 2 | u16 | D- | ×0.1mV |

**Not included:** Temperature, min/max/avg statistics, VDD

**To get temperature:** Request ADC (attr 0x0001) periodically and merge.

---

## Sampling Rates

### StartGraph Command (0x0E)

```
Format: [0x0E, TID, rate_byte, 0x00]

Rate byte encoding:
  0x00 → rate_index 0 → 2 SPS (effective ~1.8 SPS observed)
  0x02 → rate_index 1 → 10 SPS
  0x04 → rate_index 2 → 50 SPS
  0x06 → rate_index 3 → 1000 SPS
```

The rate_byte is `rate_index * 2` (device uses bits 1-2 of the control header). `km003c_lib::GraphSampleRate` uses the same mapping and multiplies by 2 when encoding StartGraph.

### StopGraph Command (0x0F)

```
Format: [0x0F, TID, 0x00, 0x00]
Response: 0x05 (Accept)
```

---

## Packet Structure

### Response Format

```
[0:4]   Main header (4 bytes)
        - Type: 0x41 (PutData)
        - TID
        - obj_count_words

[4:8]   Extended header (4 bytes)
        - Attribute: 0x0002
        - Next: 0
        - Size: 20 (per sample, not total!)

[8:N]   Payload: N × 20-byte samples
```

**Number of samples:** `(payload_length - 8) / 20`

Typical packet contains 5-50 samples (100-1000 bytes total).

---

## ADC vs AdcQueue

| Feature | ADC (0x0001) | AdcQueue (0x0002) |
|---------|--------------|-------------------|
| Purpose | Detailed snapshot | High-rate logging |
| Size | 44 bytes (1 sample) | 20 bytes × N samples |
| Samples/packet | 1 | 5-50 |
| Temperature | Yes | No |
| Statistics | Yes (min/max/avg) | No |
| D+/D- | Yes | Yes (modern firmware) |
| Sequence number | No | Yes |
| Typical rate | ~5 Hz | Up to 1000 SPS |

**Recommendation:** Use AdcQueue for graphing, ADC for status displays.

---

## Implementation Notes

### Initialization Sequence

1. **USB reset** - Clean device state
2. **Wait 1.5 seconds** - Device needs initialization time
3. **Auth (0x4C)** - Any 32-byte payload works
4. **StartGraph (0x0E)** - With rate index
5. **Poll AdcQueue** - Request attribute 0x0002 every 100-200ms
6. **StopGraph (0x0F)** - When done

### Monitoring Dropped Samples

Check sequence numbers for gaps:

```python
expected_seq = last_seq + 1
if sample.sequence != expected_seq:
    print(f"Dropped {sample.sequence - expected_seq} samples")
```

### Buffer Behavior

- Device buffers samples in circular buffer
- First request after StartGraph returns accumulated samples (~1 second worth)
- Subsequent requests return samples since last poll
- More samples = longer time between requests

### Attribute 0x0004 (ATT_ADC_QUEUE_10K)

Documented but **never used**. All captures (including 1000 SPS) use attribute 0x0002. Do not request 0x0004.

---

## Python Example

```python
import usb.core
import struct
import time

def parse_adcqueue_sample(data, offset):
    seq, marker, vbus_uv, ibus_ua, cc1, cc2, dp, dm = struct.unpack_from(
        '<HHiiHHHH', data, offset
    )
    return {
        'sequence': seq,
        'vbus_v': vbus_uv / 1_000_000,
        'ibus_a': ibus_ua / 1_000_000,
        'cc1_v': cc1 / 10000,
        'cc2_v': cc2 / 10000,
        'dp_v': dp / 10000,
        'dm_v': dm / 10000,
    }

def parse_adcqueue_response(data):
    # Skip 8-byte header
    payload = data[8:]
    samples = []
    for i in range(0, len(payload), 20):
        if i + 20 <= len(payload):
            samples.append(parse_adcqueue_sample(payload, i))
    return samples

# Example: 50 SPS streaming
device.write(0x01, bytes([0x02, 0x01, 0x00, 0x00]))  # Connect
device.read(0x81, 64)

device.write(0x01, bytes([0x4C, 0x02, 0x00, 0x02]) + bytes(32))  # Auth
device.read(0x81, 64)

device.write(0x01, bytes([0x0E, 0x03, 0x04, 0x00]))  # StartGraph 50 SPS
device.read(0x81, 64)

time.sleep(1.0)

device.write(0x01, bytes([0x0C, 0x04, 0x04, 0x00]))  # GetData AdcQueue
response = device.read(0x81, 1024)
samples = parse_adcqueue_response(bytes(response))

for s in samples:
    print(f"#{s['sequence']:4d}: {s['vbus_v']:.3f}V {s['ibus_a']*1000:.1f}mA")

device.write(0x01, bytes([0x0F, 0x05, 0x00, 0x00]))  # StopGraph
device.read(0x81, 64)
```

---

## Performance Data

From capture analysis:

| Mode | Effective Rate | Samples/Packet | Request Interval |
|------|----------------|----------------|------------------|
| 1000 SPS | ~956 SPS | 38-40 | 42 ms |
| 50 SPS | ~47 SPS | 5-10 | 100-200 ms |
| 10 SPS | ~9.6 SPS | 2-5 | Variable |
| 2 SPS | ~1.8 SPS | 1-2 | 1 second |

Maximum sustained throughput: ~1000 samples/second at 1000 SPS mode.

## Dataset Snapshot (usb_master_dataset.parquet)

- Total packets: ADC 1,877 vs AdcQueue 290
- AdcQueue size: 100–960 bytes (5–48 samples per response)
- Example captures:
  - `orig_adc_1000hz.6`: 220 AdcQueue responses, 8,798 samples, ~956 SPS
  - `orig_adc_50hz.6`: 60 responses, 320 samples, ~47 SPS
  - `pd_adcqueue_new.11`: mixed rates (1/10/50/1000 SPS) in one session

## Notes & Edge Cases

- Attribute 0x0004 (ATT_ADC_QUEUE_10K) is defined in docs but never observed in 20k+ packets, including 1000 SPS runs. Use attribute 0x0002 for all streaming.
- Extended header `size=20` is the per-sample size; compute samples as `(payload_len - 8) / 20`.
- Empty PutData (obj_count_words=0) is valid when the device buffer is empty—retry later.
- Tested on real hardware (2025-10-05): minimal sequence works, 50 SPS shows graph icon, first poll returns ~50 accumulated samples. Test scripts: `scripts/test_exact_init_sequence.py`, `scripts/test_verify_minimal.py`, `scripts/test_minimal_adcqueue.py`.
