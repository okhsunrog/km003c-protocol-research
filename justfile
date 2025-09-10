set shell := ["bash", "-uc"]

default:
    @echo "Available recipes:"
    @echo "  rust-ext   Build/install km003c_lib into the uv venv"
    @echo "  test       Run pytest"

# Build and install the Rust extension into the current uv-managed environment.
# Requires: `uv sync -E dev` so `maturin` is available, and Rust toolchain.
rust-ext:
    uv run maturin develop \
      --manifest-path /home/okhsunrog/code/rust/km003c-rs/km003c-lib/Cargo.toml \
      --features python

# Run test suite.
test:
    uv run pytest -q

