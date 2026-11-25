"""HyRegistry as the host side of an embedding application: functions, values, compile/run."""

from datetime import datetime

import pytest

from hyengine import Code
from hyengine.errors import HyEvaluationError
from hyengine.registry import HyRegistry


@pytest.fixture
def registry():
    reg = HyRegistry()

    @reg.command("add-numbers")
    def add_numbers(a, b):
        return a + b

    reg.define("answer", 42)
    reg.define("max-items", 3)
    return reg


def test_functions_and_values_are_in_scope_with_both_spellings(registry):
    assert registry.run(Code("(add-numbers answer 1)")) == 43
    assert registry.run(Code("(add_numbers max-items max_items)")) == 6


def test_compile_returns_a_callable(registry):
    double = registry.compile(Code("(fn [x] (* x 2))"))
    assert double(21) == 42


def test_compiled_functions_see_registry_names(registry):
    f = registry.compile(Code("(fn [x] (add-numbers x answer))"))
    assert f(1) == 43


def test_run_with_locals(registry):
    assert registry.run(Code("(+ x y)"), x=1, y=2) == 3


def test_time_helpers_are_available(registry):
    assert registry.run(Code("(datetime 2025 1 1)")) == datetime(2025, 1, 1)


def test_errors_carry_the_source(registry):
    with pytest.raises(HyEvaluationError, match=r"\(/ 1 0\)"):
        registry.run(Code("(/ 1 0)"))


def test_runs_do_not_leak_names_into_each_other(registry):
    registry.run(Code("(setv leaked 1)"))
    with pytest.raises(HyEvaluationError):
        registry.run(Code("leaked"))


def test_source_strings_are_accepted(registry):
    assert registry.run("(add-numbers 1 2)") == 3
