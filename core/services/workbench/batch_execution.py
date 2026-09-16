"""Batch adapter for the unique ledger; no execution quantity arithmetic here."""

from collections import defaultdict

from core.infrastructure.workbench_execution_ledger_schema import execution_ledger_objects
from core.models.workbench_command import WorkbenchCommandRejected, input_fingerprint
from core.models.workbench_execution_input import MAX_OPERATIONS
from core.services.workbench.execution_ledger import ExecutionLedgerService
from core.services.workbench.process_queries import _plain


def read_execution(conn, operation_refs):
    names = {row[0] for row in conn.execute("SELECT name FROM sqlite_master")}
    if not names.intersection(execution_ledger_objects()):
        version = conn.execute("SELECT version FROM SchemaVersion WHERE id=1").fetchone()
        receipts = conn.execute("SELECT 1 FROM WorkbenchCommandReceipts WHERE action GLOB 'execution.*' LIMIT 1").fetchone()
        if version is None or type(version[0]) is not int or not 0 <= version[0] < 25 or receipts:
            raise WorkbenchCommandRejected("execution_ledger_unavailable", "报工记录表缺失，无法读取现场进度，请联系维护人员恢复数据。")
        return {"available": False, "projections": {}, "snapshot_facts": {"schema_version": version[0]},
                "issues": [{"code": "execution_ledger_not_installed", "message": "这个数据库还没装报工记录表；现在只保留旧的状态标记和删除保护，逐次进度暂无数据。"}]}
    ledger = ExecutionLedgerService(conn)
    refs, projections = list(operation_refs), {}
    with ledger.read_snapshot() as clock:
        for start in range(0, len(refs), MAX_OPERATIONS):
            for row in ledger.project_operations(refs[start:start + MAX_OPERATIONS]):
                projections[row.operation_ref] = row.to_dict()
        if set(projections) != set(refs):
            raise WorkbenchCommandRejected("execution_ledger_unavailable", "有工序的报工记录读取失败，请联系维护人员核对。")
        return {"available": True, "projections": projections, "issues": [],
                "snapshot_facts": {**clock, "projection_hash": input_fingerprint(_plain(projections))}}


def protects_execution(projection):
    return bool(projection["reports"] or projection["legacy_facts"] or projection["execution_state"] != "unreported"
                or projection["data_quality"] == "invalid")


def operation_execution_fields(row, ref, facts):
    execution = facts["projections"].get(ref)
    gaps = list(execution["data_gaps"] if execution else facts["issues"])
    state = execution["execution_state"] if execution else None
    quality = execution["data_quality"] if execution else "unavailable"
    if execution and row["status"] == "completed" and state != "complete":
        gaps.append({"code": "completion_inconsistent", "message": "工序标着已完工，但报工记录还对不上；系统保留原来的完工标记和删除保护，请核对。"})
        quality = "invalid" if quality == "invalid" or execution["reports"] or execution["legacy_facts"] else "legacy_incomplete"
    status = {"complete": "completed", "started": "processing", "partial": "processing",
              "paused": "paused", "exception": "exception"}.get(state, row["status"]) if state is not None else row["status"]
    return {"status": "completed" if row["status"] == "completed" else status,
            "stored_status": row["status"], "execution": execution, "execution_state": state,
            "data_quality": quality, "data_gaps": gaps, "completed": state == "complete" or row["status"] == "completed"}


def old_event_bindings(facts):
    """Legacy-only protection uses preserved source identities, never batch/seq."""
    sources = defaultdict(list)
    for row in facts["WorkbenchPlanSourceRefs"]:
        if row["kind"] == "schedule_row":
            sources[(row["version"], row["source_key"], row["operation_id"])].append(row["operation_ref"])
    current = set(facts["operation_refs"].values())
    events = defaultdict(list)
    for row in facts["OperationExecutionEvents"]:
        bindings = sources[(row["schedule_version"], str(row["schedule_id"]), row["op_id"])]
        if len(bindings) == 1 and bindings[0]:
            ref = bindings[0]
        else:
            # Ambiguity blocks changes, but is not a completion or quantity claim.
            ref = facts["operation_refs"].get(row["op_id"])
        if ref in current:
            events[ref].append(row)
    return events


def batch_progress(operations, stored_status):
    done = sum(op["completed"] for op in operations)
    complete = bool(operations) and done == len(operations)
    started = any(op["execution_state"] not in (None, "unreported") for op in operations)
    return done, complete, "completed" if complete else "processing" if started else stored_status
