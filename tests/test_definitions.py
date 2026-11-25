"""Data-mode reading and writing of definition forms: (def-X name args... (prop value...) ...).

Data mode never evaluates anything: literals and registered constructors decode to
values, (quote ...) becomes a Code value, anything else is an error.
"""

from datetime import datetime
from decimal import Decimal

import pytest

from hyengine import Code, Definition, format_definition, read_definitions
from hyengine.converter import HyConverter
from hyengine.errors import HyDataError

TASK = '''(def-task "Write report"
  (active-occurrence-start-time None)
  (creation-date (datetime 2025 7 25 14 19 10 135728))
  (exclusive-resource-claims ["USER_PRIMARY_FOCUS"])
  (occurrences [{:start_time (datetime 2025 6 13 17 37 32 14816) :notes "" :metadata {}}])
  (on-start-hook (quote (do (shell "notify-send hi") (setv x 1))))
  (goal (Decimal "0.5"))
  (priority 3)
)
'''


def test_reads_name_and_props_as_values():
    [task] = read_definitions(TASK)
    assert task.head == "def-task"
    assert task.name == "Write report"
    assert task.props["priority"] == 3
    assert task.props["active-occurrence-start-time"] is None
    assert task.props["creation-date"] == datetime(2025, 7, 25, 14, 19, 10, 135728)
    assert task.props["goal"] == Decimal("0.5")
    assert task.props["exclusive-resource-claims"] == ["USER_PRIMARY_FOCUS"]
    assert task.props["occurrences"][0]["start_time"] == datetime(2025, 6, 13, 17, 37, 32, 14816)


def test_quoted_forms_become_code_and_are_not_evaluated():
    [task] = read_definitions(TASK)
    hook = task.props["on-start-hook"]
    assert isinstance(hook, Code)
    assert hook.source == '(do (shell "notify-send hi") (setv x 1))'
    assert str(hook.model[0]) == "do"


def test_quote_shorthand_is_code_too():
    [d] = read_definitions("(def-x a (action '(+ 1 2)))")
    assert d.props["action"] == Code("(+ 1 2)")


def test_symbol_names_and_positional_args():
    [d] = read_definitions('(def-entity "TASK" entity-type\n  (title {:type "string" :required True})\n)')
    assert (d.name, d.args) == ("TASK", ["entity-type"])
    assert d.props["title"] == {"type": "string", "required": True}
    [p] = read_definitions("(def-pattern DAILY-AT-0700\n  (every \"1d\")\n)")
    assert p.name == "DAILY-AT-0700" and p.symbol_name


def test_props_with_several_values_are_tuples():
    [d] = read_definitions('(def-pattern P (between "09:00" "17:00") (on ["monday"]))')
    assert d.props["between"] == ("09:00", "17:00")
    assert d.props["on"] == ["monday"]


def test_empty_expression_reads_as_empty_list():
    [d] = read_definitions("(def-x a (occurrences [{:metadata ()}]))")
    assert d.props["occurrences"] == [{"metadata": []}]


def test_unknown_expressions_are_rejected_with_location():
    with pytest.raises(HyDataError, match=r"ratio.*\(\+ 1 2\)"):
        read_definitions("(def-x a (ratio (+ 1 2)))", source_name="x.hy")


def test_symbols_other_than_literals_are_rejected():
    with pytest.raises(HyDataError, match="some-variable"):
        read_definitions("(def-x a (value some-variable))")


def test_registered_constructors_decode():
    conv = HyConverter()
    conv.register_decoder("entity-ref", lambda model, c: ":".join(str(x) for x in model[1:]))
    [d] = read_definitions('(def-x a (context (entity-ref "context" "default" "Work")))', converter=conv)
    assert d.props["context"] == "context:default:Work"


def test_heads_filter():
    defs = read_definitions('(def-a x (v 1)) (def-b y (v 2))', heads={"def-b"})
    assert [d.name for d in defs] == ["y"]


def test_reading_from_a_file(tmp_path):
    path = tmp_path / "tasks.hy"
    path.write_text(TASK)
    [task] = read_definitions(path)
    assert task.name == "Write report"


class TestFormatting:
    def test_round_trip_is_identical_data(self):
        [task] = read_definitions(TASK)
        [again] = read_definitions(format_definition(task))
        assert again == task

    def test_layout_matches_utms_files(self):
        [task] = read_definitions(TASK)
        text = format_definition(task)
        assert text.startswith('(def-task "Write report"\n  (active-occurrence-start-time None)\n')
        assert "  (on-start-hook (quote (do (shell \"notify-send hi\") (setv x 1))))\n" in text
        assert "  (creation-date (datetime 2025 7 25 14 19 10 135728))\n" in text
        assert text.endswith("\n)")

    def test_symbol_name_args_and_tuples(self):
        d = Definition(head="def-pattern", name="DAILY", symbol_name=True,
                       props={"between": ("09:00", "17:00")})
        assert format_definition(d) == '(def-pattern DAILY\n  (between "09:00" "17:00")\n)'
        e = Definition(head="def-entity", name="TASK", args=["entity-type"], props={})
        assert format_definition(e) == '(def-entity "TASK" entity-type\n)'

    def test_code_values_are_written_quoted(self):
        d = Definition(head="def-x", name="a", props={"hook": Code("(setv x 1)")})
        assert "(hook (quote (setv x 1)))" in format_definition(d)


class TestCodeValuesMode:
    """Type/trait files: whatever is not data is kept as Code (never evaluated on read)."""

    SOURCE = '''(def-trait occurrences
  (attributes {:active-occurrence-start-time {:type "datetime" :default_value current-time}})
  (actions {:start (fn [self] (setv self.x 1)) :stop (fn [self] None)}))'''

    def test_non_data_becomes_code(self):
        [d] = read_definitions(self.SOURCE, code_values=True)
        attrs = d.props["attributes"]["active-occurrence-start-time"]
        assert attrs == {"type": "datetime", "default_value": Code("current-time")}
        assert d.props["actions"]["start"] == Code("(fn [self] (setv self.x 1))")

    def test_data_is_still_decoded(self):
        [d] = read_definitions('(def-x a (when (datetime 2025 1 1 0 0 0 0)) (n (Decimal "1.5")))',
                               code_values=True)
        assert d.props["when"] == datetime(2025, 1, 1)
        assert d.props["n"] == Decimal("1.5")

    def test_strict_mode_is_the_default(self):
        with pytest.raises(HyDataError):
            read_definitions(self.SOURCE)

    def test_code_values_round_trip_through_format(self):
        [d] = read_definitions(self.SOURCE, code_values=True)
        [again] = read_definitions(format_definition(d), code_values=True)
        assert again == d
