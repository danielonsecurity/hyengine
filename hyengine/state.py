class HyState:
    """Persistent state for DSL commands."""
    def __init__(self):
        self._store = {}

    def get(self, key, default=None):
        return self._store.get(key, default)

    def set(self, key, value):
        self._store[key] = value

    def update_dict(self, key, new_dict):
        """Merge dict into existing key state."""
        current = self._store.get(key, {})
        if not isinstance(current, dict):
            current = {}
        self._store[key] = {**current, **new_dict}
