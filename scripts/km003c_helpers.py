"""
Helper functions for working with km003c_lib's Python API.

PayloadData enum variants are serialized by PyO3 as:
- Known types (Adc, AdcQueue, PdStatus, PdEvents) -> bare class instances
- Unknown payloads -> dict with 'attribute' and 'data' keys
"""

from km003c_lib import AdcData, AdcQueueData, PdStatus, PdEventStream


def get_packet_type(packet):
    """Extract packet type from dict-based Packet.

    Args:
        packet: Parsed packet dict from parse_packet()

    Returns:
        str: Packet type ("DataResponse", "GetData", "Connect", etc.)
    """
    if isinstance(packet, dict) and len(packet) > 0:
        return list(packet.keys())[0]
    return None


def get_adc_data(packet):
    """Extract ADC data from DataResponse packet.

    Args:
        packet: Parsed packet dict from parse_packet()

    Returns:
        AdcData or None: The ADC data if present
    """
    if not isinstance(packet, dict) or "DataResponse" not in packet:
        return None
    payloads = packet["DataResponse"]["payloads"]
    for payload in payloads:
        if isinstance(payload, AdcData):
            return payload
    return None


def get_adcqueue_data(packet):
    """Extract AdcQueue data from DataResponse packet.

    Args:
        packet: Parsed packet dict from parse_packet()

    Returns:
        AdcQueueData or None: The AdcQueue data if present
    """
    if not isinstance(packet, dict) or "DataResponse" not in packet:
        return None
    payloads = packet["DataResponse"]["payloads"]
    for payload in payloads:
        if isinstance(payload, AdcQueueData):
            return payload
    return None


def get_pd_status(packet):
    """Extract PD status from DataResponse packet.

    Args:
        packet: Parsed packet dict from parse_packet()

    Returns:
        PdStatus or None: The PD status if present
    """
    if not isinstance(packet, dict) or "DataResponse" not in packet:
        return None
    payloads = packet["DataResponse"]["payloads"]
    for payload in payloads:
        if isinstance(payload, PdStatus):
            return payload
    return None


def get_pd_events(packet):
    """Extract PD events from DataResponse packet.

    Args:
        packet: Parsed packet dict from parse_packet()

    Returns:
        PdEventStream or None: The PD events if present
    """
    if not isinstance(packet, dict) or "DataResponse" not in packet:
        return None
    payloads = packet["DataResponse"]["payloads"]
    for payload in payloads:
        if isinstance(payload, PdEventStream):
            return payload
    return None


def get_all_payloads(packet):
    """Get all payloads from a DataResponse packet.

    Args:
        packet: Parsed packet dict from parse_packet()

    Returns:
        list: List of payload objects, or empty list if not DataResponse
    """
    if not isinstance(packet, dict) or "DataResponse" not in packet:
        return []
    return packet["DataResponse"]["payloads"]


def get_attribute_mask(packet):
    """Extract attribute mask from GetData packet.

    Args:
        packet: Parsed packet dict from parse_packet()

    Returns:
        int or None: The attribute mask if this is a GetData packet
    """
    if not isinstance(packet, dict) or "GetData" not in packet:
        return None
    return packet["GetData"]["attribute_mask"]


# Wrapper class for backward compatibility
class PacketWrapper:
    """Wrapper to provide attribute-based access to dict-based packets.

    This provides a migration path for code that expects the old API.
    """

    def __init__(self, packet_dict):
        self._packet = packet_dict
        self._packet_type = get_packet_type(packet_dict)

    @property
    def packet_type(self):
        return self._packet_type

    @property
    def adc_data(self):
        return get_adc_data(self._packet)

    @property
    def adcqueue_data(self):
        return get_adcqueue_data(self._packet)

    @property
    def pd_status(self):
        return get_pd_status(self._packet)

    @property
    def pd_events(self):
        return get_pd_events(self._packet)

    @property
    def payloads(self):
        return get_all_payloads(self._packet)

    @property
    def attribute_mask(self):
        return get_attribute_mask(self._packet)

    @property
    def raw_packet(self):
        """Get the underlying dict representation."""
        return self._packet
