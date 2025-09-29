set shell := ["bash", "-uc"]

default:
    @echo "Available recipes:"
    @echo "  rust-ext   Build/install km003c_lib into the uv venv"
    @echo "  test       Run pytest"
    @echo "  app        Run the Streamlit protocol analyzer app"

# Build and install the Rust extension into the current uv-managed environment.
# Requires: `uv sync -E dev` so `maturin` is available, and Rust toolchain.
rust-ext:
    uv run maturin develop \
      --manifest-path /home/okhsunrog/code/rust/km003c-rs/km003c-lib/Cargo.toml \
      --features python

# Run test suite.
test:
    uv run pytest -q

# Lint code with ruff.
lint:
    uv run ruff check --output-format=github km003c_analysis scripts tests

# Format code with ruff.
format:
    uv run ruff format km003c_analysis scripts tests

# Run the Streamlit protocol analyzer app.
app:
    uv run streamlit run km003c_analysis/app.py

