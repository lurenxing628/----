from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Sequence

from core.services.scheduler.execution_fact_provider import ExecutionFact, ExecutionFactProvider


@dataclass(frozen=True)
class ExecutionSnapshot:
    revision: str
    op_ids: List[int]
    op_count: int
    state_revisions: Dict[int, str]
    identity_revisions: Dict[int, str]

    def to_summary(self) -> Dict[str, object]:
        return {
            "execution_snapshot_revision": self.revision,
            "execution_snapshot_op_ids": list(self.op_ids),
            "execution_snapshot_op_count": int(self.op_count),
            "execution_snapshot_op_ids_sample": list(self.op_ids[:50]),
            "execution_snapshot_op_ids_truncated": len(self.op_ids) > 50,
        }


def positive_op_ids(values: Sequence[int]) -> List[int]:
    seen = set()
    out: List[int] = []
    for raw in list(values or []):
        try:
            op_id = int(raw)
        except (TypeError, ValueError):
            continue
        if op_id <= 0 or op_id in seen:
            continue
        seen.add(op_id)
        out.append(op_id)
    return sorted(out)


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


def build_execution_snapshot(facts_by_op_id: Dict[int, ExecutionFact], op_ids: Sequence[int]) -> ExecutionSnapshot:
    ids = positive_op_ids(op_ids)
    state_revisions: Dict[int, str] = {}
    identity_revisions: Dict[int, str] = {}
    for op_id in ids:
        fact = facts_by_op_id.get(int(op_id))
        if fact is None:
            raise ValueError(f"缺少工序 {op_id} 的现场状态快照。")
        identity_revisions[int(op_id)] = _identity_revision(fact)
        state_revisions[int(op_id)] = str(fact.state_revision or "")
    payload = "\n".join(
        f"{op_id}|{identity_revisions[int(op_id)]}|state={state_revisions[int(op_id)]}"
        for op_id in ids
    )
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return ExecutionSnapshot(
        revision=f"execution-snapshot:{digest}",
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
    "build_execution_snapshot",
    "collect_execution_snapshot_for_plan_rows",
    "positive_op_ids",
]
