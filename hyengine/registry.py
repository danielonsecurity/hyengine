from typing import Any, Callable, Dict, Optional, Union

from .values import Code


def _spellings(name: str):
    """Hy code may write either `my-name` or `my_name`."""
    yield name
    if "-" in name:
        yield name.replace("-", "_")
    elif "_" in name:
        yield name.replace("_", "-")


class HyRegistry:
    """The host side of an application embedding Hy.

    Register Python functions (``command``) and values (``define``); then
    ``run`` Hy code or ``compile`` it into Python callables with all of them in
    scope (under both hyphen and underscore spellings), together with the time
    helpers every hyengine scope gets (datetime, date, timedelta, timezone, Decimal).

    Every run gets a fresh scope, so names defined by one piece of code never
    leak into another. Functions produced by ``compile`` keep their own scope.
    """

    def __init__(self):
        self.state = {}
        self.commands: Dict[str, Callable] = {}
        self.values: Dict[str, Any] = {}

    def command(self, name: Optional[str] = None):
        def decorator(f):
            cmd_name = name or f.__name__.replace("_", "-")
            self.commands[cmd_name] = f
            return f
        return decorator

    def define(self, name: str, value: Any) -> None:
        """Make a value available to Hy code under ``name``."""
        self.values[name] = value

    def clear(self):
        self.state = {}

    def get_locals(self):
        """Returns a scope containing both hyphenated and underscored names."""
        scope = {"ctx": self.state}
        for table in (self.values, self.commands):
            for name, item in table.items():
                for spelling in _spellings(name):
                    scope[spelling] = item
        return scope

    def scope(self, **extra: Any) -> Dict[str, Any]:
        """A fresh evaluation scope: registry names + time helpers + ``extra``."""
        from .evaluator import default_scope

        scope = self.get_locals()
        for name, value in extra.items():
            for spelling in _spellings(name):
                scope[spelling] = value
        return default_scope(scope)

    def run(self, code: Union[Code, str], **locals_: Any) -> Any:
        """Evaluate one Hy form with the registry (and ``locals_``) in scope.

        The scope is passed as *globals*, so functions created by the code (e.g.
        ``(fn ...)`` returned by ``compile``) can see registry names when called later.
        """
        import hy

        from .ast import safe_format
        from .converter import engine_converter
        from .errors import HyEngineError, HyEvaluationError

        code = code if isinstance(code, Code) else Code(str(code))
        model = code.model
        try:
            result = hy.eval(model, globals=self.scope(**locals_))
        except HyEngineError:
            raise
        except Exception as e:
            raise HyEvaluationError(str(e), expression=safe_format(model), cause=e) from e
        return engine_converter.model_to_py(result)

    def compile(self, code: Union[Code, str]) -> Any:
        """Evaluate code that produces a value, typically ``(fn [...] ...)`` -> callable."""
        return self.run(code)

    def eval(self, expr):
        from .evaluator import evaluate_expression
        from .errors import HyEngineError, HyEvaluationError
        from .ast import safe_format
        try:
            return evaluate_expression(expr, locals_dict=self.get_locals())
        except HyEngineError:
            raise
        except Exception as e:
            raise HyEvaluationError(
                str(e),
                expression=safe_format(expr),
                cause=e,
            ) from e
