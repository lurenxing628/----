"""Real old run and scenario adoption paths, including no adopted-result writes."""

import pytest

from core.errors import AppError
from core.services.execution.ledger_reader import ExecutionLedgerReader
from core.services.scheduler.run.schedule_execution_guardrails import (
    _collect_execution_guardrails,
    build_execution_guardrails_from_projections,
)
from core.services.scheduler.schedule_service import ScheduleService
from core.services.workbench.execution.ledger import ExecutionLedgerService
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
