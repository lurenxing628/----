"""Real admission/worker/adoption and production reporting across new facts."""

import pytest

from core.models.workbench_command import WorkbenchCommandRejected
from core.services.workbench.run.preflight import PreflightService
from tests.workbench.piece_adoption_support import split
from tests.workbench.run_candidate_adoption_support import INTENT, KEY, preview, service, snapshot
from tests.workbench.run_candidate_support import candidate_case as _case  # noqa: F401
from tests.workbench.run_candidate_support import compute
from tests.workbench.test_material_stage_release import add_requirement


@pytest.mark.parametrize("arrivals", [[], [{"arrival_date": "2030-01-01", "quantity": 3}]])
def test_stage_partial_adopts_only_released_work_and_keeps_pending_operations(candidate_case, arrivals):
    case = candidate_case
    later = case.operation(seq=2)
    last = case.operation(seq=3)
    add_requirement(case, later, arrivals)
    _run, candidates = compute(case, case.settings(material_strategy="stage"))
    token = preview(case, candidates[0])
    result = service(case.conn).adopt(candidates[0], token, KEY, INTENT)
    assert result["result"] == "committed"
    assert {row[0] for row in case.conn.execute("SELECT op_id FROM Schedule")} == {case.op_id}
    assert {tuple(row) for row in case.conn.execute("SELECT id,status FROM BatchOperations WHERE id IN (?,?)", (later, last))} == {(later, "pending"), (last, "pending")}
    from core.services.workbench.trial.base import prepare_base
    from core.services.workbench.trial.validation import TrialValidator
    admission, rows, live = prepare_base(case.conn, {"base": {"plan_ref": result["data"]["official_plan"]["plan_ref"]}})
    assert len(rows) == 1 and not TrialValidator(case.conn, admission, rows, live).evaluate()["issues"]
    replay = service(case.conn).adopt(candidates[0], token, KEY, INTENT)
    assert replay["replayed"] is True and replay["receipt_ref"] == result["receipt_ref"]
    _readopt_trial(case, result)


def _readopt_trial(case, result):
    from tests.workbench.trial_adoption_support import INTENT as trial_intent
    from tests.workbench.trial_adoption_support import preview as trial_preview
    from tests.workbench.trial_adoption_support import saved_scenario
    from tests.workbench.trial_adoption_support import service as trial_service

    saved = saved_scenario(case, {"base": {"plan_ref": result["data"]["official_plan"]["plan_ref"]}}, changed=False)
    assert all(row["risk"] == "unavailable" and row["late_hours"] is None for row in saved["comparison"]["batches"])
    token = trial_preview(case, saved)
    outcome = trial_service(case.conn).adopt(saved["scenario_ref"], token, "stage-trial-adopt-00001", trial_intent)
    assert outcome["result"] == "committed" and outcome["data"]["row_count"] == result["data"]["row_count"]


@pytest.mark.parametrize("piece", [False, True])
def test_stage_candidate_can_enter_trial_before_first_official_adoption(candidate_case, piece):
    from tests.workbench.trial_adoption_support import INTENT as trial_intent
    from tests.workbench.trial_adoption_support import preview as trial_preview
    from tests.workbench.trial_adoption_support import saved_scenario
    from tests.workbench.trial_adoption_support import service as trial_service

    case = candidate_case
    later = split(case)[None, 40] if piece else case.operation(seq=2)
    add_requirement(case, later, [])
    _run, candidates = compute(case, case.settings(material_strategy="stage"))
    saved = saved_scenario(case, {"base": {"candidate_ref": candidates[0]}}, changed=False)
    assert saved["scope_complete"] is False and len(saved["unplanned_operations"]) == 1
    assert all(row["risk"] == "unavailable" and row["late_hours"] is None for row in saved["comparison"]["batches"])
    result = trial_service(case.conn).adopt(saved["scenario_ref"], trial_preview(case, saved), "stage-trial-first-00001", trial_intent)
    assert result["result"] == "committed" and result["data"]["row_count"] == (7 if piece else 1)


@pytest.mark.parametrize("deferred_seq,expected", [(40, 7), (15, 1)])
def test_piece_stage_prefix_can_be_adopted_and_readopted_as_trial(candidate_case, deferred_seq, expected):
    case = candidate_case
    ids = split(case)
    later = ids[None, 40] if deferred_seq == 40 else case.operation(seq=15)
    add_requirement(case, later, [])
    _run, candidates = compute(case, case.settings(material_strategy="stage"))
    result = service(case.conn).adopt(candidates[0], preview(case, candidates[0]), KEY, INTENT)
    assert result["data"]["row_count"] == expected
    assert case.conn.execute("SELECT count(*) FROM Schedule WHERE op_id=?", (later,)).fetchone()[0] == 0
    _readopt_trial(case, result)


