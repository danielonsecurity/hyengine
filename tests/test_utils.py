import pytest
from hy.models import Keyword, Symbol
from hyengine.utils import normalize_data

def test_normalize_data_basic_types():
    assert normalize_data(42) == 42
    assert normalize_data("abc") == "abc"

def test_normalize_data_keyword_and_symbol():
    kw = Keyword(":my-key")
    sym = Symbol("some-symbol")
    assert normalize_data(kw) == "my_key"
    assert normalize_data(sym) == "some_symbol"

def test_normalize_data_nested_structures():
    data = {
        Keyword(":key-one"): [Symbol("sym-1"), 2],
        "normal": {Keyword(":inner"): Symbol("sym-2")}
    }
    normalized = normalize_data(data)
    expected = {
        "key_one": ["sym_1", 2],
        "normal": {"inner": "sym_2"}
    }
    assert normalized == expected
