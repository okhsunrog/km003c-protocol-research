#!/usr/bin/env python3
"""Decrypt KM003C .mencrypt firmware files."""

import struct
from pathlib import Path
from Crypto.Cipher import AES

# Known AES keys from Mtools.exe reverse engineering (all 4 extracted)
KEYS = {
    0: b"Lh2yfB7n6X7d9a5Z",  # Unknown68 memory download
    1: b"sdkW78R3k5dj0fHv",  # Key 1
    2: b"Uy34VW13jHj3598e",  # Key 2
    3: b"Fa0b4tA25f4R038a",  # Unknown76 auth
}


def read_qstring(data: bytes, offset: int) -> tuple[str, int]:
    """Read a Qt QString from QDataStream format.

    Returns (string_value, new_offset)
    """
    # QString format: 4-byte BE length (in bytes, not chars) + UTF-16BE content
    if offset + 4 > len(data):
        return "", offset

    byte_len = struct.unpack(">I", data[offset:offset+4])[0]
    offset += 4

    if byte_len == 0xFFFFFFFF:  # Null QString
        return "", offset

    if offset + byte_len > len(data):
        return "", offset

    string_data = data[offset:offset+byte_len]
    offset += byte_len

    # Decode UTF-16BE
    try:
        return string_data.decode('utf-16-be'), offset
    except:
        return string_data.hex(), offset


def read_qbytearray(data: bytes, offset: int) -> tuple[bytes, int]:
    """Read a Qt QByteArray from QDataStream format.

    Returns (bytes_value, new_offset)
    """
    if offset + 4 > len(data):
        return b"", offset

    length = struct.unpack(">I", data[offset:offset+4])[0]
    offset += 4

    if length == 0xFFFFFFFF:  # Null QByteArray
        return b"", offset

    if offset + length > len(data):
        # Return remaining data
        return data[offset:], len(data)

    return data[offset:offset+length], offset + length


def parse_mencrypt(filepath: Path) -> dict:
    """Parse a .mencrypt firmware file."""
    data = filepath.read_bytes()
    print(f"File size: {len(data)} bytes")

    offset = 0

    # Read string count (4 bytes big-endian)
    string_count = struct.unpack(">I", data[offset:offset+4])[0]
    offset += 4
    print(f"String count: {string_count}")

    # Read all strings
    strings = []
    for i in range(string_count):
        s, offset = read_qstring(data, offset)
        strings.append(s)
        print(f"  String {i}: {s[:80]}{'...' if len(s) > 80 else ''}")

    print(f"\nOffset after strings: 0x{offset:x} ({offset} bytes)")
    print(f"Remaining data: {len(data) - offset} bytes")

    # The rest should be the firmware binary (possibly as QByteArray or raw)
    remaining = data[offset:]

    return {
        "strings": strings,
        "binary_offset": offset,
        "binary_data": remaining,
    }


