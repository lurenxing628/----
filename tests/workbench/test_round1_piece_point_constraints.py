"""Zero occupancy never relaxes real shifts, resource conflicts or piece DAGs."""

import pytest

from core.models.workbench_command import WorkbenchCommandRejected
from tests.workbench.ea_zero_duration_support import trial_adoption_service
from tests.workbench.round1_piece_point_support import adopt, candidate, layout, operation_ref
from tests.workbench.round1_piece_point_support import point_case as point_case
from tests.workbench.trial_support import change, create, service, snapshot
from tests.workbench.trial_support import trial_case as trial_case


@pytest.mark.parametrize("start", ("2026-09-09T08:00:00", "2026-09-09T09:00:00", "2026-09-09T14:00:00"))
def test_piece_common_points_share_positive_resource_without_occupancy(point_case, start):
    case = point_case
    ids = layout(case, mixed=False)
    case.batch("B2")
    case.operation("B2", unit_hours=2)
    case.conn.commit()
    ref = candidate(case, settings=case.settings("B1", "B2"))
    draft = create(case, {"base": {"candidate_ref": ref}})
    piece_ref = operation_ref(case, ids["item-A", 50])
    index = next(i for i, task in enumerate(draft["tasks"]) if task["operation_ref"] == piece_ref)
    changed = change(case, draft, task=index, start=start, machine="M1", operator="O1")["data"]
    assert changed["validation"]["constraints_status"] == "valid", changed["validation"]
    assert all(row["overlap_hours"] == 0 for row in changed["capacity"]["resources"])
    assert all(row["occupied_hours"] == row["arranged_hours"] == 6 for row in changed["capacity"]["resources"])
    points = [task for task in changed["tasks"] if task.get("event_kind") == "point"]
    assert len(points) == len(ids)
    assert all(task["start"] == task["end"] and task["occupies_resources"] is False for task in points)
    saved = service(case.conn).save(changed["draft_ref"], {"name": "R1-A shared resource"},
        changed["write_context"]["write_token"], "r1a-coexist-save-0001")["data"]
    adopt(case, saved["scenario_ref"], trial=True, key="r1a-coexist-adopt-0001")


@pytest.mark.parametrize("work,start", ((("item-A", 20), "2026-09-09T08:00:00"),
    (("item-A", 20), "2026-09-09T13:00:00"), ((None, 40), "2026-09-09T08:45:00")))
def test_piece_points_keep_fork_join_precedence(point_case, work, start):
    case = point_case
    ids = layout(case)
    draft = create(case, {"base": {"candidate_ref": candidate(case)}})
    ref = operation_ref(case, ids[work])
    index = next(i for i, task in enumerate(draft["tasks"]) if task["operation_ref"] == ref)
    changed = change(case, draft, task=index, start=start)["data"]
    assert changed["validation"]["constraints_status"] == "blocked", changed["validation"]
    assert "precedence_violation" in {item["code"] for item in changed["validation"]["issues"]}
    saved = service(case.conn).save(changed["draft_ref"], {"name": "R1-A invalid ordering retained"},
        changed["write_context"]["write_token"], "r1a-precedence-save-0001")["data"]
    preview = trial_adoption_service(case.conn).preview(saved["scenario_ref"])
    assert not preview["validation"]["can_adopt"] and preview["write_context"]["write_token"] is None


@pytest.mark.parametrize("start", ("2026-09-09T07:59:59", "2026-09-09T16:00:00", "2026-09-09T18:00:00"))
def test_piece_point_off_shift_move_is_rejected_without_changes(point_case, start):
    case = point_case
    ids = layout(case, mixed=False)
    draft = create(case, {"base": {"candidate_ref": candidate(case)}})
    ref = operation_ref(case, ids["item-A", 50])
    index = next(i for i, task in enumerate(draft["tasks"]) if task["operation_ref"] == ref)
    before = snapshot(case.conn)
    with pytest.raises(WorkbenchCommandRejected) as caught:
        change(case, draft, task=index, start=start)
    assert caught.value.code == "point_calendar_conflict"
    assert snapshot(case.conn) == before


def test_piece_point_uses_real_personal_calendar_and_not_downtime_occupancy(point_case):
    case = point_case
    ids = layout(case, mixed=False)
    case.conn.execute("INSERT INTO OperatorCalendar(operator_id,date,shift_start,shift_hours,efficiency) "
                      "VALUES ('O1','2026-09-09','10:00',4,0.5)")
    case.conn.execute("INSERT INTO MachineDowntimes(machine_id,start_time,end_time,reason_code,status) "
                      "VALUES ('M1','2026-09-09 09:00:00','2026-09-09 12:00:00','repair','active')")
    case.conn.commit()
    plan = adopt(case, candidate(case))["data"]["official_plan"]
    rows = case.conn.execute("SELECT start_time,end_time FROM Schedule WHERE version=?", (plan["version"],)).fetchall()
    assert all(tuple(row) == ("2026-09-09 12:00:00", "2026-09-09 12:00:00") for row in rows)
    draft = create(case, {"base": {"plan_ref": plan["plan_ref"]}})
    ref = operation_ref(case, ids[None, 10])
    index = next(i for i, task in enumerate(draft["tasks"]) if task["operation_ref"] == ref)
    changed = change(case, draft, task=index, start="2026-09-09T10:00:00", machine="M1", operator="O1")["data"]
    assert changed["validation"]["constraints_status"] == "valid", changed["validation"]
    assert all(row["occupied_hours"] == row["arranged_hours"] == 0 for row in changed["capacity"]["resources"])
    saved = service(case.conn).save(changed["draft_ref"], {"name": "R1-A point in shift"},
        changed["write_context"]["write_token"], "r1a-calendar-save-0001")["data"]
    adopt(case, saved["scenario_ref"], trial=True, key="r1a-calendar-adopt-0001")
