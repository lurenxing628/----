"""Late changes to unselected work invalidate formal and simulated runs."""

from datetime import datetime

import pytest

import core.services.scheduler.run.schedule_persistence as persistence_module
import core.services.scheduler.schedule_service as service_module
from core.infrastructure.database import get_connection
from core.infrastructure.errors import AppError
from core.services.scheduler.operation_execution_feedback_service import OperationExecutionFeedbackService
from core.services.scheduler.schedule_service import ScheduleService
from tests.schedule.service.unselected_execution_guardrails_support import (
    context,
    execution_state,
    persistent_state,
    seed_plan,
    start,
)


@pytest.mark.parametrize("simulate,change", [
    (False, "start"), (True, "start"), (True, "pause"), (True, "finish"),
    (True, "exception"), (True, "resource"), (True, "duration"),
])
def test_unselected_fact_changes_during_optimizer_reject_without_schedule_writes(schema_conn, monkeypatch, simulate, change):
    seed_plan(schema_conn)
    initial = None if change == "start" else start(schema_conn)
    before = persistent_state(schema_conn)
    original = service_module.optimize_schedule
    changed = []

    def optimize(**kwargs):
        result = original(**kwargs)
        if changed:
            return result
        feedback = OperationExecutionFeedbackService(schema_conn)
        if change == "start":
            start(schema_conn)
        elif change == "pause":
            feedback.pause_operation(context(initial.state_revision, "pause"),
                                     event_time="2026-09-08 08:20:00", reason_code="equipment", remark="Paused")
        elif change == "finish":
            feedback.finish_operation(context(initial.state_revision, "finish"),
                                      event_time="2026-09-08 08:20:00", quantity_done=1)
        elif change == "exception":
            feedback.report_exception(context(initial.state_revision, "exception"),
                                      event_time="2026-09-08 08:20:00", reason_code="equipment", severity="high", remark="Broken")
        elif change == "resource":
            schema_conn.execute("UPDATE OperationExecutionEvents SET actual_machine_id = 'M2'")
            schema_conn.commit()
        else:
            schema_conn.execute("UPDATE Schedule SET end_time = '2026-09-08 09:30:00' WHERE id = 100")
            schema_conn.commit()
            before["Schedule"] = persistent_state(schema_conn)["Schedule"]
        changed.append(execution_state(schema_conn))
        return result

    monkeypatch.setattr(service_module, "optimize_schedule", optimize)
    with pytest.raises(AppError) as raised:
        ScheduleService(schema_conn).run_schedule(["B2"], start_dt="2026-09-08 08:30:00", simulate=simulate)
    assert raised.value.details["reason"] == "execution_state_changed"
    assert changed
    assert persistent_state(schema_conn) == before
    assert execution_state(schema_conn) == changed[0]


def test_change_after_version_allocation_rolls_back_version_and_preserves_original_fact(schema_conn, monkeypatch):
    seed_plan(schema_conn)
    before = persistent_state(schema_conn)
    original_facts = execution_state(schema_conn)
    original = persistence_module.validate_execution_guard_before_persist
    allocated = []

    def late_change(*args, **kwargs):
        allocated.append(schema_conn.execute("SELECT MAX(version) FROM ScheduleVersionSeq").fetchone()[0])
        start(schema_conn)
        return original(*args, **kwargs)

    monkeypatch.setattr(persistence_module, "validate_execution_guard_before_persist", late_change)
    with pytest.raises(AppError) as raised:
        ScheduleService(schema_conn).run_schedule(["B2"], start_dt="2026-09-08 08:30:00")
    assert allocated == [2]
    assert raised.value.details["reason"] == "execution_state_changed"
    assert persistent_state(schema_conn) == before
    assert execution_state(schema_conn) == original_facts


def test_final_guard_rejects_optimizer_output_that_overlaps_unselected_work(schema_conn, monkeypatch):
    seed_plan(schema_conn)
    start(schema_conn)
    before = persistent_state(schema_conn)
    original = service_module.optimize_schedule

    def overlap(**kwargs):
        result = original(**kwargs)
        for row in result.results:
            row.start_time = datetime(2026, 9, 8, 8, 30)
        return result

    monkeypatch.setattr(service_module, "optimize_schedule", overlap)
    with pytest.raises(AppError) as raised:
        ScheduleService(schema_conn).run_schedule(["B2"], start_dt="2026-09-08 08:30:00", simulate=True)
    assert raised.value.details["reason"] == "unselected_execution_resource_overlap"
    assert persistent_state(schema_conn) == before


def test_new_scope_added_during_run_is_not_hidden_by_expected_op_id_list(schema_conn, monkeypatch):
    seed_plan(schema_conn)
    original = service_module.optimize_schedule
    changed = []

    def new_scope(**kwargs):
        result = original(**kwargs)
        if not changed:
            schema_conn.executescript("""
                INSERT INTO BatchOperations(id, op_code, batch_id, seq, op_type_name, source,
                                            machine_id, operator_id, unit_hours)
                VALUES (30, 'OP30', 'B1', 20, 'Turning', 'internal', 'M1', 'O1', 1);
                INSERT INTO Schedule(id, version, op_id, machine_id, operator_id, start_time, end_time)
                VALUES (102, 1, 30, 'M1', 'O1', '2026-09-08 08:00:00', '2026-09-08 09:00:00');
            """)
            schema_conn.commit()
            changed.append(persistent_state(schema_conn))
        return result

    monkeypatch.setattr(service_module, "optimize_schedule", new_scope)
    with pytest.raises(AppError) as raised:
        ScheduleService(schema_conn).run_schedule(["B2"], start_dt="2026-09-08 08:30:00")
    assert raised.value.details["reason"] == "execution_state_changed"
    assert persistent_state(schema_conn) == changed[0]


def test_other_connection_start_is_detected_and_its_event_is_preserved(db_path, monkeypatch):
    conn = get_connection(db_path)
    other = get_connection(db_path)
    try:
        seed_plan(conn)
        before = persistent_state(conn)
        original = service_module.optimize_schedule
        changed = []

        def concurrent_start(**kwargs):
            result = original(**kwargs)
            if not changed:
                start(other)
                changed.append(execution_state(other))
            return result

        monkeypatch.setattr(service_module, "optimize_schedule", concurrent_start)
        with pytest.raises(AppError) as raised:
            ScheduleService(conn).run_schedule(["B2"], start_dt="2026-09-08 08:30:00")
        assert raised.value.details["reason"] == "execution_state_changed"
        assert persistent_state(conn) == before
        assert execution_state(conn) == changed[0]
    finally:
        other.close()
        conn.close()
