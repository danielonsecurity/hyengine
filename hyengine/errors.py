class HyEngineError(Exception):
    """Base for all hyengine errors."""
    pass


class HyParseError(HyEngineError):
    """Malformed Hy syntax — caught at read/parse time."""
    def __init__(self, message, *, file=None, cause=None):
        self.file = file
        self.cause = cause
        location = f"\n  File: {file}" if file else ""
        super().__init__(f"Parse error{location}\n{message}")


class HyEvaluationError(HyEngineError):
    """Runtime error during hy_eval of a specific expression."""
    def __init__(self, message, *, file=None, expression=None, index=None, cause=None):
        self.file = file
        self.expression = expression
        self.index = index
        self.cause = cause
        parts = [message]
        if file:
            parts.append(f"  File: {file}")
        if index is not None:
            parts.append(f"  Expression #{index + 1}")
        if expression:
            parts.append(f"  Expression: {expression}")
        super().__init__("\n".join(parts))


class HyCommandError(HyEngineError):
    """Error raised inside a registered DSL command."""
    def __init__(self, message, *, command=None, cause=None):
        self.command = command
        self.cause = cause
        cmd = f" in command '{command}'" if command else ""
        super().__init__(f"Command error{cmd}: {message}")


class HyValidationError(HyEngineError):
    """Wrong shape, missing required key, invalid enum value, etc."""
    pass
