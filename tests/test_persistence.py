import tempfile
from pathlib import Path
from hyengine.persistence import save_hy_object
from hyengine.utils import evaluate_file_normalized

def test_save_hy_object_and_load():
    with tempfile.TemporaryDirectory() as tmpdir:
        target = Path(tmpdir)
        data = [{"email": "a@b.com", "password": "pw"}]
        save_hy_object(data, base_dir=target, project="test_proj", filename="users.hy")
        loaded = evaluate_file_normalized(target / "test_proj" / "users.hy")
        
        # It should be a list with normalized dicts
        assert isinstance(loaded, list)
        assert loaded[0]["email"] == "a@b.com"
