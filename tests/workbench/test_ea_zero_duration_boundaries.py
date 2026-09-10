"""EA exact time, quantity, original evidence and public integration boundaries."""

from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from core.algorithm_contracts.schedule_point_evidence import SchedulePointEvidence
from core.infrastructure.errors import ValidationError
from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_plan_scope import PlanReadScope
from core.models.workbench_run_candidate import RunCandidateReadScope
from core.models.workbench_run_compute import CandidateRunInputError
from core.services.scheduler.run.schedule_payload_contract import build_validated_schedule_payload
from core.services.workbench.plan_queries import WorkbenchPlanQueryService
from core.services.workbench.run_candidates import WorkbenchRunCandidateQueryService
from core.services.workbench.run_compute import compute_candidate_run
from core.services.workbench.run_input import prepare_candidate_run_input
from tests.workbench.ea_zero_duration_support import adopt, adoption_service, point_candidate
from tests.workbench.run_candidate_adoption_support import INTENT
from tests.workbench.run_candidate_adoption_support import service as public_adoption
from tests.workbench.run_compute_support import run_case as run_case  # noqa: F401
from tests.workbench.run_compute_support import unchanged
from tests.workbench.trial_support import create, snapshot  # noqa: F401
from tests.workbench.trial_support import trial_case as trial_case


@pytest.mark.parametrize("setup,unit,quantity,point", [(0, 0, 3, True), (0, 7, 0, True), (2, 7, 0, False)])
def test_worker_zero_quantity_keeps_setup_and_identity(trial_case, setup, unit, quantity, point):
    case = trial_case
    ref = point_candidate(case, setup=setup, unit=unit, quantity=quantity)
    data, _ = WorkbenchRunCandidateQueryService(case.conn).workspace(RunCandidateReadScope(ref))
    task, = data["tasks"]
    assert (task["start"] == task["end"]) is point
    plan = adopt(case, ref)
    raw, = list(case.conn.execute("SELECT * FROM Schedule WHERE version=?", (plan["version"],)))
    assert raw["op_id"] == case.op_id
    assert (raw["start_time"] == raw["end_time"]) is point
    if not point:
        assert datetime.fromisoformat(raw["end_time"]) - datetime.fromisoformat(raw["start_time"]) == timedelta(hours=2)


@pytest.mark.parametrize("offset,count", [(-1, 0), (0, 1), (1, 0)])
def test_candidate_and_official_half_open_boundary(trial_case, offset, count):
    case = trial_case
    ref = point_candidate(case)
    candidate_reader = WorkbenchRunCandidateQueryService(case.conn)
    complete, _ = candidate_reader.workspace(RunCandidateReadScope(ref))
    at = datetime.fromisoformat(complete["tasks"][0]["start"])
    left, right = at + timedelta(seconds=offset), at + timedelta(seconds=offset + 1)
    data, _ = candidate_reader.workspace(RunCandidateReadScope(ref, range_start=left.isoformat(), range_end=right.isoformat()))
    assert data["task_count"] == count
    plan = adopt(case, ref)
    reader = WorkbenchPlanQueryService(case.conn)
    before = snapshot(case.conn)
    with reader.read_snapshot():
        data, _ = reader.workspace(PlanReadScope(plan["plan_ref"], left.isoformat(), right.isoformat()))
    assert data["task_count"] == count
    assert snapshot(case.conn) == before


def test_public_point_adoption_has_no_token_or_write(trial_case):
    case = trial_case
    ref = point_candidate(case)
    before = snapshot(case.conn)
    result = public_adoption(case.conn).preview(ref)
    assert result["validation"]["can_adopt"] is False
    assert result["validation"]["issues"][0]["code"] == "point_rendering_not_connected"
    assert result["write_context"]["write_token"] is None
    private_preview = adoption_service(case.conn).preview(ref)
    with pytest.raises(WorkbenchCommandRejected):
        public_adoption(case.conn).adopt(ref, private_preview["write_context"]["write_token"], "ea-public-block-0001", INTENT)
    assert snapshot(case.conn) == before


def test_official_read_uses_frozen_hours_not_current_master(trial_case):
    case = trial_case
    plan = adopt(case, point_candidate(case))
    case.conn.execute("UPDATE BatchOperations SET setup_hours=9,unit_hours=7")
    case.conn.commit()
    reader = WorkbenchPlanQueryService(case.conn)
    with reader.read_snapshot():
        data, _ = reader.workspace(PlanReadScope(plan["plan_ref"]))
    assert data["tasks"][0]["event_kind"] == "point"
    draft = create(case, {"base": {"plan_ref": plan["plan_ref"]}})
    assert draft["tasks"][0]["hours"]["total_hours"] == 0


