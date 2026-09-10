"""Frozen seeds and original execution remain mandatory for piece points."""

import pytest

from core.models.workbench_command import WorkbenchCommandRejected
from core.services.workbench.run_compute import compute_candidate_run
from tests.workbench.test_round1_piece_point_support import adopt, artifact, candidate, layout, operation_ref
from tests.workbench.test_round1_piece_point_support import point_case as point_case
from tests.workbench.trial_support import change, create, service, snapshot
from tests.workbench.trial_support import trial_case as trial_case


@pytest.mark.parametrize("freeze", (False, True))
def test_piece_point_lock_or_freeze_survives_next_managed_worker(point_case, freeze):
    case = point_case
    ids = layout(case)
    plan = adopt(case, candidate(case))["data"]["official_plan"]
    point = ids["item-A", 50]
    if freeze:
        case.config(freeze_window_enabled="yes", freeze_window_days=1)
        case.batch("B2", ready_date="2026-09-10")
        case.operation("B2", unit_hours=.25)
        case.conn.commit()
    else:
        case.conn.execute("UPDATE Schedule SET lock_status='locked' WHERE version=? AND op_id=?", (plan["version"], point))
        case.conn.commit()
    settings = case.settings("B1", "B2") if freeze else case.settings()
    before = snapshot(case.conn)
    computation = compute_candidate_run(case.conn, settings, case.projections())
    assert point in computation.schedule_input.frozen_op_ids
    assert snapshot(case.conn) == before
    ref = candidate(case, key="r1a-protected-run-0002", settings=settings)
    next_plan = adopt(case, ref, key="r1a-protected-adopt-0002")["data"]["official_plan"]
    old = case.conn.execute("SELECT start_time,end_time,machine_id,operator_id FROM Schedule WHERE version=? AND op_id=?",
                            (plan["version"], point)).fetchone()
    new = case.conn.execute("SELECT start_time,end_time,machine_id,operator_id,lock_status FROM Schedule WHERE version=? AND op_id=?",
                            (next_plan["version"], point)).fetchone()
    assert tuple(new) == tuple(old) + ("locked",)
    assert new["start_time"] == new["end_time"]
    draft = create(case, {"base": {"plan_ref": next_plan["plan_ref"]}})
    ref = operation_ref(case, point)
    index = next(i for i, task in enumerate(draft["tasks"]) if task["operation_ref"] == ref)
    before = snapshot(case.conn)
    with pytest.raises(WorkbenchCommandRejected) as caught:
        change(case, draft, task=index)
    assert caught.value.code == "task_locked"
    assert snapshot(case.conn) == before


def test_piece_point_started_execution_prevents_movement(point_case):
    case = point_case
    ids = layout(case, mixed=False)
    plan = adopt(case, candidate(case))["data"]["official_plan"]
    point = ids["item-A", 50]
    case.event(point, "start", version=plan["version"])
    draft = create(case, {"base": {"plan_ref": plan["plan_ref"]}})
    ref = operation_ref(case, point)
    index = next(i for i, task in enumerate(draft["tasks"]) if task["operation_ref"] == ref)
    before = snapshot(case.conn)
    with pytest.raises(WorkbenchCommandRejected) as caught:
        change(case, draft, task=index)
    assert caught.value.code == "execution_protected"
    assert snapshot(case.conn) == before


def test_zero_planned_piece_preserves_real_positive_execution_in_next_adoptions(point_case):
    case = point_case
    ids = layout(case, mixed=False)
    plan = adopt(case, candidate(case))["data"]["official_plan"]
    point = ids["item-A", 50]
    receipt = case.command("create", case.task(plan["version"], point), case.values(1))
    assert receipt["ok"], receipt
    original_facts = snapshot(case.conn)
    ref = candidate(case, key="r1a-executed-run-0002")
    rows = {row["op_id"]: row for row in artifact(case, ref)["results"]}
    assert rows[point]["start_time"] == "2026-09-09T08:00:00"
    assert rows[point]["end_time"] == "2026-09-09T10:00:00"
    adopted = adopt(case, ref, key="r1a-executed-adopt-0002")["data"]["official_plan"]
    draft = create(case, {"base": {"plan_ref": adopted["plan_ref"]}})
    assert draft["validation"]["constraints_status"] == "valid", draft["validation"]
    other = operation_ref(case, ids["item-B", 50])
    index = next(i for i, task in enumerate(draft["tasks"]) if task["operation_ref"] == other)
    changed = change(case, draft, task=index)["data"]
    assert changed["validation"]["constraints_status"] == "valid", changed["validation"]
    saved = service(case.conn).save(changed["draft_ref"], {"name": "R1-A real execution retained"},
        changed["write_context"]["write_token"], "r1a-executed-save-0001")["data"]
    final = adopt(case, saved["scenario_ref"], trial=True, key="r1a-executed-trial-adopt-0001")["data"]["official_plan"]
    actual = case.conn.execute("SELECT start_time,end_time,lock_status FROM Schedule WHERE version=? AND op_id=?",
                               (final["version"], point)).fetchone()
    assert tuple(actual) == ("2026-09-09 08:00:00", "2026-09-09 10:00:00", "locked")
    for name in ("BatchOperations", "Batches", "WorkbenchProductionReports", "WorkbenchProductionReportRevisions"):
        assert snapshot(case.conn)[name] == original_facts[name]
