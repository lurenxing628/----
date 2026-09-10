"""Real point candidates retain identity; public adoption still requires its UI gate."""

import json
from datetime import datetime, timedelta

import pytest

from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_run_candidate import RunCandidateReadScope
from core.models.workbench_run_compute import CandidateRunInputError
from core.services.workbench.run_candidate_adoption import WorkbenchRunCandidateAdoptionService
from core.services.workbench.run_candidates import WorkbenchRunCandidateQueryService
from core.services.workbench.run_compute import compute_candidate_run
from core.services.workbench.run_jobs_facts import capture_run_facts
from core.services.workbench.run_worker import WorkbenchRunWorker
from core.services.workbench.trial_adoption import WorkbenchTrialAdoptionService
from tests.workbench.run_candidate_adoption_support import INTENT
from tests.workbench.run_candidate_adoption_support import service as candidate_adoption
from tests.workbench.run_candidate_support import candidate_case as candidate_case  # noqa: F401
from tests.workbench.run_candidate_support import compute, retained
from tests.workbench.run_compute_support import run_case as run_case  # noqa: F401
from tests.workbench.run_compute_support import unchanged
from tests.workbench.run_jobs_support import job_case as job_case  # noqa: F401
from tests.workbench.run_jobs_support import service as run_service
from tests.workbench.trial_adoption_support import saved_scenario
from tests.workbench.trial_adoption_support import service as adoption_service
from tests.workbench.trial_support import change, create, snapshot
from tests.workbench.trial_support import trial_case as trial_case  # noqa: F401
from web.routes.workbench.write_context import issue_write_context, validate_write_context


def test_real_engine_point_keeps_original_identity_and_zero_duration_dto(candidate_case):
    case = candidate_case
    case.conn.execute("UPDATE BatchOperations SET setup_hours=0,unit_hours=0")
    successor = case.operation(seq=2)
    case.conn.commit()
    identities = {int(row[0]): row[1] for row in case.conn.execute(
        "SELECT source_key,ref FROM WorkbenchPlanSourceRefs WHERE kind='operation' AND active=1")}
    result = unchanged(case, lambda: compute_candidate_run(case.conn, case.settings(), case.projections()))
    assert result.state == "complete" and result.result_persisted is False
    assert len(result.candidate_payloads) == 4
    for payload in result.candidate_payloads.values():
        rows = {row.op_id: row for row in payload.schedule_rows}
        assert len(payload.schedule_rows) == 2 and set(rows) == payload.scheduled_op_ids == {case.op_id, successor}
        point, following = rows[case.op_id], rows[successor]
        assert point.start_time == point.end_time == following.start_time == datetime(2026, 9, 9, 8)
        assert following.end_time - following.start_time == timedelta(minutes=45)
        assert (point.machine_id, point.operator_id) == (following.machine_id, following.operator_id) == ("M1", "O1")
    before = capture_run_facts(case.conn)
    _, refs = compute(case)
    assert len(refs) == 4 and capture_run_facts(case.conn) == before
    with retained(case.conn):
        for ref in refs:
            data, _ = WorkbenchRunCandidateQueryService(case.conn).workspace(RunCandidateReadScope(ref))
            tasks = {row["operation_ref"]: row for row in data["tasks"]}
            assert data["task_count"] == len(tasks) == 2 and set(tasks) == set(identities.values())
            point, following = tasks[identities[case.op_id]], tasks[identities[successor]]
            assert point["start"] == point["end"] == following["start"] == "2026-09-09T08:00:00"
            assert point["duration_seconds"] == 0
            assert point["event_kind"] == "point" and point["occupies_resources"] is False
            assert point["machine"]["ref"] == following["machine"]["ref"] == case.ref("machine", "M1")
            assert point["operator"]["ref"] == following["operator"]["ref"] == case.ref("operator", "O1")
            assert len(point["row_ref"]) == 48 and point["row_ref"] != following["row_ref"]
            stored = case.conn.execute("SELECT operation_ref,payload_json FROM WorkbenchRunCandidateTasks WHERE row_ref=?",
                                       (point["row_ref"],)).fetchone()
            raw = json.loads(stored["payload_json"])
            assert stored["operation_ref"] == identities[case.op_id] and raw["op_id"] == case.op_id
            assert raw["start_time"] == raw["end_time"] == point["start"]


