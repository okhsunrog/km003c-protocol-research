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
- `km003c_analysis/` - Python analysis library with transaction processing
- `km003c_lib` - External Rust crate providing protocol parsing (built via maturin)

### Data Flow
1. Capture USB traffic as PCAP files
2. Convert to Parquet with 41 USB protocol fields extracted
3. Process into transactions and add semantic tags
4. Analyze via Streamlit web interface

## Development Notes

- External Rust crate must be built before running tests that import `km003c_lib`
- Master dataset: `data/processed/usb_master_dataset.parquet` (11,514 USB packets)
- Protocol documentation: `docs/protocol_specification.md`
- Ongoing research notes: `docs/protocol_research_findings_wip.md`
- Use URB IDs to match Submit/Complete transaction pairs
