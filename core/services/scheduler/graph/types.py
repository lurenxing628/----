from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Mapping, NoReturn, Optional, Tuple


class FrozenDict(dict):
    """JSON-serializable immutable dict used by graph value snapshots."""

    def _readonly(self) -> NoReturn:
        raise TypeError("FrozenDict is immutable")

    def __setitem__(self, key: Any, value: Any) -> None:
        self._readonly()

    def __delitem__(self, key: Any) -> None:
        self._readonly()

    def clear(self) -> None:
        self._readonly()

    def pop(self, key: Any, default: Any = None) -> Any:
        self._readonly()

    def popitem(self) -> Tuple[Any, Any]:
        self._readonly()

    def setdefault(self, key: Any, default: Any = None) -> Any:
        self._readonly()

    def update(self, *args: Iterable[Tuple[Any, Any]], **kwargs: Any) -> None:
        self._readonly()


def _freeze_json_like(value: Any) -> Any:
    if isinstance(value, FrozenDict):
        return value
    if isinstance(value, dict):
        return FrozenDict({str(k): _freeze_json_like(v) for k, v in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_json_like(item) for item in value)
    return value


def _compact_text_tuple(values: Any) -> Tuple[str, ...]:
    compact = []
    for item in values or ():
        if item is None:
            continue
        text = str(item).strip()
        if not text:
            continue
        compact.append(text)
    return tuple(compact)


def _require_nonblank(value: Any, *, field_name: str) -> None:
    if not str(value or "").strip():
        raise ValueError(f"OperationGraphNode.{field_name} 不能为空。")


def _require_int_value(value: Any, *, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"OperationGraphNode.{field_name} 必须是整数。")
    return value


@dataclass(frozen=True)
class OperationGraphNode:
    node_id: str
    batch_id: str
    op_code: str
    seq: int
    name: str
    duration_minutes: int
    part_no: Optional[str] = None
    priority: str = "normal"
    source: str = "internal"
    status: str = "pending"
    due_date: Optional[str] = None
    op_type_id: Optional[str] = None
    machine_id: Optional[str] = None
    operator_id: Optional[str] = None
    supplier_id: Optional[str] = None
    ext_group_id: Optional[str] = None
    ext_merge_mode: str = ""
    ext_group_total_days: Optional[float] = None
    merge_context_degraded: bool = False
    candidate_machine_ids: Tuple[str, ...] = field(default_factory=tuple)
    candidate_operator_ids: Tuple[str, ...] = field(default_factory=tuple)
    raw: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_nonblank(self.node_id, field_name="node_id")
        _require_nonblank(self.batch_id, field_name="batch_id")
        _require_nonblank(self.op_code, field_name="op_code")
        seq = _require_int_value(self.seq, field_name="seq")
        duration_minutes = _require_int_value(self.duration_minutes, field_name="duration_minutes")
        if duration_minutes < 0:
            raise ValueError("OperationGraphNode.duration_minutes 不能为负数。")
        object.__setattr__(self, "seq", seq)
        object.__setattr__(self, "duration_minutes", duration_minutes)
        object.__setattr__(self, "candidate_machine_ids", _compact_text_tuple(self.candidate_machine_ids))
        object.__setattr__(self, "candidate_operator_ids", _compact_text_tuple(self.candidate_operator_ids))
        object.__setattr__(self, "raw", _freeze_json_like(dict(self.raw or {})))


@dataclass(frozen=True)
class OperationGraphEdge:
    from_node_id: str
    to_node_id: str
    kind: str = "precedence"
    lag_minutes: int = 0
    note: str = ""


@dataclass
class GraphWarning:
    code: str
    message: str
    data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class GraphAnalysisSummary:
    node_count: int
    edge_count: int
    is_dag: bool
    cycle_edges: List[Dict[str, Any]]
    topological_order: List[str]
    critical_path: List[str]
    critical_path_minutes: int
    node_metrics: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    warnings: List[GraphWarning] = field(default_factory=list)


__all__ = [
    "FrozenDict",
    "GraphAnalysisSummary",
    "GraphWarning",
    "OperationGraphEdge",
    "OperationGraphNode",
]