@pytest.mark.parametrize("field", ["setup_hours", "unit_hours"])
@pytest.mark.parametrize("hours", [5e-324, 1e-16, 1e-12])
def test_real_engine_precision_collapse_is_not_accepted_as_zero_work(run_case, field, hours):
    case = run_case
    case.conn.execute("UPDATE BatchOperations SET setup_hours=0,unit_hours=0")
    case.conn.execute("UPDATE BatchOperations SET " + field + "=?", (hours,))
    case.conn.commit()
    with pytest.raises(CandidateRunInputError) as error:
        unchanged(case, lambda: compute_candidate_run(case.conn, case.settings(), case.projections()))
    assert error.value.reason == "point_duration_nonzero"
    assert error.value.can_adopt is False and error.value.result_persisted is False


@pytest.mark.parametrize("hours", [5e-324, 1e-16, 1e-12])
def test_worker_records_failure_without_allocating_candidate_or_official_plan(job_case, hours):
    case = job_case
    # Positive work collapsed by datetime precision is still an invalid candidate.
    case.conn.execute("UPDATE BatchOperations SET setup_hours=0,unit_hours=?", (hours,))
    case.conn.commit()
    accepted = case.accept()
    before = capture_run_facts(case.conn)
    with pytest.raises(CandidateRunInputError) as error:
        WorkbenchRunWorker(case.conn).execute(accepted["run_ref"])
    assert error.value.reason == "point_duration_nonzero"
    assert error.value.can_adopt is False and error.value.result_persisted is False
    result = run_service(case.conn).get(accepted["run_ref"])
    assert result["state"] == "failed" and result["result_persisted"] is False
    assert result["error"]["code"] == "point_duration_nonzero" and result["candidates"] == []
    for table in ("Schedule", "ScheduleHistory", "WorkbenchRunCandidates", "WorkbenchRunCandidateTasks"):
        assert case.conn.execute("SELECT COUNT(*) FROM " + table).fetchone()[0] == 0
    assert capture_run_facts(case.conn) == before


def test_worker_persists_all_point_candidates_without_allocating_official_plan(job_case):
    case = job_case
    case.conn.execute("UPDATE BatchOperations SET setup_hours=0,unit_hours=0")
    case.conn.commit()
    accepted = case.accept()
    before = capture_run_facts(case.conn)
    result = WorkbenchRunWorker(case.conn).execute(accepted["run_ref"])
    assert result["state"] == "complete" and result["result_persisted"] is True
    assert result["error"] is None and len(result["candidates"]) == 4
    assert all(row["status"] == "completed" and row["task_count"] == 1 for row in result["candidates"])
    stored = list(case.conn.execute("SELECT operation_ref,payload_json FROM WorkbenchRunCandidateTasks"))
    assert len(stored) == case.conn.execute("SELECT COUNT(*) FROM WorkbenchRunCandidates").fetchone()[0] == 4
    for row in stored:
        payload = json.loads(row["payload_json"])
        assert row["operation_ref"] == case.projections()[0].operation_ref
        assert payload["op_id"] == case.op_id
        assert payload["start_time"] == payload["end_time"] == "2026-09-09T08:00:00"
    assert capture_run_facts(case.conn) == before
    for table in ("Schedule", "ScheduleHistory", "WorkbenchTaskRefs"):
        assert case.conn.execute("SELECT COUNT(*) FROM " + table).fetchone()[0] == 0
    assert unchanged(case, lambda: WorkbenchRunWorker(case.conn).execute(accepted["run_ref"])) == result


@pytest.mark.parametrize("quantity,setup,unit,is_point", [(3, 0, 0, True), (0, 0, 7, True),
                                                        (0, 2, 7, False), (3, 0, 0.25, False)])
