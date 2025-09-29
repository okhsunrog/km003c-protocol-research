# KM003C Protocol Research - Major Breakthroughs

## ✅ Research Complete: KM003C Protocol Fully Decoded

**Status**: All major research objectives achieved with production-ready analysis tools.

### Key Achievements

1. **Complete Protocol Specification** → [`km003c_protocol_specification.md`](km003c_protocol_specification.md)
2. **USB Capture ↔ SQLite Correlation** → Perfect data correlation validated
3. **Production Analysis Tools** → Ready for operational use

---

## USB Capture to SQLite Correlation - ✅ COMPLETE

**VALIDATED: KM003C Protocol PD Message Embedding**

Successfully extracted PD messages from USB capture data (`pd_capture_new.9`) and validated perfect correlation with SQLite export findings:

### Protocol Correlation Results
- **Source_Capabilities Match**: Exact wire hex match between USB capture and SQLite
  - Wire hex: `a1612c9101082cd102002cc103002cb10400454106003c21dcc0`
  - Contains 6 PDOs: 5V/3A (15W), 9V/3A (27W), 12V/3A (36W), 15V/3A (45W), 20V/3.25A (65W), PPS 3.3-11V/3A
- **Complete Negotiation Sequence**: USB capture contains same power negotiation as SQLite
  - Source_Capabilities → Request (`8210dc700323`) → Accept (`a305`) → PS_RDY (`a607`)
- **15 PD Messages Extracted**: Successfully parsed from USB capture using dual approach (pattern matching + wrapped events)

### KM003C Protocol Format Confirmed
- **PD Embedding**: PD messages embedded in KM003C PutData packets (msg_type=65, attribute=16)
- **Payload Classification**: 12-byte payloads = KM003C status data, 18-108 byte payloads = wrapped PD events
- **Wrapped Format**: Same event structure as SQLite (6-byte headers + PD wire data)
- **Pattern Recognition**: Known PD wire patterns reliably identified in larger payloads

---

## SQLite PD Export Analysis - ✅ SOLVED

**BREAKTHROUGH**: KM003C SQLite BLOB format successfully decoded with complete PD message extraction.

### KM003C SQLite Format Findings
- **BLOB Structure**: Wrapped event format with 0x45 (status) and 0x80-0x9F (PD message) event types
- **Message Extraction**: 26-byte PD wire messages successfully extracted from KM003C BLOB events
- **Parsing Success**: 11 PD messages parsed from 13 SQLite events (usbpdpy v0.2.0)
- **Voltage Correlation**: KM003C ADC measurements correlate with PD negotiation voltage changes

### KM003C-Specific Protocol Details
- **Event Headers**: 6-byte format (size_flag, timestamp[4], sop[1]) + PD wire data
- **Timestamp Format**: 32-bit little-endian microsecond timestamps
- **Size Encoding**: `size_flag & 0x3F` gives total size, subtract 5 for wire length
- **Voltage Tracking**: Real-time correlation between negotiated PD voltages and ADC measurements

---

## KM003C Protocol Structure Summary

### Message Architecture
```
┌─────────────────┬─────────────────┬──────────────────┐
│  Main Header    │ Extended Header │     Payload      │
│    (4 bytes)    │    (4 bytes)    │   (variable)     │
└─────────────────┴─────────────────┴──────────────────┘
```

### Request/Response Patterns
| Request      | Response Type | Size    | Description           |
|--------------|---------------|---------|----------------------|
| `0C xx 02 00`| ADC only      | 52B     | ADC measurements only |
| `0C xx 22 00`| ADC+PD        | 68B     | ADC + PD status      |
| `0C xx 20 00`| PD only       | 20+B    | PD data/events       |

### Chained Payload System
- **Main Payload**: ADC measurements (44 bytes) or PD data (12+ bytes)
- **Chained Payload**: Additional data linked via `next=1` flag in Extended Header
- **ADC+PD Example**: ADC payload (44B) + PD status payload (12B) = 68B total

### PD Message Integration
- **Status Data**: 12-byte KM003C measurement summaries
- **Event Data**: 18-108 byte wrapped USB PD protocol messages
- **Wire Messages**: Extractable standard USB PD messages (Source_Capabilities, Request, Accept, etc.)

---

## Production Analysis Tools

### Primary Tools
- **[`km003c_analysis.tools.pd_sqlite_analyzer`](../km003c_analysis/tools/pd_sqlite_analyzer.py)**
  - Complete SQLite PD export analysis
  - Power negotiation tracking and export
  - JSON/Parquet output formats

### Validation Scripts
- **[`scripts/extract_pd_from_usb_capture.py`](../scripts/extract_pd_from_usb_capture.py)**
  - USB capture PD message extraction
  - Correlation validation with SQLite exports

- **[`validate_hex_samples.py`](../validate_hex_samples.py)**
  - Protocol format validation
  - Hex sample parsing verification

### Core Library
- **[`km003c_analysis`](../km003c_analysis/)** - Complete analysis library
  - USB transaction processing (`core/`)
  - Protocol parsers (`parsers/`)
  - Data exporters (`exporters/`)
  - Streamlit dashboards (`dashboards/`)

---

## Research Impact

### Technical Achievements
1. **Complete Protocol Reverse Engineering**: From unknown binary format to full specification
2. **Cross-Format Correlation**: Validated consistency between USB captures and SQLite exports
3. **Production-Ready Tools**: Operational analysis pipeline for KM003C data processing
4. **USB PD Integration**: Successfully integrated standard USB PD protocol parsing

### Documentation Delivered
- **[Protocol Specification](km003c_protocol_specification.md)**: Complete technical specification
- **[Code Organization Strategy](code_organization_strategy.md)**: Development methodology
- **Analysis Tools**: Production-ready codebase with comprehensive tooling

### External Dependencies
- **[usbpdpy v0.2.0](https://pypi.org/project/usbpdpy/)**: USB PD protocol parsing library
- **KM003C Rust Library**: Low-level protocol parsing extensions

---

*Research completed with full protocol understanding and production-ready analysis tools. All objectives achieved.*