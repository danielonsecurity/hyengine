import hy
from datetime import datetime
from typing import Any, Dict, Callable

class HyConverter:
    def __init__(self):
        self.encoders: Dict[type, Callable] = {}
        self.expression_decoders: Dict[str, Callable] = {}

    def register_encoder(self, type_obj, func):
        self.encoders[type_obj] = func

    def register_decoder(self, symbol_name, func):
        self.expression_decoders[symbol_name] = func

    def py_to_model(self, value: Any) -> hy.models.Object:
        if isinstance(value, hy.models.Object):
            return value
        
        for type_obj, encoder in self.encoders.items():
            if isinstance(value, type_obj):
                return encoder(value, self)

        if isinstance(value, datetime):
            return hy.models.Expression([
                hy.models.Symbol("datetime"), 
                hy.models.Integer(value.year), hy.models.Integer(value.month), 
                hy.models.Integer(value.day), hy.models.Integer(value.hour), 
                hy.models.Integer(value.minute)
            ])
        
        if isinstance(value, dict):
            parts = []
            for k, v in value.items():
                # Ensure we don't double-colon if the string already has one
                key_str = str(k).lstrip(':')
                parts.append(hy.models.Keyword(key_str))
                parts.append(self.py_to_model(v))
            return hy.models.Dict(parts)
        
        if isinstance(value, list):
            return hy.models.List([self.py_to_model(item) for item in value])
        
        if value is None:
            return hy.models.Symbol("None")
        if isinstance(value, bool):
            return hy.models.Symbol("True") if value else hy.models.Symbol("False")
        if isinstance(value, int):
            return hy.models.Integer(value)
        if isinstance(value, float):
            return hy.models.Float(value)
        
        return hy.models.String(str(value))


    def model_to_py(self, model: Any) -> Any:
        # 1. Handle Hy-specific models first (order of specificity)
        if isinstance(model, hy.models.Keyword):
            return str(model).lstrip(':')
        
        if isinstance(model, hy.models.String):
            return str(model)
            
        if isinstance(model, hy.models.Integer):
            return int(model)
            
        if isinstance(model, hy.models.Float):
            return float(model)
            
        if isinstance(model, hy.models.Symbol):
            s = str(model)
            if s == "True": return True
            if s == "False": return False
            if s == "None": return None
            return s

        if isinstance(model, hy.models.Dict):
            res = {}
            it = iter(model)
            for k in it:
                try:
                    v = next(it)
                    res[self.model_to_py(k)] = self.model_to_py(v)
                except StopIteration: break
            return res

        # 2. NEW/FIXED: Handle standard Python collections containing Hy objects
        # This is what hy_eval returns for {} and []
        if isinstance(model, dict):
            return {self.model_to_py(k): self.model_to_py(v) for k, v in model.items()}
            
        if isinstance(model, (list, tuple)) and not isinstance(model, hy.models.Object):
            return [self.model_to_py(item) for item in model]

        # 3. Hy Expressions and Lists
        if isinstance(model, hy.models.Expression):
            if len(model) > 0:
                symbol = str(model[0])
                if symbol == "datetime":
                    try: return datetime(*[self.model_to_py(arg) for arg in model[1:]])
                    except: pass
                if symbol in self.expression_decoders:
                    return self.expression_decoders[symbol](model, self)
            return [self.model_to_py(item) for item in model]

        if isinstance(model, hy.models.List):
            return [self.model_to_py(item) for item in model]
        
        return model

engine_converter = HyConverter()
