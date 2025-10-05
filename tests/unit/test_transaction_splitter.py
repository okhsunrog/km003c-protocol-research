import pytest
import polars as pl
from pathlib import Path
import sys
from typing import List, Tuple

# Add project root to path to allow direct import of the package
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from km003c_analysis.core.usb_transaction_splitter import split_usb_transactions

# Mark all tests in this module as unit tests
pytestmark = pytest.mark.unit

PROJECT_ROOT = Path(__file__).parent.parent.parent
DATASET_PATH = PROJECT_ROOT / "data/processed/usb_master_dataset.parquet"


@pytest.fixture(scope="module")
def master_df() -> pl.DataFrame:
    """Fixture to load the master dataset for testing."""
    if not DATASET_PATH.exists():
        pytest.fail(f"Master dataset not found at {DATASET_PATH}")
    return pl.read_parquet(DATASET_PATH)


@pytest.fixture(scope="module")
def source_dataframes(master_df) -> List[Tuple[str, pl.DataFrame]]:
    """Fixture to split the master dataset by source file."""
    source_files = master_df["source_file"].unique().sort()
    return [
        (source_file, master_df.filter(pl.col("source_file") == source_file))
        for source_file in source_files
    ]


def test_splitter_runs_without_error(master_df):
    """Ensures the transaction splitter runs to completion without raising exceptions."""
    try:
        result_df = split_usb_transactions(master_df)
        assert isinstance(result_df, pl.DataFrame)
        assert "transaction_id" in result_df.columns
    except Exception as e:
        pytest.fail(f"split_usb_transactions raised an unexpected exception: {e}")


def test_splitter_runs_per_source(source_dataframes):
    """Ensures the transaction splitter runs on each source file without errors."""
    for source_file, source_df in source_dataframes:
        try:
            result_df = split_usb_transactions(source_df)
            assert isinstance(result_df, pl.DataFrame)
            assert "transaction_id" in result_df.columns
        except Exception as e:
            pytest.fail(f"split_usb_transactions failed on {source_file}: {e}")


def test_splitter_preserves_data_integrity_and_order(master_df):
    """
    Verifies that the splitter only adds a 'transaction_id' column and does
    not alter the original data or its order.
    """
    # 1. Run the splitter
    result_df = split_usb_transactions(master_df)

    # 2. Verify row count is unchanged
    assert master_df.height == result_df.height, (
        "Row count should not be changed by the splitter."
    )

    # 3. Verify original columns are preserved in the same order
    original_cols = master_df.columns
    result_cols_without_tid = [
        col for col in result_df.columns if col != "transaction_id"
    ]
    assert original_cols == result_cols_without_tid, (
        "Original columns and their order should be preserved."
    )

    # Sort the original DataFrame the same way the splitter does for a valid comparison
    sorted_master_df = master_df.sort("frame_number")

    # 4. Verify the actual data in the original columns is unchanged
    assert sorted_master_df.equals(result_df.select(original_cols)), (
        "Original data values should not be modified."
    )


def test_splitter_preserves_data_per_source(source_dataframes):
    """
    Verifies data integrity for each source file independently.
    """
    for source_file, source_df in source_dataframes:
        # 1. Run the splitter
        result_df = split_usb_transactions(source_df)

        # 2. Verify row count is unchanged
        assert source_df.height == result_df.height, (
            f"Row count changed for {source_file}"
        )

        # 3. Verify original columns are preserved
        original_cols = source_df.columns
        result_cols_without_tid = [
            col for col in result_df.columns if col != "transaction_id"
        ]
        assert original_cols == result_cols_without_tid, (
            f"Columns changed for {source_file}"
        )

        # Sort the original DataFrame the same way the splitter does
        sorted_source_df = source_df.sort("frame_number")

        # 4. Verify the actual data is unchanged
        assert sorted_source_df.equals(result_df.select(original_cols)), (
            f"Data modified for {source_file}"
        )


def test_splitter_creates_valid_transactions(master_df):
    """
    Checks that the splitter creates a 'transaction_id' column with expected properties.
    """
    result_df = split_usb_transactions(master_df)

    # Check that the transaction_id column exists
    assert "transaction_id" in result_df.columns

    # Check that there is more than one transaction created for the master dataset
    num_transactions = result_df["transaction_id"].n_unique()
    assert num_transactions > 1, (
        "Splitter should create multiple transactions for this dataset."
    )

    # Check that transaction IDs are integers, as expected
    assert result_df["transaction_id"].dtype == pl.Int64


def test_splitter_creates_valid_transactions_per_source(source_dataframes):
    """
    Checks transaction creation for each source file independently.
    """
    for source_file, source_df in source_dataframes:
        # Skip very small files that might only have one transaction
        if source_df.height < 10:
            continue

        result_df = split_usb_transactions(source_df)

        # Check that the transaction_id column exists
        assert "transaction_id" in result_df.columns, (
            f"No transaction_id for {source_file}"
        )

        # Check that transactions are created
        num_transactions = result_df["transaction_id"].n_unique()
        assert num_transactions >= 1, f"No transactions created for {source_file}"

        # Check that transaction IDs are integers
        assert result_df["transaction_id"].dtype == pl.Int64, (
            f"Wrong dtype for {source_file}"
        )
