class HyRegistry:
    def __init__(self):
        self.state = {}
        self.commands = {}

    def command(self, name=None):
        def decorator(f):
            cmd_name = name or f.__name__.replace("_", "-")
            self.commands[cmd_name] = f
            return f
        return decorator

    def clear(self):
        self.state = {}

    def get_locals(self):
        """Returns a scope containing both hyphenated and underscored names."""
        scope = {"ctx": self.state}
        
        for name, cmd in self.commands.items():
            scope[name] = cmd
            if "-" in name:
                scope[name.replace("-", "_")] = cmd
            elif "_" in name:
                scope[name.replace("_", "-")] = cmd
                
        return scope

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
