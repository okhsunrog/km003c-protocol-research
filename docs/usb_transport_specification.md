# ChargerLAB POWER-Z KM003C: USB Transport Specification

## Document Overview

This document provides the complete USB transport specification for the **ChargerLAB POWER-Z KM003C** USB-C power analyzer, including device descriptors, interface configurations, endpoints, and low-level USB communication details.

For high-level protocol communication patterns, see [Protocol Specification](protocol_specification.md).

---

## Device Identification

### USB Device Properties
- **Vendor ID**: `0x5FC9` (ChargerLAB)
- **Product ID**: `0x0063` (KM003C model)
- **Device Version**: `1.00` (bcdDevice)
- **USB Version**: `2.10` (USB 2.1 compliant)
- **Serial Number**: `007965` (example device)
- **Device Class**: `0xEF` (Miscellaneous Device)
- **Device SubClass**: `0x02` (Interface Association)
- **Device Protocol**: `0x01` (Interface Association)
- **Max Packet Size**: `32 bytes` (EP0)
- **Power Requirements**: `100mA` (Bus powered)
- **Speed**: `12 Mbps` (Full Speed)

### Device Family
The KM003C is part of the POWER-Z family of USB-C analyzers:
- **KM002C**: Product ID `0x0061` (earlier model)
- **KM003C**: Product ID `0x0063` (current focus)

---

## Complete Interface Configuration

The KM003C implements **4 distinct USB interfaces** with different capabilities:

### Interface 0: Vendor Specific (Primary Protocol)
- **Interface Class**: `0xFF` (Vendor Specific)
- **Driver**: `powerz` (Linux kernel hwmon driver)
- **Function**: Main ADC and PD protocol communication
- **Transfer Type**: **Bulk transfers** (verified in traffic analysis)
- **Endpoints**:
  - `0x01 OUT`: Bulk, 64 bytes max packet, 0ms interval
  - `0x81 IN`: Bulk, 64 bytes max packet, 0ms interval

### Interface 1: CDC Communications (Serial Interface)
- **Interface Class**: `0x02` (Communications)
- **Interface SubClass**: `0x02` (Abstract Control Model)
- **Driver**: `cdc_acm` (CDC ACM serial driver)
- **Function**: Serial command interface
- **Transfer Type**: Interrupt transfers
- **Endpoints**:
  - `0x83 IN`: Interrupt, 8 bytes max packet, 10ms interval

### Interface 2: CDC Data (Serial Data)
- **Interface Class**: `0x0A` (CDC Data)
- **Driver**: `cdc_acm` (paired with Interface 1)
- **Function**: Serial data transfer
- **Transfer Type**: Bulk transfers
- **Endpoints**:
  - `0x02 OUT`: Bulk, 64 bytes max packet, 0ms interval
  - `0x82 IN`: Bulk, 64 bytes max packet, 0ms interval

### Interface 3: Human Interface Device
- **Interface Class**: `0x03` (HID)
- **HID Version**: `1.11`
- **Driver**: `usbhid` (Generic HID driver)
- **Function**: HID-based data interface (alternative access method)
- **Transfer Type**: Interrupt transfers
- **Endpoints**:
  - `0x05 OUT`: Interrupt, 64 bytes max packet, 1ms interval
  - `0x85 IN`: Interrupt, 64 bytes max packet, 1ms interval

---

## USB Descriptor Hierarchy

```
Device Descriptor (18 bytes)
└── Configuration Descriptor (130 bytes total)
    ├── Interface 0 (Vendor Specific - powerz driver)
    │   ├── Endpoint 0x01 OUT (Bulk)
    │   └── Endpoint 0x81 IN (Bulk)
    ├── Interface Association Descriptor (CDC)
    ├── Interface 1 (CDC Communications)
    │   ├── CDC Header Descriptor (v1.10)
    │   ├── CDC Call Management Descriptor
    │   ├── CDC ACM Descriptor
    │   ├── CDC Union Descriptor
    │   └── Endpoint 0x83 IN (Interrupt)
    ├── Interface 2 (CDC Data)
    │   ├── Endpoint 0x02 OUT (Bulk)
    │   └── Endpoint 0x82 IN (Bulk)
    └── Interface 3 (HID)
        ├── HID Descriptor (9 bytes, v1.11)
        ├── Endpoint 0x05 OUT (Interrupt)
        └── Endpoint 0x85 IN (Interrupt)
```

