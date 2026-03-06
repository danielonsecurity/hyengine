import hy
from .converter import engine_converter
from .errors import HyEngineError, HyParseError, HyEvaluationError
from .ast import safe_format
from pathlib import Path


def _extract_source_line(content, lineno):
    """Return the source line at lineno (1-based)."""
    if lineno is None:
        return None
    lines = content.splitlines()
    if 1 <= lineno <= len(lines):
        return lines[lineno - 1]
    return None


def _format_parse_error(e, content, path):
    """Extract line/col from a Hy LexException and build a useful message."""
    lineno = getattr(e, "lineno", None)
    colno = getattr(e, "colno", None)

    # Strip Hy's appended (filename, line N) suffix regardless of filename
    raw = str(e)
    if " (" in raw and raw.endswith(")"):
        raw = raw[:raw.rindex(" (")].strip()

    parts = [raw]
    if lineno is not None:
        parts.append(f"  Line {lineno}" + (f", column {colno}" if colno else ""))
        # Show 3 lines of context before the error line so the real problem is visible
        lines = content.splitlines()
        context_start = max(0, lineno - 4)
        context_end = min(len(lines), lineno)
        for i, line in enumerate(lines[context_start:context_end], start=context_start + 1):
            prefix = "-> " if i == lineno else "   "
            parts.append(f"  {prefix}{i:4d}  {line.rstrip()}")
        if colno and colno > 0:
            parts.append(f"         {' ' * (colno - 1)}^")

    return "\n".join(parts)


def evaluate_expression(expr, locals_dict=None, *, source_file=None, index=None):
    if locals_dict is None:
        locals_dict = {}
    if "__builtins__" not in locals_dict:
        locals_dict["__builtins__"] = globals().get("__builtins__", {})
    try:
        res = hy.compiler.hy_eval(expr, locals_dict, "__main__")
        return engine_converter.model_to_py(res)
    except HyEngineError:
        raise
    except Exception as e:
        raise HyEvaluationError(
            str(e),
            file=source_file,
            expression=safe_format(expr),
            index=index,
            cause=e,
        ) from e


def evaluate_file(path, locals_dict=None):
    path = Path(path)
    if not path.is_file():
        return {}

    content = path.read_text(encoding="utf-8").strip()
    if not content:
        return {}

    try:
        expressions = list(hy.read_many(content, filename=str(path)))
    except Exception as e:
        msg = _format_parse_error(e, content, path)
        raise HyParseError(msg, file=str(path), cause=e) from e

    if not expressions:
        return {}

    # Shared namespace — same dict passed to every expression so that
    # bindings from expression N are visible in expression N+1.
    # hy_eval mutates the dict in place (confirmed via live PDB inspection).
    shared_locals = locals_dict if locals_dict is not None else {}
    if "__builtins__" not in shared_locals:
        shared_locals["__builtins__"] = globals().get("__builtins__", {})

    result = None
    for i, expr in enumerate(expressions):
        try:
            res = hy.compiler.hy_eval(expr, shared_locals, "__main__")
            result = engine_converter.model_to_py(res)
        except HyEngineError:
            raise
        except Exception as e:
            raise HyEvaluationError(
                str(e),
                file=str(path),
                expression=safe_format(expr),
                index=i,
                cause=e,
            ) from e

    return result


def evaluate_file_strict(path, locals_dict=None):
    path = Path(path)
    if not path.is_file():
        raise HyEngineError(f"Hy file not found: {path}")
    return evaluate_file(path, locals_dict)


def evaluate_file_normalized(path, locals_dict=None):
    """Evaluate a Hy file and recursively normalize Keywords/Symbols to Python strings."""
    res = evaluate_file(path, locals_dict)
    return _normalize(res)


def _normalize(obj):
    from dataclasses import is_dataclass

    if is_dataclass(obj):
        return obj
    if isinstance(obj, dict):
        return {_normalize(k): _normalize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_normalize(x) for x in obj]
    obj_type = type(obj).__name__
    s_obj = str(obj)
    if obj_type == "Keyword" or s_obj.startswith(":"):
        return s_obj.lstrip(":").replace("-", "_")
    if obj_type == "Symbol":
        return s_obj.replace("-", "_")
    return obj
