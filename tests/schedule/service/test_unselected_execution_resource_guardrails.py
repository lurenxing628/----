"""Unselected live work reserves resources without becoming a new plan row."""

import pytest

import core.services.scheduler.schedule_service as schedule_service_mod
from core.services.scheduler.config.config_service import ConfigService
from core.services.scheduler.operation_execution_feedback_service import OperationExecutionFeedbackService
from core.services.scheduler.schedule_service import ScheduleService
from tests.schedule.service.unselected_execution_guardrails_support import (
    context,
    execution_state,
    persistent_state,
    preview,
    rows,
    seed_plan,
    start,
)


@pytest.mark.parametrize("machine_id,operator_id", [("M1", "O1"), ("M1", "O2"), ("M2", "O1")])
@pytest.mark.parametrize("graph_mode", ["off", "report", "on"])
def test_unselected_processing_reserves_each_actual_resource(schema_conn, machine_id, operator_id, graph_mode):
    conn = schema_conn
    seed_plan(conn)
    conn.execute("UPDATE BatchOperations SET machine_id = ?, operator_id = ? WHERE id = 20",
                 (machine_id, operator_id))
    conn.commit()
    ConfigService(conn).ensure_defaults()
    conn.execute("UPDATE ScheduleConfig SET config_value = ? WHERE config_key = 'graph_analysis_mode'", (graph_mode,))
    conn.commit()
    start(conn)
    before = execution_state(conn)
    previous_rows = rows(conn, 1)
    scheduled, _ = preview(conn)
    assert set(scheduled) == {20}
    assert scheduled[20]["start_time"] == "2026-09-08 09:00:00"
    assert execution_state(conn) == before
    assert rows(conn, 1) == previous_rows


def test_paused_unselected_work_still_reserves_resources(schema_conn):
    seed_plan(schema_conn)
    first = start(schema_conn)
    OperationExecutionFeedbackService(schema_conn).pause_operation(
        context(first.state_revision, "pause"), event_time="2026-09-08 08:20:00", reason_code="equipment", remark="Paused",
    )
    before = execution_state(schema_conn)
    scheduled, _ = preview(schema_conn)
    assert scheduled[20]["start_time"] == "2026-09-08 09:00:00"
    assert execution_state(schema_conn) == before


@pytest.mark.parametrize("state", ["pending", "completed", "unrelated"])
def test_unselected_nonoccupancy_does_not_freeze_old_plan(schema_conn, state):
    seed_plan(schema_conn)
    if state != "pending":
        first = start(schema_conn)
        if state == "completed":
            OperationExecutionFeedbackService(schema_conn).finish_operation(
                context(first.state_revision, "finish"), event_time="2026-09-08 08:20:00", quantity_done=1,
            )
        else:
            schema_conn.execute("UPDATE BatchOperations SET machine_id = 'M2', operator_id = 'O2' WHERE id = 20")
            schema_conn.commit()
    before = execution_state(schema_conn)
    scheduled, _ = preview(schema_conn)
    assert set(scheduled) == {20}
    assert scheduled[20]["start_time"] == "2026-09-08 08:30:00"
    assert execution_state(schema_conn) == before


def test_actual_resources_not_original_plan_resources_are_reserved(schema_conn):
    seed_plan(schema_conn)
    first = start(schema_conn)
    schema_conn.execute("UPDATE OperationExecutionEvents SET actual_machine_id = 'M2', actual_operator_id = 'O2'")
    schema_conn.execute("UPDATE BatchOperations SET machine_id = 'M2', operator_id = 'O1' WHERE id = 20")
    schema_conn.commit()
    assert first.state_revision
    before = execution_state(schema_conn)
    scheduled, _ = preview(schema_conn)
    assert scheduled[20]["start_time"] == "2026-09-08 09:00:00"
    assert execution_state(schema_conn) == before


