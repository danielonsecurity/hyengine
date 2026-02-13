# hyengine

hyengine is a professional-grade bridge between Python and Hy (a Lisp dialect for Python). It allows you to use Hy as a powerful, declarative configuration language or Domain Specific Language (DSL) while maintaining the ability to programmatically read, evaluate, and even edit the source code.

This library was extracted and refined from the UTMS core to provide a standalone engine for Lisp-based data management.

# Features

    Bidirectional Conversion: Seamlessly translate between Python native types (dict, list, datetime, Decimal) and Hy model objects.

    Stateful DSL Registry: Define Python functions as DSL commands and "collect" state as Hy code executes.

    Modern Hy 1.0 Support: Fully compliant with Hy 1.0 defn syntax and immutable AST models.

    Round-trip AST Editing: Parse Hy files, modify specific values programmatically, and write them back while preserving header comments and formatting.

    Advanced Resolution: Includes a custom resolver for the "dot-operator" (.) to handle Python method calls and attribute access within Hy.

# Installation

Install the package in editable mode from your local directory:

```
cd hyengine
pip install -e .
```

# Quick Start
##  Evaluating Hy Code

Use HyEngine to evaluate expressions or files with a specific context.

```
from hyengine.engine import HyEngine
import hy

engine = HyEngine()
# Basic evaluation

result = engine.evaluate_expression(hy.read("(+ 10 20)"))
print(result) # 30

# Evaluation with context (Dot-operator support)

class Service:
    def get_status(self): return "Running"

ctx = Service()
expr = hy.read("(. self get_status)")
print(engine.resolve_value(expr, context=ctx, locals_dict={"self": ctx})) # "Running"
```
## Building a DSL

Use the HyRegistry to define a declarative language for your project (e.g., an "Offer" or "Task" spec).


```
from hyengine.engine import HyEngine, HyRegistry

registry = HyRegistry()

@registry.command("check")
def handle_check(name, qty=0):
    if "items" not in registry.state:
        registry.state["items"] = []
    registry.state["items"].append({"name": name, "qty": qty})

# Execute a DSL file
# financials.hy: (check "api-security" 10)
engine = HyEngine()
locals_dict = registry.get_locals()
engine.evaluate_file("financials.hy", locals_dict=locals_dict)

print(registry.state["items"]) # [{'name': 'api-security', 'qty': 10}]
```

### Round-trip Editing (AST)

Load a file, modify a value, and save it back without losing your header comments.

```
from hyengine.ast import HyASTManager
import hy

ast = HyASTManager()

# 1. Parse
expressions = ast.parse_file("offer.hy")

# 2. Modify (Reconstruct immutable expressions)
for i, expr in enumerate(expressions):
    if isinstance(expr, hy.models.Expression) and str(expr[0]) == "check":
        items = list(expr)
        items[2] = hy.models.Integer(50) # Update Qty
        expressions[i] = hy.models.Expression(items)

# 3. Write back
with open("offer.hy", "w") as f:
    f.write(ast.to_source(expressions))

```

## Extending the Converter

You can register custom encoders and decoders for your own Python types (e.g., specialized Timestamps).


```
from hyengine.converter import engine_converter
import hy

class MyID:
    def __init__(self, val): self.val = val

def encode_id(obj, conv):
    return hy.models.Expression([hy.models.Symbol("my-id"), hy.models.String(obj.val)])

def decode_id(expr, conv):
    return MyID(conv.model_to_py(expr[1]))

engine_converter.register_encoder(MyID, encode_id)
engine_converter.register_decoder("my-id", decode_id)
```

# Development & Testing

Run the comprehensive test suite to ensure everything is working correctly:

```
pytest tests/
```
The test suite covers:

    test_converter: Data integrity and nesting.

    test_engine: Logic, symbols, and dot-operators.

    test_ast: Round-trip editing and comment preservation.

    test_extensibility: Custom type registration.
