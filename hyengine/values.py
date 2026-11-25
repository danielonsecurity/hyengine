"""Value types shared by the converter, definitions and stores."""

from typing import Any

import hy


class Code:
    """Hy source kept as data (e.g. a hook or an action read from a data file).

    Only the source text is stored, so Code values compare by source, hash, and
    pickle cleanly. ``model`` parses it on demand; nothing is ever evaluated here.
    """

    __slots__ = ("source", "_model")

    def __init__(self, source: str):
        self.source = source.strip()
        self._model = None

    @property
    def model(self) -> Any:
        if self._model is None:
            self._model = hy.read(self.source)
        return self._model

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Code) and other.source == self.source

    def __hash__(self) -> int:
        return hash(("hyengine.Code", self.source))

    def __repr__(self) -> str:
        return f"Code({self.source!r})"

    def __getstate__(self):
        return {"source": self.source}

    def __setstate__(self, state):
        self.source = state["source"]
        self._model = None
