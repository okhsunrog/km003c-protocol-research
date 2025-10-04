# AdcQueue Protocol Analysis

**Date**: 2025-10-04  
**Status**: ✅ Fully understood and implemented in km003c-rs  
**Validation**: Tested on real USB captures with multiple sampling rates

---

## Overview

**AdcQueue** (attribute 0x0002) provides high-rate streaming of power measurements by buffering multiple samples device-side and transmitting them in batches.

Unlike ADC packets (single sample with statistics), AdcQueue packets contain 5-48 buffered samples optimized for continuous data logging and graphing.

---

## Sample Structure (20 bytes)

Each sample in AdcQueue has the following structure:

| Offset | Size | Type | Field | Units | Description |
|--------|------|------|-------|-------|-------------|
| 0:2    | 2    | u16  | Sequence | - | Incrementing sequence number |
| 2:4    | 2    | u16  | Marker | - | Constant value (0x3C = 60) |
| 4:8    | 4    | i32  | VBUS | µV | Bus voltage in microvolts |
| 8:12   | 4    | i32  | IBUS | µA | Bus current in microamperes (signed) |
| 12:14  | 2    | u16  | CC1 | mV | CC1 line voltage in millivolts |
| 14:16  | 2    | u16  | CC2 | mV | CC2 line voltage in millivolts |
| 16:20  | 4    | -    | Reserved | - | Always 0 in all observed traffic |

**Validated on 8,798 samples from real device captures.**

### Fields NOT Included

⚠️ AdcQueue does **NOT** contain:
- **Temperature** (not in 20-byte structure)
- **D+ voltage** (USB data lines)
- **D- voltage** (USB data lines)
- Statistics (min/max/avg)

For these fields, use regular ADC packets (attribute 0x0001).

---

## Packet Structure

### Complete AdcQueue Response

```
[0:3]    Main header (4 bytes)
         - packet_type: 0x41 (PutData)
         - id: transaction ID
         - obj_count_words: approximate total_size/4

[4:7]    Extended header (4 bytes)
         - attribute: 0x0002 (AdcQueue)
         - next: 0 (last logical packet)
         - size: 20 (bytes PER SAMPLE, not total!)
         
[8:N]    Payload: N × 20-byte samples
         - Typical: 38-40 samples (768-808 bytes)
         - Range: 5-48 samples (100-960 bytes)
```

**Key insight**: Extended header `size=20` is the size **per sample**, not total payload size. The actual number of samples = (payload_length - 8) / 20.

---

## Sampling Rate Modes

### Observed Capture Sessions

| File | Mode | Effective Rate | Samples/Packet | Request Interval |
|------|------|---------------|----------------|------------------|
| orig_adc_1000hz.6 | 1000 Hz | 956 SPS | 40 | 42 ms |
| orig_adc_50hz.6 | 50 Hz | 47 SPS | 5-6 | 109 ms |

### How Sampling Rate Works

1. **Device-side configuration**: Sampling rate is configured on the device (not visible in USB traffic, possibly stored in flash or set via initialization)

2. **Internal buffering**: Device continuously samples at configured rate (50 Hz, 1000 Hz, etc.) into an internal circular buffer

3. **Host polling**: Application periodically requests AdcQueue data:
   - Buffer accumulates samples between requests
   - Device sends all buffered samples in one USB transfer
   - More samples = longer buffer accumulation time

4. **Efficiency**: One USB request fetches 40 samples (1000 Hz mode) vs making 40 individual ADC requests

---

## Control Commands

### Graph Mode Control

**Start graph/streaming mode**:
```
Command: 0x0E (Unknown14)
Format:  [0x0E, ID, attr_mask_low, attr_mask_high]
Example: 0E 1C 06 00  (ID=28, attr_mask=0x0003 = ADC+AdcQueue)
Response: 0x05 (Accept)
Effect: Device begins buffering samples for AdcQueue
```

**Stop graph/streaming mode**:
```
Command: 0x0F (Unknown15)
Format:  [0x0F, ID, 0x00, 0x00]
Example: 0F 25 00 00  (ID=37, no attributes)
Response: 0x05 (Accept)
Effect: Device stops AdcQueue buffering, returns to normal ADC mode
```

### Typical Workflow

