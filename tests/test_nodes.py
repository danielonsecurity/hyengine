"""HyASTManager.parse_nodes must agree with engine_converter.model_to_py on values."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from hyengine import HyASTManager


def first_arg(source):
    [node] = HyASTManager().parse_nodes(source)
    return node.args[0]


@pytest.mark.parametrize(
    "source, expected",
    [("(x True)", True), ("(x False)", False), ("(x None)", None)],
)
def test_boolean_and_none_symbols_are_literal_values(source, expected):
    node = first_arg(source)
    assert node.value is expected
    assert node.type == "literal"
    assert not node.is_dynamic


def test_other_symbols_stay_symbols():
    node = first_arg("(x some-variable)")
    assert node.type == "symbol"
    assert node.value == "some-variable"


def test_constructor_expressions_decode_to_values_but_keep_source():
    node = first_arg("(x (datetime 2025 6 13 17 37 32 14816 :tzinfo (timezone (timedelta :seconds 0))))")
    assert node.value == datetime(2025, 6, 13, 17, 37, 32, 14816, tzinfo=timezone.utc)
    assert node.original.startswith("(datetime 2025 6 13")


def test_decimal_expression_decodes_exactly():
    assert first_arg('(x (Decimal "0.1"))').value == Decimal("0.1")


def test_list_items_use_the_same_rules():
    node = first_arg("(x [True None 1])")
    assert node.value == [True, None, 1]
