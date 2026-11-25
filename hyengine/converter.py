import hy
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Callable, Dict, List, Tuple

from .values import Code


# Names a converted value may reference when its source is *evaluated*.
# The evaluator puts these in scope by default (see evaluator.default_scope).
EVAL_SCOPE: Dict[str, Any] = {
    "datetime": datetime,
    "date": date,
    "timedelta": timedelta,
    "timezone": timezone,
    "Decimal": Decimal,
}


def _sym(name: str) -> hy.models.Symbol:
    return hy.models.Symbol(name)


def _int(value: int) -> hy.models.Integer:
    return hy.models.Integer(value)


class HyConverter:
    """Converts between Python values and Hy models.

    Round-trip guarantee for built-in types: ``model_to_py(py_to_model(v)) == v``,
    and the formatted source of ``py_to_model(v)`` parses and evaluates back to ``v``.
    Temporal values use evaluable constructor forms:

    * ``datetime`` -> ``(datetime Y M D h m s us)``, plus
      ``:tzinfo (timezone (timedelta :seconds N))`` when timezone-aware
    * ``date``     -> ``(date Y M D)``
    * ``Decimal``  -> ``(Decimal "…")`` (exact, no float rounding)
    """

    def __init__(self):
        self.encoders: Dict[type, Callable] = {}
        self.expression_decoders: Dict[str, Callable] = {}
        self._builtin_decoders: Dict[str, Callable] = {
            "datetime": self._decode_datetime,
            "date": self._decode_date,
            "timedelta": self._decode_timedelta,
            "timezone": self._decode_timezone,
            "Decimal": self._decode_decimal,
        }

    def register_encoder(self, type_obj, func):
        self.encoders[type_obj] = func

    def register_decoder(self, symbol_name, func):
        self.expression_decoders[symbol_name] = func

    # ------------------------------------------------------------------ encode
    def py_to_model(self, value: Any) -> hy.models.Object:
        if isinstance(value, hy.models.Object):
            return value

        for type_obj, encoder in self.encoders.items():
            if isinstance(value, type_obj):
                return encoder(value, self)

        if isinstance(value, Code):  # code kept as data is written back quoted
            return hy.models.Expression([_sym("quote"), value.model])

        # datetime must be checked before date (datetime is a date subclass)
        if isinstance(value, datetime):
            return self._encode_datetime(value)
        if isinstance(value, date):
            return hy.models.Expression(
                [_sym("date"), _int(value.year), _int(value.month), _int(value.day)]
            )
        if isinstance(value, timedelta):
            return self._encode_timedelta(value)
        if isinstance(value, Decimal):
            return hy.models.Expression([_sym("Decimal"), hy.models.String(str(value))])

        if isinstance(value, dict):
            parts = []
            for k, v in value.items():
                key_str = str(k).lstrip(':')
                if "." in key_str or " " in key_str or "/" in key_str:
                    parts.append(hy.models.String(key_str))
                else:
                    parts.append(hy.models.Keyword(key_str))

                parts.append(self.py_to_model(v))
            return hy.models.Dict(parts)

        if isinstance(value, list):
            return hy.models.List([self.py_to_model(item) for item in value])

        if value is None:
            return hy.models.Symbol("None")
        if isinstance(value, bool):
            return hy.models.Symbol("True") if value else hy.models.Symbol("False")
        if isinstance(value, int):
            return hy.models.Integer(value)
        if isinstance(value, float):
            return hy.models.Float(value)

        return hy.models.String(str(value))

    def _encode_datetime(self, value: datetime) -> hy.models.Expression:
        parts = [
            _sym("datetime"),
            _int(value.year), _int(value.month), _int(value.day),
            _int(value.hour), _int(value.minute), _int(value.second),
            _int(value.microsecond),
        ]
        offset = value.utcoffset()
        if offset is not None:
            parts += [
                hy.models.Keyword("tzinfo"),
                hy.models.Expression([_sym("timezone"), self._encode_timedelta(offset)]),
            ]
        return hy.models.Expression(parts)

    def _encode_timedelta(self, value: timedelta) -> hy.models.Expression:
        seconds = value.total_seconds()
        number = _int(int(seconds)) if seconds == int(seconds) else hy.models.Float(seconds)
        return hy.models.Expression([_sym("timedelta"), hy.models.Keyword("seconds"), number])

    # ------------------------------------------------------------------ decode
    def model_to_py(self, model: Any) -> Any:
        # 1. Handle Hy-specific models first (order of specificity)
        if isinstance(model, hy.models.Keyword):
            return str(model).lstrip(':')

        if isinstance(model, hy.models.String):
            return str(model)

        if isinstance(model, hy.models.Integer):
            return int(model)

        if isinstance(model, hy.models.Float):
            return float(model)

        if isinstance(model, hy.models.Symbol):
            s = str(model)
            if s == "True": return True
            if s == "False": return False
            if s == "None": return None
            return s

        if isinstance(model, hy.models.Dict):
            res = {}
            it = iter(model)
            for k in it:
                try:
                    v = next(it)
                    res[self.model_to_py(k)] = self.model_to_py(v)
                except StopIteration: break
            return res

        # 2. Standard Python collections containing Hy objects
        # (this is what hy_eval returns for {} and [])
        if isinstance(model, dict):
            return {self.model_to_py(k): self.model_to_py(v) for k, v in model.items()}

        if isinstance(model, (list, tuple)) and not isinstance(model, hy.models.Object):
            return [self.model_to_py(item) for item in model]

        # 3. Hy Expressions and Lists
        if isinstance(model, hy.models.Expression):
            if len(model) > 0:
                symbol = str(model[0])
                if symbol in self.expression_decoders:
                    return self.expression_decoders[symbol](model, self)
                if symbol in self._builtin_decoders:
                    try:
                        return self._builtin_decoders[symbol](model)
                    except (TypeError, ValueError, ArithmeticError, InvalidOperation):
                        pass  # not a well-formed constructor call: treat as data
            return [self.model_to_py(item) for item in model]

        if isinstance(model, hy.models.List):
            return [self.model_to_py(item) for item in model]

        return model

    def _call_args(self, model: hy.models.Expression) -> Tuple[List[Any], Dict[str, Any]]:
        """Split ``(f a b :k v)`` into positional and keyword arguments (decoded)."""
        args: List[Any] = []
        kwargs: Dict[str, Any] = {}
        items = list(model[1:])
        i = 0
        while i < len(items):
            item = items[i]
            if isinstance(item, hy.models.Keyword):
                if i + 1 >= len(items):
                    raise ValueError(f"keyword {item} has no value")
                kwargs[str(item).lstrip(":").replace("-", "_")] = self.model_to_py(items[i + 1])
                i += 2
            else:
                args.append(self.model_to_py(item))
                i += 1
        return args, kwargs

    def _decode_datetime(self, model):
        args, kwargs = self._call_args(model)
        if "tzinfo" in kwargs and not (kwargs["tzinfo"] is None or isinstance(kwargs["tzinfo"], timezone)):
            raise ValueError("unsupported tzinfo expression")
        return datetime(*args, **kwargs)

    def _decode_date(self, model):
        args, kwargs = self._call_args(model)
        return date(*args, **kwargs)

    def _decode_timedelta(self, model):
        args, kwargs = self._call_args(model)
        return timedelta(*args, **kwargs)

    def _decode_timezone(self, model):
        args, kwargs = self._call_args(model)
        return timezone(*args, **kwargs)

    def _decode_decimal(self, model):
        args, kwargs = self._call_args(model)
        if len(args) != 1 or kwargs:
            raise ValueError("Decimal takes exactly one argument")
        return Decimal(str(args[0]))


engine_converter = HyConverter()
