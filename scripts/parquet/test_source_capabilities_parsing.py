#!/usr/bin/env python3
"""
Re-test Source_Capabilities parsing with usbpdpy v0.2.0

The research findings identified 26-byte PD messages in SQLite data that were
previously mislabeled as GoodCRC. With usbpdpy v0.2.0, let's test if these
now parse correctly as Source_Capabilities.

Based on findings: 26 bytes = 2-byte header + 6×4-byte PDOs
"""

import usbpdpy
from pathlib import Path


def test_source_capabilities_candidates():
    """Test the 26-byte Source_Capabilities candidates from SQLite data."""

    print("=== SOURCE_CAPABILITIES RE-TEST WITH USBPDPY v0.2.0 ===")
    print(f"Using usbpdpy version: {usbpdpy.__version__}")
    print()

    # From protocol_research_findings_wip.md - the 26-byte candidates
    candidates = [
        {
            "description": "Time 6.297s, ts=6297, wire_len=26",
            "header": "a1 61",
            "pdo_data": "2c 91 01 08 2c d1 02 00 2c c1 03 00 2c b1 04 00 45 41 06 00 3c 21 dc c0",
            "full_hex": "a1612c91010826d102002cc103002cb1040045410600c21dcm0"  # Will construct properly
        },
        {
            "description": "Time 6.448s, ts=6448, different header",
            "header": "a1 63",
            "pdo_data": "2c 91 01 08 2c d1 02 00 2c c1 03 00 2c b1 04 00 45 41 06 00 3c 21 dc c0",
            "full_hex": "a1632c91010826d102002cc103002cb1040045410600c21dcm0"  # Will construct properly
        }
    ]

    # Construct the actual hex strings (header + PDOs)
    candidates[0]["full_hex"] = "a1612c91010828d102002cc103002cb104004541060031c21dcc0"  # Fixed construction
    candidates[1]["full_hex"] = "a1632c91010828d102002cc103002cb104004541060031c21dcc0"  # Fixed construction

    # Actually, let me construct this more carefully from the documented structure
    candidate_wires = [
        # Time 6.297s - header a1 61 + 6 PDOs
        "a161" + "2c910108" + "2cd10200" + "2cc10300" + "2cb10400" + "45410600" + "3c21dcc0",
        # Time 6.448s - header a1 63 + same 6 PDOs
        "a163" + "2c910108" + "2cd10200" + "2cc10300" + "2cb10400" + "45410600" + "3c21dcc0"
    ]

    for i, wire_hex in enumerate(candidate_wires):
        candidate = candidates[i]
        print(f"--- Candidate {i+1}: {candidate['description']} ---")
        print(f"Wire hex: {wire_hex}")
        print(f"Length: {len(wire_hex)//2} bytes")

        try:
            # Convert hex to bytes
            wire_bytes = bytes.fromhex(wire_hex)

            # Parse with usbpdpy v0.2.0
            msg = usbpdpy.parse_pd_message(wire_bytes)

            print(f"✅ Parsed successfully!")
            print(f"Message type: {msg.header.message_type}")
            print(f"Number of data objects: {len(msg.data_objects)}")

            if msg.header.message_type == "Source_Capabilities":
                print("🎉 CORRECTLY IDENTIFIED AS SOURCE_CAPABILITIES!")

                print("\nPDO Analysis:")
                for j, pdo in enumerate(msg.data_objects):
                    print(f"  PDO{j+1}: {pdo.pdo_type}")
                    print(f"    Voltage: {pdo.voltage_v}V")
                    print(f"    Max Current: {pdo.max_current_a}A")
                    print(f"    Max Power: {pdo.max_power_w}W")
                    if hasattr(pdo, 'unconstrained_power'):
                        print(f"    Unconstrained: {pdo.unconstrained_power}")
                    print()
            else:
                print(f"⚠️  Still parsing as: {msg.header.message_type}")
                print("May need further investigation...")

        except Exception as e:
            print(f"❌ Parsing failed: {e}")

        print("-" * 60)
        print()


def test_various_pd_message_lengths():
    """Test parsing various PD message structures to understand the format."""

    print("=== TESTING VARIOUS PD MESSAGE PATTERNS ===")

    # Test some known good PD messages from the dataset for comparison
    test_cases = [
        {
            "name": "Typical GoodCRC (2 bytes)",
            "hex": "a1c1"  # From previous findings
        },
        {
            "name": "4-byte message test",
            "hex": "a1610100"
        },
        {
            "name": "26-byte Source_Capabilities candidate",
            "hex": "a1612c91010828d102002cc103002cb104004541060033c21dcc0"
        }
    ]

    for case in test_cases:
        print(f"--- {case['name']} ---")
        print(f"Hex: {case['hex']}")
        print(f"Length: {len(case['hex'])//2} bytes")

        try:
            wire_bytes = bytes.fromhex(case['hex'])
            msg = usbpdpy.parse_pd_message(wire_bytes)

            print(f"✅ Message type: {msg.header.message_type}")
            print(f"Data objects: {len(msg.data_objects)}")

            if hasattr(msg, 'data_objects') and msg.data_objects:
                for i, obj in enumerate(msg.data_objects):
                    print(f"  Object {i}: {type(obj).__name__}")

        except Exception as e:
            print(f"❌ Parse error: {e}")

        print()


if __name__ == "__main__":
    test_source_capabilities_candidates()
    test_various_pd_message_lengths()