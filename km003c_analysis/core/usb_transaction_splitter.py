"""
USB Transaction Splitter Library

A modular library for splitting USB frame data into logical transactions based on
URB (USB Request Block) patterns and bulk transfer sequences.

This library works with any Polars DataFrame containing USB frame data and is
independent of data source format (JSONL, CSV, Parquet, etc.).

Unlike the tagger, splitting carries state across rows: whether a URB is
currently outstanding depends on every earlier frame with the same URB ID. The
scan below is therefore deliberately sequential, but it only materializes the
handful of columns it actually reads.
"""

from dataclasses import dataclass
from typing import Any

import polars as pl


@dataclass
class TransactionSplitterConfig:
    """Configuration for USB transaction splitting behavior"""

    # Column names in the DataFrame
    frame_number_col: str = "frame_number"
    timestamp_col: str = "timestamp"
    transfer_type_col: str = "transfer_type"
    endpoint_address_col: str = "endpoint_address"
    urb_type_col: str = "urb_type"
    urb_status_col: str = "urb_status"
    data_length_col: str = "data_length"
    urb_id_col: str = "urb_id"

    # Transaction ID output column
    transaction_id_col: str = "transaction_id"

    # Independent capture stream. Frame numbers and URB IDs may repeat between
    # source files, so splitter state must not cross this boundary.
    source_col: str | None = "source_file"

    # USB protocol constants
    bulk_transfer_type: str = "0x03"
    control_transfer_type: str = "0x02"
    out_endpoint: str = "0x01"
    in_endpoint: str = "0x81"
    submit_urb: str = "S"
    complete_urb: str = "C"
    cancel_status: str = "-2"

    def scan_columns(self) -> list[str]:
        """Columns the sequential scan reads, in no particular order."""
        return [
            self.transfer_type_col,
            self.endpoint_address_col,
            self.urb_type_col,
            self.urb_status_col,
            self.data_length_col,
            self.urb_id_col,
        ]


