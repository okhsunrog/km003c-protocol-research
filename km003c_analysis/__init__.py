"""KM003C Analysis Package.

A comprehensive analysis library for KM003C USB protocol analyzer data.
Supports parsing, analysis, and visualization of USB and PD protocol captures.
"""

__version__ = "0.1.0"

# Only the parsing core is imported eagerly. `dashboards` pulls in Streamlit,
# Plotly and pandas, which has no business loading when a script just wants to
# split transactions, so it is resolved on first attribute access instead.
from . import core, datasets
from .core import (
    TransactionSplitterConfig,
    USBTransactionSplitter,
    split_usb_transactions,
    tag_transactions,
)

__all__ = [
    # Core functions
    "split_usb_transactions",
    "tag_transactions",
    "USBTransactionSplitter",
    "TransactionSplitterConfig",
    # Submodules
    "core",
    "datasets",
    "dashboards",
    "device",
    "tools",
]

_LAZY_SUBMODULES = frozenset({"dashboards", "device", "tools"})


def __getattr__(name: str) -> object:
    """Import the heavier submodules only when they are first used."""
    if name in _LAZY_SUBMODULES:
        import importlib

        module = importlib.import_module(f"{__name__}.{name}")
        globals()[name] = module
        return module
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(__all__)
