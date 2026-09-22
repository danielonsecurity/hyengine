from .engine import HyEngine
from .converter import engine_converter
from .ast import HyASTManager
from .utils import normalize_data


def parse_data(content: str):
    """
    Parses Lisp / Hy s-expressions or data strings into pure Python primitives
    (lists, dicts, strings) without evaluating executable code.
    Replaces raw `hy.read(stdout)`.
    """
    manager = HyASTManager()
    models = manager.parse_string(content)
    return [engine_converter.model_to_py(m) for m in models]
