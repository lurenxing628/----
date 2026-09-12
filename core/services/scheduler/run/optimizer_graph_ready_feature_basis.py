"""Explicit feature identities for baseline and successor ordering candidates."""
from __future__ import annotations

from typing import Any, Dict

from core.infrastructure.errors import ValidationError

BATCH_WORKLOAD_BASIS = "batch_workload_v1"
SUCCESSOR_WORKLOAD_BASIS = "operation_successor_v1"
BASELINE_ORDERING_FIELD = "graph_ready_baseline_ordering"
BASELINE_RANK_PREFIX = "baseline_ordering__"


def select_profile_metrics(metrics_by_op_id: Dict[int, Dict[str, Any]], *, profile: Any) -> Dict[int, Dict[str, Any]]:
    """A baseline profile must never silently consume successor feature values."""
    if not str(profile.formula_version).startswith("graph_ready_v2"):
        return metrics_by_op_id
    basis = profile.feature_basis
    if basis == SUCCESSOR_WORKLOAD_BASIS:
        return metrics_by_op_id
    if basis != BATCH_WORKLOAD_BASIS:
        raise ValidationError("GraphReady 候选特征语义不支持。", field="graph_ready_v2_features")
    selected = {}
    for op_id, row in metrics_by_op_id.items():
        baseline = row.get(BASELINE_ORDERING_FIELD)
        if not isinstance(baseline, dict) or baseline.get("graph_ready_workload_version") != basis:
            raise ValidationError("GraphReady 基础排序缺少明确的整批工时特征。", field="graph_ready_v2_features")
        selected[op_id] = baseline
    return selected
