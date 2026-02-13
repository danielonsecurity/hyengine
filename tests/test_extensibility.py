import pytest
import hy
from hyengine.converter import engine_converter

# Simulate a UTMS specific type
class DecimalTimeStamp:
    def __init__(self, value):
        self.value = value
    def __eq__(self, other):
        return self.value == other.value

def test_custom_type_registration():
    # 1. Define Hook Functions
    def encode_ts(ts, conv):
        return hy.models.Expression([
            hy.models.Symbol("DecimalTimeStamp"), 
            conv.py_to_model(ts.value)
        ])

    def decode_ts(expr, conv):
        # expr is (DecimalTimeStamp "2026.01")
        return DecimalTimeStamp(conv.model_to_py(expr[1]))

    # 2. Register with the engine
    engine_converter.register_encoder(DecimalTimeStamp, encode_ts)
    engine_converter.register_decoder("DecimalTimeStamp", decode_ts)

    # 3. Test Python -> Hy
    ts = DecimalTimeStamp("2026.500")
    model = engine_converter.py_to_model(ts)
    assert str(model[0]) == "DecimalTimeStamp"
    assert engine_converter.model_to_py(model[1]) == "2026.500"

    # 4. Test Hy -> Python
    back_to_py = engine_converter.model_to_py(model)
    assert isinstance(back_to_py, DecimalTimeStamp)
    assert back_to_py.value == "2026.500"
