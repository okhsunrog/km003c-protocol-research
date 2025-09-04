#!/usr/bin/env python3
"""
Functions for parsing the KM003C USB protocol.
"""

from __future__ import annotations
import struct
from enum import Enum
from dataclasses import dataclass
from typing import Optional, Union, Tuple
import polars as pl

# Based on packet.rs

class PacketType(Enum):
    SYNC = 0x01
    CONNECT = 0x02
    DISCONNECT = 0x03
    RESET = 0x04
    ACCEPT = 0x05
    REJECTED = 0x06
    FINISHED = 0x07
    JUMP_APROM = 0x08
    JUMP_DFU = 0x09
    GET_STATUS = 0x0A
    ERROR = 0x0B
    GET_DATA = 0x0C
    GET_FILE = 0x0D
    HEAD = 0x40
    PUT_DATA = 0x41
    UNKNOWN = 0xFF

    @classmethod
    def from_byte(cls, byte: int) -> PacketType:
        try:
            return cls(byte & 0x7F)
        except ValueError:
            return cls.UNKNOWN

    def is_ctrl_type(self) -> bool:
        return self.value < 0x40

class Attribute(Enum):
    NONE = 0x00
    ADC = 0x01
    ADC_QUEUE = 0x02
    ADC_QUEUE_10K = 0x04
    SETTINGS = 0x08
    PD_PACKET = 0x10
    PD_STATUS = 0x20
    QC_PACKET = 0x40
    UNKNOWN = 0xFFFF

    @classmethod
    def from_u16(cls, val: int) -> Attribute:
        try:
            return cls(val)
        except ValueError:
            return cls.UNKNOWN

@dataclass
class CtrlHeader:
    packet_type: PacketType
    extend: bool
    id: int
    attribute: Attribute

    @classmethod
    def from_bytes(cls, data: bytes) -> CtrlHeader:
        val, = struct.unpack('<I', data)
        packet_type = PacketType.from_byte(val & 0x7F)
        extend = (val >> 7) & 0x01
        transaction_id = (val >> 8) & 0xFF
        attribute = Attribute.from_u16((val >> 16) & 0x7FFF)
        return cls(packet_type, bool(extend), transaction_id, attribute)

@dataclass
class DataHeader:
    packet_type: PacketType
    extend: bool
    id: int
    obj_count_words: int

    @classmethod
    def from_bytes(cls, data: bytes) -> DataHeader:
        val, = struct.unpack('<I', data)
        packet_type = PacketType.from_byte(val & 0x7F)
        extend = (val >> 7) & 0x01
        transaction_id = (val >> 8) & 0xFF
        obj_count_words = (val >> 22) & 0x03FF
        return cls(packet_type, bool(extend), transaction_id, obj_count_words)

@dataclass
class ExtendedHeader:
    attribute: Attribute
    next: bool
    chunk: int
    size: int

    @classmethod
    def from_bytes(cls, data: bytes) -> ExtendedHeader:
        val, = struct.unpack('<I', data)
        attribute = Attribute.from_u16(val & 0x7FFF)
        next_val = (val >> 15) & 0x01
        chunk = (val >> 16) & 0x3F
        size = (val >> 22) & 0x03FF
        return cls(attribute, bool(next_val), chunk, size)

# Based on adc.rs
@dataclass
class AdcData:
    vbus_v: float
    ibus_a: float
    power_w: float
    vbus_avg_v: float
    ibus_avg_a: float
    temp_c: float
    cc1_v: float
    cc2_v: float
    vdp_v: float
    vdm_v: float
    internal_vdd_v: float
    rate: int
    cc2_avg_v: float
    vdp_avg_v: float
    vdm_avg_v: float

    @classmethod
    def from_raw_bytes(cls, data: bytes) -> Optional[AdcData]:
        fmt = '<iiiiiihHHHHHBBHHH'
        if len(data) < struct.calcsize(fmt):
            return None
        
        raw = struct.unpack(fmt, data[:struct.calcsize(fmt)])
        
        vbus_v = raw[0] / 1_000_000.0
        ibus_a = raw[1] / 1_000_000.0
        
        temp_raw = raw[6]
        temp_bytes = temp_raw.to_bytes(2, byteorder='little', signed=True)
        # Most literal port of the Rust formula's comment
        temp_c = (float(temp_bytes[1]) * 2000.0 + float(temp_bytes[0]) * (1000.0 / 128.0)) / 1000.0

        return cls(
            vbus_v=vbus_v,
            ibus_a=ibus_a,
            power_w=vbus_v * ibus_a,
            vbus_avg_v=raw[2] / 1_000_000.0,
            ibus_avg_a=raw[3] / 1_000_000.0,
            temp_c=temp_c,
            cc1_v=raw[7] / 10_000.0,
            cc2_v=raw[8] / 10_000.0,
            vdp_v=raw[9] / 10_000.0,
            vdm_v=raw[10] / 10_000.0,
            internal_vdd_v=raw[11] / 10_000.0,
            rate=raw[12],
            cc2_avg_v=raw[14] / 10_000.0,
            vdp_avg_v=raw[15] / 10_000.0,
            vdm_avg_v=raw[16] / 10_000.0,
        )

# Based on message.rs
@dataclass
class ParsedPacket:
    packet_type: str
    data: Optional[Union[AdcData, bytes]] = None

def parse_payload(payload_bytes: bytes) -> ParsedPacket:
    """High-level parser that classifies and parses a raw payload."""
    if len(payload_bytes) < 4:
        return ParsedPacket("UNKNOWN")

    header_bytes = payload_bytes[:4]
    packet_type = PacketType.from_byte(header_bytes[0])
    
    if packet_type.is_ctrl_type():
        header = CtrlHeader.from_bytes(header_bytes)
        if header.packet_type == PacketType.GET_DATA and header.attribute == Attribute.ADC:
            return ParsedPacket("GET_DATA_ADC")
    else: # Data Packet
        header = DataHeader.from_bytes(header_bytes)
        if header.packet_type == PacketType.PUT_DATA and len(payload_bytes) >= 8:
            ext_header = ExtendedHeader.from_bytes(payload_bytes[4:8])
            if ext_header.attribute == Attribute.ADC:
                adc_data = AdcData.from_raw_bytes(payload_bytes[8:])
                if adc_data:
                    return ParsedPacket("ADC_DATA", data=adc_data)
                else:
                    return ParsedPacket("INVALID_ADC_PACKET")

    return ParsedPacket("UNKNOWN")

# Polars helper for applying the parser to a DataFrame
def apply_parser_to_df(df: pl.DataFrame) -> pl.DataFrame:
    """Applies the full packet parser to a DataFrame, returning classified packets."""
    
    def hex_to_packet_type(payload_hex: str) -> str:
        if not payload_hex: return "UNKNOWN"
        try:
            return parse_payload(bytes.fromhex(payload_hex)).packet_type
        except (ValueError, TypeError):
            return "UNKNOWN"

    return df.with_columns(
        pl.col("payload_hex")
        .map_elements(hex_to_packet_type, return_dtype=pl.Utf8)
        .alias("packet_type")
    )
