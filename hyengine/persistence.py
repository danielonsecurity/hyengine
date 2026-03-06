from pathlib import Path
from .loader import hy_file_for_project
import hy
from .converter import engine_converter
from .ast import HyASTManager

def save_hy_object(obj, base_dir: Path, project: str, filename: str):
    path = hy_file_for_project(base_dir, project, filename)

    hy_expr = engine_converter.py_to_model(obj)
    hy_code = HyASTManager().format_expression(hy_expr)

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(hy_code, encoding="utf-8")


def load_hy_object(base_dir: Path, project: str, filename: str):
    path = hy_file_for_project(base_dir, project, filename)
    from .evaluator import evaluate_file
    return evaluate_file(str(path))
