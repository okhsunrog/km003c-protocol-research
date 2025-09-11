#!/usr/bin/env python3
"""
Analyze USB packet data from Parquet files created by the Rust converter.
This script demonstrates how to work with the raw USB payload data.
"""

import argparse
import sys
from pathlib import Path

import polars as pl


def analyze_usb_parquet(parquet_file, show_payload_samples=False):
    """Analyze USB packet data from Parquet file with payload data."""

    print(f"=== Analyzing USB Parquet Data: {parquet_file} ===\n")

    # Load the data
    df = pl.read_parquet(parquet_file)
    print(f"Loaded {len(df)} USB packets")
    print(f"Columns: {df.columns}")
    print(f"Time range: {df['timestamp'].min():.6f}s to {df['timestamp'].max():.6f}s")
    print(f"Duration: {df['timestamp'].max() - df['timestamp'].min():.6f}s\n")

    # Basic statistics
    print("=== Basic Statistics ===")
    print(f"Total packets: {len(df)}")
    print(f"Unique sessions: {df['session_id'].n_unique()}")
    print(f"Device addresses: {sorted(df['device_address'].unique().to_list())}")
    print(
        f"Payload length range: {df['data_length'].min()} - {df['data_length'].max()} bytes"
    )
    print(f"Average payload length: {df['data_length'].mean():.2f} bytes\n")

    # Direction analysis
    print("=== Direction Analysis ===")
    direction_counts = (
        df.group_by("direction")
        .agg(pl.len().alias("count"))
        .sort("count", descending=True)
    )
    print(direction_counts)
    print()

    # Endpoint analysis
    print("=== Endpoint Analysis ===")
    endpoint_counts = (
        df.group_by("endpoint_address")
        .agg(
            [pl.len().alias("count"), pl.col("data_length").mean().alias("avg_length")]
        )
        .sort("count", descending=True)
    )
    print(endpoint_counts)
    print()

    # Payload length distribution
    print("=== Payload Length Distribution ===")
    length_counts = (
        df.group_by("data_length").agg(pl.len().alias("count")).sort("data_length")
    )
    print("Most common payload lengths:")
    print(length_counts.sort("count", descending=True).head(10))
    print()

    # Time analysis
    print("=== Traffic Pattern Analysis ===")
    # Group by second to see traffic rate
    df_with_second = df.with_columns([pl.col("timestamp").floor().alias("second")])

    traffic_per_second = (
        df_with_second.group_by("second")
        .agg(
            [
                pl.len().alias("packets_per_second"),
                pl.col("data_length").sum().alias("bytes_per_second"),
            ]
        )
        .sort("second")
    )

    print(
        f"Peak traffic: {traffic_per_second['packets_per_second'].max()} packets/second"
    )
    print(
        f"Average traffic: {traffic_per_second['packets_per_second'].mean():.2f} packets/second"
    )
    print(
        f"Peak bandwidth: {traffic_per_second['bytes_per_second'].max()} bytes/second"
    )
    print(
        f"Average bandwidth: {traffic_per_second['bytes_per_second'].mean():.2f} bytes/second\n"
    )

    # Payload analysis
    print("=== Payload Data Analysis ===")

    # Find unique payload patterns
    unique_payloads = df.select(["payload_hex", "data_length"]).unique()
    print(f"Unique payload patterns: {len(unique_payloads)}")

    # Analyze payload by direction and length
    payload_stats = (
        df.group_by(["direction", "data_length"])
        .agg(
            [
                pl.len().alias("count"),
                pl.col("payload_hex").n_unique().alias("unique_payloads"),
            ]
        )
        .sort(["direction", "data_length"])
    )

    print("\nPayload patterns by direction and length:")
    print(payload_stats)
    print()

    if show_payload_samples:
        print("=== Payload Samples ===")

        # Show samples of different payload lengths
        for length in sorted(df["data_length"].unique().to_list())[
            :10
        ]:  # First 10 lengths
            samples = df.filter(pl.col("data_length") == length).head(3)
            print(f"\n--- {length} byte payloads ---")
            for row in samples.iter_rows(named=True):
                direction = row["direction"]
                frame = row["frame_number"]
                payload_hex = row["payload_hex"]

                # Convert hex to bytes for analysis
                try:
                    payload_bytes = bytes.fromhex(payload_hex)
                    # Show hex and ASCII representation
                    ascii_repr = "".join(
                        chr(b) if 32 <= b <= 126 else "." for b in payload_bytes
                    )
                    print(f"  Frame {frame} ({direction}): {payload_hex}")
                    print(f"    ASCII: {ascii_repr}")
                    print(f"    Bytes: {list(payload_bytes)}")
                except ValueError:
                    print(f"  Frame {frame} ({direction}): Invalid hex - {payload_hex}")
        print()

    return df


