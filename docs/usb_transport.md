# USB Transport Specification

USB layer documentation for the KM003C. For application protocol details, see [Protocol Reference](protocol_reference.md).

---

## Device Identification

| Property | Value |
|----------|-------|
| Vendor ID | `0x5FC9` (ChargerLAB) |
| Product ID | `0x0063` (KM003C) |
| USB Version | 2.10 |
| Device Class | `0xEF` (Miscellaneous - IAD) |
| Speed | Full Speed (12 Mbps) |
| Max Packet Size | 32 bytes (EP0), 64 bytes (bulk/interrupt) |
| Power | 100mA bus-powered |

**Device family:** KM002C (`0x0061`), KM003C (`0x0063`)

---

## Interface Configuration

The KM003C implements 4 USB interfaces:

### Interface 0: Vendor Bulk (Primary)

| Property | Value |
|----------|-------|
| Class | `0xFF` (Vendor Specific) |
| Driver | `powerz` (Linux hwmon) |
| Transfer Type | Bulk |

**Endpoints:**
- `0x01 OUT` - Bulk, 64 bytes
- `0x81 IN` - Bulk, 64 bytes

**Use:** Main protocol communication (ADC, PD, streaming)

### Interface 1: CDC Communications

| Property | Value |
|----------|-------|
| Class | `0x02` (Communications) |
| SubClass | `0x02` (ACM) |
| Driver | `cdc_acm` |

**Endpoint:**
- `0x83 IN` - Interrupt, 8 bytes, 10ms interval

### Interface 2: CDC Data

| Property | Value |
|----------|-------|
| Class | `0x0A` (CDC Data) |
| Driver | `cdc_acm` (paired with IF1) |

**Endpoints:**
- `0x02 OUT` - Bulk, 64 bytes
- `0x82 IN` - Bulk, 64 bytes

### Interface 3: HID

| Property | Value |
|----------|-------|
| Class | `0x03` (HID) |
| HID Version | 1.11 |
| Driver | `usbhid` |

**Endpoints:**
- `0x05 OUT` - Interrupt, 64 bytes, 1ms interval
- `0x85 IN` - Interrupt, 64 bytes, 1ms interval

**Use:** Alternative access method (cross-platform without drivers)

---

## Descriptor Hierarchy

```
Device Descriptor (18 bytes)
└── Configuration Descriptor (130 bytes)
    ├── Interface 0 (Vendor Specific)
    │   ├── EP 0x01 OUT (Bulk)
    │   └── EP 0x81 IN (Bulk)
    ├── Interface Association Descriptor (CDC)
    ├── Interface 1 (CDC Communications)
    │   ├── CDC Header (v1.10)
    │   ├── CDC Call Management
    │   ├── CDC ACM
    │   ├── CDC Union
    │   └── EP 0x83 IN (Interrupt)
    ├── Interface 2 (CDC Data)
    │   ├── EP 0x02 OUT (Bulk)
    │   └── EP 0x82 IN (Bulk)
    └── Interface 3 (HID)
        ├── HID Descriptor (v1.11)
        ├── EP 0x05 OUT (Interrupt)
        └── EP 0x85 IN (Interrupt)
```

### BOS Descriptor

Platform Device Capability:
- **UUID:** `{d8dd60df-4589-4cc7-9cd2-659d9e648a9f}`
- **Data:** `00 00 03 06 aa 00 20 00`

---

## Endpoint Summary

| Endpoint | Interface | Type | Direction | Max Packet | Interval |
|----------|-----------|------|-----------|------------|----------|
| 0x01 | IF0 | Bulk | OUT | 64 | - |
| 0x81 | IF0 | Bulk | IN | 64 | - |
| 0x83 | IF1 | Interrupt | IN | 8 | 10ms |
| 0x02 | IF2 | Bulk | OUT | 64 | - |
| 0x82 | IF2 | Bulk | IN | 64 | - |
| 0x05 | IF3 | Interrupt | OUT | 64 | 1ms |
| 0x85 | IF3 | Interrupt | IN | 64 | 1ms |

