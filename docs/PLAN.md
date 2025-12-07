# Documentation Restructure Plan

## Target Structure

```
docs_new/
├── README.md                         # Main index with navigation
├── protocol_reference.md             # THE definitive protocol specification
├── usb_transport.md                  # USB transport layer
│
├── features/                         # Feature deep-dives
│   ├── authentication.md             # 0x4C auth + 0x44 memory access
│   ├── adcqueue.md                   # High-rate streaming
│   ├── offline_logs.md               # Log download protocol
│   └── pd_analysis.md                # PD capture + SQLite export
│
├── firmware/                         # Firmware reverse engineering
│   ├── README.md                     # Firmware docs index
│   ├── overview.md                   # MCU, RTOS, protocols, hardware
│   ├── format.md                     # .mencrypt decryption
│   ├── handlers.md                   # Device firmware command handlers
│   └── mtools_analysis.md            # Mtools.exe (Windows app) RE
│
├── research/                         # WIP / unconfirmed
│   ├── unknown_commands.md           # Tracker for unknown commands
│   └── notes.md                      # Scratch pad
│
└── official/                         # Vendor documentation
    ├── KM002C&3C API Description.pdf
    └── KM003C_002C Protocol Trigger by Virtual Serial Port.pdf
```

---

## File Content Plan

### 1. README.md
**Purpose:** Navigation hub, project overview

**Content:**
- Project description (KM003C protocol research)
- Device identification (VID/PID)
- Quick start links
- Documentation map with descriptions
- Related projects (km003c-rs, community implementations)

---

### 2. protocol_reference.md (~800-1000 lines)
**Purpose:** Single source of truth for the complete protocol

**Sources to merge:**
- `protocol_specification.md` (core content)
- `unknown_commands_tracker.md` (command tables, confirmed protocol details)

**Sections:**
1. **Overview**
   - Device identification
   - Interface summary (bulk on IF0)

2. **Packet Headers**
   - Control header (4 bytes)
   - Data header (4 bytes)
   - Extended/logical header (4 bytes)
   - Bit layouts with diagrams

3. **Commands** (complete table)
   | Type | Name | Direction | Description |
   - 0x02 Connect
   - 0x03 Disconnect
   - 0x05 Accept
   - 0x06 Reject
   - 0x0C GetData
   - 0x0E StartGraph
   - 0x0F StopGraph
   - 0x10/0x11 PD Monitor Enable/Disable
   - 0x41 PutData
   - 0x44 MemoryRead
   - 0x4C StreamingAuth
   - etc.

4. **Attributes**
   | Attribute | Name | Size | Description |
   - 0x0001 ADC (44 bytes)
   - 0x0002 AdcQueue (20 bytes/sample)
   - 0x0008 Settings (180 bytes)
   - 0x0010 PdPacket (variable)
   - 0x0200 LogMetadata (48 bytes)

5. **Data Structures**
   - ADC payload (44 bytes) - byte offsets
   - AdcQueue sample (20 bytes) - byte offsets
   - Settings (180 bytes) - byte offsets
   - PD status (12 bytes)
   - PD event stream format

6. **Cryptography** (single source of truth)
   | Key Index | Key | Usage |
   | 0 | Lh2yfB7n6X7d9a5Z | Memory read, firmware, logs |
   | 3 | Fa0b4tA25f4R038a | Streaming auth (encrypt) |
   | 3' | FX0b4tA25f4R038a | Streaming auth (decrypt) |

7. **Communication Patterns**
   - Basic ADC polling sequence
   - AdcQueue streaming sequence
   - PD capture sequence

8. **Response Types**
   - 0x05 Accept
   - 0x06 Reject
   - 0x27 NotReadable
   - 0x1A, 0x2C, 0x3A, 0x40, 0x75 - data responses

---

### 3. usb_transport.md (~300 lines)
**Purpose:** USB layer only, no application protocol

**Source:** `usb_transport_specification.md` (mostly unchanged)

**Sections:**
- Device identification (VID/PID/class)
- Interface configuration (4 interfaces)
- Endpoint map
- Descriptor hierarchy
- Transfer characteristics
- Linux integration

