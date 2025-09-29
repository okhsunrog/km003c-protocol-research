# Code Organization Strategy

## Distinguishing Between Temporary Scripts and Production Tools

### Directory Structure

```
km003c_analysis/                    # 🏭 PRODUCTION CODE
├── tools/                         # Production-ready analysis tools
│   └── pd_sqlite_analyzer.py      # Comprehensive SQLite PD analyzer
├── core/                          # Reusable library components
├── dashboards/                    # GUI applications
└── app.py                         # Main Streamlit application

scripts/                           # 🔬 RESEARCH SCRIPTS
├── analyze_km003c_protocol.py     # Research analysis workflows
├── export_*.py                    # Data export utilities
├── parse_*.py                     # Format-specific parsers
└── experiments/                   # Temporary validation/testing scripts
    ├── test_*.py                  # Validation scripts
    ├── validate_*.py              # API testing scripts
    └── extract_*.py               # One-off analysis scripts

notebooks/                         # 📓 MANUAL EXPLORATION
├── *.ipynb                        # Jupyter notebooks only
└── (no .py files)                # Keep clean for exploration
```

### Classification Criteria

#### Production Tools (`km003c_analysis/tools/`)
- ✅ **Feature-complete** with comprehensive functionality
- ✅ **CLI interface** with argument parsing and help
- ✅ **Error handling** and input validation
- ✅ **Export capabilities** (JSON, Parquet, CSV)
- ✅ **Documentation** with usage examples
- ✅ **Module imports** - can be imported as library components
- ✅ **Stable API** - unlikely to change frequently

**Example**: `pd_sqlite_analyzer.py`
- Complete PD analysis pipeline
- CLI with `--verbose`, `--export-json`, `--help`
- Production-ready error handling
- Comprehensive documentation

#### Research Scripts (`scripts/`)
- 🔬 **Analysis workflows** for specific research questions
- 🔬 **Data processing** pipelines for datasets
- 🔬 **Format parsers** for different data sources
- 🔬 **Export utilities** for specific formats
- 🔬 **May change frequently** as research evolves

**Example**: `analyze_km003c_protocol.py`
- Specific analysis of KM003C protocol
- Research-focused output
- May evolve with findings

#### Experimental Scripts (`scripts/experiments/`)
- 🧪 **Temporary validation** scripts
- 🧪 **API testing** and exploration
- 🧪 **One-off analysis** for specific questions
- 🧪 **Delete when no longer needed**

**Examples**: `test_source_capabilities_parsing.py`, `validate_request_parsing.py`
- Created to validate specific functionality
- Can be deleted once research questions are answered

### Migration Path

**From Script → Tool**:
1. Add comprehensive CLI with `argparse`
2. Add error handling and input validation
3. Add export capabilities
4. Add proper documentation
5. Move to `km003c_analysis/tools/`
6. Update `README.md` and `CLAUDE.md`

### Documentation Requirements

#### Production Tools
- ✅ Listed in `README.md` under "Production Tools"
- ✅ Listed in `CLAUDE.md` with usage examples
- ✅ Comprehensive docstring with examples
- ✅ CLI help text with examples

#### Research Scripts
- ✅ Listed in `README.md` under "Analysis Scripts"
- ✅ Brief description in file header
- ✅ May be mentioned in research findings

#### Experimental Scripts
- ❌ Not documented in main README
- ✅ May be mentioned in research notes
- ✅ Should have clear deletion criteria

### Current Production Tools

| Tool | Purpose | CLI | Export | Status |
|------|---------|-----|--------|---------|
| `pd_sqlite_analyzer.py` | SQLite PD export analysis | ✅ | JSON, Parquet | ✅ Ready |

### Current Research Scripts

| Script | Purpose | Status |
|--------|---------|---------|
| `analyze_km003c_protocol.py` | Complete KM003C protocol analysis | Active |
| `parse_pd_wrapped.py` | Wrapped PD format parser | Active |
| `export_*.py` | Various data export utilities | Active |
| `summarize_pd_messages.py` | PD message summarization | Active |

### Benefits of This Organization

1. **Clear Intent**: Easy to distinguish stable tools from evolving research
2. **User Experience**: Production tools have consistent CLI and documentation
3. **Maintenance**: Temporary scripts can be cleaned up without affecting tools
4. **Development**: Research can iterate quickly without breaking production
5. **Documentation**: Users know where to find stable, documented functionality

### Usage Patterns

```bash
# Production workflows - stable, documented
uv run python -m km003c_analysis.tools.pd_sqlite_analyzer --verbose

# Research workflows - may change
uv run python scripts/analyze_km003c_protocol.py

# Experiments - temporary
uv run python scripts/experiments/test_new_feature.py
```

This organization ensures clear separation between production-ready tools and evolving research code while maintaining development flexibility.