### Binary Object Store (BOS) Descriptor

The device includes a BOS descriptor with Platform Device Capability:
- **UUID**: `{d8dd60df-4589-4cc7-9cd2-659d9e648a9f}`
- **Capability Data**: `00 00 03 06 aa 00 20 00`
- **Purpose**: Likely USB-C specific capabilities or vendor extensions

---

## USB Transfer Types and Traffic Analysis

### Transfer Type Encoding (Wireshark/tshark)
- `0` = Isochronous
- `1` = Interrupt
- `2` = Control
- `3` = Bulk

### Verified Traffic Patterns

Based on captured USB traffic analysis:

| Endpoint | Transfer Type | Packet Count | Usage |
|----------|---------------|--------------|-------|
| 0x01/0x81 | Bulk (0x03) | 11,710 | **Primary protocol** (Interface 0) |
| 0x80/0x00 | Control (0x02) | 286 | Device enumeration |
| 0x85 | Interrupt (0x01) | 12 | HID interface (Interface 3) |

### Primary Communication Interface

**Interface 0** is the primary communication interface using:
- **Bulk transfers** on endpoints 0x01 (OUT) and 0x81 (IN)
- **64-byte maximum packet size**
- **Vendor-specific protocol** for ADC measurements and PD analysis

---

## Linux System Integration

### USB Topology
- **Bus**: 1
- **Port**: 1.3
- **Device**: 19 (varies by connection)

### Kernel Drivers
- `powerz`: Interface 0 (hwmon driver for voltage/current monitoring)
- `cdc_acm`: Interfaces 1&2 (serial communication)
- `usbhid`: Interface 3 (HID generic driver)

### System Paths
- `/sys/bus/usb/devices/1-1.3/` - Device sysfs directory
- `/dev/ttyACM*` - CDC ACM serial devices
- `/sys/class/hwmon/hwmonX/` - Hardware monitoring interface

---

## Device Enumeration Process

### Standard USB Enumeration

The KM003C follows standard USB enumeration with comprehensive descriptor requests:

#### Device Descriptor Pattern
```
bmRequestType: 0x80 (Device-to-Host)
bRequest: 0x06 (GET_DESCRIPTOR)
wValue: 0x0100 (Device Descriptor)
wLength: 18 bytes
```

#### Configuration Descriptor Pattern
Two-stage request for complete configuration:
1. **Header Request**: wLength=9 (basic info)
2. **Full Request**: wLength=130 (complete configuration)

#### String Descriptor Requests
High-volume requests for device identification:
- Manufacturer, Product, Serial Number strings
- Multiple language support (Language ID in wIndex)
- Variable lengths: 4, 255, 258 bytes

### Multi-Stage Initialization (VM Environment)

When used in virtualized environments, a three-stage initialization occurs:

1. **Physical Connection (Host OS)**
   - Basic USB enumeration by host OS
   - Generic drivers loaded (`cdc_acm`, `hid-generic`)
   - Standard descriptors requested

2. **VM Redirection (Guest OS)**
   - Device redirected to virtual machine
   - Guest OS performs thorough enumeration
   - **Critical**: Proprietary commands sent by official driver
   - Custom command `bRequest=0x32` with `bmRequestType=0xC2`

3. **Application Startup**
   - Official software opens device
   - Additional descriptor verification
   - Main communication loop begins

### Proprietary Control Commands

#### Vendor-Specific Request (0x32)
```c
// Critical proprietary command during enumeration
struct vendor_request {
    .bmRequestType = 0xC2,  // Vendor-specific, Device-to-Host
    .bRequest = 0x32,       // Proprietary command
    .wValue = 0x0000,
    .wIndex = 0x0000,
    .wLength = 170          // Device returns 170 bytes
};
```

**Purpose**: Likely device capability query or calibration data retrieval

#### Unknown Control Commands
Additional proprietary commands discovered:
- **Type 0x10** with attribute 0x0001 (zero length)
- **Type 0x11** with attribute 0x0000 (zero length)
- **GetData** with attribute 0x0011 (undocumented)

---

## USB Bulk Transfer Protocol

### Zero-Length Packet Protocol

The KM003C uses sophisticated zero-length packet (ZLP) signaling:

#### URB Status Codes
| Status | Meaning | Count | Usage Pattern |
|--------|---------|-------|---------------|
| -115 | EINPROGRESS | 102 | IN URB pending (host buffer posted) |
| 0 | SUCCESS | 95 | Command acknowledged |
| -2 | ENOENT | 2 | Operation cancelled/not found |

#### Transfer Flags
| Flag | Hex | Meaning |
|------|-----|---------|
| URB_SHORT_NOT_OK | 0x00000200 | Strict length validation |
| Standard | 0x00000000 | Relaxed requirements |

### Handshaking Patterns

#### Pattern 1: Data Request Handshake
```
1. Host→Device: submits IN URB (buffer posted) → urb_status = -115 (EINPROGRESS)
2. Device produces data
3. Device→Host: completion with actual data (e.g., 52+ bytes for ADC PutData)
```

#### Pattern 2: Command Acknowledgment
```
1. Host→Device: Submit with command (4 bytes)
2. Device→Host: Empty Complete (Status=0, "acknowledged")
```

#### Pattern 3: Error Signaling
```
Device→Host: Empty Complete (Status=-2, "operation failed")
```

### URB Transaction Management

#### Critical Understanding: URB ID Reuse
The `urb_id` field in USB monitoring tools (like Wireshark/usbmon) represents a **kernel memory address**, not a unique transaction identifier:

- **Memory Recycling**: Same address reused for new transactions
- **Analysis Impact**: Must group by Submit→Complete pairs, not URB ID
- **Transaction Definition**: One logical transaction = One S→C pair
- **Performance**: Rapid transaction cycling creates "streaming" illusion

#### Timing Characteristics
- **Command Latency**: 77-85 microseconds
- **ADC Polling**: ~200ms intervals
- **PD Capture**: ~40ms when active
- **Maximum Throughput**: 133 packets/second sustained

---

## Performance Characteristics

### Device Performance Profiles
| Device Addr | Packets | Rate (pps) | Avg Payload | Use Case |
|-------------|---------|------------|-------------|----------|
| 6 | 2,152 | 133.1 | 97.2 bytes | High-frequency ADC |
| 13 | 2,030 | 66.0 | 8.7 bytes | Fast command-response |
| 16 | 248 | 44.0 | 12.4 bytes | Low-volume monitoring |
| 9 | 6,924 | 23.4 | 12.6 bytes | PD protocol analysis |

### Latency Analysis
- **Ultra-low command latency**: 77-85 microseconds
- **ADC collection interval**: ~200ms per reading
- **PD event capture**: ~40ms when active
- **Transaction duration range**: 40µs to 453ms
- **Sustained throughput**: Up to 133 packets/second

---

## Troubleshooting and Edge Cases

### Common Implementation Issues

#### URB ID Misinterpretation
**Problem**: Grouping packets by `urb_id` thinking it's a unique transaction identifier
**Solution**: Use Submit→Complete pairs for transaction boundaries
**Impact**: Incorrect protocol flow analysis

#### Multi-Interface Support
- **Issue**: Device has multiple USB interfaces with different capabilities
- **Solution**: Test each interface to determine optimal sampling rate
- **Recommendation**: Interface 0 for primary bulk protocol, Interface 3 (HID) for compatibility

### Interface Selection Guidelines

#### For Production Applications
- **Primary Choice**: Interface 0 (Vendor Specific) - Highest performance bulk transfers
- **Fallback**: Interface 3 (HID) - Cross-platform compatibility
- **Avoid**: Interface 2 (CDC Data) - Limited to serial communication patterns

#### For Development/Testing
- **CDC Interfaces**: Good for serial terminal debugging
- **HID Interface**: Easiest cross-platform access without drivers

---

## References

### Hardware Analysis Tools
- **lsusb**: USB device enumeration and descriptor analysis
- **Wireshark + usbmon**: USB traffic capture and analysis
- **tshark**: Command-line USB packet analysis

### Related Documentation
- [Protocol Specification](protocol_specification.md) - High-level communication protocol
- [USB 2.0 Specification](https://www.usb.org/document-library/usb-20-specification)
- [Wireshark USB Documentation](https://wiki.wireshark.org/USB) - USB protocol analysis with Wireshark
- [Linux USB Monitoring](https://www.kernel.org/doc/html/latest/usb/usbmon.html)
- [Linux hwmon powerz driver](https://github.com/torvalds/linux/blob/master/drivers/hwmon/powerz.c)