def try_decrypt_aes_ecb(data: bytes, key: bytes) -> bytes:
    """Try AES-ECB decryption."""
    # Ensure data is multiple of 16 bytes
    if len(data) % 16 != 0:
        # Truncate to multiple of 16
        data = data[:len(data) // 16 * 16]

    cipher = AES.new(key, AES.MODE_ECB)
    return cipher.decrypt(data)


def try_decrypt_aes_cbc(data: bytes, key: bytes, iv: bytes = None) -> bytes:
    """Try AES-CBC decryption with zero IV."""
    if iv is None:
        iv = b'\x00' * 16
    if len(data) % 16 != 0:
        data = data[:len(data) // 16 * 16]
    cipher = AES.new(key, AES.MODE_CBC, iv)
    return cipher.decrypt(data)


def check_firmware_signature(decrypted: bytes, mode_name: str):
    """Check if decrypted data looks like valid firmware."""
    # Check for common firmware signatures
    if decrypted[:4] == b'\x7fELF':
        print(f"  [{mode_name}] -> Found ELF signature!")
        return True
    if decrypted[:4] == b'\x89PNG':
        print(f"  [{mode_name}] -> Found PNG signature!")
        return True
    if decrypted[:2] == b'PK':
        print(f"  [{mode_name}] -> Found ZIP/PK signature!")
        return True

    # Check for ARM Cortex-M vector table patterns
    # Stack pointer usually at 0x20000000+ range, reset handler at 0x08000000+
    try:
        sp = struct.unpack("<I", decrypted[:4])[0]
        reset = struct.unpack("<I", decrypted[4:8])[0]
        if 0x20000000 <= sp <= 0x20100000 and 0x08000000 <= reset <= 0x08100000:
            print(f"  [{mode_name}] -> ARM Cortex-M vector table!")
            print(f"     SP: 0x{sp:08x}, Reset: 0x{reset:08x}")
            return True
    except:
        pass

    # Check for high entropy of printable ASCII
    try:
        text = decrypted[:64].decode('ascii')
        if text.isprintable() and len(text) > 32:
            print(f"  [{mode_name}] -> ASCII text: {text[:60]}...")
            return True
    except:
        pass

    return False


def analyze_binary(data: bytes, keys: dict):
    """Analyze the binary portion of the firmware."""
    print(f"\nBinary data analysis:")
    print(f"  Size: {len(data)} bytes")
    print(f"  First 64 bytes hex: {data[:64].hex()}")

    # Check if it starts with a QByteArray length prefix
    raw_data = data
    if len(data) >= 4:
        possible_len = struct.unpack(">I", data[:4])[0]
        print(f"  First 4 bytes as BE uint32: {possible_len}")
        if abs(possible_len - (len(data) - 4)) < 16:  # Allow small difference
            print("  -> Likely QByteArray format, skipping length prefix.")
            data = data[4:]

    # Try decryption with each key and mode
    for key_id, key in keys.items():
        print(f"\nTrying key {key_id}: {key.decode('ascii', errors='replace')}")

        # Try ECB mode
        try:
            decrypted = try_decrypt_aes_ecb(data[:1024], key)
            print(f"  ECB first 32 bytes: {decrypted[:32].hex()}")
            found = check_firmware_signature(decrypted, "ECB")

            # Check for vector table with flexible base addresses
            sp = struct.unpack("<I", decrypted[:4])[0]
            if 0x20000000 <= sp <= 0x20100000:
                print(f"  [ECB] -> Valid SP detected: 0x{sp:08x}")
                reset = struct.unpack("<I", decrypted[4:8])[0]
                print(f"  [ECB] -> Reset vector: 0x{reset:08x}")
                # Decrypt full firmware
                full_dec = try_decrypt_aes_ecb(data, key)
                dec_path = Path(f"/home/okhsunrog/code/km003c-protocol-research/fw/KM003C_V1.9.9_key{key_id}_ecb.bin")
                dec_path.write_bytes(full_dec)
                print(f"  Saved decrypted ECB to: {dec_path}")

        except Exception as e:
            print(f"  ECB Error: {e}")

        # Try CBC mode with zero IV
        try:
            decrypted = try_decrypt_aes_cbc(data[:1024], key)
            print(f"  CBC first 32 bytes: {decrypted[:32].hex()}")
            if check_firmware_signature(decrypted, "CBC"):
                # Full decryption
                full_dec = try_decrypt_aes_cbc(data, key)
                dec_path = Path(f"/home/okhsunrog/code/km003c-protocol-research/fw/KM003C_V1.9.9_key{key_id}_cbc.bin")
                dec_path.write_bytes(full_dec)
                print(f"  Saved decrypted to: {dec_path}")
        except Exception as e:
            print(f"  CBC Error: {e}")


def main():
    fw_path = Path("/home/okhsunrog/code/km003c-protocol-research/fw/KM003C_V1.9.9.mencrypt")

    if not fw_path.exists():
        print(f"Firmware file not found: {fw_path}")
        return

    result = parse_mencrypt(fw_path)
    analyze_binary(result["binary_data"], KEYS)

    # Save raw binary for further analysis
    raw_path = fw_path.with_suffix(".raw")
    raw_path.write_bytes(result["binary_data"])
    print(f"\nSaved raw binary data to: {raw_path}")


if __name__ == "__main__":
    main()
