"""Consume the unique ledger; only an explicit unavailable ledger uses old guards."""

from collections import defaultdict
from datetime import datetime
from importlib.util import find_spec

from core.models.operation_execution_event import (
    OperationExecutionEvent,
    parse_operation_event_time,
    validate_operation_execution_event_sequence,
)
from core.models.workbench_preflight import issue


def legacy_times(op, rows):
    parsed = [OperationExecutionEvent.from_row(row) for row in sorted(rows, key=lambda row: row["id"])]
    validate_operation_execution_event_sequence(parsed)
    if any(row.batch_id != op["batch_id"] for row in parsed):
        raise ValueError("wrong batch identity")
    now = datetime.now()
    if any(parse_operation_event_time(row.event_time) > now for row in parsed):
        raise ValueError("future legacy event")
    return ([parse_operation_event_time(row.event_time).isoformat() for row in parsed if row.event_type == "start"],
            [parse_operation_event_time(row.event_time).isoformat() for row in parsed if row.event_type == "finish"])


def legacy_guard(op, events):
    groups = defaultdict(list)
    for event in events:
        groups[(event["schedule_version"], event["schedule_id"], event["source_table"],
                event["effective_plan_role"], event["scenario_id"])].append(event)
    starts, finishes, gaps = [], [], []
    for rows in groups.values():
        try:
            actual_starts, actual_finishes = legacy_times(op, rows)
            starts.extend(actual_starts)
            finishes.extend(actual_finishes)
        except ValueError:
            gaps.append(issue("legacy_execution_invalid", "旧报工记录的编号或先后顺序不完整，这道工序先保持保护，等人工复核。"))
    complete = bool(finishes)
    protected = bool(events or op["status"] in ("processing", "completed", "paused", "exception"))
    return {"execution_state": "complete" if complete else "started" if starts else "unreported",
            "completion_basis": "legacy_finish_event" if complete else None,
            "first_actual_start": min(starts) if starts else None, "confirmed_finish": max(finishes) if finishes else None,
            "remaining_quantity": None, "remaining_plan": None,
            "data_quality": "invalid" if gaps else "legacy_incomplete" if protected else "incomplete",
            "data_gaps": gaps, "protected": protected, "reports": [], "legacy_facts": events}


def execution_projections(facts, operations):
    module = "core.infrastructure.workbench_execution_ledger_schema"
    installed = find_spec(module) is not None
    if installed:
        from core.infrastructure.workbench_execution_ledger_schema import execution_ledger_contract_issues

        installed = not execution_ledger_contract_issues(facts.conn)
    if installed:
        from core.services.workbench.execution_ledger import ExecutionLedgerService

        refs = [facts.operation_ref(op) for op in operations]
        service = ExecutionLedgerService(facts.conn)
        projections = []
        for offset in range(0, len(refs), 10000):
            projections.extend(service.project_operations(refs[offset:offset + 10000]))
        result = {row.operation_ref: row.to_dict() for row in projections}
        if set(result) != set(refs) or len(projections) != len(refs):
            raise ValueError("ExecutionProjection did not cover the exact preflight operation scope")
        return result, []
    events = defaultdict(list)
    for row in facts.tables["OperationExecutionEvents"]:
        events[row["op_id"]].append(row)
    result = {facts.operation_ref(op): legacy_guard(op, events[op["id"]]) for op in operations}
    return result, [issue("execution_ledger_unavailable", "新的报工记录功能尚未开通；旧报工保护已经读到，但这次排产不能提交。")]


def is_protected(projection, op):
    return bool(projection.get("protected") or projection.get("reports") or projection.get("legacy_facts")
                or projection["first_actual_start"] or projection["confirmed_finish"]
                or projection["execution_state"] != "unreported" or op["status"] in ("processing", "completed", "paused", "exception"))
