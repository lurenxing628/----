"""Batch adapter for the unique ledger; no execution quantity arithmetic here."""

from core.services.workbench.execution.ledger import ExecutionLedgerService

from .snapshot_content import record_content, shared_content


def load_execution(conn, operation_refs):
    """Read all ledger inputs under the batch caller's single snapshot."""
    if not conn.in_transaction:
        raise RuntimeError("Batch execution inputs require a caller read transaction.")
    ledger = ExecutionLedgerService(conn)
    with ledger.read_snapshot():
        return {"facts": ledger.load_many(operation_refs)}


def project_execution_snapshot(raw):
    """The ledger projector consumes captured inputs and performs no SQL."""
    ledger = ExecutionLedgerService(None)
    # load_many 已拒绝缺失的工序，project_loaded 逐个投影载入的工序，这里不再重复核对集合。
    projections = {row.operation_ref: row for row in ledger.project_loaded(raw["facts"], contexts=False)}
    # BatchFacts already includes every projection; global plan/ledger clocks add no
    # batch fact and would invalidate it when an unrelated historical plan changes.
    return {"projections": projections}


def execution_content(execution):
    """Preserve every execution field without repeating names and shared values.

    Captured ledger DTOs stay private and read-only. Only the fingerprint uses
    this compact representation; public details still use to_dict snapshots.
    Dictionary insertion order is not a fact, so operation keys are sorted
    before their values become a record matrix and a shared-value catalog.
    """
    refs = sorted(execution["projections"])
    rows = [dict(vars(execution["projections"][ref]),
                 reports=[vars(report) for report in execution["projections"][ref].reports]) for ref in refs]
    shared = shared_content(rows, ("plan_identity",))
    return dict(execution, projections={"refs": refs, "shared": shared, "records": record_content(rows)})


def protects_execution(projection):
    return bool(projection.reports or projection.execution_state != "unreported"
                or projection.data_quality == "invalid")


def operation_execution_fields(row, ref, facts, *, include_details):
    execution = facts["projections"][ref]
    gaps = list(execution.data_gaps)
    state = execution.execution_state
    quality = execution.data_quality
    if row["status"] == "completed" and state != "complete":
        gaps.append({"code": "completion_inconsistent", "message": "工序标着已完工，但报工记录还对不上；系统保留原来的完工标记和删除保护，请核对。"})
        quality = "invalid"
    status = {"complete": "completed", "started": "processing", "partial": "processing"}.get(state, row["status"])
    return {"status": "completed" if row["status"] == "completed" else status,
            "stored_status": row["status"], "execution": execution.to_dict() if include_details else None, "execution_state": state,
            "data_quality": quality, "data_gaps": gaps, "completed": state == "complete" or row["status"] == "completed"}


def batch_progress(operations, stored_status):
    done = sum(op["completed"] for op in operations)
    complete = bool(operations) and done == len(operations)
    started = any(op["execution_state"] not in (None, "unreported") for op in operations)
    return done, complete, "completed" if complete else "processing" if started else stored_status