---

## Bulk Transfer Behavior

### URB Transaction Pattern

```
Host → Device: Submit OUT (command)
Device → Host: Complete (status=0, acknowledged)

Host → Device: Submit IN (buffer posted, status=-115 EINPROGRESS)
Device → Host: Complete IN (response data)
```

### Status Codes

| Status | Name | Meaning |
|--------|------|---------|
| 0 | SUCCESS | Command acknowledged |
| -115 | EINPROGRESS | IN URB pending |
| -2 | ENOENT | Operation cancelled |

### URB Flags

| Flag | Hex | Meaning |
|------|-----|---------|
| URB_SHORT_NOT_OK | 0x00000200 | Host expects full-length transfer; short packets treated as errors |
| Standard | 0x00000000 | Relaxed length (short OK) |

### URB ID Warning

The `urb_id` in USB monitoring tools (Wireshark/usbmon) is a **kernel memory address**, not a transaction ID. It gets reused.

**Correct grouping:** Match Submit → Complete pairs by timestamp order, not by URB ID.

---

## Timing Characteristics

| Metric | Value |
|--------|-------|
| Command latency | 77-85 µs |
| ADC polling interval | ~200 ms |
| PD capture interval | ~40 ms |
| Max sustained throughput | 133 packets/s |

---

## Linux Integration

### Kernel Drivers

| Interface | Driver | Device Node |
|-----------|--------|-------------|
| IF0 | `powerz` | `/sys/class/hwmon/hwmonX/` |
| IF1+2 | `cdc_acm` | `/dev/ttyACM*` |
| IF3 | `usbhid` | `/dev/hidraw*` |

### System Paths

```
/sys/bus/usb/devices/1-X.X/          # Device sysfs
/sys/class/hwmon/hwmonX/             # hwmon interface
/dev/ttyACM*                         # CDC serial
/dev/hidraw*                         # HID raw access
```

### Unbinding powerz for Direct Access

The `powerz` hwmon driver claims Interface 0 by default. To use direct USB access:

```bash
# Find the device
echo '5fc9 0063' | sudo tee /sys/bus/usb/drivers/powerz/new_id  # If not already bound

# Unbind
echo '1-1.3:1.0' | sudo tee /sys/bus/usb/drivers/powerz/unbind
```

Or use udev rules:
```
# /etc/udev/rules.d/99-km003c.rules
ACTION=="add", SUBSYSTEM=="usb", ATTR{idVendor}=="5fc9", ATTR{idProduct}=="0063", \
    RUN+="/bin/sh -c 'echo 1-*:1.0 > /sys/bus/usb/drivers/powerz/unbind'"
```

---

## Enumeration & Vendor Control

- **Standard flow:** Device and configuration descriptors are requested twice (short header then full 130B config). String descriptors are queried at multiple lengths (4/255/258 bytes).
- **VM redirection:** In passthrough setups, a three-stage sequence occurs (host enumerate → guest enumerate → app start), followed by a proprietary control transfer.
- **Vendor request 0x32:** `bmRequestType=0xC2`, `bRequest=0x32`, `wLength=170` — returns a 170-byte blob (likely capability/calibration query).
- **Other control probes observed:** type 0x10 attr 0x0001 (zero-length), type 0x11 attr 0x0000 (zero-length), and GetData attr 0x0011 during init.

---

## Traffic Analysis (usbmon)

| Endpoint | Transfer Type | Packet Count | Usage |
|----------|---------------|--------------|-------|
| 0x01/0x81 | Bulk | 11,710 | Primary protocol (Interface 0) |
| 0x80/0x00 | Control | 286 | Descriptor + vendor control |
| 0x85 | Interrupt | 12 | HID interface (Interface 3) |

---

## Performance Profiles (captures)

