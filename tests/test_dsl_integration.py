import hy
from hyengine.registry import HyRegistry

def test_registry_command_add_user():
    registry = HyRegistry()
    
    users_state = {}
    @registry.command("add-user")
    def add_user(email, pw):
        users_state[email] = pw
        return True
    
    # simulate Hy DSL call
    expr = hy.read('(add-user "test@example.com" "secret")')
    registry.eval(expr)
    
    assert "test@example.com" in users_state
    assert users_state["test@example.com"] == "secret"
