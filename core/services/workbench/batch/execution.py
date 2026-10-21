"""Batch adapter for the unique ledger; no execution quantity arithmetic here."""

from collections import defaultdict

from core.infrastructure.connection_guards import schema_contract_memo
from core.infrastructure.workbench_execution_ledger_schema import execution_ledger_objects
from core.models.workbench_command import WorkbenchCommandRejected
from core.services.workbench.execution.ledger import ExecutionLedgerService
from data.repositories.workbench_execution_repo import WorkbenchExecutionRepository

from .snapshot_content import record_content, shared_content


def load_execution(conn, operation_refs):
    """Read all ledger inputs under the batch caller's single snapshot."""
    if not conn.in_transaction:
        raise RuntimeError("Batch execution inputs require a caller read transaction.")
    names = set(schema_contract_memo(conn).structure.objects)
    if not names.intersection(execution_ledger_objects()):
        repo = WorkbenchExecutionRepository(conn)
        version = repo.schema_version_row()
        receipts = repo.has_execution_receipts()
        if version is None or type(version["version"]) is not int or not 0 <= version["version"] < 25 or receipts:
            raise WorkbenchCommandRejected("execution_ledger_unavailable", "报工记录表缺失，无法读取现场进度，请联系维护人员恢复数据。")
        return {"available": False, "projections": {}, "snapshot_facts": {"schema_version": version["version"]},
                "issues": [{"code": "execution_ledger_not_installed", "message": "这个数据库还没装报工记录表；现在只保留旧的状态标记和删除保护，逐次进度暂无数据。"}]}
    ledger = ExecutionLedgerService(conn)
    refs = list(operation_refs)
    with ledger.read_snapshot():
        return {"available": True, "refs": refs, "facts": ledger.load_many(refs), "now": ledger.clock()}


def project_execution_snapshot(raw):
    """The ledger projector consumes captured inputs and performs no SQL."""
    if not raw["available"]:
        return raw
    ledger = ExecutionLedgerService(None, clock=lambda: raw["now"])
    projections = {row.operation_ref: row for row in ledger.project_loaded(raw["facts"], contexts=False)}
    if set(projections) != set(raw["refs"]):
        raise WorkbenchCommandRejected("execution_ledger_unavailable", "有工序的报工记录读取失败，请联系维护人员核对。")
    # BatchFacts already includes every projection; global plan/ledger clocks add no
    # batch fact and would invalidate it when an unrelated historical plan changes.
    return {"available": True, "projections": projections, "issues": []}


def execution_content(execution):
    """Preserve every execution field without repeating names and shared values.

    Captured ledger DTOs stay private and read-only. Only the fingerprint uses
    this compact representation; public details still use to_dict snapshots.
    Dictionary insertion order is not a fact, so operation keys are sorted
    before their values become a record matrix and a shared-value catalog.
    """
    if not execution["available"]:
        return execution
    refs = sorted(execution["projections"])
    rows = [dict(vars(execution["projections"][ref]),
                 reports=[vars(report) for report in execution["projections"][ref].reports]) for ref in refs]
    shared = shared_content(rows, ("plan_identity",))
    return dict(execution, projections={"refs": refs, "shared": shared, "records": record_content(rows)})


def protects_execution(projection):
    return bool(projection.reports or projection.legacy_facts or projection.execution_state != "unreported"
                or projection.data_quality == "invalid")


def operation_execution_fields(row, ref, facts, *, include_details=True):
    execution = facts["projections"].get(ref)
    gaps = list(execution.data_gaps if execution else facts["issues"])
    state = execution.execution_state if execution else None
    quality = execution.data_quality if execution else "unavailable"
    if execution and row["status"] == "completed" and state != "complete":
        gaps.append({"code": "completion_inconsistent", "message": "工序标着已完工，但报工记录还对不上；系统保留原来的完工标记和删除保护，请核对。"})
        quality = "invalid" if quality == "invalid" or execution.reports or execution.legacy_facts else "legacy_incomplete"
    status = {"complete": "completed", "started": "processing", "partial": "processing",
              "paused": "paused", "exception": "exception"}.get(state, row["status"]) if state is not None else row["status"]
    return {"status": "completed" if row["status"] == "completed" else status,
            "stored_status": row["status"], "execution": execution.to_dict() if execution and include_details else None, "execution_state": state,
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
