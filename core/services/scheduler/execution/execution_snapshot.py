from __future__ import annotations

from dataclasses import dataclass, fields
from typing import Any, Dict, List

from core.models.content import content_text

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
    # 工序集合就是事实字典的键；固定顺序，使相同来源的快照内容不受字典插入顺序影响。
    ids = sorted(facts_by_op_id)
    names = [field.name for field in fields(ExecutionFact)]
    # The complete original arrangement owns reservation durations and resources.
    # Encode it with the facts once, rather than embedding another snapshot text.
    payload = {"op_ids": ids, "fact_fields": names,
               "facts": [[getattr(facts_by_op_id[op_id], name) for name in names] for op_id in ids],
               "plan_rows": [[op_id, plan_rows[op_id]] for op_id in ids]}
    return ExecutionSnapshot(
        revision=RESOURCE_SNAPSHOT_PREFIX + content_text(payload),
        op_ids=ids,
        op_count=len(ids),
    )


__all__ = [
    "ExecutionSnapshot",
    "build_execution_snapshot",
]
