# AdcQueue Protocol Analysis

**Date**: 2025-10-05  
**Status**: ✅ Fully understood and validated on real hardware  
**Validation**: Tested on real KM003C device + analyzed USB captures with multiple sampling rates

---

## Quick Start: How to Use AdcQueue

**MINIMAL sequence (validated on real hardware):**

1. **USB reset** - Reset device to clean state
2. **Wait 1.5 seconds** - Device needs time to fully initialize after reset
3. **Start Graph** - Send `0x0E` command with rate parameter (rate_index: 0/1/2/3 → 1/10/50/1000 SPS)
4. **Wait ~1 second** - Allow device to accumulate samples in buffer
5. **Request AdcQueue** - Send GetData with attribute `0x0002` repeatedly  
6. **Stop Graph** - Send `0x0F` command when done

**Example (50 SPS):**
```python
# After USB reset
device.reset()
time.sleep(1.5)  # CRITICAL: Wait for device to fully initialize

# Start graph mode at 50 SPS (rate_index=2)
device.send([0x0E, 0x01, 0x04, 0x00])   # Start Graph, rate=2 (encoded as 0x04 in bytes)
time.sleep(1.0)                          # Wait for ~50 samples to accumulate

# Request AdcQueue data (attribute 0x0002, encoded as 0x0400 in bytes 2-3)
device.send([0x0C, 0x02, 0x04, 0x00])   # GetData attribute 0x0002
response = device.read()                 # Returns 1008 bytes = 50 samples

# Continue requesting (every 200ms gets ~10 new samples)
device.send([0x0C, 0x03, 0x04, 0x00])   
response = device.read()                 # Returns 208 bytes = 10 samples

# Stop when done
device.send([0x0F, 0x04, 0x00, 0x00])   # Stop Graph
```

**Working test script:** See `scripts/test_adcqueue.py` for complete minimal implementation

**Key insight:** Unknown76 (0x4C) is **required** for AdcQueue streaming - without it, StartGraph succeeds but returns 0 samples. However, Unknown76 content doesn't matter - any 32-byte payload works. Connect and Unknown68 are optional for basic streaming.

---

## Overview

**AdcQueue** (attribute 0x0002) provides high-rate streaming of power measurements by buffering multiple samples device-side and transmitting them in batches.

Unlike ADC packets (single sample with statistics), AdcQueue packets contain 5-50 buffered samples optimized for continuous data logging and graphing.

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

**Discovered**: Sample rate is configured via **command 0x0E** (Start Graph) using the "attribute" field to specify a **rate index**.

**Rate Index Encoding** (stored in bits 17-31 of the 4-byte command):
```
Command format: [0x0E, transaction_ID, byte2, byte3]

The rate index is encoded in the upper bits:
  Byte sequence → Rate Index → Sample Rate
  [0x0E, ID, 0x00, 0x00] → 0 → 1 SPS      (1 sample per second)
  [0x0E, ID, 0x02, 0x00] → 1 → 10 SPS     (10 samples per second)
  [0x0E, ID, 0x04, 0x00] → 2 → 50 SPS     (50 samples per second)
  [0x0E, ID, 0x06, 0x00] → 3 → 1000 SPS   (1000 samples per second)
```

**Note on byte encoding:** Due to the bitfield structure (attribute in bits 17-31), the rate index N appears as `(N*2)` in byte 2. This is an implementation detail of the 32-bit little-endian header format.

**Validated from captures:**
- `0E XX 00 00` (rate=0) → 1 SPS mode
- `0E XX 02 00` (rate=1) → 10 SPS mode
- `0E XX 04 00` (rate=2) → 50 SPS mode (✓ tested on real hardware)
- `0E XX 06 00` (rate=3) → 1000 SPS mode

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

**Minimal sequence (validated on real hardware):**

1. **USB reset** → Wait 1.5 seconds for device initialization
2. **Start Graph** (0x0E) → Device responds with Accept (0x05)
3. **Wait ~1 second** → Device accumulates samples
4. **Request AdcQueue** (0x0C, attr 0x0002) → Returns multi-sample data
5. **Poll repeatedly** → Every 200ms returns new samples
6. **Stop Graph** (0x0F) → Device stops buffering

**Official app sequence (includes extra commands):**
1. Connect, Unknown68×4, Unknown76, GetData PD/Unknown *(not required for AdcQueue)*
2. Normal ADC polling ~200ms (attribute 0x0001)
3. User selects rate → UI shows 1/10/50/1000 SPS
4. User clicks "Start Graph" → App sends 0x0E with rate
5. AdcQueue polling begins → App requests attribute 0x0002
6. User clicks "Stop Graph" → App sends 0x0F

