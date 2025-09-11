# USB Transaction Splitter

A modular library for splitting USB frame data into logical transactions based on URB patterns and bulk transfer sequences.

## Overview

This library provides intelligent grouping of USB frames into logical transactions, particularly optimized for bulk transfer command-response cycles. It separates USB enumeration, control transfers, and bulk operations into meaningful transaction boundaries.

## Architecture

### 🏗️ **Modular Design**

```
📁 Project Structure
├── usb_transaction_splitter.py     # 📚 Core library (format-agnostic)
├── split_usb_transactions_jsonl.py # 🔧 JSONL command-line tool  
├── example_usage.py                # 📖 Usage examples
└── README_transaction_splitter.md  # 📋 This documentation
```

### 🎯 **Key Features**

- **Format-agnostic**: Works with any Polars DataFrame
- **Configurable**: Custom column names and behavior
- **Validated**: Built-in ordering and integrity checks
- **Extensible**: Easy to adapt for different USB protocols

## Core Library (`usb_transaction_splitter.py`)

### Quick Start

```python
import polars as pl
from usb_transaction_splitter import split_usb_transactions

# Load your USB data into a Polars DataFrame
df = pl.read_parquet("usb_data.parquet")

# Split into transactions (adds/updates 'transaction_id' column)
df_with_transactions = split_usb_transactions(df)

print(f"Split into {df_with_transactions['transaction_id'].max()} transactions")
```

### Advanced Usage

```python
from usb_transaction_splitter import USBTransactionSplitter, TransactionSplitterConfig

# Custom configuration for different column names
config = TransactionSplitterConfig(
    frame_number_col="frame_id",
    urb_id_col="request_id",
    transaction_id_col="group_id"
)

# Create splitter with detailed control
splitter = USBTransactionSplitter(config)
df_result = splitter.split_transactions(df)

# Validate results
validation = splitter.validate_output(df_result)
stats = splitter.get_transaction_stats(df_result)
```

### Required DataFrame Columns

| Column | Default Name | Description |
|--------|--------------|-------------|
| Frame Number | `frame_number` | Sequential frame identifier |
| Transfer Type | `transfer_type` | USB transfer type (e.g., "0x02", "0x03") |
| Endpoint | `endpoint_address` | USB endpoint (e.g., "0x01", "0x81") |
| URB Type | `urb_type` | Submit ("S") or Complete ("C") |
| URB ID | `urb_id` | Unique request identifier |
| URB Status | `urb_status` | Status code (optional) |
| Data Length | `data_length` | Payload size in bytes (optional) |

## Command-Line Tool (`split_usb_transactions_jsonl.py`)

### Usage

```bash
# Basic usage
python split_usb_transactions_jsonl.py input.jsonl output.jsonl

# Verbose output with analysis
python split_usb_transactions_jsonl.py input.jsonl output.jsonl --verbose

# Skip validation for faster processing
python split_usb_transactions_jsonl.py input.jsonl output.jsonl --no-validate
```

### Features

- ✅ **Validation**: Checks frame/timestamp/transaction ordering
- 📊 **Statistics**: Transaction count, size distribution
- 🔍 **Analysis**: Bulk sequence pattern detection
- ⚙️ **Configuration**: Custom column mapping via JSON config

## Transaction Logic

### 🔄 **Transaction Boundaries**

The library identifies logical transaction boundaries using:

1. **New URB IDs**: Each new USB request starts a potential transaction
2. **Bulk Command Patterns**: Command-response cycles are grouped together
3. **Special Frame Rules**:
   - **Bulk Setup** frames go to previous transaction
   - **Cancellation** frames go to previous transaction

### 📋 **Typical Transaction Patterns**

**Control Transfer (2 frames):**
```
Frame N: Submit (S) → Frame N+1: Complete (C)
```

**Bulk Command-Response (4+ frames):**
```
Frame N: Command (0x01 S) → Frame N+1: ACK (0x01 C) 
→ Frame N+2: Data Response (0x81 C) → Frame N+3: Setup (0x81 S)
```

**Multi-frame Response (7+ frames):**
```
Command → ACK → Data Part 1 → Setup → Data Part 2 → Setup → ...
```

## Examples

See `example_usage.py` for comprehensive examples:

- Basic JSONL processing
- Custom column names
- Detailed analysis and validation  
- Multiple file format support
- Large dataset processing concepts

## Validation

The library ensures all output maintains proper ordering:

- ✅ **Frame numbers**: Ascending order preserved
- ✅ **Timestamps**: Chronological order maintained
- ✅ **Transaction IDs**: Monotonically increasing

## Performance

- **Memory Efficient**: Uses Polars for fast DataFrame operations
- **Scalable**: Handles large datasets efficiently
- **Configurable**: Skip validation for maximum speed

## Extending the Library

To support different USB protocols:

1. **Subclass** `USBTransactionSplitter`
2. **Override** pattern detection methods (`is_bulk_setup`, etc.)
3. **Customize** transaction boundary logic (`should_start_new_transaction`)

```python
class CustomUSBSplitter(USBTransactionSplitter):
    def is_bulk_command_start(self, frame):
        # Custom logic for your protocol
        return custom_detection_logic(frame)
```

## Migration from Original Script

If migrating from `split_transactions_grouped.py`:

```python
# Old approach
from split_transactions_grouped import USBTransactionSplitterGrouped
splitter = USBTransactionSplitterGrouped()

# New approach  
from usb_transaction_splitter import USBTransactionSplitter
splitter = USBTransactionSplitter()
```

The API is compatible, and results are identical.

---

## 🚀 **Getting Started**

1. **Library Usage**: Import `usb_transaction_splitter` and call `split_usb_transactions(df)`
2. **Command Line**: Run `python split_usb_transactions_jsonl.py input.jsonl output.jsonl`
3. **Examples**: Check `example_usage.py` for various use cases

**Perfect for**: USB protocol analysis, device debugging, transaction pattern recognition, and data preprocessing pipelines.