def test_public_candidate_adoption_requires_point_rendering_only_for_real_points(candidate_case, quantity, setup, unit, is_point):
    case = candidate_case
    case.conn.execute("UPDATE Batches SET quantity=?", (quantity,))
    case.conn.execute("UPDATE BatchOperations SET setup_hours=?,unit_hours=?", (setup, unit))
    case.conn.commit()
    _, refs = compute(case)
    public = candidate_adoption(case.conn)
    connected = WorkbenchRunCandidateAdoptionService(case.conn, integration_enabled=True,
        point_rendering_enabled=True, context_factory=issue_write_context, context_validator=validate_write_context)
    with retained(case.conn):
        for ref in refs:
            verified = connected.preview(ref)
            assert verified["validation"]["can_adopt"] is True, verified
            preview = public.preview(ref)
            assert preview["validation"]["can_adopt"] is not is_point, preview
            assert preview["write_context"]["capabilities"]["scheduling.candidate.adopt"] is not is_point
            if is_point:
                assert [row["code"] for row in preview["validation"]["issues"]] == ["point_rendering_not_connected"]
                assert preview["write_context"]["write_token"] is None
                with pytest.raises(WorkbenchCommandRejected) as error:
                    public.adopt(ref, verified["write_context"]["write_token"], "eh-blocked-point-" + ref, INTENT)
                assert error.value.code == "point_rendering_not_connected"
            else:
                assert preview["validation"]["issues"] == [] and preview["write_context"]["write_token"]


def test_saved_zero_work_does_not_gain_official_adoption_from_math_opt_in(trial_case):
    case = trial_case
    case.conn.execute("UPDATE BatchOperations SET setup_hours=0,unit_hours=0")
    case.conn.commit()
    _, refs = compute(case)
    saved = saved_scenario(case, {"base": {"candidate_ref": refs[0]}}, changed=False)
    before = snapshot(case.conn)
    connected = WorkbenchTrialAdoptionService(case.conn, integration_enabled=True,
        point_rendering_enabled=True, context_factory=issue_write_context, context_validator=validate_write_context)
    verified = connected.preview(saved["scenario_ref"])
    assert verified["validation"]["can_adopt"] is True, verified
    preview = adoption_service(case.conn).preview(saved["scenario_ref"])
    assert preview["validation"]["can_adopt"] is False
    assert [row["code"] for row in preview["validation"]["issues"]] == ["point_rendering_not_connected"]
    assert preview["write_context"]["write_token"] is None
    assert not any(preview["write_context"]["capabilities"].values())
    with pytest.raises(WorkbenchCommandRejected) as error:
        adoption_service(case.conn).adopt(saved["scenario_ref"], verified["write_context"]["write_token"],
                                         "eh-blocked-trial-point", INTENT)
    assert error.value.code == "point_rendering_not_connected"
    assert snapshot(case.conn) == before


@pytest.mark.parametrize("setup", [0, 2])
def test_zero_quantity_point_has_no_occupancy_but_setup_work_still_conflicts(trial_case, setup):
    case = trial_case
    case.conn.execute("UPDATE Batches SET quantity=0")
    case.conn.execute("UPDATE BatchOperations SET setup_hours=?,unit_hours=7", (setup,))
    case.batch("B2")
    case.operation("B2", unit_hours=1)
    case.conn.commit()
    _, refs = compute(case, case.settings("B1", "B2"))
    draft = create(case, {"base": {"candidate_ref": refs[0]}})
    index = next(i for i, row in enumerate(draft["tasks"]) if row["batch_ref"] == case.ref("batch", "B1"))
    other = next(row for row in draft["tasks"] if row["batch_ref"] == case.ref("batch", "B2"))
    start = datetime.fromisoformat(other["start"]) + timedelta(hours=1)
    changed = change(case, draft, task=index, start=start.isoformat(), machine="M1", operator="O1")["data"]
    task = next(row for row in changed["tasks"] if row["task_ref"] == draft["tasks"][index]["task_ref"])
    assert task["operation_ref"] == draft["tasks"][index]["operation_ref"]
    assert (task["start"] == task["end"]) is (setup == 0)
    assert changed["validation"]["constraints_status"] == ("valid" if setup == 0 else "blocked")
    expected_issues = {"scenario_adoption_not_connected"}
    if setup:
        expected_issues.update({"machine_overlap", "operator_overlap"})
    assert {row["code"] for row in changed["validation"]["issues"]} == expected_issues
    capacity = changed["capacity"]
    assert capacity["state"] == "available" and len(capacity["resources"]) == 2
    for resource in capacity["resources"]:
        assert resource["arranged_hours"] == 3 + setup
        assert resource["occupied_hours"] == 3
        assert resource["overlap_hours"] == setup
    if setup == 0:
        assert task["event_kind"] == "point" and task["occupies_resources"] is False
        assert task["duration_seconds"] == 0
    else:
        assert task.get("event_kind") != "point"
