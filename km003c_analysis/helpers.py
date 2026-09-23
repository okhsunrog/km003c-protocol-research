"""Helper functions for working with the `km003c` Python API.

`parse_packet()` returns a one-key dictionary naming the active enum variant.
Inside a ``DataResponse`` the payload list mixes native classes (AdcData,
AdcQueueData, PdStatus, PdEventStream, ...) with plain dictionaries for
payloads the library does not model yet.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any, NamedTuple, TypeVar

from km003c import AdcData, AdcQueueData, AdcQueueRawData, PdEventStream, PdStatus

__all__ = [
    "PdWireMessage",
    "get_adc_data",
    "get_adcqueue_data",
    "get_adcqueue_raw_data",
    "get_all_payloads",
    "get_attribute_mask",
    "get_packet_type",
    "get_pd_events",
    "get_pd_status",
    "iter_pd_messages",
    "pd_event_kind",
    "pd_message_sop",
    "pd_message_wire",
]

T = TypeVar("T")

Packet = dict[str, Any]


def get_packet_type(packet: object) -> str | None:
    """Name of the active `Packet` variant, e.g. ``"DataResponse"``."""
    if isinstance(packet, dict) and packet:
        return str(next(iter(packet)))
    return None


def get_all_payloads(packet: object) -> list[Any]:
    """All payloads of a DataResponse packet, or an empty list."""
    if not isinstance(packet, dict) or "DataResponse" not in packet:
        return []
    payloads: list[Any] = packet["DataResponse"]["payloads"]
    return payloads


def _find_payload(packet: object, payload_type: type[T]) -> T | None:
    """First payload of `payload_type` in a DataResponse packet."""
    for payload in get_all_payloads(packet):
        if isinstance(payload, payload_type):
            return payload
    return None


def get_adc_data(packet: object) -> AdcData | None:
    """ADC measurements from a DataResponse packet, if present."""
    return _find_payload(packet, AdcData)


def get_adcqueue_data(packet: object) -> AdcQueueData | None:
    """Rate-decoded AdcQueue samples from a DataResponse packet, if present."""
    return _find_payload(packet, AdcQueueData)


def get_adcqueue_raw_data(packet: object) -> AdcQueueRawData | None:
    """AdcQueue samples parsed without a known graph rate, if present.

    `parse_packet()` produces this variant; `parse_packet_with_graph_rate()`
    produces :func:`get_adcqueue_data` instead.
    """
    return _find_payload(packet, AdcQueueRawData)


def get_pd_status(packet: object) -> PdStatus | None:
    """12-byte PD measurement block from a DataResponse packet, if present."""
    return _find_payload(packet, PdStatus)


def get_pd_events(packet: object) -> PdEventStream | None:
    """PD event stream from a DataResponse packet, if present."""
    return _find_payload(packet, PdEventStream)


def get_attribute_mask(packet: object) -> int | None:
    """Attribute bitmask of a GetData packet, if this is one."""
    if not isinstance(packet, dict) or "GetData" not in packet:
        return None
    mask: int = packet["GetData"]["attribute_mask"]
    return mask


# --- PD events --------------------------------------------------------------
#
# `PdEvent.data` is a one-key dictionary naming the event variant, the same
# convention `parse_packet()` uses for packets:
#
#     {"Connect": None}
#     {"Disconnect": None}
#     {"PdMessage": {"sop": int, "wire_data": list[int]}}
#
# km003c 0.3 and earlier exposed Connect and Disconnect as a bare `None` and a
# PD message as the inner dictionary alone. Reading events only through these
# helpers keeps a future change of that shape to a single file.


class PdWireMessage(NamedTuple):
    """One USB PD message captured on the wire."""

    timestamp_ms: float
    sop: int
    wire: bytes


def _pd_message_body(event: object) -> dict[str, Any] | None:
    data = getattr(event, "data", None)
    if isinstance(data, dict):
        body = data.get("PdMessage")
        if isinstance(body, dict):
            return body
    return None


def pd_event_kind(event: object) -> str | None:
    """Variant of a PD event: ``"Connect"``, ``"Disconnect"`` or ``"PdMessage"``."""
    data = getattr(event, "data", None)
    if isinstance(data, dict) and len(data) == 1:
        return str(next(iter(data)))
    return None


def pd_message_wire(event: object) -> bytes | None:
    """Raw USB PD wire bytes of a PdMessage event, or None for other events."""
    body = _pd_message_body(event)
    if body is None:
        return None
    return bytes(body.get("wire_data") or b"")


def pd_message_sop(event: object) -> int | None:
    """SOP type of a PdMessage event, or None for other events."""
    body = _pd_message_body(event)
    if body is None or body.get("sop") is None:
        return None
    return int(body["sop"])


def iter_pd_messages(source: object) -> Iterator[PdWireMessage]:
    """PD messages with wire bytes from a packet or a PdEventStream.

    Connection events and messages without wire bytes are skipped.
    """
    stream = source if isinstance(source, PdEventStream) else get_pd_events(source)
    if stream is None:
        return
    for event in stream.events:
        wire = pd_message_wire(event)
        sop = pd_message_sop(event)
        if wire and sop is not None:
            yield PdWireMessage(float(event.timestamp), sop, wire)
