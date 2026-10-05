"""Real old run and scenario adoption paths, including no adopted-result writes."""

import pytest

from core.errors import AppError
from core.services.scheduler.schedule_service import ScheduleService
from tests.schedule.service.test_scheduler_reschedule_execution_minimum_guard import _seed_two_operation_plan
from tests.workbench.scheduler_execution_ledger_support import (
    formal_rows,
    install_case,
    raw_connection,
    read_facts,
)
from tests.workbench.scheduler_execution_ledger_support import ledger_case as ledger_fixture  # noqa: F401


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
