import hy
from hy.compiler import hy_eval

def evaluate_expression(expr, locals_dict=None):
    if locals_dict is None: locals_dict = {}
    locals_dict["__builtins__"] = globals()["__builtins__"]
    return hy_eval(expr, locals_dict, "__main__")

def evaluate_file(path, locals_dict=None):
    with open(path, "r") as f:
        code = f.read()
    expressions = hy.read_many(code)
    last_res = None
    for expr in expressions:
        last_res = evaluate_expression(expr, locals_dict)
    return last_res
