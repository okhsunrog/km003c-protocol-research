# Test Organization

Tests are separated into unit and integration tests for efficient development workflow.

## Test Structure

```text
tests/
├── unit/              # Fast tests, no hardware required
│   ├── test_packet_parsing.py       # km003c_lib parsing (ADC, AdcQueue, PD)
│   ├── test_pd_parsing.py           # USB PD messages from captured traffic
│   ├── test_raw_packet.py            # Low-level protocol structures
│   ├── test_app_entrypoint.py         # Streamlit application entry point
│   ├── test_transaction_splitter.py  # USB transaction grouping
│   └── test_transaction_tagger.py    # Transaction pattern tagging
│
└── integration/       # Slow tests, require real KM003C device
    └── test_integration_device.py    # Device communication and protocol validation
```

## Running Tests

### Unit Tests (Default - Fast, No Hardware)

```bash
# Run all unit tests (default)
uv run --locked pytest

# Or explicitly
uv run --locked pytest -m unit

# Or by directory
uv run --locked pytest tests/unit/

# Quick mode
uv run --locked pytest -m unit -q
```

**Run time:** ~30-40 seconds  
**Requirements:** Dataset file, no hardware

### Integration Tests (Requires Device)

```bash
# Run all integration tests
uv run --locked pytest -m integration -v -s

# Or by directory
uv run --locked pytest tests/integration/ -v -s
```

**Run time:** ~10-20 seconds  
**Requirements:** Real KM003C device connected via USB

### All Tests (Unit + Integration)

```bash
# Run everything
uv run --locked pytest -m "unit or integration"

# Or without markers
uv run --locked pytest tests/ --override-ini="addopts="
```

## What Each Suite Tests

### Unit Tests (48 tests)

- ✅ Transaction splitter logic (7 tests)
- ✅ Transaction tagger patterns (8 tests)  
- ✅ Packet and PD parsing with km003c_lib (24 tests, including 4 capture-dependent cases)
- ✅ Raw packet protocol structures and rate encoding (8 tests)
- ✅ Streamlit entry point (1 test)
- ✅ Validates against 20,862-packet dataset

### Integration Tests (8 tests)

- ✅ Device discovery and connection
- ✅ Basic commands (Connect, GetData ADC)
- ✅ Start/Stop Graph commands
- ✅ km003c_lib bindings on real responses
- ✅ Authenticated AdcQueue streaming, including responses larger than 1024 bytes

## CI/CD Configuration

The default `pytest` command runs only unit tests (fast, no hardware).  
This is configured in `pyproject.toml`:

```toml
[tool.pytest.ini_options]
addopts = "-v -m unit"  # Default: unit tests only
```

For CI/CD pipelines, use:

```bash
uv run --locked pytest -m unit
```

## Markers

Tests are marked with:

- `@pytest.mark.unit` - No hardware required
- `@pytest.mark.integration` - Requires device

These markers are registered in `pyproject.toml`.
