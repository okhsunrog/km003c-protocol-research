import pytest
import polars as pl
from pathlib import Path
import sys
from typing import List, Tuple

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


@pytest.fixture(scope="module")
def tagged_source_dataframes() -> List[Tuple[str, pl.DataFrame]]:
    """Fixture to split, and tag each source file separately."""
    if not DATASET_PATH.exists():
        pytest.fail(f"Master dataset not found at {DATASET_PATH}")

    master_df = pl.read_parquet(DATASET_PATH)
    source_files = master_df["source_file"].unique().sort()

    result = []
    for source_file in source_files:
        source_df = master_df.filter(pl.col("source_file") == source_file)
        df_split = split_usb_transactions(source_df)
        df_tagged = tag_transactions(df_split)
        result.append((source_file, df_tagged))

    return result


def test_tagger_adds_tags_column(tagged_df):
    """Ensures the tagger adds a 'tags' column of the correct list type."""
    assert "tags" in tagged_df.columns
    assert isinstance(tagged_df["tags"].dtype, pl.List), (
        "Tags column should be a list type."
    )


def test_tagger_adds_tags_column_per_source(tagged_source_dataframes):
    """Ensures the tagger adds tags column for each source file."""
    for source_file, df_tagged in tagged_source_dataframes:
        assert "tags" in df_tagged.columns, f"No tags column for {source_file}"
        assert isinstance(df_tagged["tags"].dtype, pl.List), (
            f"Wrong tags type for {source_file}"
        )


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


def test_tagger_identifies_control_only_per_source(tagged_source_dataframes):
    """Verify CONTROL_ONLY tagging for each source file."""
    for source_file, df_tagged in tagged_source_dataframes:
        # Find control-only transactions
        control_only = (
            df_tagged.filter(pl.col("transfer_type") == "0x02")
            .group_by("transaction_id")
            .first()
        )

        if control_only.height > 0:
            # Check at least one has the CONTROL_ONLY tag
            has_control_tag = False
            for tags in control_only["tags"]:
                if "CONTROL_ONLY" in tags:
                    has_control_tag = True
                    break
            assert has_control_tag, f"No CONTROL_ONLY tags found in {source_file}"


def test_tagger_identifies_bulk_command_response(tagged_df):
    """Verify that BULK_COMMAND_RESPONSE transactions are tagged correctly."""
    # Find transactions that have been tagged with BULK_COMMAND_RESPONSE
    candidate_transactions = tagged_df.filter(
        pl.col("tags").list.contains("BULK_COMMAND_RESPONSE")
    )
    assert not candidate_transactions.is_empty(), (
        "No BULK_COMMAND_RESPONSE transactions were found."
    )

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


def test_tagger_identifies_bulk_command_response_per_source(tagged_source_dataframes):
    """Verify BULK_COMMAND_RESPONSE tagging for each source file."""
    for source_file, df_tagged in tagged_source_dataframes:
        # Check if this source has bulk transfers
        has_bulk = (df_tagged["transfer_type"] == "0x03").any()

        if has_bulk:
            # Find BULK_COMMAND_RESPONSE transactions
            bulk_cmd_resp = df_tagged.filter(
                pl.col("tags").list.contains("BULK_COMMAND_RESPONSE")
            )

            # Some sources might not have this pattern, which is okay
            if not bulk_cmd_resp.is_empty():
                # Verify at least one transaction structure
                test_tid = bulk_cmd_resp["transaction_id"][0]
                test_group = df_tagged.filter(pl.col("transaction_id") == test_tid)

                out_requests = test_group.filter(
                    (pl.col("endpoint_address") == "0x01") & (pl.col("urb_type") == "S")
                ).height
                in_responses = test_group.filter(
                    (pl.col("endpoint_address") == "0x81") & (pl.col("urb_type") == "C")
                ).height

                assert out_requests >= 1, (
                    f"Invalid BULK_COMMAND_RESPONSE in {source_file}"
                )
                assert in_responses == 1, (
                    f"Invalid BULK_COMMAND_RESPONSE in {source_file}"
                )


def test_tagger_identifies_enumeration(tagged_df):
    """Verify that a known ENUMERATION transaction is tagged correctly."""
    # First, filter for control transfers which are the only ones with brequest values
    control_transactions = tagged_df.filter(pl.col("transfer_type") == "0x02")

    # Now, find a standard enumeration transaction (brequest=6 is GET_DESCRIPTOR)
    enumeration_transaction = control_transactions.filter(pl.col("brequest") == "6")
    assert not enumeration_transaction.is_empty(), (
        "Could not find a GET_DESCRIPTOR (brequest=6) transaction to test."
    )

    # Check the tags of the first one found
    tags = enumeration_transaction["tags"][0]
    assert "ENUMERATION" in tags
    assert "CONTROL_ONLY" in tags


def test_tagger_identifies_enumeration_per_source(tagged_source_dataframes):
    """Verify ENUMERATION tagging for each source file."""
    for source_file, df_tagged in tagged_source_dataframes:
        # Check for control transfers with enumeration requests
        control_transactions = df_tagged.filter(pl.col("transfer_type") == "0x02")

        if control_transactions.height > 0:
            # Check for enumeration requests (0, 6, 9 are common)
            enum_requests = control_transactions.filter(
                pl.col("brequest").is_in(["0", "6", "9"])
            )

            if not enum_requests.is_empty():
                # At least one should be tagged as ENUMERATION
                has_enum_tag = False
                for tags in enum_requests["tags"]:
                    if "ENUMERATION" in tags:
                        has_enum_tag = True
                        break
                assert has_enum_tag, (
                    f"No ENUMERATION tags found in {source_file} despite having enum requests"
                )
