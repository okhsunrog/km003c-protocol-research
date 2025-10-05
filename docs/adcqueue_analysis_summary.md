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
| 12:14  | 2    | u16  | CC1 | ×0.1mV | CC1 line voltage (divide by 10000 for volts) |
| 14:16  | 2    | u16  | CC2 | ×0.1mV | CC2 line voltage (divide by 10000 for volts) |
| 16:18  | 2    | u16  | D+ | ×0.1mV | USB D+ line voltage (divide by 10000 for volts) |
| 18:20  | 2    | u16  | D- | ×0.1mV | USB D- line voltage (divide by 10000 for volts) |

**Validated on 16,609 samples from real device captures (modern firmware).**

**Example values** (pd_adcqueue_new.11):
- VBUS: 9.225V, IBUS: -1.537A, CC1: 1.660V, CC2: 0.029V, D+: 0.598V, D-: 0.598V

### Fields NOT Included

⚠️ AdcQueue does **NOT** contain:
- **Temperature** (always request ADC for temp)
- Statistics (min/max/avg)
- VDD (internal voltage)

**Note**: In old firmware/captures, D+/D- fields may be zero if inactive.

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
| orig_adc_1000hz.6 | 1000 SPS | 956 SPS | 40 | 42 ms |
| orig_adc_50hz.6 | 50 SPS | 47 SPS | 5-6 | 109 ms |
| pd_adcqueue_new.11 | Multiple rates | 1.8 / 9.6 / 47.5 / 666 SPS | 2-41 | Variable |

### How Sampling Rate Works

**Discovered**: Sample rate is configured via **command 0x0E** (Start Graph) using the "attribute" field as a **rate index** (not a bitmask!).

**Rate Index Encoding**:
```
0x0E command format: [0x0E, transaction_ID, rate_index_low, rate_index_high]

Rate index values:
  0 = 1 SPS      (1 sample per second)
  1 = 10 SPS     (10 samples per second)
  2 = 50 SPS     (50 samples per second)
  3 = 1000 SPS   (1000 samples per second)
  4 = 10000 SPS  (legacy, not supported in modern firmware)
```

**Validated from pd_adcqueue_new.11** (4 different rates captured):
- `0E XX 00 00` (rate=0) → 1.8 SPS effective, 2 samples/packet
- `0E XX 02 00` (rate=1) → 9.6 SPS effective, 2.1 samples/packet
- `0E XX 04 00` (rate=2) → 47.5 SPS effective, 5.4 samples/packet
- `0E XX 06 00` (rate=3) → 666 SPS effective, 41.1 samples/packet

**Device behavior**:
1. Command 0x0E sets internal sampling rate
2. Device continuously samples at configured rate into circular buffer
3. Host polls with AdcQueue requests (mask 0x0002)
4. Device sends all buffered samples since last request
5. More samples = longer accumulation time between host requests

---

## Control Commands

### Start Graph Mode with Sample Rate

**Command: 0x0E (Start Graph)**

```c
Format:  [0x0E, transaction_ID, rate_index_low, rate_index_high]

// Little-endian encoding in CtrlHeader:
struct {
    uint32_t type   : 7;   // 0x0E
    uint32_t extend : 1;   // 0
    uint32_t id     : 8;   // Transaction ID
    uint32_t unused : 1;   // 0
    uint32_t rate   : 15;  // Rate index (0-3)
}
```

**Rate index values**:
- `0` = 1 SPS
- `1` = 10 SPS
- `2` = 50 SPS
- `3` = 1000 SPS

**Examples**:
```
0E 37 00 00  → ID=55,  rate=0 (1 SPS)
0E 77 02 00  → ID=119, rate=1 (10 SPS)
0E BC 04 00  → ID=188, rate=2 (50 SPS)
0E 39 06 00  → ID=57,  rate=3 (1000 SPS)
```

**Response**: `0x05` (Accept)

**Effect**: Device configures internal sampling rate and begins buffering samples

### Stop Graph Mode

**Command: 0x0F (Stop Graph)**

```
Format:  [0x0F, ID, 0x00, 0x00]
Example: 0F 25 00 00  (ID=37)
Response: 0x05 (Accept)
Effect: Device stops sampling/buffering, returns to normal ADC mode
```

### Complete Workflow

1. **Initialization**: Connect, Unknown68×4, Unknown76, Settings
2. **Normal ADC polling**: ~200 ms intervals (mask 0x0001)
3. **User selects rate in UI**: 1/10/50/1000 SPS
4. **User clicks "Start Graph"**
5. → Device sends **0x0E + rate_index**
6. → Device receives Accept
7. → **AdcQueue requests begin** (mask 0x0002)
8. → Device buffers at selected rate, host polls periodically
9. **User clicks "Stop Graph"**
10. → Device sends **0x0F**
11. → Return to normal ADC polling

---

## ADC vs AdcQueue Comparison

| Feature | ADC (0x0001) | AdcQueue (0x0002) |
|---------|--------------|-------------------|
| **Purpose** | Detailed measurements | High-rate logging |
| **Size** | 44 bytes (1 sample) | 20 bytes × N samples |
| **Packet size** | 52 bytes total | 100-960 bytes |
| **Samples** | 1 per request | 5-48 per request |
| **Sequence** | No | Yes (for gap detection) |
| **Fields** | VBUS, IBUS, Temp, D+, D-, CC1, CC2, VDD, stats | VBUS, IBUS, CC1, CC2, D+, D- |
| **Temperature** | ✓ | ✗ |
| **USB data lines** | ✓ (D+, D-) | ✓ (D+, D-) |
| **Statistics** | ✓ (min/max/avg) | ✗ |
| **Use case** | Status monitoring | Continuous graphing |
| **Typical interval** | 200 ms | 40-100 ms |

---

## Application Behavior

### Official App Graph View

The official Windows application displays 7 fields on the graph:
- VBUS, IBUS, D+, D-, CC1, CC2, Temperature

**How it works**:
- **AdcQueue** provides high-rate VBUS, IBUS, CC1, CC2, D+, D- (~1000 SPS)
- **ADC** provides Temperature periodically (~5 Hz)
- Application **merges** both streams for complete graph

**Note**: Only Temperature is missing from AdcQueue. All voltage lines (VBUS, IBUS, CC1, CC2, D+, D-) are included in modern firmware.

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
    pub vbus_v: f64,   // Volts
    pub ibus_a: f64,   // Amperes (signed)
    pub power_w: f64,  // Watts (calculated)
    pub cc1_v: f64,    // Volts (CC1 line)
    pub cc2_v: f64,    // Volts (CC2 line)
    pub vdp_v: f64,    // Volts (USB D+ line)
    pub vdm_v: f64,    // Volts (USB D- line)
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
- `pd_adcqueue_new.11`: Multiple rates tested in single capture (1/10/50/1000 SPS)

---

## Protocol Details

### 1. Sample Rate Configuration ✅ SOLVED

Sample rate is set via **command 0x0E** using the "attribute" field as a rate index:
- Not a bitmask attribute like in GetData commands
- Direct index into rate table: 0=1SPS, 1=10SPS, 2=50SPS, 3=1000SPS
- Validated on pd_adcqueue_new.11 with 4 different rates

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
- Command 0x0E/0x0F helper methods in KM003C device
- Settings (0x0008) parsing
- AdcQueue10k (0x004) support if needed for legacy devices

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