@pytest.mark.parametrize("missing", ["resource", "engine", "existing_plan"])
def test_stage_policy_does_not_authorize_other_omissions(candidate_case, missing):
    case = candidate_case
    later = case.operation(seq=3)
    add_requirement(case, later, [])
    if missing == "resource":
        other = case.operation(seq=2)
        case.conn.execute("UPDATE BatchOperations SET machine_id=NULL WHERE id=?", (other,))
    elif missing == "engine":
        case.operation(seq=2, unit_hours=100)
    else:
        case.plan(1, [later])
    case.conn.commit()
    settings = case.settings(material_strategy="stage", missing_resource_policy="exclude", end_date="2026-09-09")
    _run, candidates = compute(case, settings)
    before = snapshot(case.conn)
    assert service(case.conn).preview(candidates[0])["validation"]["can_adopt"] is False
    assert snapshot(case.conn) == before


@pytest.mark.parametrize("strategy", ["stage", "strict"])
def test_piece_run_adopts_dated_material_and_secondary_machine_type(candidate_case, strategy):
    case = candidate_case
    ids = split(case)
    case.conn.execute("INSERT INTO OpTypes(op_type_id,name,category) VALUES ('T2','Milling','both')")
    case.conn.execute("INSERT INTO MachineOpTypes(machine_id,op_type_id) VALUES ('M1','T2')")
    case.conn.execute("UPDATE BatchOperations SET op_type_id='T2',op_type_name='Milling'")
    case.conn.commit()
    add_requirement(case, ids[None, 10], [{"arrival_date": "2030-01-01", "quantity": 3}])
    settings = case.settings(material_strategy=strategy, start_date="2030-01-01", end_date="2030-01-10")
    data, _ = PreflightService(case.conn).evaluate(settings)
    assert data["counts"]["ready_tasks"] == 8
    _run, candidates = compute(case, settings)
    token = preview(case, candidates[0])
    result = service(case.conn).adopt(candidates[0], token, KEY, INTENT)
    assert result["result"] == "committed" and result["data"]["row_count"] == 8
    assert case.conn.execute("SELECT min(start_time) FROM Schedule").fetchone()[0] >= "2030-01-01"


@pytest.mark.parametrize("capable", [True, False])
def test_secondary_machine_can_be_recorded_in_actual_production_only_when_capable(candidate_case, capable):
    case = candidate_case
    case.conn.execute("INSERT INTO OpTypes(op_type_id,name,category) VALUES ('T2','Milling','both')")
    case.conn.execute("UPDATE BatchOperations SET op_type_id='T2',op_type_name='Milling'")
    if capable:
        case.conn.execute("INSERT INTO MachineOpTypes(machine_id,op_type_id) VALUES ('M1','T2')")
    case.conn.commit()
    case.plan(1, [case.op_id])
    if capable:
        outcome = case.command("create", case.task(1, case.op_id), case.values(1))
        assert outcome["result"] == "committed"
    else:
        with pytest.raises(WorkbenchCommandRejected, match="设备工种"):
            case.command("create", case.task(1, case.op_id), case.values(1))


@pytest.mark.parametrize("piece", [False, True])
@pytest.mark.parametrize("ready_check", [False, True])
@pytest.mark.parametrize("origin", ["candidate", "official"])
def test_ready_date_policy_survives_compute_adoption_and_trial(candidate_case, piece, ready_check, origin):
    from core.services.workbench.facts.candidate_store import CandidateStore
    from core.services.workbench.trial.materials import plan_material_policy
    from tests.workbench.trial_adoption_support import INTENT as trial_intent
    from tests.workbench.trial_adoption_support import preview as trial_preview
    from tests.workbench.trial_adoption_support import saved_scenario
    from tests.workbench.trial_adoption_support import service as trial_service

    case = candidate_case
    if piece:
        split(case)
    ready_status = "yes" if ready_check else "no"
    case.conn.execute("UPDATE Batches SET ready_status=?,ready_date='2026-09-15'", (ready_status,))
    case.conn.commit()
    run, refs = compute(case, case.settings(ready_check=ready_check, material_strategy="strict"))
    expected_day = "2026-09-15" if ready_check else "2026-09-09"
    for item in CandidateStore(case.conn).candidates(run):
        assert min(row["start_time"] for row in item["artifact"]["results"])[:10] == expected_day
        assert service(case.conn).preview(item["candidate_ref"])["validation"]["can_adopt"] is True
    base = {"candidate_ref": refs[0]}
    if origin == "official":
        adopted = service(case.conn).adopt(refs[0], preview(case, refs[0]), KEY, INTENT)
        base = {"plan_ref": adopted["data"]["official_plan"]["plan_ref"]}
    saved = saved_scenario(case, {"base": base}, changed=False)
    adopted = trial_service(case.conn).adopt(saved["scenario_ref"], trial_preview(case, saved),
        "ready-policy-trial-adopt-001", trial_intent)
    assert adopted["result"] == "committed" and adopted["data"]["row_count"] == (8 if piece else 1)
    version = case.conn.execute("SELECT max(version) FROM ScheduleHistory").fetchone()[0]
    assert plan_material_policy(case.conn, version) == {"ready_check": ready_check, "material_strategy": "strict"}
    assert tuple(case.conn.execute("SELECT ready_status,ready_date FROM Batches").fetchone()) == (ready_status, "2026-09-15")


