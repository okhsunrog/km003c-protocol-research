"""
USB Transaction Splitter Library

A modular library for splitting USB frame data into logical transactions based on
URB (USB Request Block) patterns and bulk transfer sequences.

This library works with any Polars DataFrame containing USB frame data and is
independent of data source format (JSONL, CSV, Parquet, etc.).
"""

import polars as pl
from typing import Set, Dict, Any, Optional
from dataclasses import dataclass


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

    # USB protocol constants
    bulk_transfer_type: str = "0x03"
    control_transfer_type: str = "0x02"
    out_endpoint: str = "0x01"
    in_endpoint: str = "0x81"
    submit_urb: str = "S"
    complete_urb: str = "C"
    cancel_status: str = "-2"


class USBTransactionSplitter:
    """
    Core USB transaction splitting logic.

    Implements intelligent grouping of USB frames into logical transactions
    based on protocol patterns, particularly for bulk transfer command-response cycles.
    """

    def __init__(self, config: Optional[TransactionSplitterConfig] = None):
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
        self.seen_urb_ids: Set[str] = set()
        self.completed_urb_ids: Set[str] = set()

    def is_bulk_setup(self, frame: Dict[str, Any]) -> bool:
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

    def is_cancellation(self, frame: Dict[str, Any]) -> bool:
        """
        Check if frame is a cancellation.

        Args:
            frame: Dictionary containing frame data

        Returns:
            True if this is a cancellation frame (urb_status -2)
        """
        return frame.get(self.config.urb_status_col) == self.config.cancel_status

    def is_completion(self, frame: Dict[str, Any]) -> bool:
        """
        Check if frame is a completion.

        Args:
            frame: Dictionary containing frame data

        Returns:
            True if this is a completion frame (urb_type C)
        """
        return frame.get(self.config.urb_type_col) == self.config.complete_urb

    def is_bulk_command_start(self, frame: Dict[str, Any]) -> bool:
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
        self, frame: Dict[str, Any], frame_index: int
    ) -> bool:
        """
        Determine if this frame should start a new transaction.

        Transaction boundaries are determined by:
        1. First frame always starts transaction 1
        2. Bulk command start frames (0x01 S with data) start new transactions
        3. New URB IDs start new transactions (except for special cases)
        4. Bulk setup and cancellation frames never start new transactions

        Args:
            frame: Dictionary containing frame data
            frame_index: 0-based index of this frame in the sequence

        Returns:
            True if this frame should start a new transaction
        """
        urb_id = frame.get(self.config.urb_id_col, "")

        # First frame doesn't start a new transaction (it starts transaction 1)
        if frame_index == 0:
            return False

        # Check special cases that go to previous transaction
        if self.is_bulk_setup(frame) or self.is_cancellation(frame):
            return False

        # For bulk transfers, prioritize command-response pattern recognition
        if frame.get(self.config.transfer_type_col) == self.config.bulk_transfer_type:
            # Bulk command starts always start new transactions
            if self.is_bulk_command_start(frame):
                return True

            # Other bulk frames (ACK, data response) continue current transaction
            return False

        # For non-bulk transfers, use URB ID logic
        if not urb_id:
            return False

        # Check if this URB ID is new
        is_truly_new_urb = (
            urb_id not in self.seen_urb_ids and urb_id not in self.completed_urb_ids
        )
        is_reused_urb = (
            urb_id in self.completed_urb_ids and urb_id not in self.seen_urb_ids
        )

        return is_truly_new_urb or is_reused_urb

    def process_frame(self, frame: Dict[str, Any], frame_index: int) -> int:
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
            is_bulk_setup = self.is_bulk_setup(frame)
            is_cancellation = self.is_cancellation(frame)
            is_completion = self.is_completion(frame)

            if is_bulk_setup or is_cancellation:
                # Don't mark bulk setup or cancellation URB IDs as seen
                # This allows their completion/related frames to start new transactions
                pass
            elif is_completion:
                # Mark completion URB IDs as completed (enables reuse)
                self.completed_urb_ids.add(urb_id)
                # Remove from seen so it can be reused
                self.seen_urb_ids.discard(urb_id)
            else:
                # Mark normal URB IDs as seen
                self.seen_urb_ids.add(urb_id)

        return self.current_transaction

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

        # Sort by frame number to ensure proper chronological order
        df = df.sort(self.config.frame_number_col)

        # Reset state for new processing
        self.reset_state()

        # Convert to list of dicts for processing
        rows = df.to_dicts()

        # Process each frame to get its transaction ID
        transaction_ids = []
        for i, row in enumerate(rows):
            transaction_id = self.process_frame(row, i)
            transaction_ids.append(transaction_id)

        # Create a new DataFrame with just the transaction IDs
        tid_df = pl.DataFrame({self.config.transaction_id_col: transaction_ids})

        # Horizontally concatenate the transaction ID column with the original, sorted DataFrame
        return pl.concat([df, tid_df], how="horizontal")

    def validate_output(self, df: pl.DataFrame) -> Dict[str, bool]:
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

        # Extract sequences for validation
        frame_nums = df.select(self.config.frame_number_col).to_series().to_list()
        tx_ids = df.select(self.config.transaction_id_col).to_series().to_list()

        # Check ordering requirements
        frame_order_valid = all(
            frame_nums[i] <= frame_nums[i + 1] for i in range(len(frame_nums) - 1)
        )
        tx_order_valid = all(tx_ids[i] <= tx_ids[i + 1] for i in range(len(tx_ids) - 1))

        timestamp_order_valid = True
        if self.config.timestamp_col in df.columns:
            timestamps = df.select(self.config.timestamp_col).to_series().to_list()
            timestamp_order_valid = all(
                timestamps[i] <= timestamps[i + 1] for i in range(len(timestamps) - 1)
            )

        return {
            "valid": frame_order_valid and timestamp_order_valid and tx_order_valid,
            "frame_order": frame_order_valid,
            "timestamp_order": timestamp_order_valid,
            "transaction_order": tx_order_valid,
        }

    def get_transaction_stats(self, df: pl.DataFrame) -> Dict[str, Any]:
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

        transaction_stats = (
            df.group_by(self.config.transaction_id_col)
            .len()
            .sort(self.config.transaction_id_col)
        )

        total_transactions = transaction_stats.height
        total_frames = df.height
        avg_frames = total_frames / total_transactions if total_transactions > 0 else 0

        # Size distribution
        frame_counts = transaction_stats.select("len").to_series().to_list()
        size_1 = sum(1 for count in frame_counts if count == 1)
        size_2_4 = sum(1 for count in frame_counts if 2 <= count <= 4)
        size_5_plus = sum(1 for count in frame_counts if count >= 5)

        return {
            "total_transactions": total_transactions,
            "total_frames": total_frames,
            "avg_frames_per_transaction": avg_frames,
            "size_distribution": {
                "1_frame": size_1,
                "2_4_frames": size_2_4,
                "5_plus_frames": size_5_plus,
            },
            "largest_transaction_size": max(frame_counts) if frame_counts else 0,
        }


def create_default_splitter() -> USBTransactionSplitter:
    """
    Create a USB transaction splitter with default configuration.

    Returns:
        Configured USBTransactionSplitter instance
    """
    return USBTransactionSplitter()


def split_usb_transactions(
    df: pl.DataFrame, config: Optional[TransactionSplitterConfig] = None
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
