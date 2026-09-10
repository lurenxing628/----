from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from typing import Any, Dict, Tuple

from core.infrastructure.errors import AppError, ErrorCode
from core.models.schedule_plan_role import ROLE_ADOPTED, SOURCE_SCHEDULE
from core.services.scheduler.execution.execution_fact_provider import ExecutionFact, ExecutionFactProvider
from core.services.scheduler.execution.execution_snapshot import ExecutionSnapshot, build_execution_snapshot

RESOURCE_SNAPSHOT_PREFIX = "execution-snapshot:resources-v1:"


def _conflict(reason: str) -> AppError:
    return AppError(
        ErrorCode.SCHEDULE_CONFLICT,
        "现场执行事实或正式计划身份不完整，本次没有写入新排程。请先核对现场反馈和正式计划。",
        details={"reason": reason},
    )


def _latest_plan_rows(svc: Any, version: int) -> Dict[int, Dict[str, Any]]:
    # The latest version need not contain every batch. Select each operation's
    # last official identity, never candidate/scenario rows or unscoped events.
    cursor = svc.conn.execute(
        """
        SELECT s.id AS schedule_id, s.version, s.op_id, bo.batch_id,
               bo.source, s.start_time, s.end_time
        FROM Schedule s
        LEFT JOIN BatchOperations bo ON bo.id = s.op_id
        JOIN (SELECT op_id, MAX(version) AS version FROM Schedule
              WHERE version <= ? GROUP BY op_id) latest
          ON latest.op_id = s.op_id AND latest.version = s.version
        ORDER BY s.op_id, s.id
        """,
        (int(version),),
    )
    columns = [item[0] for item in cursor.description]
    rows: Dict[int, Dict[str, Any]] = {}
    for values in cursor:
        row = dict(zip(columns, values))
        op_id = int(row["op_id"])
        if op_id in rows:
            raise _conflict("duplicate_previous_schedule_rows")
        rows[op_id] = row
    return rows


def _validate_event_plan_identities(svc: Any) -> None:
    invalid = svc.conn.execute(
        """
        SELECT e.op_id FROM OperationExecutionEvents e
        LEFT JOIN Schedule s ON s.id = e.schedule_id
        LEFT JOIN BatchOperations bo ON bo.id = e.op_id
        WHERE e.source_table = ? AND e.effective_plan_role = ? AND e.scenario_id IS NULL
          AND (s.id IS NULL OR bo.id IS NULL OR e.schedule_version != s.version
               OR e.op_id != s.op_id OR e.batch_id != bo.batch_id)
        LIMIT 1
        """,
        (SOURCE_SCHEDULE, ROLE_ADOPTED),
    ).fetchone()
    if invalid is not None:
        raise _conflict("execution_scope_missing")


def resource_execution_snapshot(
    facts: Dict[int, ExecutionFact], plan_rows: Dict[int, Dict[str, Any]],
) -> ExecutionSnapshot:
    snapshot = build_execution_snapshot(facts, sorted(facts))
    # Include the reservation inputs as well as append-only event revisions:
    # a plan-duration or actual-resource edit must not pass the final recheck.
    payload = [snapshot.revision, [
        [plan_rows[op_id], fact.actual_status,
         fact.actual_start_time.isoformat() if fact.actual_start_time else None,
         fact.actual_end_time.isoformat() if fact.actual_end_time else None,
         fact.actual_machine_id, fact.actual_operator_id]
        for op_id, fact in sorted(facts.items())
    ]]
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=True).encode("utf-8")).hexdigest()
    return replace(snapshot, revision=RESOURCE_SNAPSHOT_PREFIX + digest)


def collect_resource_execution_facts(
    svc: Any, *, prev_version: int,
) -> Tuple[Dict[int, ExecutionFact], Dict[int, Dict[str, Any]], ExecutionSnapshot]:
    try:
        _validate_event_plan_identities(svc)
        plan_rows = _latest_plan_rows(svc, prev_version)
        facts = ExecutionFactProvider(svc.conn, logger=getattr(svc, "logger", None)).facts_by_op_id_for_plan_rows(
            list(plan_rows.values()),
            {"source_table": SOURCE_SCHEDULE, "effective_plan_role": ROLE_ADOPTED, "scenario_id": None},
            include_op_ids=sorted(plan_rows),
        )
        snapshot = resource_execution_snapshot(facts, plan_rows)
    except (ValueError, TypeError, OverflowError) as exc:
        raise _conflict("invalid_execution_fact") from exc
    return facts, plan_rows, snapshot
