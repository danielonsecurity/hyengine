from .evaluator import evaluate_expression

class HyRegistry:
    def __init__(self):
        self.state = {}      # The 'Evaluated' result (e.g., Offer objects)
        self.commands = {}   # The DSL functions (e.g., 'check', 'phase')

    def command(self, name=None):
        """Decorator to register a Python function as a Hy DSL command."""
        def decorator(f):
            cmd_name = name or f.__name__.replace("_", "-")
            self.commands[cmd_name] = f
            return f
        return decorator

    def clear(self):
        self.state = {}

    def get_locals(self):
        """Returns the scope for Hy evaluation."""
        return {**self.commands, "ctx": self.state}
