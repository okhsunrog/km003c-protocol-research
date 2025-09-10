# KM003C Power Delivery (PD) Protocol Analysis

## Overview

The KM003C device functions as both an ADC measurement tool and a USB Power Delivery (PD) protocol analyzer. This document focuses on investigating the PD analysis capabilities and understanding the protocol structure used for PD communication capture and analysis.

## Device Modes

### ADC Mode
- **Purpose**: Voltage, current, power, and temperature measurements
- **Packet Types**: `CmdGetSimpleAdcData` → `SimpleAdcData`
- **Data Size**: 4-byte requests, 52-byte responses
- **Analysis**: Covered in `usb_protocol_analysis.ipynb`

### PD Analyzer Mode  
- **Purpose**: USB Power Delivery protocol capture and analysis
- **Packet Types**: Various `Generic` packets, potentially PD-specific commands
- **Data Size**: Variable, potentially larger payloads for PD message capture
- **Analysis**: This document and `pd_protocol_analysis.ipynb`

## Investigation Goals

### 1. Protocol Identification
- [ ] Identify PD-specific packet patterns in USB captures
- [ ] Differentiate PD analyzer packets from ADC measurement packets
- [ ] Understand command structure for PD capture control

### 2. PD Message Structure
- [ ] Analyze how PD messages are encapsulated in USB packets
- [ ] Understand timestamp correlation for PD events
- [ ] Map PD message types to USB packet payloads

### 3. Capture Control Protocol
- [ ] Commands to start/stop PD capture
- [ ] Configuration of PD capture parameters
- [ ] Status reporting and error handling

## Key Discoveries - PD File Analysis

### File: `orig_with_pd.13`
- **Duration**: 42.093 seconds
- **Total packets**: 2,056
- **Transactions**: 1,015

**Major finding**: Contains **NEW PACKET TYPES**:
- **347 × `CmdGetPdData`** - Host commands to request PD data
- **347 × `PdRawData`** - Device responses with PD capture data

### File: `pd_capture_new.9`  
- **Duration**: 295.600 seconds (5 minutes)
- **Total packets**: 6,930
- **Transactions**: 3,461

**Mixed mode operation**:
- **1,401 × `CmdGetSimpleAdcData`** - Regular ADC measurements
- **310 × `CmdGetPdData`** - PD data requests
- **1,400 × `SimpleAdcData`** - ADC responses  
- **310 × `PdRawData`** - PD responses

## Protocol Structure Discovery

### PD Command Pattern
```
Host → Device: CmdGetPdData (request PD data)
Device → Host: PdRawData (PD capture data)
```

### Dual Mode Operation
The KM003C operates in **dual mode** during PD analysis:
1. **Continuous ADC polling** (~200ms intervals)
2. **PD event capture** (on-demand when PD events occur)

### Packet Classification (Updated)
1. **SimpleAdcData** (0x41 prefix): ADC measurement responses
2. **CmdGetSimpleAdcData** (0x0C + 0x0200): ADC measurement requests  
3. **PdRawData**: PD protocol capture data ⭐ **NEW**
4. **CmdGetPdData**: PD data request commands ⭐ **NEW**
5. **Generic** (various): Setup/control commands

### Initial Setup Patterns
Both files show initial setup sequences with **Generic** commands:
- `[02 01 00 00]` - 4-byte commands
- `[44 XX 01 01]` - 36-byte extended commands  
- `[c4 XX 01 01]` - 20-byte responses

These likely configure the device for PD capture mode.

## Analysis Methodology

### 1. Packet Pattern Analysis
```python
# Filter for non-ADC packets
pd_candidates = parsed_df.filter(pl.col('packet_type') == 'Generic')

# Look for common payload prefixes
prefix_patterns = pd_candidates.with_columns(
    pl.col('payload_hex').str.slice(0, 8).alias('payload_prefix')
).group_by('payload_prefix').agg(pl.len().alias('count'))
```

### 2. Timing Analysis
- Analyze transaction timing patterns
- Look for burst patterns indicating PD event capture
- Correlate timing with potential PD negotiation sequences

### 3. Payload Size Analysis
- PD messages have specific size patterns
- Control messages: typically 16-32 bytes
- Data messages: can be larger (64+ bytes)
- Look for size patterns that match PD specifications

## Expected PD Protocol Elements

### USB PD Message Types
Based on USB PD 3.0 specification, expect to see:

1. **Control Messages**:
   - GoodCRC, Accept, Reject
   - PS_RDY, Get_Source_Cap, etc.

2. **Data Messages**:
   - Source_Capabilities, Request
   - Battery_Status, Alert, etc.

3. **Extended Messages**:
   - Battery_Capabilities, Status
   - Manufacturer_Info, etc.

### KM003C Encapsulation
Need to understand how these PD messages are:
- Encapsulated in USB packets
- Timestamped for analysis
- Associated with CC pin monitoring
- Correlated with VBUS/VCONN events

## Research Questions

### Protocol Structure
1. How does the KM003C encode PD message timestamps?
2. What is the format for PD message payloads in USB packets?
3. How are CC1/CC2 events correlated with PD messages?

### Device Control
1. What commands control PD capture start/stop?
2. How is PD capture configured (which events to monitor)?
3. What status information is available during capture?

### Data Format
1. How are PD message headers preserved?
2. What metadata is captured with each PD event?
3. How are transmission errors/retries handled?

## Investigation Steps

### Phase 1: Pattern Recognition ✅ 
- [x] Create PD analysis notebook
- [x] Identify capture files containing PD data (`orig_with_pd.13`, `pd_capture_new.9`)
- [x] Analyze packet patterns in PD captures
- [x] **DISCOVERED**: New packet types `CmdGetPdData` and `PdRawData`

### Phase 2: Protocol Reverse Engineering 🔄
- [x] ~~Decode Generic packet structures~~ → Focus on PD packet types instead
- [x] Identify PD command/response patterns → `CmdGetPdData` ↔ `PdRawData`
- [ ] **URGENT**: Understand `PdRawData` payload format 
- [ ] **URGENT**: Decode actual PD messages within `PdRawData`
- [ ] Map PD message timing and sequence

### Phase 3: Implementation 📋
- [ ] Extend Rust parser to decode `PdRawData` contents
- [ ] Add PD message decoding functions  
- [ ] Create PD-specific visualization tools
- [ ] Add PD timing analysis

## Next Immediate Steps

### 1. Analyze PdRawData Structure
The Rust parser already recognizes `PdRawData` packets but we need to understand:
- What's inside the `pd_data` payload?
- How are PD messages encoded?
- What's the timestamp/metadata format?

### 2. Compare with USB PD Specification
- Map discovered data to USB PD message types
- Understand how CC pin events are encoded
- Analyze VBUS/VCONN correlation

### 3. Timing Analysis
- Correlate PD events with ADC measurements
- Analyze PD negotiation sequences
- Look for power delivery state changes

## Reference Materials

### USB PD Specifications
- USB Power Delivery 3.0 Specification
- USB Type-C Cable and Connector Specification
- USB PD 3.1 Specification (if applicable)

### KM003C Documentation
- Official protocol documentation (if available)
- Community reverse engineering efforts
- Similar device analysis for comparison

## Notes and Observations

### Capture File Analysis
*Document findings from analyzing specific capture files here*

### Protocol Patterns
*Record discovered packet patterns and their potential meanings*

### Timing Characteristics  
*Note timing patterns that might indicate PD events*

---

*This document is a living investigation log. Update findings as the analysis progresses.*