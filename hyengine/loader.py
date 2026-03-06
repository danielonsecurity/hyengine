from pathlib import Path

def hy_file_for_project(base_dir: Path, project: str, filename: str) -> Path:
    if not base_dir:
        raise ValueError("base_dir must be provided")
    if not project:
        raise ValueError("project must be provided")
    if not filename:
        raise ValueError("filename must be provided")
    return base_dir / project / filename


def load_hy_file(path: Path, evaluate=True, locals_dict=None):
    from .evaluator import evaluate_file

    if not path.is_file():
        raise FileNotFoundError(f"Hy file not found: {path}")

    content = path.read_text(encoding="utf-8").strip()
    if not content:
        return {} if evaluate else ""

    if evaluate:
        return evaluate_file(str(path), locals_dict)
    return content