def test_old_equal_interval_is_not_reclassified_using_current_zero_hours(trial_case):
    case = trial_case
    case.conn.execute("UPDATE BatchOperations SET setup_hours=0,unit_hours=0")
    case.conn.commit()
    case.plan(1, [case.op_id], start="2026-09-09T08:00:00", end="2026-09-09T08:00:00")
    before = snapshot(case.conn)
    reader = WorkbenchPlanQueryService(case.conn)
    with pytest.raises(WorkbenchCommandRejected), reader.read_snapshot():
        reader.workspace(PlanReadScope(case.plan_ref(1)))
    assert snapshot(case.conn) == before


@pytest.mark.parametrize("hours", [5e-324, 1e-16, 1e-12])
def test_positive_precision_collapse_is_rejected_before_candidate_save(run_case, hours):
    case = run_case
    case.conn.execute("UPDATE BatchOperations SET setup_hours=0,unit_hours=?", (hours,))
    case.conn.commit()
    with pytest.raises(CandidateRunInputError) as error:
        unchanged(case, lambda: compute_candidate_run(case.conn, case.settings(), case.projections()))
    assert error.value.reason == "point_duration_nonzero"


@pytest.mark.parametrize("proof", [True, {}, None, "point"])
def test_parser_does_not_accept_user_flags_as_witnesses(proof):
    at = datetime(2026, 9, 9, 8)
    row = SimpleNamespace(op_id=1, source="internal", machine_id="M1", operator_id="O1", start_time=at, end_time=at)
    with pytest.raises(ValidationError):
        build_validated_schedule_payload([row], point_validator=lambda value: proof)


@pytest.mark.parametrize("patch", [{"op_id": 2}, {"unit_hours": 5e-324}, {"setup_hours": -1},
    {"quantity": True}, {"machine_id": "M2"}, {"at": datetime(2026, 9, 9, 8, 0, 0, 1)}])
def test_parser_rechecks_identity_operands_and_precision(patch):
    at = datetime(2026, 9, 9, 8)
    row = SimpleNamespace(op_id=1, source="internal", machine_id="M1", operator_id="O1", start_time=at, end_time=at)
    values = dict(op_id=1, machine_id="M1", operator_id="O1", at=at, setup_hours=0, unit_hours=0, quantity=3)
    values.update(patch)
    with pytest.raises(ValidationError):
        build_validated_schedule_payload([row], point_validator=lambda value: SchedulePointEvidence(**values))


@pytest.mark.parametrize("setup,unit", [(-1, 1), (None, 0), (0, None), (0, float("inf"))])
def test_bad_hours_fail_before_engine_and_retain_raw_rows(run_case, setup, unit):
    case = run_case
    case.conn.execute("PRAGMA ignore_check_constraints=ON")
    case.conn.execute("UPDATE Batches SET quantity=1")
    case.conn.execute("UPDATE BatchOperations SET setup_hours=?,unit_hours=?", (setup, unit))
    case.conn.commit()
    with pytest.raises(CandidateRunInputError) as error:
        unchanged(case, lambda: prepare_candidate_run_input(case.conn, case.settings(), []))
    assert error.value.reason == "hours_missing"


def test_point_at_compute_right_boundary_is_not_schedulable(run_case):
    from core.services.workbench.run_compute_validation import validate_candidate

    case = run_case
    case.conn.execute("UPDATE BatchOperations SET setup_hours=0,unit_hours=0")
    case.conn.commit()
    prepared = prepare_candidate_run_input(case.conn, case.settings(end_date="2026-09-09"), case.projections())
    at = datetime(2026, 9, 10)
    # Calendar legality is checked before the half-open requested window.
    case.conn.execute("INSERT INTO OperatorCalendar(operator_id,date,shift_start,shift_hours) VALUES ('O1','2026-09-10','00:00',8)")
    case.conn.commit()
    row = SimpleNamespace(op_id=case.op_id, source="internal", machine_id="M1", operator_id="O1", start_time=at, end_time=at)
    with pytest.raises(CandidateRunInputError) as error:
        validate_candidate(prepared, [row], [])
    assert error.value.reason == "candidate_outside_window"
