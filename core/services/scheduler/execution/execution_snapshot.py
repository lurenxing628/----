from __future__ import annotations

from dataclasses import dataclass, fields
from typing import Any, Dict, List, Mapping, Optional, Sequence

from core.models.content import content_text

from .execution_fact_provider import ExecutionFact, ExecutionFactProvider, positive_op_ids

EXECUTION_SNAPSHOT_PREFIX = "execution-snapshot:content-v2:"
RESOURCE_SNAPSHOT_PREFIX = "execution-snapshot:resources-v2:"


@dataclass(frozen=True)
class ExecutionSnapshot:
    revision: str
    op_ids: List[int]
    op_count: int
    state_revisions: Dict[int, str]
    identity_revisions: Dict[int, str]


def _identity_revision(fact: ExecutionFact) -> str:
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
    scenario_id = str(fact.scenario_id or "").strip()
    return (
        f"v={schedule_version};"
        f"schedule={schedule_id};"
        f"op={op_id};"
        f"batch={batch_id};"
        f"source={source_table};"
        f"role={effective_plan_role};"
        f"scenario={scenario_id}"
    )


def execution_fact_values(fact: ExecutionFact) -> Dict[str, Any]:
    """Retain every projection field, including exact actual protection inputs."""
    return {field.name: getattr(fact, field.name) for field in fields(fact)}


def build_execution_snapshot(
    facts_by_op_id: Dict[int, ExecutionFact], op_ids: Sequence[int], *,
    plan_rows: Optional[Dict[int, Dict[str, Any]]] = None,
) -> ExecutionSnapshot:
    ids = positive_op_ids(op_ids)
    state_revisions: Dict[int, str] = {}
    identity_revisions: Dict[int, str] = {}
    for op_id in ids:
        fact = facts_by_op_id.get(int(op_id))
        if fact is None:
            raise ValueError(f"缺少工序 {op_id} 的现场状态快照。")
        identity_revisions[int(op_id)] = _identity_revision(fact)
        state_revisions[int(op_id)] = str(fact.state_revision or "")
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
        state_revisions=state_revisions,
        identity_revisions=identity_revisions,
    )


def collect_execution_snapshot_for_plan_rows(
    conn,
    rows: Sequence[Any],
    plan_fields: Mapping[str, Any],
    *,
    op_ids: Sequence[int],
    logger=None,
) -> ExecutionSnapshot:
    ids = positive_op_ids(op_ids)
    facts = ExecutionFactProvider(conn, logger=logger).facts_by_op_id_for_plan_rows(
        rows,
        plan_fields,
        include_op_ids=ids,
    )
    return build_execution_snapshot(facts, ids)


__all__ = [
    "ExecutionSnapshot",
    "execution_fact_values",
    "build_execution_snapshot",
    "collect_execution_snapshot_for_plan_rows",
    "positive_op_ids",
]
