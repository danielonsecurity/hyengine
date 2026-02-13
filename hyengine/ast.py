import hy
from io import StringIO

class HyASTManager:
    def __init__(self):
        self.header_comments = []

    def parse_string(self, content):
        """Parses a string, capturing header comments before the first code form."""
        lines = content.splitlines()
        self.header_comments = []
        
        # Capture all comments at the top of the file
        for line in lines:
            stripped = line.strip()
            if not stripped: continue
            if stripped.startswith(";;"):
                self.header_comments.append(line) # Keep original line for formatting
            else:
                # Stop at the first line of code
                break
                
        return list(hy.read_many(content))

    def parse_file(self, filepath):
        """Loads a file and parses it using parse_string."""
        with open(filepath, 'r', encoding='utf-8') as f:
            return self.parse_string(f.read())

    def to_source(self, expressions):
        """Converts expressions back to source, prepending header comments."""
        output = []
        if self.header_comments:
            output.extend(self.header_comments)
            output.append("") # Blank line after header

        for expr in expressions:
            output.append(self.format_expression(expr))
        
        return "\n\n".join(output) + "\n"

    def format_expression(self, model):
        """Recursive formatter for human-readable Hy source."""
        if isinstance(model, hy.models.String):
            return f'"{model}"'
        if isinstance(model, hy.models.Symbol):
            return str(model)
        if isinstance(model, hy.models.Keyword):
            return str(model)
        if isinstance(model, hy.models.Integer):
            return str(int(model))
        if isinstance(model, hy.models.Float):
            return str(float(model))
        if isinstance(model, hy.models.Dict):
            parts = []
            it = iter(model)
            for k in it:
                try:
                    v = next(it)
                    parts.append(f"{self.format_expression(k)} {self.format_expression(v)}")
                except StopIteration: break
            return "{" + " ".join(parts) + "}"
        if isinstance(model, hy.models.List):
            items = [self.format_expression(i) for i in model]
            return "[" + " ".join(items) + "]"
        if isinstance(model, hy.models.Expression):
            items = [self.format_expression(i) for i in model]
            return "(" + " ".join(items) + ")"
        return str(model)
