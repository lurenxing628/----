from __future__ import annotations

from dataclasses import dataclass, fields
from typing import Any, Dict, List, Optional

from core.models.content import content_text

from .execution_fact_provider import ExecutionFact

EXECUTION_SNAPSHOT_PREFIX = "execution-snapshot:content-v2:"
RESOURCE_SNAPSHOT_PREFIX = "execution-snapshot:resources-v2:"


@dataclass(frozen=True)
class ExecutionSnapshot:
    revision: str
    op_ids: List[int]
    op_count: int


def _validate_fact_identity(fact: ExecutionFact) -> None:
    missing = []
    op_id = int(fact.op_id or 0)
    schedule_version = int(fact.schedule_version or 0)
    schedule_id = int(fact.schedule_id or 0)
    if op_id <= 0:
        missing.append("op_id")
    if schedule_version <= 0:
        missing.append("schedule_version")
    if schedule_id <= 0:
        missing.append("schedule_id")
    batch_id = str(fact.batch_id or "").strip()
    source_table = str(fact.source_table or "").strip()
    effective_plan_role = str(fact.effective_plan_role or "").strip()
    if not batch_id:
        missing.append("batch_id")
    if not source_table:
        missing.append("source_table")
    if not effective_plan_role:
        missing.append("effective_plan_role")
    if missing:
        raise ValueError(f"现场状态快照缺少完整计划身份：{missing[0]}")


def build_execution_snapshot(
    facts_by_op_id: Dict[int, ExecutionFact], *,
    plan_rows: Optional[Dict[int, Dict[str, Any]]] = None,
) -> ExecutionSnapshot:
    # 工序集合就是事实字典的键；固定顺序，使相同来源的快照内容不受字典插入顺序影响。
    ids = sorted(facts_by_op_id)
    for op_id in ids:
        _validate_fact_identity(facts_by_op_id[op_id])
    names = [field.name for field in fields(ExecutionFact)]
    payload = {"op_ids": ids, "fact_fields": names,
               "facts": [[getattr(facts_by_op_id[op_id], name) for name in names] for op_id in ids]}
    prefix = EXECUTION_SNAPSHOT_PREFIX
    if plan_rows is not None:
        # The complete original arrangement owns reservation durations and resources.
        # Encode it with the facts once, rather than embedding another snapshot text.
        payload["plan_rows"] = [[op_id, plan_rows[op_id]] for op_id in ids]
        prefix = RESOURCE_SNAPSHOT_PREFIX
    return ExecutionSnapshot(
        revision=prefix + content_text(payload),
        op_ids=ids,
        op_count=len(ids),
    )


__all__ = [
    "ExecutionSnapshot",
    "build_execution_snapshot",
]