---

### 4. features/authentication.md (~400 lines)
**Purpose:** Deep dive on auth & memory access

**Sources to merge:**
- `unknown76_authentication.md` (all content)
- Memory access parts from `unknown_commands_tracker.md`

**Sections:**
1. Overview (feature gating summary)
2. Command 0x4C (StreamingAuth)
   - Packet structure
   - AES mechanism
   - Why any payload works
   - Minimal working command
3. Command 0x44 (MemoryRead)
   - Packet structure
   - CRC calculation
   - Known addresses table
4. Authentication Levels (from firmware)
   - Level 0: basic
   - Level 1: device-authenticated
   - Level 2: calibration
5. Python examples

**Note:** References `protocol_reference.md` for header format, doesn't duplicate it.

---

### 5. features/adcqueue.md (~350 lines)
**Purpose:** High-rate streaming guide

**Source:** `adcqueue_analysis_summary.md` (streamlined)

**Sections:**
1. Quick Start (minimal sequence)
2. Sample structure (20 bytes)
3. Sampling rate modes (0-3)
4. StartGraph/StopGraph commands
5. ADC vs AdcQueue comparison
6. Implementation notes

**Note:** References `protocol_reference.md` for AdcQueue structure definition.

---

### 6. features/offline_logs.md (~300 lines)
**Purpose:** Log download protocol

**Source:** `offline_log_protocol.md` (streamlined)

**Sections:**
1. Overview
2. Protocol flow
3. Log metadata (attr 0x0200)
4. Data chunk format (0x34, 0x4E, 0x76, 0x68)
5. ADC log sample structure (16 bytes)
6. Python example

---

### 7. features/pd_analysis.md (~200 lines)
**Purpose:** PD capture & export

**Source:** `pd_sqlite_export_format.md` (mostly unchanged)

**Sections:**
1. PD packet types in protocol
2. SQLite export format
3. Wire format parsing
4. Event types (0x45 status, 0x80-0x9F wrapped)

---

### 8. firmware/README.md (~50 lines)
**Purpose:** Index for firmware docs

**Content:**
- What's in each firmware doc
- Links to handlers.md, mtools_analysis.md
- Ghidra project info

---

### 9. firmware/overview.md (~600 lines)
**Purpose:** Device firmware internals

**Source:** `firmware_analysis.md` (core content, minus command handlers)

**Sections:**
1. Firmware properties (size, arch, version)
2. Memory layout
3. RTOS tasks
4. Charging protocols supported
5. USB Type-C state machine
6. MCU identification (Kinetis analysis)
7. Peripheral map
8. Graphics (LVGL)
9. Notable strings

---

### 10. firmware/format.md (~250 lines)
**Purpose:** .mencrypt decryption

**Source:** `firmware_format.md` (unchanged)

---

### 11. firmware/handlers.md (~400 lines)
**Purpose:** Device firmware command handlers (Ghidra)

**Sources:**
- Command dispatcher from `unknown_commands_tracker.md`
- Access control from `firmware_analysis.md`

**Sections:**
1. Main dispatcher (FUN_0004eaf0)
2. Command handler table
3. Hardware crypto functions
4. Authentication system (DAT_20004041)
5. Memory read access control
6. Response building

---

### 12. firmware/mtools_analysis.md (~500 lines) **[NEW]**
**Purpose:** Mtools.exe (official Windows app) reverse engineering

**Content to gather from existing docs + organize:**

**Sections:**
1. **Overview**
   - File info (Qt5 app, x64)
   - Ghidra analysis summary

2. **Key Functions Table**
   | Address | Name | Purpose |
   |---------|------|---------|
   | 0x14006e9e0 | send_auth_packet_and_verify | Unknown76 handler |
   | 0x1400735e0 | get_crypto_key | AES key selection |
   | 0x14006b470 | build_command_header | Packet construction |
   | 0x14006b5f0 | build_download_request_packet | Memory read packets |
   | 0x14006b9b0 | build_data_packet_header | Data packet construction |
   | 0x14006d1b0 | handle_response_packet | Response parsing |
   | 0x14006ec70 | send_simple_command | Generic command |
   | 0x14006ef10 | manage_data_stream | StartGraph/StopGraph |
   | 0x14006f870 | download_large_data | Memory download |

