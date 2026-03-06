"""
Comprehensive error handling tests for hyengine.

These tests define the CONTRACT for how hyengine must behave when things go wrong.
They test against HyEngineError, HyParseError, and HyEvaluationError — exceptions
that do not yet exist. All tests here should FAIL until the error handling is
implemented, then PASS once it is.

Run with: pytest tests/test_error_handling.py -v
"""

import tempfile
import pytest
import hy
from pathlib import Path
from hyengine.registry import HyRegistry


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_hy_file(tmpdir, content, filename="test.hy"):
    p = Path(tmpdir) / filename
    p.write_text(content, encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# 1. Exception hierarchy exists and is importable
# ---------------------------------------------------------------------------

class TestExceptionHierarchy:
    def test_hyengine_error_importable(self):
        from hyengine.errors import HyEngineError
        assert issubclass(HyEngineError, Exception)

    def test_hyparse_error_importable(self):
        from hyengine.errors import HyParseError, HyEngineError
        assert issubclass(HyParseError, HyEngineError)

    def test_hyevaluation_error_importable(self):
        from hyengine.errors import HyEvaluationError, HyEngineError
        assert issubclass(HyEvaluationError, HyEngineError)

    def test_hycommand_error_importable(self):
        from hyengine.errors import HyCommandError, HyEngineError
        assert issubclass(HyCommandError, HyEngineError)

    def test_hyvalidation_error_importable(self):
        from hyengine.errors import HyValidationError, HyEngineError
        assert issubclass(HyValidationError, HyEngineError)


# ---------------------------------------------------------------------------
# 2. HyParseError — malformed syntax
# ---------------------------------------------------------------------------

class TestParseErrors:
    def test_unclosed_paren_raises_hyparse_error(self):
        from hyengine.errors import HyParseError
        from hyengine.evaluator import evaluate_file
        with tempfile.TemporaryDirectory() as tmpdir:
            f = make_hy_file(tmpdir, "(setup-client :name \"Acme\"")  # missing )
            with pytest.raises(HyParseError) as exc_info:
                evaluate_file(f)
            assert exc_info.value.file is not None
            assert "test.hy" in exc_info.value.file

    def test_parse_error_is_hyengine_error(self):
        """HyParseError must be catchable as HyEngineError."""
        from hyengine.errors import HyEngineError
        from hyengine.evaluator import evaluate_file
        with tempfile.TemporaryDirectory() as tmpdir:
            f = make_hy_file(tmpdir, "(unclosed")
            with pytest.raises(HyEngineError):
                evaluate_file(f)

    def test_parse_error_contains_filename(self):
        from hyengine.errors import HyParseError
        from hyengine.evaluator import evaluate_file
        with tempfile.TemporaryDirectory() as tmpdir:
            f = make_hy_file(tmpdir, "(unclosed paren", "provider.hy")
            try:
                evaluate_file(f)
                pytest.fail("Expected HyParseError")
            except HyParseError as e:
                assert "provider.hy" in str(e)

    def test_parse_error_preserves_original_cause(self):
        from hyengine.errors import HyParseError
        from hyengine.evaluator import evaluate_file
        with tempfile.TemporaryDirectory() as tmpdir:
            f = make_hy_file(tmpdir, "(unclosed paren")
            try:
                evaluate_file(f)
                pytest.fail("Expected HyParseError")
            except HyParseError as e:
                assert e.__cause__ is not None


# ---------------------------------------------------------------------------
# 3. HyEvaluationError — runtime errors during eval
# ---------------------------------------------------------------------------

class TestEvaluationErrors:
    def test_undefined_name_raises_hyevaluation_error(self):
        from hyengine.errors import HyEvaluationError
        from hyengine.evaluator import evaluate_file
        with tempfile.TemporaryDirectory() as tmpdir:
            # undefined_variable is not in locals_dict
            f = make_hy_file(tmpdir, "(setup-client :name undefined_variable)")
            with pytest.raises(HyEvaluationError) as exc_info:
                evaluate_file(f, locals_dict={
                    "setup-client": lambda **kw: kw,
                    "setup_client": lambda **kw: kw,
                })
            err = exc_info.value
            assert err.file is not None
            assert "test.hy" in err.file

    def test_evaluation_error_contains_expression(self):
        from hyengine.errors import HyEvaluationError
        from hyengine.evaluator import evaluate_file
        with tempfile.TemporaryDirectory() as tmpdir:
            f = make_hy_file(tmpdir, "(this-command-does-not-exist 42)")
            try:
                evaluate_file(f)
                pytest.fail("Expected HyEvaluationError")
            except HyEvaluationError as e:
                # The failing expression should be present in the error
                assert e.expression is not None
                assert len(e.expression) > 0

    def test_evaluation_error_contains_expression_index(self):
        """When a file has multiple expressions, the index of the failing one is reported."""
        from hyengine.errors import HyEvaluationError
        from hyengine.evaluator import evaluate_file

        state = {}
        def good_cmd(val):
            state["good"] = val

        with tempfile.TemporaryDirectory() as tmpdir:
            # First expression is fine, second fails
            content = '(good-cmd "hello")\n(bad-cmd "world")'
            f = make_hy_file(tmpdir, content)
            try:
                evaluate_file(f, locals_dict={
                    "good-cmd": good_cmd,
                    "good_cmd": good_cmd,
                })
                pytest.fail("Expected HyEvaluationError")
            except HyEvaluationError as e:
                # Index should be 1 (second expression, 0-based)
                assert e.index == 1

    def test_evaluation_error_is_hyengine_error(self):
        from hyengine.errors import HyEngineError
        from hyengine.evaluator import evaluate_file
        with tempfile.TemporaryDirectory() as tmpdir:
            f = make_hy_file(tmpdir, "(nonexistent-fn)")
            with pytest.raises(HyEngineError):
                evaluate_file(f)

    def test_evaluation_error_preserves_cause(self):
        from hyengine.errors import HyEvaluationError
        from hyengine.evaluator import evaluate_file
        with tempfile.TemporaryDirectory() as tmpdir:
            f = make_hy_file(tmpdir, "(nonexistent-fn)")
            try:
                evaluate_file(f)
                pytest.fail("Expected HyEvaluationError")
            except HyEvaluationError as e:
                assert e.__cause__ is not None

    def test_error_message_is_human_readable(self):
        """The error message should not be a raw Python/Hy traceback blob."""
        from hyengine.errors import HyEvaluationError
        from hyengine.evaluator import evaluate_file
        with tempfile.TemporaryDirectory() as tmpdir:
            f = make_hy_file(tmpdir, "(nonexistent-fn)", "financials.hy")
            try:
                evaluate_file(f)
                pytest.fail("Expected HyEvaluationError")
            except HyEvaluationError as e:
                msg = str(e)
                # Must contain filename
                assert "financials.hy" in msg
                # Must not be empty
                assert len(msg) > 10

    def test_type_error_in_command_is_wrapped(self):
        """A TypeError inside a DSL command should become HyEvaluationError."""
        from hyengine.errors import HyEvaluationError
        from hyengine.evaluator import evaluate_file

        def bad_cmd(x):
            return x + 1  # will fail if x is a string

        with tempfile.TemporaryDirectory() as tmpdir:
            f = make_hy_file(tmpdir, '(bad-cmd "not-a-number")')
            with pytest.raises(HyEvaluationError):
                evaluate_file(f, locals_dict={
                    "bad-cmd": bad_cmd,
                    "bad_cmd": bad_cmd,
                })


# ---------------------------------------------------------------------------
# 4. Namespace preservation across expressions in a single file
# ---------------------------------------------------------------------------

class TestNamespacePreservation:
    def test_setv_in_first_expr_visible_in_second(self):
        """Variables set by setv in expression N must be visible in expression N+1."""
        from hyengine.evaluator import evaluate_file
        results = []

        def capture(val):
            results.append(val)

        with tempfile.TemporaryDirectory() as tmpdir:
            content = "(setv asset-count 7)\n(capture asset-count)"
            f = make_hy_file(tmpdir, content)
            evaluate_file(f, locals_dict={
                "capture": capture,
            })
        assert results == [7]

    def test_multiple_set_content_calls_accumulate(self):
        """Multiple side-effectful calls in a file must all execute."""
        from hyengine.evaluator import evaluate_file
        calls = []

        def set_content(d):
            calls.append(d)

        with tempfile.TemporaryDirectory() as tmpdir:
            content = '(set-content "a")\n(set-content "b")\n(set-content "c")'
            f = make_hy_file(tmpdir, content)
            evaluate_file(f, locals_dict={
                "set-content": set_content,
                "set_content": set_content,
            })
        assert calls == ["a", "b", "c"]

    def test_cross_file_namespace_via_shared_locals(self):
        """When the same locals_dict is passed to two evaluate_file calls,
        bindings from the first file are visible in the second."""
        from hyengine.evaluator import evaluate_file
        results = []

        def capture(val):
            results.append(val)

        shared = {"capture": capture}

        with tempfile.TemporaryDirectory() as tmpdir:
            f1 = make_hy_file(tmpdir, "(setv client-name \"Acme\")", "meta.hy")
            f2 = make_hy_file(tmpdir, "(capture client-name)", "content.hy")
            evaluate_file(f1, locals_dict=shared)
            evaluate_file(f2, locals_dict=shared)

        assert results == ["Acme"]

    def test_error_in_third_expression_still_executes_first_two(self):
        """Expressions before the failing one must have already run."""
        from hyengine.errors import HyEvaluationError
        from hyengine.evaluator import evaluate_file
        calls = []

        def ok(v):
            calls.append(v)

        with tempfile.TemporaryDirectory() as tmpdir:
            content = '(ok 1)\n(ok 2)\n(bad-cmd)\n(ok 3)'
            f = make_hy_file(tmpdir, content)
            with pytest.raises(HyEvaluationError):
                evaluate_file(f, locals_dict={"ok": ok})
        # First two must have run, third must have stopped execution
        assert calls == [1, 2]


# ---------------------------------------------------------------------------
# 5. HyRegistry error wrapping
# ---------------------------------------------------------------------------

class TestRegistryErrors:
    def test_registry_eval_wraps_undefined_command(self):
        from hyengine.errors import HyEngineError
        registry = HyRegistry()
        expr = hy.read("(nonexistent-command 42)")
        with pytest.raises(HyEngineError):
            registry.eval(expr)

    def test_registry_eval_wraps_command_runtime_error(self):
        from hyengine.errors import HyEngineError
        registry = HyRegistry()

        @registry.command("bad-op")
        def bad_op(x):
            raise ValueError("intentional failure")

        expr = hy.read('(bad-op "trigger")')
        with pytest.raises(HyEngineError):
            registry.eval(expr)

    def test_registry_eval_success_still_works(self):
        """Wrapping must not break the happy path."""
        registry = HyRegistry()
        results = []

        @registry.command("collect")
        def collect(val):
            results.append(val)

        expr = hy.read('(collect "hello")')
        registry.eval(expr)
        assert results == ["hello"]


# ---------------------------------------------------------------------------
# 6. safe_format — expression formatting for error messages
# ---------------------------------------------------------------------------

class TestSafeFormat:
    def test_safe_format_importable(self):
        from hyengine.ast import safe_format
        assert callable(safe_format)

    def test_safe_format_simple_expression(self):
        from hyengine.ast import safe_format
        expr = hy.read('(setup-client :name "Acme")')
        result = safe_format(expr)
        assert "setup-client" in result
        assert "Acme" in result

    def test_safe_format_truncates_long_expressions(self):
        from hyengine.ast import safe_format
        # Build a very long expression
        items = " ".join([f'"item-{i}"' for i in range(50)])
        expr = hy.read(f"(add-items {items})")
        result = safe_format(expr, max_len=60)
        assert len(result) <= 63  # max_len + "..."
        assert result.endswith("...")

    def test_safe_format_never_raises(self):
        from hyengine.ast import safe_format
        # Even with garbage input it must not raise
        result = safe_format(None)
        assert isinstance(result, str)

    def test_safe_format_nested_expression(self):
        from hyengine.ast import safe_format
        expr = hy.read('(add-financials (check "api.bola" 8 :status "recommended"))')
        result = safe_format(expr)
        assert "add-financials" in result
        assert "check" in result


# ---------------------------------------------------------------------------
# 7. HyEngine.evaluate_expression error wrapping
# ---------------------------------------------------------------------------

class TestHyEngineErrors:
    def test_engine_evaluate_expression_wraps_errors(self):
        from hyengine.errors import HyEvaluationError
        from hyengine.engine import HyEngine
        engine = HyEngine()
        expr = hy.read("(this-does-not-exist)")
        with pytest.raises(HyEvaluationError):
            engine.evaluate_expression(expr)

    def test_engine_evaluate_expression_success_unchanged(self):
        from hyengine.engine import HyEngine
        engine = HyEngine()
        expr = hy.read("(+ 1 2)")
        assert engine.evaluate_expression(expr) == 3

    def test_engine_error_contains_expression(self):
        from hyengine.errors import HyEvaluationError
        from hyengine.engine import HyEngine
        engine = HyEngine()
        expr = hy.read('(setup-provider :name undefined-var)')
        try:
            engine.evaluate_expression(expr)
            pytest.fail("Expected HyEvaluationError")
        except HyEvaluationError as e:
            assert e.expression is not None


# ---------------------------------------------------------------------------
# 8. evaluate_file_strict uses new error types
# ---------------------------------------------------------------------------

class TestEvaluateFileStrict:
    def test_strict_missing_file_raises_hyengine_error(self):
        from hyengine.errors import HyEngineError
        from hyengine.evaluator import evaluate_file_strict
        with pytest.raises(HyEngineError):
            evaluate_file_strict(Path("/nonexistent/path/file.hy"))

    def test_strict_parse_error_raises_hyparse_error(self):
        from hyengine.errors import HyParseError
        from hyengine.evaluator import evaluate_file_strict
        with tempfile.TemporaryDirectory() as tmpdir:
            f = make_hy_file(tmpdir, "(unclosed paren")
            with pytest.raises(HyParseError):
                evaluate_file_strict(f)


# ---------------------------------------------------------------------------
# 9. Empty and edge case files
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_empty_file_returns_none_not_error(self):
        from hyengine.evaluator import evaluate_file
        with tempfile.TemporaryDirectory() as tmpdir:
            f = make_hy_file(tmpdir, "")
            result = evaluate_file(f)
            assert result is None or result == {}

    def test_comment_only_file_returns_none_not_error(self):
        from hyengine.evaluator import evaluate_file
        with tempfile.TemporaryDirectory() as tmpdir:
            f = make_hy_file(tmpdir, ";; This is just a comment\n;; Another comment")
            # Should not raise
            result = evaluate_file(f)
            assert result is None or result == {}

    def test_whitespace_only_file_returns_none_not_error(self):
        from hyengine.evaluator import evaluate_file
        with tempfile.TemporaryDirectory() as tmpdir:
            f = make_hy_file(tmpdir, "   \n\n\t  ")
            result = evaluate_file(f)
            assert result is None or result == {}
