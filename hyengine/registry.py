class HyRegistry:
    def __init__(self):
        self.state = {}
        self.commands = {}

    def command(self, name=None):
        def decorator(f):
            # Store with hyphens for DSL consistency
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
            # If the command has a hyphen, also provide the underscore version
            # so the Python compiler can resolve it after mangling
            if "-" in name:
                scope[name.replace("-", "_")] = cmd
            # Vice versa: if it has underscores, provide the hyphen version
            elif "_" in name:
                scope[name.replace("_", "-")] = cmd
                
        return scope