class USBTransactionSplitter:
    """
    Core USB transaction splitting logic.

    Implements intelligent grouping of USB frames into logical transactions
    based on protocol patterns, particularly for bulk transfer command-response cycles.
    """

    def __init__(self, config: TransactionSplitterConfig | None = None):
        """
        Initialize the transaction splitter.

        Args:
            config: Configuration object. If None, uses default configuration.
        """
        self.config = config or TransactionSplitterConfig()
        self.reset_state()

    def reset_state(self) -> None:
        """Reset internal state for processing a new dataset"""
        self.current_transaction = 1
        # URB IDs with an outstanding submit: added when a submit is seen and
        # removed again by its completion.
        self.outstanding_urb_ids: set[str] = set()

    def is_bulk_setup(self, frame: dict[str, Any]) -> bool:
        """
        Check if frame is a bulk setup frame.

        Bulk setup frames prepare receive buffers and have:
        - Transfer type: bulk (0x03)
        - Endpoint: IN endpoint (0x81)
        - URB type: Submit (S)
        - Data length: 0 (no payload)

        Args:
            frame: Dictionary containing frame data

        Returns:
            True if this is a bulk setup frame
        """
        return (
            frame.get(self.config.transfer_type_col) == self.config.bulk_transfer_type
            and frame.get(self.config.endpoint_address_col) == self.config.in_endpoint
            and frame.get(self.config.urb_type_col) == self.config.submit_urb
            and frame.get(self.config.data_length_col, 0) == 0
        )

    def is_cancellation(self, frame: dict[str, Any]) -> bool:
        """
        Check if frame is a cancellation.

        Args:
            frame: Dictionary containing frame data

        Returns:
            True if this is a cancellation frame (urb_status -2)
        """
        return frame.get(self.config.urb_status_col) == self.config.cancel_status

    def is_completion(self, frame: dict[str, Any]) -> bool:
        """
        Check if frame is a completion.

        Args:
            frame: Dictionary containing frame data

        Returns:
            True if this is a completion frame (urb_type C)
        """
        return frame.get(self.config.urb_type_col) == self.config.complete_urb

    def is_bulk_command_start(self, frame: dict[str, Any]) -> bool:
        """
        Check if frame starts a bulk command sequence.

        Command start frames have:
        - Transfer type: bulk (0x03)
        - Endpoint: OUT endpoint (0x01)
        - URB type: Submit (S)
        - Data length: > 0 (contains command payload)

        Args:
            frame: Dictionary containing frame data

        Returns:
            True if this frame starts a bulk command sequence
        """
        return (
            frame.get(self.config.transfer_type_col) == self.config.bulk_transfer_type
            and frame.get(self.config.endpoint_address_col) == self.config.out_endpoint
            and frame.get(self.config.urb_type_col) == self.config.submit_urb
            and frame.get(self.config.data_length_col, 0) > 0
        )

    def should_start_new_transaction(
        self, frame: dict[str, Any], frame_index: int
    ) -> bool:
        """
        Determine if this frame should start a new transaction.

        Transaction boundaries are determined by:
        1. First frame always starts transaction 1
        2. Bulk command start frames (0x01 S with data) start new transactions
        3. A URB ID with no outstanding submit starts a new transaction
        4. Bulk setup and cancellation frames never start new transactions

        Args:
            frame: Dictionary containing frame data
            frame_index: 0-based index of this frame in the sequence

        Returns:
            True if this frame should start a new transaction
        """
        # First frame doesn't start a new transaction (it starts transaction 1)
        if frame_index == 0:
            return False

        # Check special cases that go to previous transaction
        if self.is_bulk_setup(frame) or self.is_cancellation(frame):
            return False

        # For bulk transfers, prioritize command-response pattern recognition
        if frame.get(self.config.transfer_type_col) == self.config.bulk_transfer_type:
            # Bulk command starts always start new transactions; other bulk
            # frames (ACK, data response) continue the current transaction.
            return self.is_bulk_command_start(frame)

        # For non-bulk transfers, a frame belongs to the current transaction
        # only while its URB is still outstanding. Anything else - a fresh URB
        # ID or a reused one whose submit already completed - starts a new one.
        urb_id = frame.get(self.config.urb_id_col, "")
        if not urb_id:
            return False
        return urb_id not in self.outstanding_urb_ids

    def process_frame(self, frame: dict[str, Any], frame_index: int) -> int:
        """
        Process a single frame and return its transaction ID.

        Args:
            frame: Dictionary containing frame data
            frame_index: 0-based index of this frame in the sequence

        Returns:
            Transaction ID for this frame
        """
        urb_id = frame.get(self.config.urb_id_col, "")

        # Check if we should start a new transaction
        if self.should_start_new_transaction(frame, frame_index):
            self.current_transaction += 1

        # Update URB ID tracking
        if urb_id:
            if self.is_bulk_setup(frame) or self.is_cancellation(frame):
                # Neither opens a URB, so their completion or related frames
                # stay free to start a new transaction.
                pass
            elif self.is_completion(frame):
                # The URB is closed and its ID may be reused by the kernel.
                self.outstanding_urb_ids.discard(urb_id)
            else:
                self.outstanding_urb_ids.add(urb_id)

        return self.current_transaction

    def _split_single_stream(
        self, df: pl.DataFrame, first_transaction_id: int
    ) -> pl.DataFrame:
        """Split one capture stream with fresh URB state."""
        df = df.sort(self.config.frame_number_col)
        self.reset_state()
        self.current_transaction = first_transaction_id

        # Only the columns the scan reads are materialized as Python objects.
        scan = df.select(self.config.scan_columns())
        transaction_ids = [
            self.process_frame(row, index)
            for index, row in enumerate(scan.iter_rows(named=True))
        ]
        tid_series = pl.Series(
            self.config.transaction_id_col,
            transaction_ids,
            dtype=pl.Int64,
        )
        return df.with_columns(tid_series)

    def split_transactions(self, df: pl.DataFrame) -> pl.DataFrame:
        """
        Split a DataFrame of USB frames into logical transactions.

        Args:
            df: Polars DataFrame containing USB frame data with required columns

        Returns:
            DataFrame with added/updated transaction_id column

        Raises:
            ValueError: If required columns are missing from the DataFrame
        """
        # Validate required columns
        required_cols = [
            self.config.frame_number_col,
            self.config.transfer_type_col,
            self.config.endpoint_address_col,
            self.config.urb_type_col,
            self.config.urb_id_col,
        ]

        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            raise ValueError(f"Missing required columns: {missing_cols}")

        if df.is_empty():
            return df.with_columns(
                pl.Series(self.config.transaction_id_col, [], dtype=pl.Int64)
            )

        split_streams = []
        next_transaction_id = 1
        for stream in self._streams(df):
            split_stream = self._split_single_stream(stream, next_transaction_id)
            split_streams.append(split_stream)
            next_transaction_id = self.current_transaction + 1

        return pl.concat(split_streams)

    def _streams(self, df: pl.DataFrame) -> list[pl.DataFrame]:
        """Split the frame into independent capture streams."""
        source_col = self.config.source_col
        if source_col is not None and source_col in df.columns:
            return df.partition_by(source_col, maintain_order=True)
        return [df]

    def validate_output(self, df: pl.DataFrame) -> dict[str, bool]:
        """
        Validate that the output maintains proper ordering.

        Args:
            df: DataFrame with transaction IDs assigned

        Returns:
            Dictionary with validation results
        """
        if df.height == 0:
            return {
                "valid": True,
                "frame_order": True,
                "timestamp_order": True,
                "transaction_order": True,
            }

        streams = self._streams(df)

        def column_is_sorted(stream: pl.DataFrame, column: str) -> bool:
            return bool(stream[column].is_sorted())

        frame_order_valid = all(
            column_is_sorted(stream, self.config.frame_number_col) for stream in streams
        )
        tx_order_valid = column_is_sorted(df, self.config.transaction_id_col)

        timestamp_order_valid = True
        if self.config.timestamp_col in df.columns:
            timestamp_order_valid = all(
                column_is_sorted(stream, self.config.timestamp_col)
                for stream in streams
            )

        return {
            "valid": frame_order_valid and timestamp_order_valid and tx_order_valid,
            "frame_order": frame_order_valid,
            "timestamp_order": timestamp_order_valid,
            "transaction_order": tx_order_valid,
        }

    def get_transaction_stats(self, df: pl.DataFrame) -> dict[str, Any]:
        """
        Get statistics about the transaction splitting results.

        Args:
            df: DataFrame with transaction IDs assigned

        Returns:
            Dictionary with transaction statistics
        """
        if df.height == 0:
            return {
                "total_transactions": 0,
                "total_frames": 0,
                "avg_frames_per_transaction": 0,
            }

        frame_counts = (
            df.group_by(self.config.transaction_id_col)
            .len()
            .select(
                pl.len().alias("total_transactions"),
                (pl.col("len") == 1).sum().alias("size_1"),
                ((pl.col("len") >= 2) & (pl.col("len") <= 4)).sum().alias("size_2_4"),
                (pl.col("len") >= 5).sum().alias("size_5_plus"),
                pl.col("len").max().alias("largest"),
            )
            .row(0, named=True)
        )

        total_transactions = frame_counts["total_transactions"]
        total_frames = df.height

        return {
            "total_transactions": total_transactions,
            "total_frames": total_frames,
            "avg_frames_per_transaction": (
                total_frames / total_transactions if total_transactions > 0 else 0
            ),
            "size_distribution": {
                "1_frame": frame_counts["size_1"],
                "2_4_frames": frame_counts["size_2_4"],
                "5_plus_frames": frame_counts["size_5_plus"],
            },
            "largest_transaction_size": frame_counts["largest"],
        }


def create_default_splitter() -> USBTransactionSplitter:
    """
    Create a USB transaction splitter with default configuration.

    Returns:
        Configured USBTransactionSplitter instance
    """
    return USBTransactionSplitter()


def split_usb_transactions(
    df: pl.DataFrame, config: TransactionSplitterConfig | None = None
) -> pl.DataFrame:
    """
    Convenience function to split USB transactions in a DataFrame.

    Args:
        df: Polars DataFrame containing USB frame data
        config: Optional configuration. If None, uses defaults.

    Returns:
        DataFrame with transaction_id column added/updated

    Example:
        >>> import polars as pl
        >>> df = pl.read_parquet("usb_data.parquet")
        >>> df_with_transactions = split_usb_transactions(df)
        >>> print(f"Split into {df_with_transactions['transaction_id'].max()} transactions")
    """
    splitter = USBTransactionSplitter(config)
    return splitter.split_transactions(df)
