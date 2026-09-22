#!/usr/bin/env python3
"""Decrypt and analyze offline ADC data from reading_logs0.11 capture."""

import struct

import polars as pl

from km003c_analysis.datasets import load_master_dataset
from km003c_analysis.device import (
    ADDR_OFFLINE_LOG,
    OFFLINE_LOG_SAMPLE_SIZE,
    aligned_response_size,
    decrypt_memory_payload,
    parse_memory_read_confirmation,
)


def main() -> None:
    df = load_master_dataset()

    # Filter for reading_logs0.11 capture
    logs_df = df.filter(pl.col("source_file").str.contains("reading_logs"))
    print(f"Packets in reading_logs capture: {len(logs_df)}")

    # Find and validate MemoryRead confirmations.
    bulk_in = logs_df.filter(
        (pl.col("endpoint_address") == "0x81")
        & (pl.col("urb_type") == "C")
        & pl.col("payload_hex").is_not_null()
    )

    print(f"\nBulk IN completions: {len(bulk_in)}")

    print("\n--- MemoryRead Confirmations ---")
    log_confirmation_frame = None
    requested_log_size = None
    for row in bulk_in.iter_rows(named=True):
        payload_hex = row["payload_hex"]
        if payload_hex:
            payload = bytes.fromhex(payload_hex)
            pkt_type = payload[0] & 0x7F
            if pkt_type == 0x44 and len(payload) == 20:
                print(f"  Frame {row['frame_number']}: type=0x{pkt_type:02X}")
                print(f"    Raw: {payload.hex()}")
                echoed = parse_memory_read_confirmation(payload)
                if echoed is None:
                    print("    Parsed: invalid magic or CRC")
                    continue
                addr, size = echoed
                print(f"    Parsed: addr=0x{addr:08X}, size={size}")
                if addr == ADDR_OFFLINE_LOG:
                    log_confirmation_frame = row["frame_number"]
                    requested_log_size = size

    if log_confirmation_frame is None or requested_log_size is None:
        raise ValueError("Offline-log MemoryRead confirmation not found")

    # Collect the raw transfers immediately following the log confirmation.
    expected_ciphertext_size = aligned_response_size(requested_log_size)
    large_chunks = []
    received = 0
    data_rows = bulk_in.filter(pl.col("frame_number") > log_confirmation_frame).sort(
        "frame_number"
    )
    for row in data_rows.iter_rows(named=True):
        if received == expected_ciphertext_size:
            break
        payload_hex = row["payload_hex"]
        if payload_hex:
            payload = bytes.fromhex(payload_hex)
            print(f"  Frame {row['frame_number']}: raw ciphertext, size={len(payload)}")
            if received + len(payload) > expected_ciphertext_size:
                raise ValueError(
                    "MemoryRead transfers exceed the requested AES-aligned size"
                )
            large_chunks.append((row["frame_number"], payload))
            received += len(payload)

    if received != expected_ciphertext_size:
        raise ValueError(
            f"MemoryRead ended at {received} bytes, expected {expected_ciphertext_size}"
        )
    print(f"\nFound {len(large_chunks)} raw transfers")

    encrypted = b"".join(payload for _, payload in large_chunks)
    print(f"\n=== Decrypting {len(encrypted)} raw ciphertext bytes ===")
    decrypted = decrypt_memory_payload(encrypted)

    num_samples = len(decrypted) // OFFLINE_LOG_SAMPLE_SIZE
    print(
        f"Number of {OFFLINE_LOG_SAMPLE_SIZE}-byte samples: {num_samples} (expected 521)"
    )

    samples = [
        struct.unpack_from("<iiii", decrypted, offset)
        for offset in range(
            0, num_samples * OFFLINE_LOG_SAMPLE_SIZE, OFFLINE_LOG_SAMPLE_SIZE
        )
    ]

    # Analyze each field with the recovered protocol units.
    print("\n--- Field Analysis ---")
    fields = [
        (0, "Voltage", "V", 1_000_000),
        (1, "Current", "A", 1_000_000),
        (2, "Charge accumulator", "mAh", 1_000),
        (3, "Energy accumulator", "mWh", 1_000),
    ]
    for field_idx, name, unit, scale in fields:
        values = [s[field_idx] for s in samples]
        min_v = min(values)
        max_v = max(values)
        avg_v = sum(values) / len(values)
        print(
            f"{name}: avg={avg_v / scale:.6f} {unit}, "
            f"range={min_v / scale:.6f}..{max_v / scale:.6f} {unit}"
        )

    # Show the first 10 samples in physical units.
    print("\n--- First 10 Samples ---")
    print(
        f"{'#':>4} {'Voltage(V)':>12} {'Current(A)':>12} "
        f"{'Charge(mAh)':>12} {'Energy(mWh)':>12}"
    )
    for i, (voltage_uv, current_ua, charge_uah, energy_uwh) in enumerate(samples[:10]):
        print(
            f"{i:4} {voltage_uv / 1e6:12.6f} {current_ua / 1e6:12.6f} "
            f"{charge_uah / 1e3:12.3f} {energy_uwh / 1e3:12.3f}"
        )


if __name__ == "__main__":
    main()
