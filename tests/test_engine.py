import pytest
from hyengine.engine import HyEngine
import hy

class MockService:
    def __init__(self, name):
        self.service_name = name
        self.active = True
    
    def get_status(self, prefix=""):
        return f"{prefix}Status: {self.service_name}"

def test_basic_evaluation():
    engine = HyEngine()
    expr = hy.read("(+ 10 20)")
    assert engine.evaluate_expression(expr) == 30

def test_context_resolution():
    engine = HyEngine()
    obj = MockService("AuthService")
    # Resolve a symbol 'service_name' from the object context
    expr = hy.models.Symbol("service_name")
    assert engine.resolve_value(expr, context=obj) == "AuthService"

def test_dot_operator_method_call():
    engine = HyEngine()
    obj = MockService("PricingEngine")
    
    # Test (. self get-status "Current ")
    expr = hy.read('(. self get_status "Current ")')
    result = engine.resolve_value(expr, context=obj, locals_dict={"self": obj})
    assert result == "Current Status: PricingEngine"

def test_dot_operator_attribute_access():
    engine = HyEngine()
    obj = MockService("Nexus")
    
    # Test (. self active)
    expr = hy.read("(. self active)")
    assert engine.resolve_value(expr, context=obj, locals_dict={"self": obj}) is True
