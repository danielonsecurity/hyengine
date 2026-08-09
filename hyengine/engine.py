import hy
import os
from hy.compiler import hy_eval
from hy.models import Symbol, Expression
from .converter import engine_converter
from .errors import HyEngineError, HyEvaluationError
from .ast import safe_format

class HyEngine:
    def __init__(self, globals_dict=None):
        # Persistent scope for this engine instance
        self.scope = globals_dict or {}
        if "__builtins__" not in self.scope:
            self.scope["__builtins__"] = __builtins__

    def evaluate_expression(self, expr, locals_dict=None):
        """Evaluates an AST expression within the persistent scope."""
        # Merge any temporary locals provided for this specific call
        if locals_dict:
            self.scope.update(locals_dict)
        try:
            # Evaluate using the persistent scope
            res = hy_eval(expr, self.scope, "__main__")
            return engine_converter.model_to_py(res)
        except Exception as e:
            raise HyEvaluationError(str(e), expression=safe_format(expr), cause=e)

    def evaluate_string(self, content, locals_dict=None, source_name="<string>"):
        """Evaluates a string within the persistent scope."""
        if locals_dict:
            self.scope.update(locals_dict)
        try:
            expressions = list(hy.read_many(content, filename=source_name))
            result = None
            for expr in expressions:
                result = hy_eval(expr, self.scope, "__main__")
            return engine_converter.model_to_py(result)
        except Exception as e:
            raise HyEvaluationError(str(e), file=source_name, cause=e)
    
    def evaluate_file(self, path, locals_dict=None):
        """Evaluates a .hy file, allowing it to modify/read the persistent scope."""
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        # If no locals provided, use the persistent scope.
        # This is the "Bridge" that allows rush.hy variables to reach eco_production.hy.
        target_locals = locals_dict if locals_dict is not None else self.scope
        return self.evaluate_string(content, locals_dict=target_locals, source_name=str(path))

    def resolve_value(self, expr, context=None, locals_dict=None):
        if isinstance(expr, Symbol):
            name = str(expr)
            if context and hasattr(context, name):
                return getattr(context, name)
            if locals_dict and name in locals_dict:
                return locals_dict[name]
            return name 

        if isinstance(expr, Expression):
            if len(expr) > 0 and str(expr[0]) == ".":
                return self._handle_dot(expr, context, locals_dict)
            fn = self.resolve_value(expr[0], context, locals_dict)
            args = [self.resolve_value(a, context, locals_dict) for a in expr[1:]]
            if callable(fn):
                return fn(*args)

        return engine_converter.model_to_py(expr)

    def _handle_dot(self, expr, context, locals_dict):
        obj = self.resolve_value(expr[1], context, locals_dict)
        attr = str(expr[2])
        res = getattr(obj, attr)
        if callable(res) and len(expr) > 3:
            args = [self.resolve_value(a, context, locals_dict) for a in expr[3:]]
            return res(*args)
        return res
