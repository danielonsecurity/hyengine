import hy
from hy.compiler import hy_eval
from hy.models import Symbol, Expression
from .converter import engine_converter

class HyEngine:
    """The base resolver and evaluator."""
    
    def __init__(self, globals_dict=None):
        self.globals = globals_dict or {}

    def evaluate_expression(self, expr, locals_dict=None):
        if locals_dict is None: locals_dict = {}
        # Ensure dot-operator handling or standard eval
        try:
            return hy_eval(expr, {**self.globals, **locals_dict}, "__main__")
        except Exception as e:
            # Re-implement your handle_dot_operator logic here if needed
            raise e

    def resolve_value(self, expr, context=None, locals_dict=None):
        """The recursive resolver from HyResolver."""
        if isinstance(expr, Symbol):
            name = str(expr)
            if context and hasattr(context, name):
                return getattr(context, name)
            if locals_dict and name in locals_dict:
                return locals_dict[name]
            return name # Return as string if not found
            
        if isinstance(expr, Expression):
            # Handle (.) operator or Function calls
            if len(expr) > 0 and str(expr[0]) == ".":
                return self._handle_dot(expr, context, locals_dict)
            
            # Standard call
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
