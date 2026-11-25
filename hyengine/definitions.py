"""Definition forms in *data mode*: ``(def-X name args... (prop value...) ...)``.

Data mode never evaluates. Values decode as:

* literals (strings, numbers, keywords, True/False/None, lists, dicts) -> Python values
* constructor forms with a decoder (``datetime``, ``Decimal``, ... and any decoder
  registered on the converter, e.g. ``entity-ref``) -> the decoded value
* ``(quote X)`` / ``'X`` -> :class:`Code` holding X's source
* ``()`` -> ``[]`` (older serializers wrote empty collections that way)
* anything else (calls, variable symbols) -> :class:`HyDataError`
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Union

import hy

from .ast import HyASTManager
from .converter import HyConverter, engine_converter
from .errors import HyDataError, HyParseError
from .values import Code

_LITERAL_SYMBOLS = {"True": True, "False": False, "None": None}
_BARE_SYMBOL = re.compile(r"^[^\s\"'();\[\]{}]+$")


@dataclass
class Definition:
    """One ``(head name args... (prop value...) ...)`` form.

    ``props`` keeps file order. A prop with several values holds a tuple;
    a single value (including a list) is stored as-is.
    """

    head: str
    name: str
    props: Dict[str, Any] = field(default_factory=dict)
    args: List[Any] = field(default_factory=list)
    # written as (def-x NAME) rather than (def-x "NAME"); None = not specified
    # (a replaced definition then keeps the style of the one it replaces)
    symbol_name: Optional[bool] = field(default=None, compare=False)
    source_file: Optional[Path] = field(default=None, compare=False)


def header_comments(text: str) -> List[str]:
    """Leading ``;;`` comment lines (kept when a file is rewritten)."""
    header = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith(";"):
            header.append(line)
        else:
            break
    return header


class _Source:
    """Original text of a file, to keep Code exactly as written (formatting, sugar)."""

    def __init__(self, text: str):
        self.text = text
        self.offsets = [0]
        for line in text.splitlines(keepends=True):
            self.offsets.append(self.offsets[-1] + len(line))

    def of(self, model: Any) -> Optional[str]:
        try:
            start = self.offsets[model.start_line - 1] + model.start_column - 1
            end = self.offsets[model.end_line - 1] + model.end_column
        except (AttributeError, TypeError, IndexError):
            return None
        snippet = self.text[start:end]
        return snippet if snippet.strip() else None


def _code(model: Any, source: Optional["_Source"]) -> Code:
    text = source.of(model) if source is not None else None
    return Code(text if text is not None else _src(model))


def _location(source_name: Optional[str], definition: str, prop: Optional[str]) -> str:
    where = f"{source_name}: " if source_name else ""
    return f"{where}{definition}" + (f" ({prop})" if prop else "")


def decode_data(
    model: Any,
    converter: HyConverter = engine_converter,
    where: str = "",
    code_values: bool = False,
    _source: Optional[_Source] = None,
) -> Any:
    """Decode a Hy model as data (see module docstring). Raises HyDataError.

    With ``code_values=True`` (type/trait files) anything that is not data is
    kept as :class:`Code` instead of raising.
    """
    def nested(m):
        return decode_data(m, converter, where, code_values, _source)

    if isinstance(model, hy.models.Expression):
        if not len(model):
            return []  # `()`: written by older serializers for empty collections
        head = str(model[0])
        if head == "quote":
            if len(model) != 2:
                raise HyDataError(f"{where}: malformed quote {hy.repr(model)}")
            return _code(model[1], _source)
        if head in converter.expression_decoders:
            return converter.expression_decoders[head](model, converter)
        if head in converter._builtin_decoders:
            try:
                return converter._builtin_decoders[head](model)
            except Exception as e:
                if code_values:
                    return _code(model, _source)
                raise HyDataError(f"{where}: invalid {head} form {_src(model)}: {e}") from e
        if code_values:
            return _code(model, _source)
        raise HyDataError(
            f"{where}: expressions are not allowed in data, got {_src(model)} "
            "(quote it to store code)"
        )
    if isinstance(model, hy.models.Symbol):
        name = str(model)
        if name in _LITERAL_SYMBOLS:
            return _LITERAL_SYMBOLS[name]
        if code_values:
            return Code(name)
        raise HyDataError(f"{where}: symbol '{name}' is not data (variables are not resolved here)")
    if isinstance(model, hy.models.Dict):
        items = list(model)
        if len(items) % 2:
            raise HyDataError(f"{where}: dict with an odd number of forms")
        return {converter.model_to_py(k): nested(v) for k, v in zip(items[::2], items[1::2])}
    if isinstance(model, hy.models.List):
        return [nested(v) for v in model]
    return converter.model_to_py(model)


def _src(model: Any) -> str:
    return HyASTManager().format_expression(model)


def read_definitions(
    content_or_path: Union[str, Path],
    heads: Optional[Iterable[str]] = None,
    converter: HyConverter = engine_converter,
    source_name: Optional[str] = None,
    code_values: bool = False,
) -> List[Definition]:
    """Parse definition forms from a file path or a source string.

    Data mode by default; ``code_values=True`` keeps non-data as :class:`Code`.
    """
    path = None
    if isinstance(content_or_path, Path) or (
        isinstance(content_or_path, str) and "\n" not in content_or_path
        and "(" not in content_or_path and Path(content_or_path).is_file()
    ):
        path = Path(content_or_path)
        text = path.read_text(encoding="utf-8")
        source_name = source_name or str(path)
    else:
        text = str(content_or_path)
    wanted = set(heads) if heads is not None else None

    try:
        forms = list(hy.read_many(text, filename=source_name or "<string>"))
    except Exception as e:
        raise HyParseError(str(e), file=source_name, cause=e) from e

    source = _Source(text)
    definitions = []
    for form in forms:
        if not (isinstance(form, hy.models.Expression) and len(form) >= 2
                and isinstance(form[0], hy.models.Symbol)):
            raise HyDataError(f"{source_name or '<string>'}: not a definition form: {_src(form)}")
        head = str(form[0])
        if wanted is not None and head not in wanted:
            continue

        name_model = form[1]
        if isinstance(name_model, hy.models.String):
            name, symbol_name = str(name_model), False
        elif isinstance(name_model, hy.models.Symbol):
            name, symbol_name = str(name_model), True
        else:
            raise HyDataError(f"{source_name}: {head} needs a name, got {_src(name_model)}")

        label = f"({head} {name})"
        args, props = [], {}
        for item in form[2:]:
            if isinstance(item, hy.models.Expression) and len(item) and isinstance(item[0], hy.models.Symbol):
                key = str(item[0])
                where = _location(source_name, label, key)
                vals = [decode_data(v, converter, where, code_values, source) for v in item[1:]]
                props[key] = None if not vals else vals[0] if len(vals) == 1 else tuple(vals)
            elif isinstance(item, hy.models.Symbol) and str(item) not in _LITERAL_SYMBOLS:
                args.append(str(item))  # positional markers such as `entity-type`
            else:
                args.append(decode_data(item, converter, _location(source_name, label, None), code_values, source))

        definitions.append(
            Definition(head=head, name=name, props=props, args=args,
                       symbol_name=symbol_name, source_file=path)
        )
    return definitions


def format_value(value: Any, converter: HyConverter = engine_converter, code_values: bool = False) -> str:
    """Render a value as Hy source. Code is written verbatim (quoted in data files)."""
    if isinstance(value, Code):
        return value.source if code_values else f"(quote {value.source})"
    if isinstance(value, dict):
        parts = []
        for k, v in value.items():
            key = str(k).lstrip(":")
            rendered_key = f'"{key}"' if any(c in key for c in "./ ") else f":{key}"
            parts.append(f"{rendered_key} {format_value(v, converter, code_values)}")
        return "{" + " ".join(parts) + "}"
    if isinstance(value, list):
        return "[" + " ".join(format_value(v, converter, code_values) for v in value) + "]"
    return HyASTManager().format_expression(converter.py_to_model(value))


def format_definition(
    definition: Definition, converter: HyConverter = engine_converter, code_values: bool = False
) -> str:
    """Write a definition in the layout used by UTMS files.

    In data files Code is written quoted; with ``code_values=True`` it is written raw.
    """
    fmt = HyASTManager().format_expression
    name = definition.name if definition.symbol_name else fmt(hy.models.String(definition.name))
    head = [definition.head, name]
    for arg in definition.args:
        if isinstance(arg, str) and _BARE_SYMBOL.match(arg):
            head.append(arg)
        else:
            head.append(format_value(arg, converter, code_values))

    lines = ["(" + " ".join(head)]
    for key, value in definition.props.items():
        if isinstance(value, tuple):
            rendered = " ".join(format_value(v, converter, code_values) for v in value)
        elif value is None:
            rendered = "None"
        else:
            rendered = format_value(value, converter, code_values)
        lines.append(f"  ({key} {rendered})")
    return "\n".join(lines) + "\n)"
