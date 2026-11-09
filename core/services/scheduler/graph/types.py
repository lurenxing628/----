from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Tuple


@dataclass(frozen=True)
class OperationGraphNode:
    node_id: str
    batch_id: str
    op_code: str
    seq: int
    duration_minutes: int
    piece_id: Optional[str] = None
    source: str = "internal"
    is_frozen: bool = False
    machine_id: Optional[str] = None
    candidate_machine_ids: Tuple[str, ...] = field(default_factory=tuple)
    external_group_key: Optional[Tuple[str, ...]] = None
    raw: Mapping[str, Any] = field(default_factory=dict)


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
    "GraphAnalysisSummary",
    "GraphWarning",
    "OperationGraphEdge",
    "OperationGraphNode",
]
