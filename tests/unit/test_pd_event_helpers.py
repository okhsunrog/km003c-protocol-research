"""Capture-backed tests for the PD event accessors in km003c_analysis.helpers.

These accessors exist because km003c 0.4.0 changed `PdEvent.data` from a flat
dictionary to a one-key variant dictionary. Scripts that read it directly either
silently skipped every event after the upgrade, or had never worked at all: four
of them looked for a `wire_data` attribute that `PdEvent` has never had.
"""

import pytest
from km003c import parse_packet

from km003c_analysis.helpers import (
    PdWireMessage,
    get_pd_events,
    iter_pd_messages,
    pd_event_kind,
    pd_message_sop,
    pd_message_wire,
)

pytestmark = pytest.mark.unit

# Source: usb_master_dataset.parquet
CONNECT_PACKET = (
    "419dc20010008004def81200000000007406020045d4f8120011"  # orig_with_pd.13 #666
)
DISCONNECT_PACKET = (
    "413bc20010008004eb0d1300f1130000a80c7f0045cc0d130012"  # orig_with_pd.13 #1298
)
GOODCRC_PACKET = (  # pd_epr0.9 frame 1371
    "410d02011000000506ba0100876ef9ff0000030687d8b90100004102"
)


def only_event(packet_hex: str):
    stream = get_pd_events(parse_packet(bytes.fromhex(packet_hex)))
    assert stream is not None
    assert len(stream.events) == 1
    return stream.events[0]


@pytest.mark.parametrize(
    ("packet_hex", "kind"),
    [(CONNECT_PACKET, "Connect"), (DISCONNECT_PACKET, "Disconnect")],
)
def test_connection_events_have_a_kind_but_no_wire(packet_hex: str, kind: str) -> None:
    event = only_event(packet_hex)

    assert pd_event_kind(event) == kind
    assert pd_message_wire(event) is None
    assert pd_message_sop(event) is None


def test_pd_message_exposes_its_sop_and_wire_bytes() -> None:
    event = only_event(GOODCRC_PACKET)

    assert pd_event_kind(event) == "PdMessage"
    assert pd_message_sop(event) == 0
    assert pd_message_wire(event) == bytes.fromhex("4102")  # GoodCRC header


def test_iter_pd_messages_accepts_a_packet_or_a_stream() -> None:
    packet = parse_packet(bytes.fromhex(GOODCRC_PACKET))
    stream = get_pd_events(packet)

    from_packet = list(iter_pd_messages(packet))
    from_stream = list(iter_pd_messages(stream))

    assert from_packet == from_stream
    assert len(from_packet) == 1
    message = from_packet[0]
    assert isinstance(message, PdWireMessage)
    assert message.sop == 0
    assert message.wire == bytes.fromhex("4102")
    assert message.timestamp_ms == pytest.approx(113112.0)


def test_iter_pd_messages_skips_connection_events_and_non_pd_packets() -> None:
    assert list(iter_pd_messages(parse_packet(bytes.fromhex(CONNECT_PACKET)))) == []
    # A Connect control packet carries no PD event stream at all.
    assert list(iter_pd_messages(parse_packet(bytes.fromhex("02010000")))) == []