def find_patterns(df):
    """Find interesting patterns in the USB data."""

    print("=== Pattern Analysis ===")

    # Look for repeating patterns
    print("Most common payloads:")
    common_payloads = (
        df.group_by("payload_hex")
        .agg(
            [
                pl.len().alias("count"),
                pl.col("direction").first().alias("direction"),
                pl.col("data_length").first().alias("length"),
            ]
        )
        .sort("count", descending=True)
        .head(10)
    )

    for row in common_payloads.iter_rows(named=True):
        count = row["count"]
        direction = row["direction"]
        length = row["length"]
        payload_hex = row["payload_hex"]

        print(f"  {count:4d}x {direction} {length:2d}b: {payload_hex}")

        # Try to decode as ASCII if reasonable
        if length <= 32:  # Only for shorter payloads
            try:
                payload_bytes = bytes.fromhex(payload_hex)
                ascii_repr = "".join(
                    chr(b) if 32 <= b <= 126 else "." for b in payload_bytes
                )
                print(f"             ASCII: {ascii_repr}")
            except ValueError:
                pass
    print()

    # Look for command/response patterns
    print("Command/Response Pattern Analysis:")

    # Group consecutive packets by frame number
    df_sorted = df.sort("frame_number")

    # Find H->D followed by D->H patterns
    h2d_packets = df_sorted.filter(pl.col("direction") == "H->D")
    d2h_packets = df_sorted.filter(pl.col("direction") == "D->H")

    print(f"Host to Device packets: {len(h2d_packets)}")
    print(f"Device to Host packets: {len(d2h_packets)}")

    # Look for timing patterns
    if len(h2d_packets) > 0 and len(d2h_packets) > 0:
        # Calculate time differences between consecutive packets of same direction
        h2d_time_diffs = h2d_packets.sort("timestamp").with_columns(
            [(pl.col("timestamp") - pl.col("timestamp").shift(1)).alias("time_diff")]
        )

        avg_h2d_interval = h2d_time_diffs["time_diff"].mean()
        print(f"Average interval between H->D packets: {avg_h2d_interval:.6f}s")

        d2h_time_diffs = d2h_packets.sort("timestamp").with_columns(
            [(pl.col("timestamp") - pl.col("timestamp").shift(1)).alias("time_diff")]
        )

        avg_d2h_interval = d2h_time_diffs["time_diff"].mean()
        print(f"Average interval between D->H packets: {avg_d2h_interval:.6f}s")

    print()


def export_payload_data(df, output_file):
    """Export payload data in various formats for further analysis."""

    print(f"=== Exporting Payload Data to {output_file} ===")

    # Create a detailed export with decoded payloads
    export_df = df.with_columns(
        [
            # Add decoded payload as bytes
            pl.col("payload_hex")
            .map_elements(
                lambda hex_str: list(bytes.fromhex(hex_str)) if hex_str else [],
                return_dtype=pl.List(pl.UInt8),
            )
            .alias("payload_bytes_list"),
            # Add ASCII representation
            pl.col("payload_hex")
            .map_elements(
                lambda hex_str: (
                    "".join(
                        chr(b) if 32 <= b <= 126 else "."
                        for b in bytes.fromhex(hex_str)
                    )
                    if hex_str
                    else ""
                ),
                return_dtype=pl.Utf8,
            )
            .alias("payload_ascii"),
        ]
    )

    # Save as CSV for easy viewing
    csv_file = output_file.with_suffix(".csv")
    export_df.write_csv(csv_file)
    print(f"Exported to CSV: {csv_file}")

    # Save as Parquet for efficient storage
    parquet_file = output_file.with_suffix(".parquet")
    export_df.write_parquet(parquet_file)
    print(f"Exported to Parquet: {parquet_file}")

    print(f"Exported {len(export_df)} records with decoded payload data")


def main():
    parser = argparse.ArgumentParser(
        description="Analyze USB packet data from Rust-generated Parquet files"
    )
    parser.add_argument("parquet_file", help="Input Parquet file from Rust converter")
    parser.add_argument(
        "--show-payload-samples", action="store_true", help="Show sample payload data"
    )
    parser.add_argument(
        "--export", type=str, help="Export processed data to file (specify base name)"
    )
    parser.add_argument(
        "--find-patterns",
        action="store_true",
        help="Perform pattern analysis on the data",
    )

    args = parser.parse_args()

    if not Path(args.parquet_file).exists():
        print(f"Error: File {args.parquet_file} not found")
        return 1

    try:
        # Load and analyze the data
        df = analyze_usb_parquet(args.parquet_file, args.show_payload_samples)

        # Find patterns if requested
        if args.find_patterns:
            find_patterns(df)

        # Export if requested
        if args.export:
            export_payload_data(df, Path(args.export))

        print("=== Analysis Complete ===")
        print(f"Successfully analyzed {len(df)} USB packets with payload data!")
        print(
            "The Rust converter successfully extracted raw USB payload data that pyshark couldn't access."
        )

        return 0

    except Exception as e:
        print(f"Error analyzing file: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
