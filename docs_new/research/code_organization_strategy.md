# Code Organization Strategy

How to separate production tools from research/experiments.

## Directory Roles

- `km003c_analysis/`: production library + tools (CLI, error handling, exports).
- `scripts/`: research workflows and exports that may change frequently.
- `scripts/experiments/`: throwaway validation/tests; safe to delete when done.
- `notebooks/`: manual exploration only (no .py files).

## Promotion Path (script → tool)

1. Add CLI (`argparse`) and validation.
2. Add exports (JSON/Parquet/CSV) and docs/examples.
3. Move into `km003c_analysis/tools/` and update README/CLAUDE.

## Current Production Tool

| Tool | Purpose | Status |
|------|---------|--------|
| `km003c_analysis/tools/pd_sqlite_analyzer.py` | SQLite PD export analysis | Ready (CLI, exports) |

## Current Research Scripts

- `scripts/analyze_km003c_protocol.py`
- `scripts/parse_pd_wrapped.py`
- `scripts/export_*.py`
- `scripts/summarize_pd_messages.py`

## Usage Examples

- Production: `uv run python -m km003c_analysis.tools.pd_sqlite_analyzer --help`
- Research: `uv run python scripts/analyze_km003c_protocol.py`
- Experiment: `uv run python scripts/experiments/test_new_feature.py`
