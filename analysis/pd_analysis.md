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

## Preliminary Findings

### Packet Classification
Based on initial analysis, KM003C packets can be classified as:

1. **SimpleAdcData** (0x41 prefix): ADC measurement responses
2. **CmdGetSimpleAdcData** (0x0C + 0x0200): ADC measurement requests  
3. **Generic** (various): Likely includes PD analyzer commands and data

### Potential PD Patterns
Looking for patterns in `Generic` packets that might indicate PD functionality:

- **Setup Commands**: Device configuration for PD capture
- **Capture Commands**: Start/stop PD monitoring
- **Data Transfer**: PD message payload transfer
- **Status/Control**: Device state and error reporting

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

### Phase 1: Pattern Recognition
- [x] Create PD analysis notebook
- [ ] Identify capture files containing PD data
- [ ] Analyze packet patterns in PD captures
- [ ] Look for timing correlations

### Phase 2: Protocol Reverse Engineering
- [ ] Decode Generic packet structures
- [ ] Identify PD command/response patterns
- [ ] Map payload formats to PD message types

### Phase 3: Implementation
- [ ] Extend Rust parser with PD packet types
- [ ] Add PD message decoding functions
- [ ] Create PD-specific visualization tools

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