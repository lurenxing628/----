"""Persist an already validated complete plan in the caller's write transaction."""

from datetime import datetime

from core.infrastructure.logging import OperationLogger
from core.models.workbench_command import canonical_json
from core.models.workbench_plan_reference import WorkbenchPlanLocator
from data.repositories.schedule_history_repo import ScheduleHistoryRepository
from data.repositories.schedule_repo import ScheduleRepository
from data.repositories.workbench_plan_identity_repo import WorkbenchPlanIdentityRepository


def persist_official_plan_in_tx(conn, *, prepared, payload, baseline, audit, application_operator):
    if not conn.in_transaction:
        raise RuntimeError("Official plan persistence requires the caller's write transaction")
    audit = dict(audit)
    action = audit.pop("action")
    if not isinstance(action, str) or not action or not audit.get("source"):
        raise ValueError("Official plan audit requires an action and source")
    history = ScheduleHistoryRepository(conn)
    version = history.allocate_next_version()
    locked_ids = prepared.frozen_op_ids | prepared.execution_fixed_op_ids | prepared.execution_completed_op_ids
    rows = [{"op_id": row.op_id, "version": version, "machine_id": row.machine_id,
             "operator_id": row.operator_id, "start_time": row.start_time.isoformat(sep=" "),
             "end_time": row.end_time.isoformat(sep=" "),
             "lock_status": "locked" if row.op_id in locked_ids else "unlocked"}
            for row in payload.schedule_rows]
    if ScheduleRepository(conn).bulk_create(rows) != len(rows):
        raise RuntimeError("Official schedule insert count does not match validated scope")
    audit.update(baseline_ref=baseline["plan_ref"], baseline_version=baseline["version"],
                 version=version, validation="valid", row_count=len(rows),
                 application_operator=application_operator,
                 adopted_at=datetime.now().isoformat(timespec="seconds"), is_simulation=False)
    # Legacy publishers own transactions or update master status. Only their
    # append repositories are composable with the caller's durable receipt.
    history.create({"version": version, "strategy": "manual", "batch_count": len(prepared.batches),
                    "op_count": len(rows), "result_status": "success", "result_summary": canonical_json(audit),
                    "created_by": application_operator})
    identities = WorkbenchPlanIdentityRepository(conn)
    plan_ref = identities.get_plan_ref(WorkbenchPlanLocator(version, "adopted"))
    persisted = [dict(row) for row in conn.execute(
        "SELECT id AS schedule_id,op_id,version FROM Schedule WHERE version=? ORDER BY id", (version,))]
    if len(identities.get_task_refs(plan_ref, persisted)) != len(rows):
        raise RuntimeError("New official task identities are incomplete")
    audit["plan_ref"] = plan_ref
    if not OperationLogger(conn).info("scheduler", action, target_type="schedule", target_id=plan_ref,
                                     operator=application_operator, detail=audit, raise_on_fail=True):
        raise RuntimeError("Official plan adoption audit was not saved")
    identity = {"plan_ref": plan_ref, "version": version, "kind": "official", "is_current_official": True,
                "display_name": "正式计划 v" + str(version), "baseline_ref": baseline["plan_ref"],
                "completeness": "complete",
                "capabilities": {"view": True, "edit_draft": False, "adopt": False, "report_actual": True},
                "blocked_reasons": []}
    return {"official_plan": identity, "row_count": len(rows)}
