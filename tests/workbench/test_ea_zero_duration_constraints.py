"""EA frozen points, precedence, calendar, occupancy, and lossless old-row retention."""

import pytest

from core.models.workbench_command import WorkbenchCommandRejected
from core.services.workbench.run_compute import compute_candidate_run
from core.services.workbench.run_worker import WorkbenchRunWorker
from tests.workbench.ea_zero_duration_support import adopt, point_candidate, trial_adoption_service
from tests.workbench.trial_support import change, create, service, snapshot  # noqa: F401
from tests.workbench.trial_support import trial_case as trial_case


@pytest.mark.parametrize("freeze", [False, True])
def test_locked_or_frozen_point_survives_next_real_engine(trial_case, freeze):
    case = trial_case
    successor = case.operation(seq=2, setup_hours=0, unit_hours=0.25)
    plan = adopt(case, point_candidate(case))
    if freeze:
        case.config(freeze_window_enabled="yes", freeze_window_days=1)
        case.batch("B2")
        extra = case.operation("B2")
        case.conn.commit()
    else:
        case.conn.execute("UPDATE Schedule SET lock_status='locked' WHERE op_id=?", (case.op_id,))
        case.conn.commit()
    before = snapshot(case.conn)
    settings = case.settings("B1", "B2") if freeze else case.settings()
    result = compute_candidate_run(case.conn, settings, case.projections())
    assert case.op_id in result.schedule_input.frozen_op_ids
    for payload in result.candidate_payloads.values():
        by_id = {row.op_id: row for row in payload.schedule_rows}
        assert set(by_id) == ({case.op_id, successor, extra} if freeze else {case.op_id, successor})
        assert by_id[case.op_id].start_time == by_id[case.op_id].end_time
    assert snapshot(case.conn) == before
    if not freeze:
        draft = create(case, {"base": {"plan_ref": plan["plan_ref"]}})
        before = snapshot(case.conn)
        with pytest.raises(WorkbenchCommandRejected) as error:
            change(case, draft)
        assert error.value.code == "task_locked"
        assert snapshot(case.conn) == before
    accepted = case.accept(key="ea-next-point-run-0001", settings=settings)
    persisted = WorkbenchRunWorker(case.conn).execute(accepted["run_ref"])
    next_plan = adopt(case, persisted["candidates"][0]["candidate_ref"], key="ea-next-point-adopt-0001")
    point = case.conn.execute("SELECT * FROM Schedule WHERE version=? AND op_id=?", (next_plan["version"], case.op_id)).fetchone()
    assert point["start_time"] == point["end_time"]
    assert point["lock_status"] == "locked"


def test_point_can_share_occupied_resource_without_hiding_positive_conflict(trial_case):
    case = trial_case
    case.batch("B2")
    case.operation("B2", setup_hours=0, unit_hours=1)
    ref = point_candidate(case, settings=case.settings("B1", "B2"))
    draft = create(case, {"base": {"candidate_ref": ref}})
    index = next(i for i, row in enumerate(draft["tasks"]) if row.get("event_kind") == "point")
    changed = change(case, draft, task=index, start="2026-09-09T09:00:00", machine="M1", operator="O1")["data"]
    assert changed["validation"]["constraints_status"] == "valid", changed["validation"]
    assert all(row["overlap_hours"] == 0 for row in changed["capacity"]["resources"])
    saved = service(case.conn).save(changed["draft_ref"], {"name": "EA coexistence"},
        changed["write_context"]["write_token"], "ea-share-save-0001")["data"]
    preview = trial_adoption_service(case.conn).preview(saved["scenario_ref"])
    assert preview["validation"]["can_adopt"], preview


def test_point_adjustment_still_enforces_precedence(trial_case):
    case = trial_case
    case.operation(seq=2)
    draft = create(case, {"base": {"candidate_ref": point_candidate(case)}})
    index = next(i for i, row in enumerate(draft["tasks"]) if row.get("event_kind") == "point")
    changed = change(case, draft, task=index, start="2026-09-09T09:00:00")["data"]
    assert changed["validation"]["constraints_status"] == "blocked"
    assert "precedence_violation" in {row["code"] for row in changed["validation"]["issues"]}
    saved = service(case.conn).save(changed["draft_ref"], {"name": "EA invalid retained"},
        changed["write_context"]["write_token"], "ea-invalid-save-0001")["data"]
    assert not trial_adoption_service(case.conn).preview(saved["scenario_ref"])["validation"]["can_adopt"]


@pytest.mark.parametrize("start", ["2026-09-09T07:00:00", "2026-09-09T16:00:00", "2026-09-09T18:00:00"])
def test_off_shift_point_adjustment_does_not_create_positive_duration(trial_case, start):
    case = trial_case
    draft = create(case, {"base": {"candidate_ref": point_candidate(case)}})
    before = snapshot(case.conn)
    with pytest.raises(WorkbenchCommandRejected) as error:
        change(case, draft, start=start)
    assert error.value.code == "point_calendar_conflict"
    assert snapshot(case.conn) == before


def test_point_execution_cannot_be_moved_or_overwritten(trial_case):
    case = trial_case
    plan = adopt(case, point_candidate(case))
    case.event(case.op_id, "start")
    draft = create(case, {"base": {"plan_ref": plan["plan_ref"]}})
    before = snapshot(case.conn)
    with pytest.raises(WorkbenchCommandRejected) as error:
        change(case, draft)
    assert error.value.code == "execution_protected"
    assert snapshot(case.conn) == before


@pytest.mark.parametrize("day,frozen", [("2026-09-09", True), ("2026-09-10", False), ("2026-09-11", False)])
def test_freeze_point_uses_left_inclusive_right_exclusive_window(trial_case, day, frozen):
    case = trial_case
    case.conn.execute("UPDATE Batches SET ready_date=?", (day,))
    case.conn.execute("INSERT INTO OperatorCalendar(operator_id,date,shift_start,shift_hours) VALUES ('O1',?,'00:00',8)", (day,))
    adopt(case, point_candidate(case))
    case.config(freeze_window_enabled="yes", freeze_window_days=1)
    case.batch("B2")
    case.operation("B2")
    case.conn.commit()
    before = snapshot(case.conn)
    result = compute_candidate_run(case.conn, case.settings("B1", "B2"), case.projections())
    assert (case.op_id in result.schedule_input.frozen_op_ids) is frozen
    assert snapshot(case.conn) == before
