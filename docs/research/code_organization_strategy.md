# Code Organization Strategy

How to separate production tools from research/experiments.

## Directory Roles

- `km003c_analysis/`: production library + tools (CLI, error handling, exports).
- `scripts/`: research workflows and exports that may change frequently.
- `scripts/experiments/`: throwaway validation/tests; safe to delete when done.
- `notebooks/`: manual exploration only (no .py files).

### Layout (reference)

```
km003c_analysis/            # 🏭 production
├── tools/                  # CLI tools (export, analyzers)
├── core/                   # reusable parsing logic
├── dashboards/             # GUI apps
└── app.py                  # Streamlit entry

scripts/                    # 🔬 research
└── experiments/            # 🧪 temporary tests

notebooks/                  # 📓 exploration only
```

## Classification Criteria

- Production tool: feature-complete, argparse CLI/help, validation, exports (JSON/Parquet/CSV), documented usage, stable API, importable.
- Research script: evolving analysis or export workflow; may change frequently.
- Experiment: one-off validation; keep small and deletable.

Documentation expectations:
- Production → listed in README/CLAUDE with examples; has CLI help and docstring.
- Research → brief header description; may be mentioned in findings.
- Experiments → no main README entry; keep deletion criteria in-file if needed.

## Promotion Path (script → tool)

1. Add CLI (`argparse`) and validation.
2. Add exports (JSON/Parquet/CSV) and docs/examples.
3. Move into `km003c_analysis/tools/` and update README/CLAUDE.

## Current Production Tool

| Tool | Purpose | Status |
|------|---------|--------|
| `km003c_analysis/tools/pd_sqlite_analyzer.py` | SQLite PD export analysis | Ready (CLI, exports) |

## Current Research Scripts

- `scripts/parquet/analyze_km003c_protocol.py`
- `scripts/parquet/parse_pd_wrapped.py`
- `scripts/parquet/export_*.py`
- `scripts/parquet/summarize_pd_messages.py`

## Usage Examples

- Production: `uv run python -m km003c_analysis.tools.pd_sqlite_analyzer --help`
- Research: `uv run python scripts/parquet/analyze_km003c_protocol.py`
- Experiment: `uv run python scripts/experiments/test_new_feature.py`