1. **Initialization** (Connect, Unknown68×4, Unknown76, Settings)
2. **Normal ADC polling** (~200 ms intervals, mask 0x0001)
3. User selects sample rate in application UI
4. User clicks "Start Graph"
5. → **Command 0x0E** sent (with appropriate attr_mask)
6. → **AdcQueue requests** begin (mask 0x0002, fast polling 40-100ms)
7. User clicks "Stop Graph"
8. → **Command 0x0F** sent
9. → Return to **normal ADC polling**

---

## ADC vs AdcQueue Comparison

| Feature | ADC (0x0001) | AdcQueue (0x0002) |
|---------|--------------|-------------------|
| **Purpose** | Detailed measurements | High-rate logging |
| **Size** | 44 bytes (1 sample) | 20 bytes × N samples |
| **Packet size** | 52 bytes total | 100-960 bytes |
| **Samples** | 1 per request | 5-48 per request |
| **Sequence** | No | Yes (for gap detection) |
| **Fields** | VBUS, IBUS, Temp, D+, D-, CC1, CC2, VDD, stats | VBUS, IBUS, CC1, CC2 only |
| **Temperature** | ✓ | ✗ |
| **USB data lines** | ✓ (D+, D-) | ✗ |
| **Statistics** | ✓ (min/max/avg) | ✗ |
| **Use case** | Status monitoring | Continuous graphing |
| **Typical interval** | 200 ms | 40-100 ms |

---

## Application Behavior

### Official App Graph View

The official Windows application displays 7 fields on the graph:
- VBUS, IBUS, D+, D-, CC1, CC2, Temperature

**How it works**:
- **AdcQueue** provides high-rate VBUS, IBUS, CC1, CC2 (~1000 SPS)
- **ADC** provides Temperature, D+, D- periodically (~5 Hz)
- Application **merges** both streams for complete graph

This explains why Temperature/D+/D- are not in AdcQueue - they're fetched separately via ADC requests.

---

## Rust Implementation

### Structures (km003c-lib/src/adcqueue.rs)

```rust
pub struct AdcQueueSampleRaw {
    pub sequence: U16,
    pub marker: U16,           // Always 0x3C (60)
    pub vbus_uv: I32,          // Microvolts
    pub ibus_ua: I32,          // Microamperes (signed)
    pub cc1_mv: U16,           // Millivolts
    pub cc2_mv: U16,           // Millivolts
    pub reserved: [u8; 4],     // Always 0
}

pub struct AdcQueueSample {
    pub sequence: u16,
    pub vbus_v: f64,
    pub ibus_a: f64,
    pub power_w: f64,  // Calculated
    pub cc1_v: f64,
    pub cc2_v: f64,
}

pub struct AdcQueueData {
    pub samples: Vec<AdcQueueSample>,
}
```

### Usage Example

```rust
use km003c_lib::{KM003C, Attribute, AttributeSet};

let mut device = KM003C::new().await?;

// Start graph mode
device.send_command(0x0E, AttributeSet::single(Attribute::AdcQueue)).await?;

// Poll AdcQueue data
loop {
    let packet = device.request_data(AttributeSet::single(Attribute::AdcQueue)).await?;
    
    if let Some(PayloadData::AdcQueue(queue)) = packet.get_payload() {
        println!("Received {} samples", queue.samples.len());
        
        for sample in &queue.samples {
            println!("  #{}: {:.3}V {:.3}mA", 
                     sample.sequence, sample.vbus_v, sample.ibus_a * 1000.0);
        }
        
        // Check for dropped samples
        if queue.has_dropped_samples() {
            println!("⚠️ Dropped samples detected!");
        }
    }
    
    // Stop after some time
    if done {
        device.send_command(0x0F, AttributeSet::empty()).await?;
        break;
    }
}
```

---

## Testing Recommendations

### Test 1: Multiple Sample Rates in One Capture

**Procedure**:
1. Start Wireshark USB capture
2. Open official app
3. For each rate (1 SPS, 10 SPS, 50 SPS, 1000 SPS):
   - Select rate in UI
   - Click "Start Graph"
   - Wait 5-10 seconds
   - Click "Stop Graph"
   - Wait 2 seconds
4. Stop capture

**Expected observations**:
- Command 0x0E before each graph start
- Command 0x0F after each graph stop
- Different AdcQueue packet sizes/intervals per rate
- Possible rate configuration command between stops and starts

### Test 2: Rate Configuration Search

