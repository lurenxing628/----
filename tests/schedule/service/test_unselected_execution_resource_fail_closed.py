"""Malformed, exceptional or indeterminate unselected execution cannot be ignored."""

import pytest

from core.infrastructure.errors import AppError
from core.services.scheduler.operation_execution_feedback_service import OperationExecutionFeedbackService
from core.services.scheduler.schedule_service import ScheduleService
from tests.schedule.service.unselected_execution_guardrails_support import (
    context,
    execution_state,
    persistent_state,
    rows,
    seed_plan,
    start,
)


@pytest.mark.parametrize("sql,reason", [
    ("UPDATE OperationExecutionEvents SET actual_machine_id = NULL", "missing_actual_resource"),
    ("UPDATE OperationExecutionEvents SET actual_operator_id = NULL", "missing_actual_resource"),
    ("UPDATE OperationExecutionEvents SET actual_machine_id = 'missing'", "unknown_actual_resource"),
    ("UPDATE OperationExecutionEvents SET actual_operator_id = 'missing'", "unknown_actual_resource"),
    ("UPDATE OperationExecutionEvents SET reported_status = 'unknown'", "invalid_execution_fact"),
    ("UPDATE OperationExecutionEvents SET event_time = 'bad-time'", "invalid_execution_fact"),
    ("UPDATE OperationExecutionEvents SET schedule_id = 999", "execution_scope_missing"),
    ("UPDATE OperationExecutionEvents SET batch_id = 'B2'", "execution_scope_missing"),
    ("UPDATE Schedule SET start_time = 'bad-time' WHERE id = 100", "invalid_previous_schedule_time"),
    ("UPDATE Schedule SET end_time = start_time WHERE id = 100", "invalid_previous_schedule_time"),
    ("UPDATE BatchOperations SET source = 'external' WHERE id = 10", "invalid_execution_resource_source"),
    ("UPDATE BatchOperations SET source = 'unknown' WHERE id = 10", "invalid_execution_resource_source"),
])
def test_invalid_unselected_fact_fails_closed_without_writing(schema_conn, sql, reason):
    seed_plan(schema_conn)
    start(schema_conn)
    schema_conn.execute("PRAGMA foreign_keys = OFF")
    schema_conn.execute("PRAGMA ignore_check_constraints = ON")
    schema_conn.execute(sql)
    schema_conn.commit()
    schema_conn.execute("PRAGMA ignore_check_constraints = OFF")
    schema_conn.execute("PRAGMA foreign_keys = ON")
    before = persistent_state(schema_conn)
    actual_before = execution_state(schema_conn)
    with pytest.raises(AppError) as raised:
        ScheduleService(schema_conn).run_schedule(["B2"], start_dt="2026-09-08 08:30:00")
    assert raised.value.code.value == "6003"
    assert raised.value.details["reason"] == reason
    assert persistent_state(schema_conn) == before
    assert execution_state(schema_conn) == actual_before


def test_unselected_exception_blocks_auto_reschedule(schema_conn):
    seed_plan(schema_conn)
    first = start(schema_conn)
    OperationExecutionFeedbackService(schema_conn).report_exception(
        context(first.state_revision, "exception"), event_time="2026-09-08 08:20:00",
        reason_code="equipment", severity="high", remark="Broken",
    )
    before = persistent_state(schema_conn)
    with pytest.raises(AppError) as raised:
        ScheduleService(schema_conn).run_schedule(["B2"], start_dt="2026-09-08 08:30:00")
    assert raised.value.details["reason"] == "execution_exception_blocks_auto_reschedule"
    assert raised.value.details["op_ids"] == [10]
    assert persistent_state(schema_conn) == before


@pytest.mark.parametrize("start_time", ["2026-09-08 09:00:00", "2026-09-09 08:00:00"])
def test_overdue_processing_fact_cannot_be_assumed_finished(schema_conn, start_time):
    seed_plan(schema_conn)
    start(schema_conn)
    before = persistent_state(schema_conn)
    with pytest.raises(AppError) as raised:
        ScheduleService(schema_conn).run_schedule(["B2"], start_dt=start_time)
    assert raised.value.details["reason"] == "execution_resource_release_unknown"
    assert persistent_state(schema_conn) == before


@pytest.mark.parametrize("assignment", [
    "effective_plan_role = 'candidate'", "source_table = 'scenario_schedule'", "scenario_id = 'preview-1'",
])
def test_nonadopted_events_never_become_real_resource_occupancy(schema_conn, assignment):
    seed_plan(schema_conn)
    start(schema_conn)
    schema_conn.execute("PRAGMA ignore_check_constraints = ON")
    schema_conn.execute("UPDATE OperationExecutionEvents SET " + assignment)
    schema_conn.commit()
    schema_conn.execute("PRAGMA ignore_check_constraints = OFF")
    before = execution_state(schema_conn)
    result = ScheduleService(schema_conn).run_schedule(["B2"], start_dt="2026-09-08 08:30:00")
    assert rows(schema_conn, result["version"])[20]["start_time"] == "2026-09-08 08:30:00"
    assert execution_state(schema_conn) == before
