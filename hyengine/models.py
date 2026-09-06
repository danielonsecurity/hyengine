import uuid
import hy

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, List, Optional, Union, TypeAlias


@dataclass
class HyNode:
    """High-level AST Node representing a Hy form or expression without exposing hy.models."""

    type: str  # e.g. "expression", "symbol", "keyword", "string", "list", "dict", "literal"
    value: Any  # Pure Python native representation
    head: Optional[str] = (
        None  # For expressions: the function/form name (e.g. "custom-set-config")
    )
    args: List[Any] = field(default_factory=list)  # Arguments/children
    original: Optional[str] = None  # Original Hy code string (e.g. '(+ 10 50)')
    is_dynamic: bool = False  # True if this is an unevaluated expression or code form
    raw: Any = (
        None  # Internal reference to underlying model (for hyengine internal use only)
    )

    @property
    def is_expression(self) -> bool:
        return self.type == "expression"

    @property
    def is_symbol(self) -> bool:
        return self.type == "symbol"

    def get_arg(self, index: int, default: Any = None) -> Any:
        if 0 <= index < len(self.args):
            return self.args[index]
        return default

    def to_python(self) -> Any:
        """Returns clean Python native data structure."""
        if self.is_dynamic and self.original:
            return self.original
        return self.value


# Type Aliases for clarity
HyExpression: TypeAlias = hy.models.Expression
HySymbol: TypeAlias = hy.models.Symbol
HyDict: TypeAlias = hy.models.Dict


@dataclass
class EvaluationRecord:
    value: Any
    timestamp: datetime = field(default_factory=datetime.now)
    original_expr: Optional[Any] = None
    record_id: str = field(default_factory=lambda: str(uuid.uuid4()))


@dataclass
class DynamicExpressionInfo:
    original: Any
    is_dynamic: bool = True
    history: List[EvaluationRecord] = field(default_factory=list)

    def add_evaluation(self, value: Any, original_expr: Optional[Any] = None):
        record = EvaluationRecord(
            value=value, original_expr=original_expr or self.original
        )
        self.history.append(record)
        return record

    @property
    def latest_value(self):
        return self.history[-1].value if self.history else None