**Procedure**:
1. Start capture
2. Open app
3. Change sample rate dropdown (WITHOUT starting graph)
4. Start graph
5. Stop capture

**Goal**: Find if/how sample rate selection sends USB commands

### Test 3: Temperature + Graph

**Procedure**:
1. Capture session with graph running (any rate)
2. Analyze request pattern:
   - Count AdcQueue requests (0x0002)
   - Count ADC requests (0x0001)
   - Measure intervals

**Expected**: Application alternates AdcQueue (fast) and ADC (slow) to get temperature data for graph overlay.

### Test 4: Long Buffer Test

**Procedure**:
1. Start graph at 1000 Hz
2. Stop requests for several seconds (pause in code)
3. Resume - observe if buffer overflows or device behavior

**Goal**: Understand buffer size limits and overflow behavior

---

## Dataset Statistics

From `usb_master_dataset.parquet`:

| Metric | ADC (attr=1) | AdcQueue (attr=2) |
|--------|--------------|-------------------|
| Total packets | 1,877 | 290 |
| Size | 52 bytes (fixed) | 100-960 bytes (variable) |
| Samples per packet | 1 | 5-48 |
| Effective rate | ~5 Hz polling | 47-956 SPS |

**Files analyzed**:
- `orig_adc_1000hz.6`: 220 AdcQueue packets, 8,798 samples, 956 SPS effective
- `orig_adc_50hz.6`: 60 AdcQueue packets, 320 samples, 47 SPS effective

---

## Known Issues & Limitations

### 1. Sample Rate Configuration Not Found

Sample rate setting mechanism is not visible in USB traffic. Possibilities:
- Stored in device flash memory
- Set via initialization commands (Unknown68/76 with encrypted payload)
- Auto-detected based on first AdcQueue request timing

### 2. Extended Header Size Field Ambiguity

The extended header `size=20` field is **per-sample size**, not total payload:
- Can be confusing for parsers expecting total size
- Must calculate num_samples = payload_length / 20

### 3. Missing Fields in AdcQueue

For complete data, applications must:
- Request AdcQueue for VBUS/IBUS/CC (high rate)
- Request ADC periodically for Temperature/D+/D- (low rate)
- Merge data streams client-side

---

## Implementation Status

### km003c-rs Library

✅ **Implemented**:
- AdcQueueSampleRaw (zerocopy parsing)
- AdcQueueData (multi-sample container)
- Sequence number tracking
- Dropped sample detection
- Integration into PayloadData enum
- Tests passing

⏳ **TODO**:
- Python bindings for AdcQueue
- Command 0x0E/0x0F wrappers (start/stop graph)
- Sample rate configuration discovery
- Settings (0x0008) parsing

### Python Analysis

✅ **Scripts**:
- Manual AdcQueue parsing examples
- Sample rate analysis from captures
- Control command identification

---

## Related Documentation

- `docs/protocol_specification.md` - Main protocol specification
- `docs/transaction_correlation_analysis.md` - Request-response correlation
- `km003c-lib/src/adcqueue.rs` - Rust implementation
- `km003c-lib/tests/adcqueue_tests.rs` - Test cases

---

## Example Data

### Real Sample from orig_adc_1000hz.6

```
Sample #78:
  VBUS:  5.082 V
  IBUS:  0.210 mA
  CC1:   67 mV (0.067 V)
  CC2:   3235 mV (3.235 V)
  Power: 1.067 mW
```

Matches ADC packet from same session:
- VBUS: 5.082 V ✓
- CC1: 67 mV ✓
- CC2: 3235 mV ✓

Temperature from ADC: 24.6°C (not in AdcQueue)

---

## Recommendations

### For Application Developers

1. **Use AdcQueue for graphs**: Request with mask 0x0002 during active graphing
2. **Mix with ADC**: Periodically request ADC (0x0001) for temperature and D+/D- data
3. **Monitor sequence numbers**: Use to detect buffer overflows or dropped samples
4. **Send control commands**:
   - 0x0E to start streaming
   - 0x0F to stop streaming
5. **Buffer management**: Expect 5-48 samples per packet, allocate appropriately

### For Protocol Research

1. **Capture rate transitions**: Record session changing rates multiple times
2. **Find rate configuration**: Focus on commands between rate changes
3. **Test buffer limits**: Long captures to find max buffer size
4. **Analyze Unknown commands**: Unknown68, Unknown76, Unknown(14/15) need reverse engineering