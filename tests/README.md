# Test Organization

Tests are separated into unit and integration tests for efficient development workflow.

## Test Structure

```
tests/
├── unit/              # Fast tests, no hardware required
│   ├── test_packet_parsing.py       # km003c_lib parsing (ADC, AdcQueue, PD)
│   ├── test_raw_packet.py            # Low-level protocol structures
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
uv run pytest

# Or explicitly
uv run pytest -m unit

# Or by directory
uv run pytest tests/unit/

# Quick mode
uv run pytest -m unit -q
```

**Run time:** ~30-40 seconds  
**Requirements:** Dataset file, no hardware

### Integration Tests (Requires Device)

```bash
# Run all integration tests
uv run pytest -m integration -v -s

# Or by directory
uv run pytest tests/integration/ -v -s
```

**Run time:** ~10-20 seconds  
**Requirements:** Real KM003C device connected via USB

### All Tests (Unit + Integration)

```bash
# Run everything
uv run pytest -m "unit or integration"

# Or without markers
pytest tests/ --override-ini="addopts="
```

## What Each Suite Tests

### Unit Tests (33 tests)
- ✅ Transaction splitter logic (6 tests)
- ✅ Transaction tagger patterns (8 tests)  
- ✅ Packet parsing with km003c_lib (15 tests)
- ✅ Raw packet protocol structures (4 tests)
- ✅ Validates against 20,862-packet dataset

### Integration Tests (7 tests)
- ✅ Device discovery and connection
- ✅ Basic commands (Connect, GetData ADC)
- ✅ Start/Stop Graph commands
- ✅ km003c_lib bindings on real responses
- ⚠️ AdcQueue streaming (xfail - use `scripts/test_adcqueue.py` instead)

## CI/CD Configuration

The default `pytest` command runs only unit tests (fast, no hardware).  
This is configured in `pyproject.toml`:

```toml
[tool.pytest.ini_options]
addopts = "-v -m unit"  # Default: unit tests only
```

For CI/CD pipelines, use:
```bash
uv run pytest -m unit
```

## Markers

Tests are marked with:
- `@pytest.mark.unit` - No hardware required
- `@pytest.mark.integration` - Requires device

These markers are registered in `pyproject.toml`.
