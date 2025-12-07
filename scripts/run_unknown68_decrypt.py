#!/usr/bin/env python3
"""
Analyze Unknown68 packets - try to decrypt the request payloads.
"""

from Crypto.Cipher import AES

# Keys from Ghidra analysis
KEYS = {
    0: b"Lh2yfB7n6X7d9a5Z",  # Download requests
    1: b"sdkW78R3k5dj0fHv",
    2: b"Uy34VW13jHj3598e",
    3: b"Fa0b4tA25f4R038a",  # Unknown76 auth
}

# Captured Unknown68 packets (first 16 bytes of payload = encrypted data)
packets = [
    ("33f8860c0054288cdc7e52729826872d", "Packet 1 (addr=0x420, size=0x40)"),
    ("636beaf3f0856506eee9a27e89722dcf", "Packet 2"),
    ("c51167ae613a6d46ec84a6bde8bd462a", "Packet 3 (addr=0x3000c00, size=0x40)"),
    ("9c409debc8df53b83b066c315250d05c", "Packet 4"),
]

# The constant last 16 bytes in all packets
CONSTANT_KEY = bytes.fromhex("d18b539a39c407d5c063d91102e36a9e")

print("Trying to decrypt Unknown68 request payloads:\n")

for key_idx, key in KEYS.items():
    print(f"=== Using Key {key_idx}: {key.decode()} ===")
    cipher = AES.new(key, AES.MODE_ECB)

    for enc_hex, desc in packets:
        enc_bytes = bytes.fromhex(enc_hex)
        dec_bytes = cipher.decrypt(enc_bytes)
        print(f"  {desc}:")
        print(f"    Encrypted: {enc_hex}")
        print(f"    Decrypted: {dec_bytes.hex()}")

        # Try to parse as address/size
        if len(dec_bytes) >= 8:
            addr = int.from_bytes(dec_bytes[0:4], 'little')
            size = int.from_bytes(dec_bytes[4:8], 'little')
            print(f"    As addr/size: 0x{addr:08X} / 0x{size:X}")
        print()

    print()

# Also try decrypting the constant key
print("=== Decrypting the constant key ===")
for key_idx, key in KEYS.items():
    cipher = AES.new(key, AES.MODE_ECB)
    dec = cipher.decrypt(CONSTANT_KEY)
    print(f"  Key {key_idx}: {dec.hex()}")
    # Try as ASCII
    try:
        ascii_str = dec.decode('ascii', errors='replace')
        print(f"         ASCII: {ascii_str}")
    except:
        pass
