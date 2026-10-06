"""Real old run and scenario adoption paths, including no adopted-result writes."""

import json
from dataclasses import replace

import pytest

from core.errors import AppError
from core.services.personnel.operator_machine_service import OperatorMachineService
from core.services.scheduler.execution.execution_ledger_guard import ensure_ledger_execution_schedulable
from core.services.scheduler.operation_execution_feedback_service import (
    ExecutionFeedbackContext,
    OperationExecutionFeedbackService,
)
from core.services.scheduler.schedule_service import ScheduleService
from core.services.workbench.run.worker import WorkbenchRunWorker
from tests.schedule.service.test_scheduler_reschedule_execution_minimum_guard import _seed_two_operation_plan
from tests.workbench.field_workspace_support import FieldAPI
from tests.workbench.run_candidate_adoption_support import INTENT, preview, service
from tests.workbench.run_candidate_support import candidate_case as candidate_fixture  # noqa: F401
from tests.workbench.run_candidate_support import compute
from tests.workbench.scheduler_execution_ledger_support import (
    formal_rows,
    install_case,
    raw_connection,
    read_facts,
)


@pytest.mark.parametrize("simulate", [False])
@pytest.mark.parametrize("payload", [{"completed_quantity": 4}])
def test_old_run_cannot_skip_partial_or_started_new_reports(tmp_path, simulate, payload):
    conn = raw_connection(tmp_path)
    try:
        _seed_two_operation_plan(conn)
        conn.execute("UPDATE BatchOperations SET piece_id=NULL WHERE batch_id='B1'")
        case = install_case(conn)
        case.command("create", case.task(1, 10), payload)
        before = formal_rows(conn)
        with pytest.raises(AppError) as error:
            ScheduleService(conn).run_schedule(["B1"], start_dt="2026-05-01 08:00:00", simulate=simulate, created_by="pytest")
        assert error.value.details["reason"] == "execution_ledger_requires_reconciliation"
        assert error.value.details["op_id"] == 10
        assert formal_rows(conn) == before
    finally:
        conn.close()


def test_complete_report_is_fixed_seed_in_real_run(tmp_path):
    conn = raw_connection(tmp_path)
    try:
        _seed_two_operation_plan(conn)
        case = install_case(conn)
        case.command("create", case.task(1, 10), case.values(1, actual_start="2026-05-01T08:20:00",
            actual_end="2026-05-01T08:50:00", effective_processing_hours=0.5))
        old = formal_rows(conn)
        result = ScheduleService(conn).run_schedule(["B1"], start_dt="2026-05-01 08:00:00", created_by="pytest")
        row = conn.execute("SELECT * FROM Schedule WHERE version=? AND op_id=10", (result["version"],)).fetchone()
        assert row["start_time"] == "2026-05-01 08:20:00" and row["end_time"] == "2026-05-01 08:50:00"
        assert row["machine_id"] == "M1" and row["operator_id"] == "O1" and row["lock_status"] == "locked"
        assert [tuple(r) for r in conn.execute("SELECT * FROM Schedule WHERE version=1 ORDER BY id")] == old["Schedule"]
        assert formal_rows(conn)["OperationExecutionEvents"] == []
        assert read_facts(conn, result["version"])[10].actual_status == "completed"
    finally:
        conn.close()


def test_normal_old_finish_can_be_supplemented_and_used_by_real_replan(candidate_case):
    case = candidate_case
    _, refs = compute(case)
    adopted = service(case.conn).adopt(refs[0], preview(case, refs[0]), "legacy-first-adoption-001", INTENT)
    version = adopted["data"]["official_plan"]["version"]
    schedule = case.conn.execute("SELECT id FROM Schedule WHERE version=? AND op_id=?", (version, case.op_id)).fetchone()[0]
    feedback = OperationExecutionFeedbackService(case.conn)
    context = ExecutionFeedbackContext(version, schedule, case.op_id, "B1", f"{case.op_id}:0:0", "original-operator",
        "legacy-normal-start-001", "adopted", "schedule", "adopted")
    started = feedback.start_operation(context, event_time="2026-09-09 08:00", machine_id="M1", operator_id="O1")
    feedback.finish_operation(replace(context, expected_state_revision=started.state_revision,
        idempotency_key="legacy-normal-finish-001"), event_time="2026-09-09 10:00", quantity_done=3)
    original = formal_rows(case.conn)["OperationExecutionEvents"]
    ensure_ledger_execution_schedulable(read_facts(case.conn, version))
    api = FieldAPI(case)
    task = api.task()
    legacy = task["execution"]["legacy_facts"][-1]
    assert legacy["actual_machine_ref"] is None and legacy["actual_operator_ref"] is None
    OperatorMachineService(case.conn).remove_link("O1", "M1")
    api.create(case.values(3, legacy_fact_ref=legacy["legacy_fact_ref"], reason="保留原实际，只补有效工时"), task)
    assert api.task()["execution"]["data_quality"] == "complete"
    ensure_ledger_execution_schedulable(read_facts(case.conn, version))
    OperatorMachineService(case.conn).add_link("O1", "M1")
    case.batch("B2")
    case.operation("B2")
    case.conn.commit()
    accepted = case.accept(key="legacy-supplement-replan-001", settings=case.settings("B1", "B2"))
    result = WorkbenchRunWorker(case.conn).execute(accepted["run_ref"])
    assert result["state"] == "complete" and result["candidates"]
    for candidate in result["candidates"]:
        tasks = [json.loads(row[0]) for row in case.conn.execute(
            "SELECT payload_json FROM WorkbenchRunCandidateTasks WHERE candidate_ref=?", (candidate["candidate_ref"],))]
        actual = next(row for row in tasks if row["op_id"] == case.op_id)
        assert (actual["start_time"], actual["end_time"]) == ("2026-09-09T08:00:00", "2026-09-09T10:00:00")
        assert (actual["machine_id"], actual["operator_id"]) == ("M1", "O1")
    assert formal_rows(case.conn)["OperationExecutionEvents"] == original
