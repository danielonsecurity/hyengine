import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, List, Optional, Union, TypeAlias, Dict, Callable

import hy
from hy.models import Expression, Symbol, Keyword, List as HyList, Dict as HyDict, Integer, String

# Type Aliases
HyValue: TypeAlias = Union[Integer, float, int, String, Symbol, HyList, Expression]
ResolvedValue: TypeAlias = Any
LocalsDict: TypeAlias = Dict[str, Any]

@dataclass
class HyNode:
    type: str  
    value: Any 
    children: Optional[List["HyNode"]] = None
    comment: Optional[str] = None  
    original: Optional[str] = None  
    is_dynamic: bool = False
    field_name: Optional[str] = None

    def __post_init__(self):
        self.children = self.children or []

@dataclass
class DynamicExpressionInfo:
    original: Any
    is_dynamic: bool = True
    history: List[Any] = field(default_factory=list)

    def add_evaluation(self, value: Any):
        self.history.append({"value": value, "ts": datetime.now()})
