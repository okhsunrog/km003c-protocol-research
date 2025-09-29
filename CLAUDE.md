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
uv run pytest -q                    # Tests only
uv run mypy km003c_analysis/        # Type checking
uv run ruff check km003c_analysis   # Linting
uv run ruff format km003c_analysis  # Formatting
```

### Applications
```bash
just app     # Launch Streamlit web interface
```

## Architecture

### Core Components
- `rust_pcap_converter/` - PCAP to Parquet converter using tshark
- `km003c_analysis/` - Python analysis library with modular structure:
  - `core/` - USB transaction processing (splitter, tagger)
  - `parsers/` - Protocol parsers (PD SQLite, KM003C protocol, wrapped PD)
  - `exporters/` - Data export utilities (Parquet, analysis reports, summaries)
  - `dashboards/` - Streamlit web interfaces (main app, PD analysis dashboard)
  - `app.py` - Main entry point for Streamlit GUI
- `km003c_lib` - External Rust crate providing protocol parsing (built via maturin)
- `notebooks/` - Jupyter notebooks for manual data exploration

### Data Flow
1. Capture USB traffic as PCAP files
2. Convert to Parquet with 41 USB protocol fields extracted
3. Process into transactions and add semantic tags
4. Analyze via Streamlit web interface or specialized parsers

### Module Usage
```python
# Core transaction processing
from km003c_analysis.core import split_usb_transactions, tag_transactions

# Protocol parsing
from km003c_analysis.parsers import pd_sqlite, protocol, wrapped_pd

# Data export
from km003c_analysis.exporters import analysis, pd_messages, summary

# Launch main GUI
uv run python -m streamlit run km003c_analysis/app.py
```

## Development Notes

- External Rust crate must be built before running tests that import `km003c_lib`
- Master dataset: `data/processed/usb_master_dataset.parquet` (11,514 USB packets)
- Protocol documentation: `docs/protocol_specification.md`
- Ongoing research notes: `docs/protocol_research_findings_wip.md`
- PD SQLite export format: `docs/pd_sqlite_export_format.md`
- Use URB IDs to match Submit/Complete transaction pairs
