#!/usr/bin/env python3
"""
Functions for parsing the KM003C USB protocol.
"""

from __future__ import annotations
from typing import Optional
import polars as pl

# This module is now a wrapper around the Rust native extension
# built with Maturin.
from km003c_lib import parse_packet, AdcData

def apply_parser_to_df(df: pl.DataFrame) -> pl.DataFrame:
    """
    Applies the Rust-based parser to a DataFrame, returning classified packets
    and parsed ADC data where applicable.
    """

    def parse_hex_payload(payload_hex: str) -> Optional[dict]:
        """Wrapper to handle hex decoding and call the Rust parser."""
        NULL_ADC_DICT = {
            'vbus_v': None, 'ibus_a': None, 'power_w': None, 'vbus_avg_v': None,
            'ibus_avg_a': None, 'temp_c': None, 'vdp_v': None, 'vdm_v': None,
            'vdp_avg_v': None, 'vdm_avg_v': None, 'cc1_v': None, 'cc2_v': None,
        }
        if not payload_hex:
            return NULL_ADC_DICT
        try:
            payload_bytes = bytes.fromhex(payload_hex)
            adc_data = parse_packet(payload_bytes)
            if adc_data:
                # Manually convert the Rust struct to a dictionary for Polars
                return {
                    'vbus_v': adc_data.vbus_v,
                    'ibus_a': adc_data.ibus_a,
                    'power_w': adc_data.power_w,
                    'vbus_avg_v': adc_data.vbus_avg_v,
                    'ibus_avg_a': adc_data.ibus_avg_a,
                    'temp_c': adc_data.temp_c,
                    'vdp_v': adc_data.vdp_v,
                    'vdm_v': adc_data.vdm_v,
                    'vdp_avg_v': adc_data.vdp_avg_v,
                    'vdm_avg_v': adc_data.vdm_avg_v,
                    'cc1_v': adc_data.cc1_v,
                    'cc2_v': adc_data.cc2_v,
                }
            return NULL_ADC_DICT
        except (ValueError, TypeError):
            return NULL_ADC_DICT
    
    adc_struct_type = pl.Struct([
        pl.Field('vbus_v', pl.Float64), pl.Field('ibus_a', pl.Float64),
        pl.Field('power_w', pl.Float64), pl.Field('vbus_avg_v', pl.Float64),
        pl.Field('ibus_avg_a', pl.Float64), pl.Field('temp_c', pl.Float64),
        pl.Field('vdp_v', pl.Float64), pl.Field('vdm_v', pl.Float64),
        pl.Field('vdp_avg_v', pl.Float64), pl.Field('vdm_avg_v', pl.Float64),
        pl.Field('cc1_v', pl.Float64), pl.Field('cc2_v', pl.Float64),
    ])

    # The Rust function returns AdcData for ADC packets and None otherwise.
    # We can use this to create the two columns we need.
    parsed_series = df["payload_hex"].map_elements(
        parse_hex_payload, 
        return_dtype=adc_struct_type
    )

    return df.with_columns(
        pl.when(parsed_series.is_not_null())
          .then(pl.lit("ADC_DATA"))
          .otherwise(pl.lit("UNKNOWN"))
          .alias("packet_type"),
        parsed_series.alias("adc_data")
    ).unnest("adc_data")
