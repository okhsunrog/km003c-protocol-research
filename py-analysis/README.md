# USB PD Analysis with usbpdpy

Python analysis project demonstrating usage of the `usbpdpy` package for USB Power Delivery message analysis.

## Setup

```bash
# Install dependencies
uv sync --index-strategy unsafe-best-match

# Install usbpdpy from TestPyPI
source .venv/bin/activate
uv pip install --index-url https://test.pypi.org/simple/ usbpdpy
```

## Usage

### Jupyter Notebook
```bash
source .venv/bin/activate
jupyter notebook usbpdpy_examples.ipynb
```

### Python Scripts
```python
import usbpdpy

# Parse USB PD message
msg = usbpdpy.parse_pd_message(usbpdpy.hex_to_bytes("1161"))
print(f"Type: {usbpdpy.get_message_type_name(msg.header.message_type)}")
```

## Features

- **Basic message parsing** from hex strings
- **Batch processing** of multiple messages
- **Data analysis** with pandas
- **Visualization** with matplotlib/seaborn
- **Error handling** examples
- **Performance** demonstrations

## Dependencies

- `usbpdpy` - Fast USB PD message parsing
- `jupyter` - Interactive notebooks
- `pandas` - Data analysis
- `matplotlib` - Plotting
- `seaborn` - Statistical visualization
