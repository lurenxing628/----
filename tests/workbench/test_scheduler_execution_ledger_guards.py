"""Real old run and scenario adoption paths, including no adopted-result writes."""

import pytest

from core.infrastructure.errors import AppError
from core.infrastructure.logging import OperationLogger
from core.services.execution.ledger_reader import ExecutionLedgerReader
from core.services.scheduler.gantt_adjustment_publish_service import GanttAdjustmentPublishService
from core.services.scheduler.run.schedule_execution_guardrails import (
    _collect_execution_guardrails,
    build_execution_guardrails_from_projections,
)
from core.services.scheduler.schedule_service import ScheduleService
from core.services.workbench.execution_ledger import ExecutionLedgerService
from tests.gantt.test_gantt_scenario_publish import _saved_scenario, _seed_base
from tests.schedule.service.test_scheduler_reschedule_execution_minimum_guard import _seed_two_operation_plan
from tests.workbench.scheduler_execution_ledger_support import (
    formal_rows,
    install_case,
    raw_connection,
    read_facts,
)
from tests.workbench.scheduler_execution_ledger_support import ledger_case as ledger_fixture


@pytest.mark.parametrize("simulate", [False, True])
@pytest.mark.parametrize("payload", [{"completed_quantity": 4}, {"actual_start": "2026-05-01T08:20:00"}])
def test_old_run_cannot_skip_partial_or_started_new_reports(tmp_path, simulate, payload):
    conn = raw_connection(tmp_path)
    try:
        _seed_two_operation_plan(conn)
        conn.execute("UPDATE BatchOperations SET piece_id=NULL WHERE id=10")
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


@pytest.mark.parametrize("kind", ["partial", "complete", "corrected"])
def test_adoption_protects_new_reports_even_when_saved_after_report(tmp_path, kind):
    conn = raw_connection(tmp_path)
    try:
        _seed_base(conn)
        case = install_case(conn)
        payload = case.values(1, actual_start="2026-05-04T08:20:00", actual_end="2026-05-04T08:50:00",
                              effective_processing_hours=0.5)
        if kind == "partial":
            payload["effective_processing_hours"] = None
        saved = case.command("create", case.task(5, 10), payload)["data"]["rows"][0]
        scenario = _saved_scenario(conn)
        if kind == "corrected":
            case.command("correct", saved["report_ref"], {"actual_end": "2026-05-04T08:55:00",
                "original_revision_ref": saved["revision_ref"], "reason": "Correct clock"})
        before = formal_rows(conn)
        with pytest.raises(AppError) as error:
            GanttAdjustmentPublishService(conn, op_logger=OperationLogger(conn)).publish_scenario(
                scenario_id=scenario.scenario_id, confirm_text="正式采用", reason="Verified", published_by="pytest")
        expected = {"partial": "execution_ledger_requires_reconciliation", "complete": "execution_completed_start_moved",
                    "corrected": "execution_snapshot_changed"}
        assert error.value.details["reason"] == expected[kind]
        assert formal_rows(conn) == before
        assert conn.execute("SELECT status FROM ScheduleAdjustmentScenario WHERE scenario_id=?", (scenario.scenario_id,)).fetchone()[0] == "active"
        assert conn.execute("SELECT count(*) FROM OperationLogs WHERE action='publish_scenario'").fetchone()[0] == 0
    finally:
        conn.close()


def test_reporting_after_real_adoption_never_rewrites_adopted_result(tmp_path):
    conn = raw_connection(tmp_path)
    try:
        _seed_base(conn)
        case = install_case(conn)
        scenario = _saved_scenario(conn)
        result = GanttAdjustmentPublishService(conn, op_logger=OperationLogger(conn)).publish_scenario(
            scenario_id=scenario.scenario_id, confirm_text="正式采用", reason="Verified", published_by="pytest")
        before = formal_rows(conn)
        case.command("create", case.task(result.new_version, 10), {"completed_quantity": 0, "remark": "Observed"})
        fact = read_facts(conn, result.new_version)[10]
        assert fact.actual_status == "processing"
        assert formal_rows(conn) == before
    finally:
        conn.close()


@pytest.mark.parametrize("keep_actual_resource", [False, True])
def test_completed_report_adoption_requires_exact_actual_resource(tmp_path, keep_actual_resource):
    conn = raw_connection(tmp_path)
    try:
        _seed_base(conn)
        case = install_case(conn)
        machine, operator = ("M1", "O1") if keep_actual_resource else ("M2", "O2")
        case.command("create", case.task(5, 10), case.values(1, actual_start="2026-05-04T08:00:00",
            actual_end="2026-05-04T09:00:00", effective_processing_hours=1,
            actual_machine_ref=case.ref("machine", machine), actual_operator_ref=case.ref("operator", operator)))
        scenario = _saved_scenario(conn)
        before = formal_rows(conn)
        service = GanttAdjustmentPublishService(conn, op_logger=OperationLogger(conn))
        arguments = {"scenario_id": scenario.scenario_id, "confirm_text": "正式采用", "reason": "Verified", "published_by": "pytest"}
        if keep_actual_resource:
            result = service.publish_scenario(**arguments)
            assert read_facts(conn, result.new_version)[10].actual_status == "completed"
        else:
            with pytest.raises(AppError) as error:
                service.publish_scenario(**arguments)
            assert error.value.details["reason"] == "execution_completed_resource_moved"
            assert formal_rows(conn) == before
    finally:
        conn.close()


@pytest.mark.parametrize("quantity", [None, 4, 10])
def test_supplied_aj_projection_is_consumed_without_report_reload(ledger_case, monkeypatch, quantity):
    case = ledger_case
    case.install()
    if quantity is not None:
        case.command("create", case.task(1, case.op_id), case.values(quantity))
    refs = [row[0] for row in case.conn.execute("SELECT ref FROM WorkbenchPlanSourceRefs WHERE kind='operation' AND active=1")]
    projections = case.ledger.project_operations(refs)
    svc = ScheduleService(case.conn)
    operations = svc.op_repo.list_by_batch("B1")
    expected = None if quantity == 4 else _collect_execution_guardrails(svc, operations, prev_version=1)

    def forbidden(*_args, **_kwargs):
        raise AssertionError("AQ must consume the supplied AJ projection, not read reports again")

    for reader in (ExecutionLedgerReader, ExecutionLedgerService):
        for method in ("load", "project_loaded", "project_operations"):
            monkeypatch.setattr(reader, method, forbidden)
    if quantity == 4:
        with pytest.raises(AppError) as error:
            build_execution_guardrails_from_projections(svc, operations, prev_version=1, execution_projections=projections)
        assert error.value.details["reason"] == "execution_ledger_requires_reconciliation"
    else:
        actual = build_execution_guardrails_from_projections(svc, operations, prev_version=1, execution_projections=projections)
        assert actual == expected


@pytest.mark.parametrize("kind", ["missing", "duplicate", "wrong_plan", "none"])
def test_supplied_projection_missing_duplicate_or_wrong_plan_is_rejected(ledger_case, kind):
    from dataclasses import replace

    case = ledger_case
    case.install()
    projection = case.ledger.get_task(case.task(1, case.op_id))
    values = {"missing": [], "duplicate": [projection, projection],
              "wrong_plan": [replace(projection, plan_identity=None)], "none": None}
    svc = ScheduleService(case.conn)
    with pytest.raises((AppError, ValueError)):
        build_execution_guardrails_from_projections(svc, [], prev_version=1, execution_projections=values[kind])
