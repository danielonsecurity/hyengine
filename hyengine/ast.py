import hy
from .models import HyNode
from .converter import engine_converter
from typing import Any, Union, List
from io import StringIO
from pathlib import Path


def safe_format(expr, max_len=120):
    """Format a Hy expression for error messages. Never raises."""
    try:
        if expr is None:
            return "None"
        s = HyASTManager().format_expression(expr)
        if len(s) > max_len:
            return s[:max_len] + "..."
        return s
    except Exception:
        try:
            return repr(expr)[:max_len]
        except Exception:
            return "<unprintable expression>"


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
            if not stripped:
                continue
            if stripped.startswith(";;"):
                self.header_comments.append(line)  # Keep original line for formatting
            else:
                # Stop at the first line of code
                break

        return list(hy.read_many(content))

    def parse_file(self, filepath):
        """Loads a file and parses it using parse_string."""
        with open(filepath, "r", encoding="utf-8") as f:
            return self.parse_string(f.read())

    def to_source(self, expressions):
        """Converts expressions back to source, prepending header comments."""
        output = []
        if self.header_comments:
            output.extend(self.header_comments)
            output.append("")  # Blank line after header

        for expr in expressions:
            output.append(self.format_expression(expr))

        return "\n\n".join(output) + "\n"

    def format_expression(self, model):
        """Recursive formatter for human-readable Hy source."""
        if isinstance(model, hy.models.String):
            content = str(model)
            if '"' in content or "\n" in content:
                return f"#[logic[\n{content}]logic]"
            return f'"{content}"'
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
                    parts.append(
                        f"{self.format_expression(k)} {self.format_expression(v)}"
                    )
                except StopIteration:
                    break
            return "{" + " ".join(parts) + "}"
        if isinstance(model, hy.models.List):
            items = [self.format_expression(i) for i in model]
            return "[" + " ".join(items) + "]"
        if isinstance(model, hy.models.Expression):
            items = [self.format_expression(i) for i in model]
            return "(" + " ".join(items) + ")"
        return str(model)

    def _model_to_hynode(self, model: Any) -> HyNode:
        """Recursively converts internal hy.models to clean agnostic HyNode."""
        orig_str = self.format_expression(model)

        if isinstance(model, hy.models.Expression):
            head_str = str(model[0]) if len(model) > 0 else ""
            child_args = [self._model_to_hynode(arg) for arg in model[1:]]
            py_val = engine_converter.model_to_py(model)
            return HyNode(
                type="expression",
                value=py_val,
                head=head_str,
                args=child_args,
                original=orig_str,
                is_dynamic=True,
                raw=model,
            )

        if isinstance(model, hy.models.Symbol):
            return HyNode(
                type="symbol",
                value=str(model),
                original=str(model),
                is_dynamic=False,
                raw=model,
            )

        if isinstance(model, hy.models.Keyword):
            return HyNode(
                type="keyword",
                value=str(model).lstrip(":"),
                original=str(model),
                is_dynamic=False,
                raw=model,
            )

        if isinstance(model, hy.models.List):
            items = [self._model_to_hynode(item) for item in model]
            return HyNode(
                type="list",
                value=[i.value for i in items],
                args=items,
                original=orig_str,
                raw=model,
            )

        if isinstance(model, hy.models.Dict):
            py_dict = engine_converter.model_to_py(model)
            return HyNode(
                type="dict",
                value=py_dict,
                original=orig_str,
                raw=model,
            )

        # Primitives: String, Integer, Float, Boolean, etc.
        py_val = engine_converter.model_to_py(model)
        return HyNode(
            type="literal",
            value=py_val,
            original=orig_str,
            raw=model,
        )

    def parse_nodes(self, content_or_path: Union[str, Path]) -> List[HyNode]:
        """Parses a Hy file or string directly into clean HyNode instances.
        Caller never needs to import hy or check hy.models!"""
        path = (
            Path(content_or_path)
            if isinstance(content_or_path, (str, Path))
            and os.path.exists(str(content_or_path))
            else None
        )

        if path and path.is_file():
            raw_models = self.parse_file(str(path))
        else:
            raw_models = self.parse_string(str(content_or_path))

        return [self._model_to_hynode(m) for m in raw_models]
