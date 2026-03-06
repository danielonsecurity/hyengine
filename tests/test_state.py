import pytest
from hyengine.state import HyState

def test_hystate_set_get_update():
    state = HyState()
    state.set("key1", 123)
    assert state.get("key1") == 123
    state.update_dict("key2", {"a": 1, "b": 2})
    assert state.get("key2") == {"a": 1, "b": 2}

def test_hystate_update_merges_existing_dict():
    state = HyState()
    state.set("d", {"x": 1})
    state.update_dict("d", {"y": 2})
    assert state.get("d") == {"x": 1, "y": 2}