**Key findings:**
- ✅ **Minimal initialization required** after USB reset + 1.5s wait
- ✅ Unknown76 (0x4C) **is required** for AdcQueue streaming (any 32-byte payload works)
- ✅ Connect, Unknown68 commands are **optional** for basic AdcQueue
- ✅ Request attribute `0x0002` (encoded as bytes `0x0400`) for AdcQueue data
- ✅ Attribute `0x0004` (ATT_ADC_QUEUE_10K) documented but **never used** (0/20,862 packets)
- ⚠️ **Critical**: Must wait 1.5s after USB reset (0.5s insufficient)

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

### 1. Attribute 0x0002 vs 0x0004 (ATT_ADC_QUEUE_10K) ✅ CLARIFIED

According to official documentation, three AdcQueue attributes exist:
- `0x0001` (ATT_ADC): Single ADC sample
- `0x0002` (ATT_ADC_QUEUE): AdcQueue buffered samples
- `0x0004` (ATT_ADC_QUEUE_10K): 10K SPS variant

**However, analysis of 20,862 packets shows:**
- ✗ Attribute `0x0004` is **NEVER used** (0 requests, 0 responses across all captures)
- ✓ All sampling rates (1, 10, 50, 1000 SPS) use attribute `0x0002`
- ✓ Even the 1000 SPS captures use `0x0002`, not `0x0004`

**Conclusion:** ATT_ADC_QUEUE_10K (0x0004) was likely planned for a 10,000 SPS mode that was never implemented. Use attribute `0x0002` for all AdcQueue operations.

### 2. Sample Rate Configuration ✅ SOLVED

Sample rate is set via **command 0x0E** using the "attribute" field as a rate index:
- Not a bitmask attribute like in GetData commands
- Rate indices: 0=1SPS, 1=10SPS, 2=50SPS, 3=1000SPS
- Validated on real hardware at 50 SPS

### 3. Extended Header Size Field Ambiguity

The extended header `size=20` field is **per-sample size**, not total payload:
- Can be confusing for parsers expecting total size
- Must calculate num_samples = (payload_length - 8) / 20

### 4. Missing Fields in AdcQueue

For complete data, applications must:
- Request AdcQueue for VBUS/IBUS/CC (high rate)
- Request ADC periodically for Temperature (low rate)
- Merge data streams client-side

**Note:** Modern firmware includes D+/D- in AdcQueue samples

---

## Implementation Status

### Hardware Validation (2025-10-05)

✅ **Verified on real KM003C device**:
- Minimal sequence works: Reset → Stop → Start → Request
- 50 SPS mode confirmed (graph icon appears on device screen)
- Multi-sample data retrieval successful (10 samples per 200ms at 50 SPS)
- First request after Start Graph returns ~50 accumulated samples
- No initialization commands required
- Test scripts: `scripts/test_exact_init_sequence.py`, `scripts/test_verify_minimal.py`

### km003c-rs Library

✅ **Implemented**:
- AdcQueueSampleRaw (zerocopy parsing)
- AdcQueueData (multi-sample container)
- Sequence number tracking
- Dropped sample detection
- Integration into PayloadData enum
- GraphSampleRate enum (Sps1/10/50/1000)
- Tests passing

📝 **Notes**:
- AdcQueue10k (0x004) is documented but unused - can be marked as unimplemented
- Python bindings exist but need AdcQueue-specific examples
- Settings (0x0008) parsing is separate feature

### Python Analysis & Test Scripts

✅ **Working examples**:
- `scripts/test_exact_init_sequence.py` - Full initialization + AdcQueue test
- `scripts/test_verify_minimal.py` - Minimal sequence validation
- `scripts/test_minimal_adcqueue.py` - Systematic testing of init requirements
- Manual AdcQueue parsing examples in analysis scripts

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

**Minimal implementation:**
1. **Reset device** via USB reset
2. **Send Stop Graph** (0x0F) to ensure clean state
3. **Send Start Graph** (0x0E) with desired rate index (0-3)
4. **Wait** for samples to accumulate (~1 second recommended)
5. **Request AdcQueue** (GetData with attribute 0x0002) repeatedly
6. **Send Stop Graph** (0x0F) when finished

**Optional enhancements:**
- Mix with ADC: Periodically request ADC (0x0001) for temperature
- Monitor sequence numbers: Detect buffer overflows or dropped samples
- Buffer management: Expect 5-50 samples per packet

**Common mistakes to avoid:**
- ❌ Don't request attribute 0x0004 (not implemented)
- ❌ Don't assume initialization commands are required (they're not)
- ❌ Don't request AdcQueue immediately after Start Graph (wait for accumulation)
- ❌ Don't forget to send Stop Graph on exit

### For Protocol Research

1. ✅ **AdcQueue fully documented** - minimal sequence confirmed on hardware
2. ✅ **Rate configuration understood** - 0x0E command with rate index
3. ✅ **Attribute 0x0004 clarified** - documented but never used
4. ✅ **Unknown76 (0x4C) reversed** - Streaming authentication, required for AdcQueue to return samples. See [unknown76_authentication.md](unknown76_authentication.md)
5. ✅ **Unknown68 (0x44) reversed** - Memory download command for device info and offline logs. See [offline_log_protocol.md](offline_log_protocol.md)