"""Pure scheduler graph input/output dataclasses.

This module must not import NetworkX. It also must not store nx.Graph or
nx.DiGraph objects in any public dataclass field.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class OperationGraphNode:
    """Business-level operation node used by scheduler graph analysis."""

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
    candidate_machine_ids: List[str] = field(default_factory=list)
    candidate_operator_ids: List[str] = field(default_factory=list)
    raw: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class OperationGraphEdge:
    """Business-level directed edge between operation graph nodes."""

    from_node_id: str
    to_node_id: str
    kind: str = "precedence"
    lag_minutes: int = 0
    note: str = ""


@dataclass
class GraphWarning:
    """Business-readable graph warning produced by validators or metrics."""

    code: str
    message: str
    data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class GraphAnalysisSummary:
    """Small graph-analysis summary safe to convert into result diagnostics."""

    node_count: int
    edge_count: int
    is_dag: bool
    cycle_edges: List[Dict[str, Any]] = field(default_factory=list)
    topological_order: List[str] = field(default_factory=list)
    critical_path: List[str] = field(default_factory=list)
    critical_path_minutes: int = 0
    warnings: List[GraphWarning] = field(default_factory=list)
