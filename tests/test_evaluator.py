import tempfile
from pathlib import Path
from hyengine.utils import evaluate_file_normalized

def test_evaluate_file_normalized_creates_normalized_result():
    with tempfile.TemporaryDirectory() as tmpdir:
        hy_file = Path(tmpdir) / "test.hy"
        hy_file.write_text("""
        {:email "test@example.com" :password "pass123"}
        """)
        result = evaluate_file_normalized(hy_file)
        assert result["email"] == "test@example.com"
        assert result["password"] == "pass123"

def test_evaluate_file_strict_missing_file_raises():
    from hyengine.evaluator import evaluate_file_strict
    from hyengine.errors import HyEngineError
    import pytest
    from pathlib import Path
    fake_path = Path("/nonexistent/file.hy")
    with pytest.raises(HyEngineError):
        evaluate_file_strict(fake_path)
