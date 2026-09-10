"""Do not publish a version that leaves live work unable to report finish."""

from dataclasses import replace

import pytest

import core.services.scheduler.run.schedule_input_collector as collector_module
from core.infrastructure.errors import AppError
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


@pytest.mark.parametrize("paused", [False, True])
def test_publish_rejected_then_original_scope_can_finish(schema_conn, paused):
    seed_plan(schema_conn)
    current = start(schema_conn)
    feedback = OperationExecutionFeedbackService(schema_conn)
    if paused:
        current = feedback.pause_operation(
            context(current.state_revision, "pause"), event_time="2026-09-08 08:20:00",
            reason_code="equipment", remark="Waiting for adjustment",
        )
    before = persistent_state(schema_conn)
    actual_before = execution_state(schema_conn)
    with pytest.raises(AppError) as raised:
        ScheduleService(schema_conn).run_schedule(["B2"], start_dt="2026-09-08 08:30:00")
    assert raised.value.details["reason"] == "execution_feedback_continuity_blocks_publish"
    assert raised.value.details["batch_ids"] == ["B1"]
    assert raised.value.details["unselected_batch_ids"] == ["B1"]
    assert persistent_state(schema_conn) == before
    assert execution_state(schema_conn) == actual_before
    finished = feedback.finish_operation(
        context(current.state_revision, "finish"), event_time="2026-09-08 09:00:00", quantity_done=1,
    )
    assert finished.state.current_status == "completed"
    assert (finished.event.schedule_version, finished.event.schedule_id) == (1, 100)
    result = ScheduleService(schema_conn).run_schedule(["B2"], start_dt="2026-09-08 09:00:00")
    assert set(rows(schema_conn, result["version"])) == {20}
    assert rows(schema_conn, result["version"])[20]["start_time"] == "2026-09-08 09:00:00"


@pytest.mark.parametrize("paused", [False, True])
def test_selected_live_work_keeps_existing_formal_reschedule_path(schema_conn, paused):
    seed_plan(schema_conn)
    first = start(schema_conn)
    if paused:
        OperationExecutionFeedbackService(schema_conn).pause_operation(
            context(first.state_revision, "pause"), event_time="2026-09-08 08:20:00",
            reason_code="equipment", remark="Waiting for adjustment",
        )
    before_events = execution_state(schema_conn)["events"]
    result = ScheduleService(schema_conn).run_schedule(["B1", "B2"], start_dt="2026-09-08 08:30:00")
    scheduled = rows(schema_conn, result["version"])
    assert set(scheduled) == {10, 20}
    assert scheduled[10]["start_time"] == "2026-09-08 08:00:00"
    assert scheduled[10]["lock_status"] == "locked"
    assert scheduled[20]["start_time"] == "2026-09-08 09:00:00"
    assert execution_state(schema_conn)["events"] == before_events


@pytest.mark.parametrize("selected", [["B2"], ["B1", "B2"]])
def test_repeated_simulations_leave_original_finish_available(schema_conn, selected):
    seed_plan(schema_conn)
    first = start(schema_conn)
    before = persistent_state(schema_conn)
    for _ in range(2):
        scheduled, _ = preview(schema_conn, selected)
        assert scheduled[20]["start_time"] == "2026-09-08 09:00:00"
    assert persistent_state(schema_conn) == before
    finished = OperationExecutionFeedbackService(schema_conn).finish_operation(
        context(first.state_revision, "finish"), event_time="2026-09-08 09:00:00", quantity_done=1,
    )
    assert finished.state.current_status == "completed"


@pytest.mark.parametrize("selected", [["B2"], ["B1", "B2"]])
def test_guard_disabled_counterexample_confirms_latest_and_full_scope_conflict(schema_conn, selected, monkeypatch):
    seed_plan(schema_conn)
    first = start(schema_conn)
    # Reproduce legacy partial publishing only in the isolated DB. All-selected
    # publishing is the unchanged product path, with no guard bypass.
    if selected == ["B2"]:
        monkeypatch.setattr(collector_module, "ensure_execution_feedback_publishable", lambda *args, **kwargs: None)
    result = ScheduleService(schema_conn).run_schedule(selected, start_dt="2026-09-08 08:30:00")
    current_rows = rows(schema_conn, result["version"])
    feedback = OperationExecutionFeedbackService(schema_conn)
    with pytest.raises(AppError) as old_error:
        feedback.finish_operation(context(first.state_revision, "finish-old"),
                                  event_time="2026-09-08 09:00:00", quantity_done=1)
    assert old_error.value.details["reason"] == "not_current_official_plan"
    if "B1" in selected:
        fresh_context = replace(context("10:0:0", "finish-new"),
                                schedule_version=result["version"], schedule_id=current_rows[10]["id"])
        with pytest.raises(AppError) as new_error:
            feedback.finish_operation(fresh_context, event_time="2026-09-08 09:00:00", quantity_done=1)
        assert new_error.value.details["reason"] == "invalid_state_transition"
        assert new_error.value.details["current_status"] == "not_started"
    else:
        assert 10 not in current_rows
    events = schema_conn.execute("SELECT schedule_version, schedule_id, event_type FROM OperationExecutionEvents").fetchall()
    assert [tuple(row) for row in events] == [(1, 100, "start")]
