# AdcQueue Structure Analysis - Summary

## Problem Statement

During reverse engineering of the POWER-Z KM003C protocol, the **AdcQueue** (attribute=0x0002) packet structure was difficult to parse and understand correctly. The extended header's `size` field indicated 20 bytes, but packets contained 768-808 bytes of payload data.

## Root Cause

The extended header's `size` field (20 bytes) refers to **the size of each individual sample**, not the total payload size. AdcQueue packets contain **multiple queued samples** in a single USB transfer.

## AdcQueue Packet Structure

### Overall Format
```
[0:3]    Main header (4 bytes)
[4:7]    Extended header (4 bytes)
         - Attribute: 2 (AdcQueue)
         - Size: 20 (bytes per sample)
[8:N]    Payload: N × 20-byte samples (where N = 1-48 samples)
```

### 20-Byte Sample Structure
Each sample in the queue has this format:

| Offset | Size | Type | Field | Units | Description |
|--------|------|------|-------|-------|-------------|
| 0:2    | 2    | u16  | Sequence | - | Incrementing sequence number |
| 2:4    | 2    | u16  | Unknown | - | Marker/constant (typically 60) |
| 4:8    | 4    | i32  | V_bus | µV | Bus voltage in microvolts |
| 8:12   | 4    | i32  | I_bus | µA | Bus current in microamperes |
| 12:14  | 2    | i16  | Temp | 0.1°C | Temperature (multiply by 0.1 for °C) |
| 14:16  | 2    | i16  | V_line | mV | USB data line voltage (D+ or CC1) |
| 16:20  | 4    | u32  | Reserved | - | Always 0 |

## Comparison: ADC vs AdcQueue

| Feature | ADC (attribute=1) | AdcQueue (attribute=2) |
|---------|-------------------|------------------------|
| Size per response | 44 bytes (single sample) | 20 bytes × N samples |
| Typical packet size | 52 bytes total | 768-808 bytes total |
| Samples per packet | 1 | 38-40 (up to 48) |
| Sequence number | No | Yes (incrementing) |
| Statistics | Min/max/avg included | Instant readings only |
| Voltage lines | V_D+, V_D-, V_CC1, V_CC2 | 1 line only |
| Use case | Detailed single measurement | High-rate continuous logging |

## Dataset Statistics

From `usb_master_dataset.parquet`:
- **ADC packets**: 1,877 occurrences
  - Fixed size: 44 bytes payload, 52 bytes total
- **AdcQueue packets**: 288 occurrences
  - Variable size: 20-960 bytes payload (1-48 samples)
  - Most common: 768-808 bytes (38-40 samples)

## Example Values

### Sample AdcQueue Reading (Frame 1004, Sample 0):
```
Sequence:     78
V_bus:        5.0820 V
I_bus:        0.0002 A
Temperature:  6.7°C
V_line:       3.235 V
```

### Nearby ADC Reading (Frame 1002):
```
V_bus:        5.0822 V
I_bus:        0.0000 A
V_bus_avg:    5.0820 V
Temperature:  0.0°C
V_D+:         (appears corrupted)
V_CC1:        3.238 V
```

## Why This Was Confusing

1. **Size field ambiguity**: The extended header `size=20` didn't match the actual payload size (780 bytes), causing parsers to fail
2. **Kernel driver workaround**: The Linux powerz driver skips the 8-byte header and treats the data as a fixed struct, which accidentally works but misaligns fields
3. **Attribute mismatch**: When requesting AdcQueue (0x0002) on Interface 3, the device sometimes responds with ADC (0x0001) on other interfaces
4. **Variable payload**: Unlike ADC's fixed 44 bytes, AdcQueue has variable length depending on buffer fill level

## Correct Parsing Algorithm

```python
# Parse AdcQueue packet
data = response_bytes  # Raw USB response

# Skip headers
payload = data[8:]  # Skip main (4B) + extended (4B) headers

# Extract samples
sample_size = 20
num_samples = len(payload) // sample_size

for i in range(num_samples):
    offset = i * sample_size
    sample = payload[offset:offset+20]

    seq = int.from_bytes(sample[0:2], 'little')
    vbus = int.from_bytes(sample[4:8], 'little', signed=True) / 1e6  # µV → V
    ibus = int.from_bytes(sample[8:12], 'little', signed=True) / 1e6  # µA → A
    temp = int.from_bytes(sample[12:14], 'little', signed=True) * 0.1  # → °C
    vline = int.from_bytes(sample[14:16], 'little', signed=True) / 1e3  # mV → V
```

## Recommendations

1. **Use AdcQueue for streaming**: When continuous, high-rate monitoring is needed
2. **Use ADC for analysis**: When detailed statistics (min/max/avg) are required
3. **Check sequence numbers**: Use the sequence field to detect dropped samples
4. **Interface selection**: Interface 0/1 with endpoints 0x01/0x81 for ADC, Interface 3 with 0x05/0x85 for AdcQueue
5. **Buffer management**: AdcQueue packets can contain up to 48 samples (960 bytes), plan buffer sizes accordingly

## References

- Main dataset: `data/processed/usb_master_dataset.parquet`
- Protocol docs: `docs/protocol_specification.md`
- Transport docs: `docs/usb_transport_specification.md`
- Analysis scripts: `/tmp/kernel_vs_rust.py`, `/tmp/parse_response.py`
- Working implementation: `scripts/adc_simple.py`
