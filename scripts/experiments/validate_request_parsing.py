#!/usr/bin/env python3
"""
Validate Request message parsing using usbpdpy v0.2.0 state-aware API

This script demonstrates the correct usage of parse_pd_message_with_state()
for parsing Request messages with PDO context, as documented in the usbpdpy README.
"""

import usbpdpy


def test_request_parsing_with_state():
    """Test Request message parsing with PDO state as documented in usbpdpy README."""

    print("=== VALIDATING REQUEST PARSING WITH STATE ===")
    print(f"Using usbpdpy v{usbpdpy.__version__}")
    print()

    # From our SQLite findings - the actual messages from the negotiation
    source_caps_hex = "a1612c9101082cd102002cc103002cb10400454106003c21dcc0"  # 26 bytes
    request_hex = "8210dc700323"  # From pd_sqlite.py output: raw RDO 0x230370dc

    print("--- Step 1: Parse Source_Capabilities to get PDO state ---")
    source_bytes = bytes.fromhex(source_caps_hex)
    source_msg = usbpdpy.parse_pd_message(source_bytes)

    print(f"✅ Source_Capabilities parsed: {len(source_msg.data_objects)} PDOs")
    for i, pdo in enumerate(source_msg.data_objects):
        print(f"  PDO{i+1}: {pdo.pdo_type} {pdo.voltage_v}V @ {pdo.max_current_a}A = {pdo.max_power_w}W")
    print()

    print("--- Step 2: Parse Request WITHOUT state (basic parsing) ---")
    request_bytes = bytes.fromhex(request_hex)
    try:
        basic_request = usbpdpy.parse_pd_message(request_bytes)
        print(f"✅ Basic parsing: {basic_request.header.message_type}")
        print(f"Request objects: {len(basic_request.request_objects)}")
        if basic_request.request_objects:
            rdo = basic_request.request_objects[0]
            print(f"  RDO without state: position={rdo.object_position}, type={rdo.rdo_type}")
    except Exception as e:
        print(f"❌ Basic parsing failed: {e}")
    print()

    print("--- Step 3: Parse Request WITH PDO state (enhanced parsing) ---")
    try:
        enhanced_request = usbpdpy.parse_pd_message_with_state(
            request_bytes,
            source_msg.data_objects
        )

        print(f"✅ State-aware parsing: {enhanced_request.header.message_type}")
        print(f"Request objects: {len(enhanced_request.request_objects)}")

        if enhanced_request.request_objects:
            rdo = enhanced_request.request_objects[0]
            print(f"  Enhanced RDO parsing:")
            print(f"    └─ Object position: {rdo.object_position}")
            print(f"    └─ RDO type: {rdo.rdo_type}")
            print(f"    └─ Operating current: {rdo.operating_current_a}A")
            print(f"    └─ Max operating current: {rdo.max_operating_current_a}A")
            print(f"    └─ Capability mismatch: {rdo.capability_mismatch}")
            print(f"    └─ Raw RDO: 0x{rdo.raw:08x}")

            # Cross-reference with requested PDO
            if 1 <= rdo.object_position <= len(source_msg.data_objects):
                requested_pdo = source_msg.data_objects[rdo.object_position - 1]
                print(f"  Requested PDO details: {requested_pdo}")
                print(f"    └─ {requested_pdo.pdo_type}: {requested_pdo.voltage_v}V @ {requested_pdo.max_current_a}A = {requested_pdo.max_power_w}W")

    except Exception as e:
        print(f"❌ State-aware parsing failed: {e}")
    print()


def test_negotiation_sequence():
    """Test a complete negotiation sequence as shown in usbpdpy README."""

    print("=== TESTING COMPLETE NEGOTIATION SEQUENCE ===")

    # From the README example and our actual data
    messages = [
        "a1612c9101082cd102002cc103002cb10400454106003c21dcc0",  # Source_Capabilities
        "8210dc700323",  # Request
        "a305",          # Accept (if we have it)
        "a607",          # PS_RDY (if we have it)
    ]

    print("Parsing negotiation sequence:")

    # Parse Source_Capabilities
    source_msg = usbpdpy.parse_pd_message(bytes.fromhex(messages[0]))
    print(f"1. {source_msg.header.message_type}: {len(source_msg.data_objects)} PDOs")

    # Parse Request with state
    request_msg = usbpdpy.parse_pd_message_with_state(
        bytes.fromhex(messages[1]),
        source_msg.data_objects
    )
    print(f"2. {request_msg.header.message_type}: Requesting PDO #{request_msg.request_objects[0].object_position}")

    # Parse control messages (Accept, PS_RDY) - these don't need state
    for i, msg_hex in enumerate(messages[2:], 3):
        try:
            msg = usbpdpy.parse_pd_message(bytes.fromhex(msg_hex))
            print(f"{i}. {msg.header.message_type}")
        except Exception as e:
            print(f"{i}. Parse failed: {e}")

    print(f"\n✅ Negotiation: Sink requested {source_msg.data_objects[request_msg.request_objects[0].object_position - 1]}")


if __name__ == "__main__":
    test_request_parsing_with_state()
    test_negotiation_sequence()