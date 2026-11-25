"""Round-trip guarantees for the converter.

Invariant: whatever ``py_to_model`` writes must come back as an equal Python
value through every read path hyengine offers:

1. ``model_to_py`` on the model itself,
2. formatting to source and parsing it again (data files are often only parsed),
3. formatting to source and *evaluating* it (data files are also evaluated).
"""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from hyengine import HyASTManager, engine_converter, parse_data
from hyengine.evaluator import evaluate_string

CET = timezone(timedelta(hours=1))
NEG = timezone(-timedelta(hours=5, minutes=30))

VALUES = {
    "datetime-minutes": datetime(2025, 6, 13, 17, 37),
    "datetime-seconds": datetime(2025, 6, 13, 17, 37, 32),
    "datetime-microseconds": datetime(2025, 6, 13, 17, 37, 32, 14816),
    "datetime-utc": datetime(2025, 6, 13, 17, 37, 32, 14816, tzinfo=timezone.utc),
    "datetime-plus-one": datetime(2025, 6, 13, 17, 37, 32, tzinfo=CET),
    "datetime-negative-offset": datetime(2025, 1, 1, 0, 0, 0, 1, tzinfo=NEG),
    "date": date(2025, 6, 13),
    "decimal-integral": Decimal("8"),
    "decimal-fraction": Decimal("0.5"),
    "decimal-high-precision": Decimal("5.3912464466619436120988365792329601114251212890458704606604191900696754478334996470771394295075989533354214968720319323125522714690305292606353759765625E-44"),
    "decimal-negative": Decimal("-435485579904000000"),
    "int": 42,
    "float": 0.1,
    "bool-true": True,
    "bool-false": False,
    "none": None,
    "string": "plain",
    "string-with-quotes": 'say "hi"',
    "string-with-newline": "line1\nline2",
    "empty-list": [],
    "empty-dict": {},
    "nested": {
        "occurrences": [
            {
                "start_time": datetime(2025, 6, 13, 17, 37, 32, 14816),
                "end_time": datetime(2025, 6, 13, 18, 0, 0, tzinfo=timezone.utc),
                "notes": "",
                "metadata": {},
                "value": Decimal("2.5"),
                "done": True,
            }
        ]
    },
}

PARAMS = pytest.mark.parametrize("value", list(VALUES.values()), ids=list(VALUES))


def source_of(value):
    return HyASTManager().format_expression(engine_converter.py_to_model(value))


def assert_identical(actual, expected):
    assert actual == expected
    assert type(actual) is type(expected)
    if isinstance(expected, datetime):
        assert actual.utcoffset() == expected.utcoffset()


@PARAMS
def test_model_round_trip(value):
    assert_identical(engine_converter.model_to_py(engine_converter.py_to_model(value)), value)


@PARAMS
def test_source_parse_round_trip(value):
    [parsed] = parse_data(source_of(value))
    assert_identical(parsed, value)


@PARAMS
def test_source_evaluate_round_trip(value):
    assert_identical(evaluate_string(source_of(value)), value)


def test_datetime_source_is_human_readable():
    assert source_of(datetime(2025, 6, 13, 17, 37, 32, 14816)) == "(datetime 2025 6 13 17 37 32 14816)"
    assert source_of(datetime(2025, 6, 13, 17, 37)) == "(datetime 2025 6 13 17 37 0 0)"


def test_existing_utms_datetime_forms_still_parse():
    """Forms already present in UTMS data files."""
    [a, b] = parse_data("(datetime 2025 6 13 17 37 32 14816) (datetime 2025 5 23 19 46)")
    assert a == datetime(2025, 6, 13, 17, 37, 32, 14816)
    assert b == datetime(2025, 5, 23, 19, 46)


def test_evaluation_scope_provides_time_helpers_without_overriding_callers():
    scope = {"datetime": "mine"}
    assert evaluate_string("datetime", scope) == "mine"
    assert evaluate_string("(timedelta :hours 1)") == timedelta(hours=1)
