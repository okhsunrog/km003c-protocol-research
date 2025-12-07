#!/usr/bin/env python3
"""Decrypt and analyze offline ADC data from reading_logs0.11 capture."""

import polars as pl
from pathlib import Path
from Crypto.Cipher import AES
import struct

# AES key for Unknown68 (key index 0)
AES_KEY = b"Lh2yfB7n6X7d9a5Z"

def decrypt_ecb(data: bytes) -> bytes:
    """Decrypt data using AES-128 ECB."""
    cipher = AES.new(AES_KEY, AES.MODE_ECB)
    return cipher.decrypt(data)

def main():
    # Load the dataset
    dataset_path = Path("data/processed/usb_master_dataset.parquet")
    df = pl.read_parquet(dataset_path)

    # Filter for reading_logs0.11 capture
    logs_df = df.filter(pl.col("source_file").str.contains("reading_logs"))
    print(f"Packets in reading_logs capture: {len(logs_df)}")

    # First, find the Unknown68 response to check encryption flag
    bulk_in = logs_df.filter(
        (pl.col("endpoint_address") == "0x81") &
        (pl.col("urb_type") == "C") &
        pl.col("payload_hex").is_not_null()
    )

    print(f"\nBulk IN completions: {len(bulk_in)}")

    # Find Unknown68 responses (type 0x44 or 0xC4)
    print(f"\n--- Unknown68 Responses (looking for encryption flag) ---")
    for row in bulk_in.iter_rows(named=True):
        payload_hex = row["payload_hex"]
        if payload_hex:
            payload = bytes.fromhex(payload_hex)
            pkt_type = payload[0] & 0x7F
            if pkt_type == 0x44 and len(payload) == 20:  # Unknown68 response
                header_u32 = struct.unpack('<I', payload[:4])[0]
                bit16 = (header_u32 >> 16) & 1
                print(f"  Frame {row['frame_number']}: type=0x{pkt_type:02X}, bit16={bit16}")
                print(f"    Raw: {payload.hex()}")
                # Decrypt the 16-byte payload
                if len(payload) >= 20:
                    encrypted_resp = payload[4:20]
                    decrypted_resp = decrypt_ecb(encrypted_resp)
                    print(f"    Decrypted: {decrypted_resp.hex()}")
                    addr, size, marker, crc = struct.unpack('<IIII', decrypted_resp)
                    print(f"    Parsed: addr=0x{addr:08X}, size={size}, marker=0x{marker:08X}, crc=0x{crc:08X}")

    # Find large chunks (> 500 bytes)
    large_chunks = []
    for row in bulk_in.iter_rows(named=True):
        payload_hex = row["payload_hex"]
        if payload_hex and len(payload_hex) > 1000:  # > 500 bytes
            payload = bytes.fromhex(payload_hex)
            pkt_type = payload[0] & 0x7F if payload else 0
            print(f"  Frame {row['frame_number']}: type=0x{pkt_type:02X}, size={len(payload)}")
            large_chunks.append((row["frame_number"], payload))

    print(f"\nFound {len(large_chunks)} large chunks")

    if not large_chunks:
        print("No large chunks found!")
        return

    # Analyze chunk headers first
    print(f"\n--- Chunk Header Analysis ---")
    for frame, payload in large_chunks:
        header = payload[:4]
        pkt_type = header[0] & 0x7F
        tid = header[1]
        flags = struct.unpack('<H', header[2:4])[0]
        bit16 = (struct.unpack('<I', header)[0] >> 16) & 1
        print(f"  Frame {frame}: type=0x{pkt_type:02X}, tid={tid}, flags=0x{flags:04X}, bit16={bit16}")
        print(f"    Raw header: {header.hex()}")

    # Best result: decrypt entire payload including header bytes (skip=0)
    print(f"\n=== Decrypting full chunks (no header skip) ===")
    all_data = b""
    for frame, payload in large_chunks:
        chunk_data = payload  # Use entire payload

        # Decrypt - ensure alignment
        if len(chunk_data) % 16 != 0:
            padding = 16 - (len(chunk_data) % 16)
            chunk_data += b'\x00' * padding
        decrypted_chunk = decrypt_ecb(chunk_data)
        all_data += decrypted_chunk

    print(f"Total decrypted: {len(all_data)} bytes")

    decrypted = all_data

    # Parse as 16-byte samples
    num_samples = len(decrypted) // 16
    print(f"Number of 16-byte samples: {num_samples} (expected 521)")

    # Collect all fields
    samples = []
    for i in range(num_samples):
        sample = decrypted[i*16:(i+1)*16]
        v0, v1, v2, v3 = struct.unpack('<iiii', sample)
        samples.append((v0, v1, v2, v3))

    # Analyze each field
    print(f"\n--- Field Analysis ---")
    for field_idx in range(4):
        values = [s[field_idx] for s in samples]
        min_v = min(values)
        max_v = max(values)
        avg_v = sum(values) / len(values)
        print(f"Field {field_idx}: min={min_v:>12}, max={max_v:>12}, avg={avg_v:>12.0f}")
        if 1_000_000 < avg_v < 30_000_000:
            print(f"         -> Likely VOLTAGE: {avg_v/1e6:.3f} V (range {min_v/1e6:.3f} - {max_v/1e6:.3f} V)")
        elif abs(avg_v) < 10_000_000 and avg_v != 0:
            print(f"         -> Likely CURRENT: {avg_v/1e6:.6f} A ({avg_v/1e3:.3f} mA)")

    # Show first 10 and last 10 samples
    print(f"\n--- First 10 Samples ---")
    print(f"{'#':>4} {'Voltage(V)':>12} {'Current(A)':>12} {'Field2':>12} {'Field3':>12}")
    for i, (v0, v1, v2, v3) in enumerate(samples[:10]):
        print(f"{i:4} {v0:12} {v1:12} {v2:12} {v3:12}")

    # Check for monotonic timestamps
    for field_idx in range(4):
        values = [s[field_idx] for s in samples]
        diffs = [values[i+1] - values[i] for i in range(len(values)-1)]
        if all(d >= 0 for d in diffs) and max(diffs) > 0:
            print(f"\nField {field_idx} is monotonically increasing!")
            print(f"  First: {values[0]}, Last: {values[-1]}")
            print(f"  Min delta: {min(diffs)}, Max delta: {max(diffs)}, Avg delta: {sum(diffs)/len(diffs):.0f}")


if __name__ == "__main__":
    main()
