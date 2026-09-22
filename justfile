set shell := ["bash", "-uc"]

default:
    @echo "Available recipes:"
    @echo "  sync        Install locked dependencies, including km003c"
    @echo "  test        Run pytest"
    @echo "  typecheck   Run mypy over the analysis package"
    @echo "  converter   Build and lint the pcapng to Parquet converter"
    @echo "  docs-check  Lint Markdown and verify local links"
    @echo "  check       Run formatting, lint, types, docs, converter, and tests"
    @echo "  app         Run the Streamlit protocol analyzer app"

# Install the exact dependency set from uv.lock. The pinned km003c git source
# is built by maturin as part of the normal uv sync.
sync:
    uv sync --locked

# Run test suite.
test: sync
    uv run --locked pytest -q

# Lint code with ruff.
lint: sync
    uv run --locked ruff check km003c_analysis scripts tests

# Format code with ruff.
format: sync
    uv run --locked ruff format km003c_analysis scripts tests

# Check formatting without changing files.
format-check: sync
    uv run --locked ruff format --check km003c_analysis scripts tests

# Enforce the strict mypy configuration in pyproject.toml.
typecheck: sync
    uv run --locked mypy km003c_analysis

# The pcapng to Parquet converter produces the master dataset, so a build
# failure there silently rots the input to every other tool in this repo.
converter:
    cargo fmt --manifest-path rust_pcap_converter/Cargo.toml -- --check
    cargo clippy --manifest-path rust_pcap_converter/Cargo.toml --locked -- -D warnings
    cargo build --manifest-path rust_pcap_converter/Cargo.toml --locked

# Lint Markdown and verify repository-local link targets.
docs-check: sync
    uv run --locked rumdl check README.md docs tests/README.md
    uv run --locked python scripts/check_markdown_links.py

# Run the same checks as CI.
check: format-check lint typecheck docs-check converter test

# Run the Streamlit protocol analyzer app.
app: sync
    uv run --locked streamlit run km003c_analysis/app.py
