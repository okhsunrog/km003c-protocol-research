# USB Master Dataset Analysis

## Overview
Comprehensive analysis of the USB master dataset containing traffic from multiple KM003C USB protocol research sessions.

**Dataset Statistics:**
- **Total Packets:** 11,514
- **Devices:** 4 (addresses 6, 9, 13, 16)
- **Capture Sessions:** 7
- **Time Range:** Multiple capture sessions spanning hours
- **Data Fields:** 41 comprehensive USB protocol fields per packet

## Transfer Types Distribution

| Transfer Type | Count | Percentage | Devices | Description |
|---------------|-------|------------|---------|-------------|
| Bulk (0x03) | 11,354 | 98.61% | All 4 | High-throughput data transfers |
| Control (0x02) | 160 | 1.39% | All 4 | Device enumeration and setup |

## Device Analysis

### Device Summary
| Device | Total Packets | Sessions | Transfer Types | Endpoints | Payload % | Avg Payload Size |
|--------|---------------|----------|----------------|-----------|-----------|------------------|
| 6 | 2,230 | 3 | 2 | 3 | 47.98% | 94.3 bytes |
| 9 | 6,930 | 1 | 2 | 3 | 49.96% | 12.6 bytes |
| 13 | 2,056 | 1 | 2 | 3 | 49.27% | 8.8 bytes |
| 16 | 298 | 2 | 2 | 4 | 34.56% | 12.8 bytes |

### Device-Specific Communication Patterns

#### Device 6 (3 sessions: 1000Hz, 50Hz, record)
- **Primary Use:** High-frequency ADC data collection
- **Endpoints:** 0x01 (OUT), 0x80 (Control), 0x81 (IN)
- **Pattern:** Regular bulk transfers with largest payload sizes (avg 94.3 bytes, max 968 bytes)
- **Timing:** Consistent intervals (avg 0.027s between packets)
- **Payload Distribution:** Large data packets (up to 872-byte frames)

#### Device 9 (1 session: pd_capture_new)
- **Primary Use:** Power Delivery protocol analysis
- **Endpoints:** 0x01 (OUT), 0x80 (Control), 0x81 (IN)
- **Pattern:** Most active device (6,930 packets) with balanced bidirectional communication
- **Timing:** Regular intervals (avg 0.050s) over 295.6 seconds
- **Frame Distribution:** Primarily 64-byte (3,465), 68-byte (1,733), and 116-byte (1,401) frames

#### Device 13 (1 session: orig_with_pd)
- **Primary Use:** Power Delivery with original protocol
- **Endpoints:** 0x01 (OUT), 0x80 (Control), 0x81 (IN)
- **Pattern:** Moderate activity with smallest average payload (8.8 bytes)
- **Timing:** Longer intervals (avg 0.133s) with highest variance
- **Duration:** 42.1 seconds of continuous communication

#### Device 16 (2 sessions: open_close, simple_logger)
- **Primary Use:** Logging and device control operations
- **Endpoints:** 0x00 (Control), 0x01 (OUT), 0x80 (Control), 0x81 (IN)
- **Pattern:** Lowest activity (298 packets) with unique control endpoint 0x00
- **Payload:** Lowest percentage with payload (34.56%)
- **Sessions:** Two short sessions (7.0s and 9.8s)

## Session Analysis

| Session | Device | Duration | Packets | Payload Packets | Transfer Types |
|---------|--------|----------|---------|----------------|----------------|
| pd_capture_new.9 | 9 | 295.6s | 6,930 | 3,462 | 2 |
| orig_with_pd.13 | 13 | 42.1s | 2,056 | 1,013 | 2 |
| orig_adc_1000hz.6 | 6 | 17.9s | 1,240 | 605 | 2 |
| orig_adc_50hz.6 | 6 | 16.1s | 570 | 270 | 2 |
| orig_adc_record.6 | 6 | 18.3s | 420 | 195 | 2 |
| orig_open_close.16 | 16 | 9.8s | 152 | 61 | 2 |
| rust_simple_logger.16 | 16 | 7.0s | 146 | 42 | 2 |

## USB Protocol Structure

### Endpoint Usage Patterns
| Device | Endpoint | Direction | Usage | Packet Count |
|--------|----------|-----------|--------|--------------|
| All | 0x80 | IN (D→H) | Control responses | 128 |
| All | 0x01 | OUT (H→D) | Bulk data commands | 5,674 |
| All | 0x81 | IN (D→H) | Bulk data responses | 5,564 |
| 16 only | 0x00 | OUT (H→D) | Control requests | 6 |

### Control Packet Analysis
- **Total Control Packets:** 160 (1.39% of all traffic)
- **Descriptor Types:**
  - 0x03 (String): 104 packets
  - 0x02 (Configuration): 36 packets  
  - 0x01 (Device): 14 packets
  - 0x0f (BOS): 4 packets
- **Usage:** Device enumeration during session initialization

### Frame Size Distribution
| Frame Size | Count | Percentage | Devices | Notes |
|------------|-------|------------|---------|-------|
| 64 bytes | 5,788 | 50.3% | All | Standard USB packet size |
| 68 bytes | 2,817 | 24.5% | All | Extended control packets |
| 116 bytes | 1,749 | 15.2% | All | Larger data payloads |
| 84 bytes | 671 | 5.8% | All | Medium data packets |
| 872 bytes | 127 | 1.1% | 6 only | Maximum payload packets |

### URB Transaction Patterns
- **Submit/Complete Pairs:** Perfect 1:1 ratio (5,757 each)
- **Transaction Completeness:** All USB operations properly paired
- **Direction Balance:** Near-equal bidirectional communication across all devices

## Key Findings

### Communication Characteristics
1. **High Bulk Transfer Usage:** 98.61% bulk transfers indicates high-throughput data communication
2. **Minimal Control Overhead:** Only 1.39% control packets for device setup
3. **Balanced Bidirectional Flow:** Even split between IN/OUT transfers
4. **Device-Specific Patterns:** Each device shows distinct usage characteristics

### Protocol Insights
1. **KM003C Protocol Structure:** Request-response pattern using endpoints 0x01 (OUT) and 0x81 (IN)
2. **Data Categories:**
   - **Device 6:** ADC measurements and high-frequency data logging
   - **Device 9:** Power Delivery protocol capture and analysis
   - **Device 13:** Power Delivery with legacy protocol support
   - **Device 16:** Device management and logging operations

3. **Timing Behavior:**
   - **Regular Intervals:** Devices maintain consistent communication timing
   - **Variable Patterns:** Different devices use different polling/response intervals
   - **Session Duration:** Ranges from seconds (testing) to minutes (data collection)

### Technical Specifications
- **USB Transfer Types:** Bulk-dominant architecture optimized for throughput
- **Endpoint Strategy:** Standardized 0x01/0x81 bulk pair across devices
- **Payload Efficiency:** ~47% of packets carry actual data payload
- **Protocol Completeness:** All URB transactions properly paired (Submit/Complete)

This analysis confirms the KM003C protocol implements a robust USB bulk transfer system optimized for high-throughput data collection and Power Delivery protocol analysis, with device-specific variations for different operational modes.