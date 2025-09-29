"""KM003C Analysis Package.

A comprehensive analysis library for KM003C USB protocol analyzer data.
Supports parsing, analysis, and visualization of USB and PD protocol captures.
"""

__version__ = "0.1.0"

# Core USB transaction processing
from .core import (
    split_usb_transactions,
    tag_transactions,
    USBTransactionSplitter,
    TransactionSplitterConfig,
)

# Import submodules for easy access
from . import core
from . import parsers  
from . import exporters
from . import dashboards

__all__ = [
    # Core functions
    "split_usb_transactions",
    "tag_transactions", 
    "USBTransactionSplitter",
    "TransactionSplitterConfig",
    # Submodules
    "core",
    "parsers",
    "exporters", 
    "dashboards",
]
