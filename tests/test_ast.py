import hy
import pytest
from hyengine.ast import HyASTManager

def test_round_trip_modification():
    ast = HyASTManager()
    
    content = """;; Project Alpha
(set-meta "v1")
(check "api-bola" 10)
"""
    
    # FIX: Use the manager to parse so it captures comments
    expressions = ast.parse_string(content)
    
    # Modify
    for i, expr in enumerate(expressions):
        if isinstance(expr, hy.models.Expression) and len(expr) > 0 and str(expr[0]) == "check":
            if str(expr[1]) == 'api-bola':
                # Reconstruct immutable expression
                items = list(expr)
                items[2] = hy.models.Integer(20)
                expressions[i] = hy.models.Expression(items)

    # Generate source
    new_source = ast.to_source(expressions)
    
    # Assertions
    assert '(check "api-bola" 20)' in new_source
    assert ";; Project Alpha" in new_source
