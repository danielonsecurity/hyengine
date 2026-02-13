import os
import hy
from hy.compiler import hy_eval
from .converter import engine_converter # Import the converter

def evaluate_expression(expr, locals_dict=None):
    if locals_dict is None: 
        locals_dict = {}
    if "__builtins__" not in locals_dict:
        locals_dict["__builtins__"] = globals().get("__builtins__", {})
    
    # Evaluate
    res = hy_eval(expr, locals_dict, "__main__")
    
    # Convert result to Python native types (Keywords -> Strings, etc.)
    return engine_converter.model_to_py(res)

def evaluate_file(path, locals_dict=None):
    if not os.path.exists(path):
        return {}
    if locals_dict is None:
        locals_dict = {}

    with open(path, "r", encoding="utf-8") as f:
        code = f.read()
        if not code.strip(): return {}
        
        full_code = f"(do {code})"
        try:
            expr = hy.read(full_code)
            return evaluate_expression(expr, locals_dict)
        except Exception as e:
            print(f"--- ERROR EVALUATING HY FILE: {path} ---")
            raise e