| Device Addr | Packets | Rate (pps) | Avg Payload | Use Case |
|-------------|---------|------------|-------------|----------|
| 6 | 2,152 | 133.1 | 97.2 bytes | High-frequency ADC |
| 13 | 2,030 | 66.0 | 8.7 bytes | Fast command-response |
| 16 | 248 | 44.0 | 12.4 bytes | Low-volume monitoring |
| 9 | 6,924 | 23.4 | 12.6 bytes | PD protocol analysis |

---

## Troubleshooting & Edge Cases

- **URB ID reuse:** Kernel urb_id is an address, not a transaction identifier; always correlate Submit→Complete pairs instead of grouping by urb_id.
- **Empty Complete:** A 0-length IN Complete (status=0) is a normal acknowledgment path for control/bulk commands.
- **ENOENT (-2):** Seen when operations are cancelled; not fatal if the next request succeeds.
- **Driver conflicts:** If the `powerz` driver is bound, bulk interface 0 will NAK; unbind (see above) before direct access.

---

## Interface Selection Guide

| Use Case | Interface | Notes |
|----------|-----------|-------|
| High-performance streaming | IF0 (Bulk) | Requires driver unbind on Linux |
| Cross-platform, no drivers | IF3 (HID) | Works everywhere, slightly slower |
| Serial debugging | IF1+2 (CDC) | Limited to serial protocols |

**Note:** AdcQueue streaming and full authentication only work on Interface 0 (vendor bulk).

---

## Control Transfers

### Standard Enumeration

Device follows standard USB enumeration:
1. Device Descriptor (18 bytes)
2. Configuration Descriptor (9 bytes header, then 130 bytes full)
3. String Descriptors (manufacturer, product, serial)

### Vendor-Specific Control Request

Discovered proprietary request during enumeration:

```
bmRequestType: 0xC2 (Vendor, Device-to-Host)
bRequest:      0x32
wValue:        0x0000
wIndex:        0x0000
wLength:       170
```

Purpose: Likely device capability or calibration query.

---

## Traffic Analysis

### Transfer Type Encoding (Wireshark)
- `0` Isochronous, `1` Interrupt, `2` Control, `3` Bulk

### Observed Counts (captures)

| Endpoint | Type | Packets | Usage |
|----------|------|---------|-------|
| 0x01/0x81 | Bulk | 11,710 | Primary protocol |
| 0x80/0x00 | Control | 286 | Enumeration |
| 0x85 | Interrupt | 12 | HID (IF3) |

### Handshakes & ZLP

- **Data request:** Host posts IN URB (status -115 EINPROGRESS) → device completes with data.
- **Ack only:** Host sends command → empty Complete status=0.
- **Error:** Empty Complete status=-2 (ENOENT).
- **URB IDs are kernel addresses**: never use `urb_id` for correlation; pair Submit→Complete by order.

### Timing (typical)

| Metric | Value |
|--------|-------|
| Command latency | 77–85 µs |
| ADC polling interval | ~200 ms |
| PD capture interval | ~40 ms |
| Max sustained throughput | ~133 packets/s |

### Performance Profiles

| Device Addr | Packets | Rate (pps) | Avg Payload | Use Case |
|-------------|---------|------------|-------------|---------|
| 6 | 2,152 | 133.1 | 97.2 B | High-frequency ADC |
| 13 | 2,030 | 66.0 | 8.7 B | Fast command/response |
| 16 | 248 | 44.0 | 12.4 B | Low-volume monitoring |
| 9 | 6,924 | 23.4 | 12.6 B | PD analysis |

### Troubleshooting

- Mis-grouping by `urb_id` leads to corrupted flows; always match Submit→Complete pairs.
- Interface 0 gives best latency; HID (IF3) is slower but driverless; CDC mostly for serial/debug.

---

## Related Documentation

- [Protocol Reference](protocol_reference.md) - Application protocol
- [Linux hwmon powerz driver](https://github.com/torvalds/linux/blob/master/drivers/hwmon/powerz.c)