@pytest.mark.parametrize("piece", [False, True])
@pytest.mark.parametrize("path", ["candidate", "trial"])
def test_enabled_readiness_still_rejects_early_candidate_and_trial(candidate_case, piece, path):
    from datetime import datetime, timedelta

    from tests.workbench.run_candidate_adoption_support import rewrite_candidate
    from tests.workbench.trial_support import change, create

    case = candidate_case
    if piece:
        split(case)
    case.conn.execute("UPDATE Batches SET ready_date='2026-09-15'")
    case.conn.commit()
    _run, refs = compute(case, case.settings(ready_check=True))
    if path == "trial":
        draft = create(case, {"base": {"candidate_ref": refs[0]}})
        first = min(range(len(draft["tasks"])), key=lambda index: draft["tasks"][index]["start"])
        changed = change(case, draft, task=first, start="2026-09-09T08:00:00", machine="M1", operator="O1")["data"]
        assert "before_ready_date" in {item["code"] for item in changed["validation"]["issues"]}
        return

    def move_before_ready(row):
        for field in ("start_time", "end_time"):
            row[field] = (datetime.fromisoformat(row[field]) - timedelta(days=6)).isoformat()

    rewrite_candidate(case, refs[0], move_before_ready)
    before = snapshot(case.conn)
    checked = service(case.conn).preview(refs[0])
    assert checked["validation"]["can_adopt"] is False and checked["write_context"]["write_token"] is None
    assert checked["validation"]["issues"][0]["code"] == ("piece_before_ready_date" if piece else "candidate_before_ready_date")
    assert snapshot(case.conn) == before


@pytest.mark.parametrize("piece", [False, True])
def test_enabling_readiness_keeps_completed_actuals_through_replan_and_trial(candidate_case, piece):
    from core.services.workbench.run.worker import WorkbenchRunWorker
    from tests.workbench.trial_adoption_support import INTENT as trial_intent
    from tests.workbench.trial_adoption_support import preview as trial_preview
    from tests.workbench.trial_adoption_support import saved_scenario
    from tests.workbench.trial_adoption_support import service as trial_service

    case = candidate_case
    if piece:
        first = split(case)[None, 10]
    else:
        first = case.op_id
        case.operation(seq=2)
    case.conn.execute("UPDATE Batches SET ready_date='2026-09-15'")
    case.conn.commit()
    _run, refs = compute(case, case.settings(ready_check=False))
    service(case.conn).adopt(refs[0], preview(case, refs[0]), KEY, INTENT)
    version = case.conn.execute("SELECT max(version) FROM ScheduleHistory").fetchone()[0]
    result = case.command("create", case.task(version, first), case.values(3,
        actual_start="2026-09-09T08:00:00", actual_end="2026-09-09T08:45:00", effective_processing_hours=.75))
    assert result["result"] == "committed"
    accepted = case.accept(key="readiness-enabled-run-002", settings=case.settings(ready_check=True))
    run = WorkbenchRunWorker(case.conn).execute(accepted["run_ref"])
    ref = run["candidates"][0]["candidate_ref"]
    adopted = service(case.conn).adopt(ref, preview(case, ref), "readiness-enabled-adopt-002", INTENT)
    saved = saved_scenario(case, {"base": {"plan_ref": adopted["data"]["official_plan"]["plan_ref"]}}, changed=False)
    assert saved["validation"]["constraints_status"] == "valid"
    result = trial_service(case.conn).adopt(saved["scenario_ref"], trial_preview(case, saved),
        "readiness-actual-trial-adopt-001", trial_intent)
    assert result["result"] == "committed"
    version = case.conn.execute("SELECT max(version) FROM ScheduleHistory").fetchone()[0]
    rows = {row["op_id"]: dict(row) for row in case.conn.execute("SELECT * FROM Schedule WHERE version=?", (version,))}
    assert rows[first]["start_time"] == "2026-09-09 08:00:00" and rows[first]["end_time"] == "2026-09-09 08:45:00"
    assert all(row["start_time"] >= "2026-09-15" for op_id, row in rows.items() if op_id != first)
