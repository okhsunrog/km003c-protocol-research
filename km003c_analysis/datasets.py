"""Locations of the capture datasets shipped with this repository.

Fifteen scripts and tests used to spell out
``data/processed/usb_master_dataset.parquet`` relative to their own location.
Resolving it once here means a moved or renamed dataset is a one-line change,
and callers get a clear error instead of a Polars file-not-found trace.
"""

from pathlib import Path

import polars as pl

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
PROCESSED_DIR = DATA_DIR / "processed"
RAW_DIR = DATA_DIR / "raw"
SQLITE_DIR = DATA_DIR / "sqlite"

#: Every USB frame captured across all sessions, one row per frame.
MASTER_DATASET = PROCESSED_DIR / "usb_master_dataset.parquet"


def master_dataset_path() -> Path:
    """Path of the master capture dataset.

    Raises:
        FileNotFoundError: If the dataset has not been generated yet.
    """
    if not MASTER_DATASET.exists():
        raise FileNotFoundError(
            f"Master dataset not found at {MASTER_DATASET}. "
            "Generate it with rust_pcap_converter, or check out the file from git."
        )
    return MASTER_DATASET


def load_master_dataset() -> pl.DataFrame:
    """Read the master capture dataset."""
    return pl.read_parquet(master_dataset_path())