3. **Data Locations**
   | Address | Description |
   |---------|-------------|
   | 0x140184ac8 | Key 0 obfuscation string |
   | 0x140184af8 | Key 1 obfuscation string |
   | 0x140184b28 | Key 2 obfuscation string |
   | 0x140184b60 | Key 3 obfuscation string |
   | 0x140277089 | Transaction ID counter |
   | 0x14017acb0 | Sample rate timing table |

4. **Protocol Implementation Details**
   - How Mtools builds auth packets
   - Response verification flow
   - Settings parsing (offset 0x60)
   - Attribute handling in handle_response_packet

5. **UI/Feature Mapping**
   - Graph view → manage_data_stream
   - Device info → download_large_data
   - PD capture → handle_response_packet attr=0x10

---

### 13. research/unknown_commands.md (~200 lines)
**Purpose:** Tracker for unknown/WIP commands

**Source:** Bootloader commands table from `unknown_commands_tracker.md`

**Sections:**
1. Bootloader/DFU commands (0x00-0x09, etc.)
2. Unknown attributes
3. Questions / investigation needed

---

### 14. research/notes.md (~50 lines)
**Purpose:** Scratch pad for ongoing research

**Content:**
- Template for adding notes
- Links to create issues

---

## Migration Checklist

### Phase 1: Structure
- [ ] Create docs_new/ directories
- [ ] Create README.md
- [ ] Copy official PDFs

### Phase 2: Core Docs
- [ ] protocol_reference.md (biggest task - consolidation)
- [ ] usb_transport.md

### Phase 3: Features
- [ ] features/authentication.md
- [ ] features/adcqueue.md
- [ ] features/offline_logs.md
- [ ] features/pd_analysis.md

### Phase 4: Firmware
- [ ] firmware/README.md
- [ ] firmware/overview.md
- [ ] firmware/format.md
- [ ] firmware/handlers.md
- [ ] firmware/mtools_analysis.md (NEW)

### Phase 5: Research
- [ ] research/unknown_commands.md
- [ ] research/notes.md

### Phase 6: Review
- [ ] Cross-reference links work
- [ ] No duplicate information
- [ ] All content migrated
- [ ] User confirmation

---

## Deduplication Rules

| Topic | Canonical Location | Other docs should... |
|-------|-------------------|---------------------|
| Packet headers | protocol_reference.md | Link to it |
| AES keys | protocol_reference.md § Cryptography | Link to it |
| ADC structure | protocol_reference.md § Data Structures | Link to it |
| Command table | protocol_reference.md § Commands | Link to it |
| USB descriptors | usb_transport.md | Link to it |
| Firmware addresses | firmware/handlers.md | Link to it |
| Mtools addresses | firmware/mtools_analysis.md | Link to it |

---

## Estimated Sizes

| File | Lines | Notes |
|------|-------|-------|
| README.md | 80 | Navigation |
| protocol_reference.md | 900 | Main consolidation |
| usb_transport.md | 340 | Mostly unchanged |
| features/authentication.md | 400 | Merge of 2 docs |
| features/adcqueue.md | 350 | Streamlined |
| features/offline_logs.md | 300 | Streamlined |
| features/pd_analysis.md | 180 | Mostly unchanged |
| firmware/README.md | 50 | Index |
| firmware/overview.md | 600 | From firmware_analysis.md |
| firmware/format.md | 260 | Unchanged |
| firmware/handlers.md | 400 | Device firmware |
| firmware/mtools_analysis.md | 500 | NEW - Windows app |
| research/unknown_commands.md | 200 | Bootloader etc |
| research/notes.md | 50 | Template |
| **Total** | ~4600 | vs current ~4500 |

---

## Ready to Proceed?

Once you approve this plan, I'll create the files in docs_new/ one by one, starting with the structure and README.md.
