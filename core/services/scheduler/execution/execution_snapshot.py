from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

from .execution_fact_provider import ExecutionFact

RESOURCE_SNAPSHOT_PREFIX = "execution-snapshot:resources-v2:"


@dataclass(frozen=True)
class ExecutionSnapshot:
    revision: str
    op_ids: List[int]
    op_count: int


def build_execution_snapshot(
    facts_by_op_id: Dict[int, ExecutionFact], *, plan_rows: Dict[int, Dict[str, Any]],
) -> ExecutionSnapshot:
    """Facts keep the plan identity their execution scopes were admitted with (OperationExecutionScope.from_values)."""
    ids = sorted(facts_by_op_id)
    return ExecutionSnapshot(
        revision=f"{RESOURCE_SNAPSHOT_PREFIX}{len(ids)}:{len(plan_rows)}",
        op_ids=ids,
        op_count=len(ids),
    )


__all__ = [
    "ExecutionSnapshot",
    "build_execution_snapshot",
]
