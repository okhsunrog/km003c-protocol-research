# CLAUDE.md

Development guidance for the KM003C protocol research project.

## Environment Setup

```bash
# Install dependencies
uv sync

# Install development dependencies (includes maturin)
uv sync -E dev

# Build Rust Python extension
just rust-ext
```

## Development Commands

### Testing and Quality
```bash
# Run all checks
just test     # Run test suite
just lint     # Lint code with ruff
just format   # Format code with ruff

# Individual commands
uv run pytest -q                          # Tests only
uv run mypy km003c_analysis/              # Type checking
uv run ruff check km003c_analysis scripts # Linting
uv run ruff format km003c_analysis scripts # Formatting
```

### Applications
```bash
just app     # Launch Streamlit web interface
```

## Architecture

### Core Components
- `rust_pcap_converter/` - PCAP to Parquet converter using tshark
- `km003c_analysis/` - Python analysis library (reusable components):
  - `core/` - USB transaction processing (splitter, tagger)
  - `tools/` - Production-ready analysis tools
    - `pd_sqlite_analyzer.py` - Comprehensive SQLite PD export analyzer
  - `dashboards/` - Streamlit web interfaces (main app, PD analysis dashboard)
  - `app.py` - Main entry point for Streamlit GUI
- `scripts/` - Research analysis scripts:
  - `analyze_km003c_protocol.py` - Complete KM003C protocol analysis
  - `parse_pd_wrapped.py` - Wrapped PD format parser
  - `export_*.py` - Data export utilities
  - `summarize_pd_messages.py` - PD message summarization
  - `experiments/` - Temporary validation and testing scripts
- `km003c_lib` - External Rust crate providing protocol parsing (built via maturin)
- `notebooks/` - Jupyter notebooks for manual data exploration

### Data Flow
1. Capture USB traffic as PCAP files
2. Convert to Parquet with 41 USB protocol fields extracted
3. Process into transactions and add semantic tags
4. Analyze via Streamlit web interface or run analysis scripts

### Module Usage
```python
# Core transaction processing (reusable library)
from km003c_analysis.core import split_usb_transactions, tag_transactions

# Production tools
from km003c_analysis.tools.pd_sqlite_analyzer import SQLitePDAnalyzer

# Launch main GUI
uv run python -m streamlit run km003c_analysis/app.py

# Run production tools
uv run python -m km003c_analysis.tools.pd_sqlite_analyzer --verbose
uv run python -m km003c_analysis.tools.pd_sqlite_analyzer --export-json results.json

# Run analysis scripts
uv run python scripts/analyze_km003c_protocol.py
uv run python scripts/export_complete_pd_analysis.py
```

## Development Notes

- External Rust crate must be built before running tests that import `km003c_lib`
- Master dataset: `data/processed/usb_master_dataset.parquet` (11,514 USB packets)
- **Protocol specification**: `docs/km003c_protocol_specification.md` - Complete KM003C protocol format
- Research summary: `docs/protocol_research_findings_wip.md` - Major breakthroughs achieved
- Code organization: `docs/code_organization_strategy.md` - Development methodology
- Use URB IDs to match Submit/Complete transaction pairs

## Research Status

✅ **KM003C Protocol Fully Decoded**: Complete specification with production-ready analysis tools
✅ **USB ↔ SQLite Correlation**: Perfect data correlation validated between capture formats
✅ **PD Message Integration**: Full USB PD protocol parsing with usbpdpy v0.2.0