@pytest.mark.parametrize("dispatch_mode", ["batch_order", "sgs"])
def test_auto_assignment_observes_machine_and_operator_reservations(schema_conn, dispatch_mode):
    seed_plan(schema_conn)
    start(schema_conn)
    schema_conn.executescript("""
        INSERT INTO OpTypes(op_type_id, name) VALUES ('TURN', 'Turning');
        UPDATE Machines SET op_type_id = 'TURN';
        UPDATE BatchOperations SET op_type_id = 'TURN', machine_id = NULL, operator_id = NULL WHERE id = 20;
    """)
    config = ConfigService(schema_conn)
    config.set_auto_assign_enabled("yes")
    config.set_dispatch(dispatch_mode, "slack")
    scheduled, _ = preview(schema_conn)
    row = scheduled[20]
    assert row["start_time"] == "2026-09-08 08:30:00"
    assert (row["machine_id"], row["operator_id"]) == ("M2", "O2")


def test_snapshot_includes_unselected_pending_but_seeds_and_outputs_do_not(schema_conn, monkeypatch):
    seed_plan(schema_conn)
    start(schema_conn)
    original = schedule_service_mod.optimize_schedule
    calls = []

    def capture(**kwargs):
        calls.append(kwargs)
        return original(**kwargs)

    monkeypatch.setattr(schedule_service_mod, "optimize_schedule", capture)
    before = persistent_state(schema_conn)
    _, summary = preview(schema_conn)
    assert calls
    assert all(set(call["batches"]) == {"B2"} and not call["seed_results"] for call in calls)
    assert summary["execution_snapshot"]["execution_snapshot_op_ids"] == [10, 20]
    assert summary["execution_snapshot"]["execution_snapshot_op_count"] == 2
    assert summary["counts"] == {
        "batch_count": 1, "op_count": 1, "scheduled_ops": 1, "failed_ops": 0, "unscheduled_batch_count": 0,
    }
    assert persistent_state(schema_conn) == before


def test_simulate_only_reserves_without_writing_a_version(schema_conn, monkeypatch):
    seed_plan(schema_conn)
    start(schema_conn)
    before = persistent_state(schema_conn)
    actual_before = execution_state(schema_conn)
    original = schedule_service_mod.optimize_schedule
    outcomes = []

    def capture(**kwargs):
        outcome = original(**kwargs)
        outcomes.append(outcome)
        return outcome

    monkeypatch.setattr(schedule_service_mod, "optimize_schedule", capture)
    result = ScheduleService(schema_conn).run_schedule(["B2"], start_dt="2026-09-08 08:30:00", simulate=True)
    assert result["is_simulation"] is True
    assert result["version"] is None
    assert persistent_state(schema_conn) == before
    assert execution_state(schema_conn) == actual_before
    assert outcomes and all([row.op_id for row in item.results] == [20] for item in outcomes)
    assert all(item.results[0].start_time.strftime("%H:%M") == "09:00" for item in outcomes)


def test_selected_and_unselected_modes_agree_on_resource_release(schema_conn):
    seed_plan(schema_conn)
    start(schema_conn)
    scheduled, _ = preview(schema_conn, ["B1", "B2"])
    assert set(scheduled) == {10, 20}
    assert scheduled[10]["start_time"] == "2026-09-08 08:00:00"
    assert scheduled[10]["seed_source"] == "execution_fact"
    assert scheduled[20]["start_time"] == "2026-09-08 09:00:00"


def test_unselected_fact_survives_two_versions_without_its_batch(schema_conn):
    conn = schema_conn
    seed_plan(conn)
    start(conn)
    before = execution_state(conn)
    for version in (2, 3):
        # A legacy partial version, not a version the new publish guard permits.
        conn.execute("INSERT INTO ScheduleVersionSeq(version) VALUES (?)", (version,))
        conn.execute("INSERT INTO Schedule(op_id, version, machine_id, operator_id, start_time, end_time) "
                     "VALUES (20, ?, 'M1', 'O1', '2026-09-08 09:00:00', '2026-09-08 10:00:00')", (version,))
        conn.execute("INSERT INTO ScheduleHistory(version, strategy, batch_count, op_count, result_summary) "
                     "VALUES (?, 'priority_first', 1, 1, '{}')", (version,))
        conn.commit()
        scheduled, _ = preview(conn)
        assert set(scheduled) == {20}
        assert scheduled[20]["start_time"] == "2026-09-08 09:00:00"
    assert execution_state(conn) == before
