"""Regression tests for GetData/PutData correlation classification."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.parquet.analyze_request_response_correlation import (
    parse_getdata_header,
    parse_putdata_header,
)

pytestmark = pytest.mark.unit


def test_getdata_parser_rejects_memory_read_request() -> None:
    request = "4402010133f8860c0054288cdc7e52729826872dd18b539a39c407d5c063d91102e36a9e"

    assert parse_getdata_header(request) is None


def test_putdata_parser_rejects_memory_read_confirmation() -> None:
    confirmation = "c40201012004000040000000ffffffff1b8c1b24"

    assert parse_putdata_header(confirmation) is None


def test_correlation_parsers_accept_getdata_and_putdata() -> None:
    request = parse_getdata_header("0c0a0200")
    response = parse_putdata_header(
        "410080020100000b451c4d00ae9efeffdb1c4d00239ffeffe11c4d00819ffeff"
        "c90c8a100e0000000000787e0080020000000000"
    )

    assert request is not None
    assert request.transaction_id == 10
    assert request.attribute_mask == 1
    assert response is not None
    assert response.transaction_id == 0
