set shell := ["bash", "-uc"]

default:
    @echo "Available recipes:"
    @echo "  sync       Install locked dependencies, including km003c"
    @echo "  test       Run pytest"
    @echo "  check      Run formatting, lint, and tests"
    @echo "  app        Run the Streamlit protocol analyzer app"

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

# Run the same checks as CI.
check: format-check lint test

# Run the Streamlit protocol analyzer app.
app: sync
    uv run --locked streamlit run km003c_analysis/app.py
