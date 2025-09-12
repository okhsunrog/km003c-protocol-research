import pytest
import polars as pl
from pathlib import Path
import sys

# Add project root to path to allow direct import of the package
sys.path.insert(0, str(Path(__file__).parent.parent))

from km003c_analysis.usb_transaction_splitter import split_usb_transactions
from km003c_analysis.transaction_tagger import tag_transactions

PROJECT_ROOT = Path(__file__).parent.parent
DATASET_PATH = PROJECT_ROOT / "data/processed/usb_master_dataset.parquet"

@pytest.fixture(scope="module")
def tagged_df() -> pl.DataFrame:
    """Fixture to load, split, and tag the master dataset for testing."""
    if not DATASET_PATH.exists():
        pytest.fail(f"Master dataset not found at {DATASET_PATH}")
    
    df = pl.read_parquet(DATASET_PATH)
    df_split = split_usb_transactions(df)
    return tag_transactions(df_split)

def test_tagger_adds_tags_column(tagged_df):
    """Ensures the tagger adds a 'tags' column of the correct list type."""
    assert "tags" in tagged_df.columns
    assert isinstance(tagged_df["tags"].dtype, pl.List), "Tags column should be a list type."

def test_tagger_identifies_control_only(tagged_df):
    """Verify that a known CONTROL_ONLY transaction is tagged correctly."""
    # Find a transaction that should be CONTROL_ONLY (e.g., the very first one)
    first_tid = tagged_df.sort("timestamp")["transaction_id"][0]
    first_transaction_frames = tagged_df.filter(pl.col("transaction_id") == first_tid)
    
    # Verify the underlying data is what we expect
    assert (first_transaction_frames["transfer_type"] == "0x02").all()
    
    # Verify the tag is correctly applied
    tags = first_transaction_frames["tags"][0]
    assert "CONTROL_ONLY" in tags
    assert "BULK_ONLY" not in tags, "Should not be tagged as BULK_ONLY."

def test_tagger_identifies_bulk_command_response(tagged_df):
    """Verify that BULK_COMMAND_RESPONSE transactions are tagged correctly."""
    # Find transactions that have been tagged with BULK_COMMAND_RESPONSE
    candidate_transactions = tagged_df.filter(
        pl.col("tags").list.contains("BULK_COMMAND_RESPONSE")
    )
    assert not candidate_transactions.is_empty(), "No BULK_COMMAND_RESPONSE transactions were found."
    
    # Verify the structure of the first candidate transaction
    test_tid = candidate_transactions["transaction_id"][0]
    test_group = tagged_df.filter(pl.col("transaction_id") == test_tid)
    
    # Check for the defining pattern: 1 outgoing request, 1 incoming response
    out_requests = test_group.filter(
        (pl.col("endpoint_address") == "0x01") & (pl.col("urb_type") == "S")
    ).height
    in_responses = test_group.filter(
        (pl.col("endpoint_address") == "0x81") & (pl.col("urb_type") == "C")
    ).height
        
    # The simple pattern is one of each, but the splitter might group the ACK too.
    # The key is a single incoming response.
    assert out_requests >= 1
    assert in_responses == 1

def test_tagger_identifies_enumeration(tagged_df):
    """Verify that a known ENUMERATION transaction is tagged correctly."""
    # Find a standard enumeration transaction, e.g., 'Get Descriptor'
    enumeration_transaction = tagged_df.filter(
        pl.col("bRequest_name") == "Get Descriptor"
    )
    assert not enumeration_transaction.is_empty(), "Could not find a 'Get Descriptor' transaction to test."
    
    # Check the tags of the first one found
    tags = enumeration_transaction["tags"][0]
    assert "ENUMERATION" in tags
    assert "CONTROL_ONLY" in tags
