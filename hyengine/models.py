from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, List, Optional, Union, TypeAlias
import uuid
import hy

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
        record = EvaluationRecord(value=value, original_expr=original_expr or self.original)
        self.history.append(record)
        return record

    @property
    def latest_value(self):
        return self.history[-1].value if self.history else None
