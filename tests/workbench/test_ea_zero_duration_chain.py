"""EA: real temporary DB and engine; no live DB or existing preview access."""

from core.models.workbench_plan_scope import PlanReadScope
from core.services.workbench.plan_queries import WorkbenchPlanQueryService
from core.services.workbench.run_compute import compute_candidate_run
from tests.workbench.ea_zero_duration_support import adoption_service, trial_adoption_service
from tests.workbench.run_candidate_adoption_support import INTENT, assert_retained
from tests.workbench.run_candidate_support import compute
from tests.workbench.run_compute_support import run_case as run_case  # noqa: F401
from tests.workbench.run_compute_support import unchanged
from tests.workbench.trial_adoption_support import service as public_trial_adoption
from tests.workbench.trial_support import change, connect, create, snapshot
from tests.workbench.trial_support import service as trial_service
from tests.workbench.trial_support import trial_case as trial_case  # noqa: F401


def test_real_point_reaches_validated_candidates(run_case):
    case = run_case
    case.conn.execute("UPDATE BatchOperations SET setup_hours=0,unit_hours=0")
    successor = case.operation(seq=2)
    case.conn.commit()
    result = unchanged(case, lambda: compute_candidate_run(case.conn, case.settings(), case.projections()))
    assert result.state == "complete"
    for payload in result.candidate_payloads.values():
        rows = {row.op_id: row for row in payload.schedule_rows}
        assert rows[case.op_id].start_time == rows[case.op_id].end_time
        assert rows[successor].start_time >= rows[case.op_id].end_time
        assert set(rows) == {case.op_id, successor}


def test_real_point_candidate_adoption_read(trial_case):
    case = trial_case
    case.conn.execute("UPDATE BatchOperations SET setup_hours=0,unit_hours=0")
    case.conn.commit()
    _, refs = compute(case)
    svc = adoption_service(case.conn)
    preview = svc.preview(refs[0])
    assert preview["validation"]["can_adopt"], preview
    before = snapshot(case.conn)
    result = svc.adopt(refs[0], preview["write_context"]["write_token"], "ea-adopt-point-0001", INTENT)
    assert result["ok"], result
    assert_retained(before, snapshot(case.conn))
    plan = result["data"]["official_plan"]
    reader = WorkbenchPlanQueryService(case.conn)
    with reader.read_snapshot():
        data, _ = reader.workspace(PlanReadScope(plan["plan_ref"]))
    point, = data["tasks"]
    assert point["start"] == point["end"]
    assert point["event_kind"] == "point" and point["occupies_resources"] is False
    draft = create(case, {"base": {"plan_ref": plan["plan_ref"]}}, key="ea-trial-create-0001")
    changed = change(case, draft, start="2026-09-09T13:00:00", key="ea-trial-change-0001")["data"]
    assert changed["tasks"][0]["start"] == changed["tasks"][0]["end"] == "2026-09-09T13:00:00"
    assert changed["validation"]["constraints_status"] == "valid", changed["validation"]
    saved = trial_service(case.conn).save(changed["draft_ref"], {"name": "EA exact point"},
        changed["write_context"]["write_token"], "ea-trial-save-0001")["data"]
    adopting = trial_adoption_service(case.conn)
    public_preview = public_trial_adoption(case.conn).preview(saved["scenario_ref"])
    assert public_preview["validation"]["can_adopt"] is False
    assert public_preview["validation"]["issues"][0]["code"] == "point_rendering_not_connected"
    preview = adopting.preview(saved["scenario_ref"])
    assert preview["validation"]["can_adopt"], preview
    before = snapshot(case.conn)
    result = adopting.adopt(saved["scenario_ref"], preview["write_context"]["write_token"], "ea-trial-adopt-0001", INTENT)
    assert result["ok"], result
    assert_retained(before, snapshot(case.conn))
    reopened = connect(case.path)
    try:
        reader = WorkbenchPlanQueryService(reopened)
        with reader.read_snapshot():
            data, _ = reader.workspace(PlanReadScope(result["data"]["official_plan"]["plan_ref"]))
    finally:
        reopened.close()
    after, = data["tasks"]
    assert after["operation_ref"] == point["operation_ref"]
    assert after["start"] == after["end"] == "2026-09-09T13:00:00"
    assert after["occupies_resources"] is False
    assert data["projections"]["baseline"]["state"] == "available"
