from hy.models import Keyword, Symbol
from pathlib import Path
from hyengine.evaluator import evaluate_file

def normalize_data(obj):
    """Convert Hy objects into pure Python objects."""
    if isinstance(obj, Keyword):
        return str(obj).lstrip(':').replace("-", "_")
    if isinstance(obj, Symbol):
        return str(obj).replace("-", "_")
    if isinstance(obj, dict):
        return {normalize_data(k): normalize_data(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [normalize_data(x) for x in obj]
    return obj

def evaluate_file_normalized(path: Path, locals_dict=None):
    """Evaluate a Hy file and normalize result for Python consumption."""
    if not isinstance(path, Path):
        path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"Hy file not found: {path}")
    raw = evaluate_file(str(path), locals_dict)
    return normalize_data(raw)
