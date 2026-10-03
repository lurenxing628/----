"""Real trial publication preserves actual execution anchors and original plans."""

import json
import os
import shutil
import subprocess
from copy import deepcopy
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from core.errors import AppError, ErrorCode
from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_trial_codec import dump, fingerprint
from core.services.equipment.machine_downtime_service import MachineDowntimeService
from core.services.equipment.machine_service import MachineService
from core.services.personnel.operator_machine_service import OperatorMachineService
from core.services.personnel.operator_service import OperatorService
from core.services.process.supplier_service import SupplierService
from core.services.workbench.facts.trial_policy import load_draft
from core.services.workbench.run.preflight import PreflightService
from core.services.workbench.run.worker import WorkbenchRunWorker
from core.services.workbench.trial.execution_anchors import anchor_issue
from data.repositories.workbench_trial_repo import WorkbenchTrialRepository
from tests.workbench.piece_adoption_support import split
from tests.workbench.run_candidate_adoption_support import INTENT as candidate_intent
from tests.workbench.run_candidate_adoption_support import candidate
from tests.workbench.run_candidate_adoption_support import preview as candidate_preview
from tests.workbench.run_candidate_adoption_support import service as candidate_adoption
from tests.workbench.run_candidate_support import corrupt_update
from tests.workbench.test_execution_dependency_regressions import external_route, late_merged_actual, next_cycle_run
from tests.workbench.trial_adoption_support import BASE, INTENT, api, assert_retained, full_plan
from tests.workbench.trial_adoption_support import service as adoption_service
from tests.workbench.trial_support import change, create, snapshot
from tests.workbench.trial_support import service as trial_service
from tests.workbench.trial_support import trial_case as trial_case

PUBLIC_ARRANGEMENT = ("start", "end", "machine_ref", "operator_ref")


@pytest.mark.parametrize("legacy", [False, True])
def test_actual_anchor_preserves_completed_fact_across_past_maintenance(trial_case, legacy):
    case = trial_case
    case.operation(seq=2, machine_id="M2", operator_id="O2")
    case.plan(1, [case.op_id])
    if legacy:
        case.event(case.op_id, "start")
        case.event(case.op_id, "finish", quantity=3)
    else:
        case.command("create", case.task(1, case.op_id), case.values(3))
    MachineDowntimeService(case.conn).create("M1", "2026-09-09 08:00", "2026-09-09 09:00", "maintenance")
    ref = candidate(case)
    assert candidate_adoption(case.conn).preview(ref)["validation"]["can_adopt"]
    draft = create(case, {"base": {"candidate_ref": ref}})
    saved = _save(case, draft, "past-maintenance")
    checked = adoption_service(case.conn).preview(saved["scenario_ref"])
    assert checked["validation"]["can_adopt"]
    result = adoption_service(case.conn).adopt(saved["scenario_ref"], checked["write_context"]["write_token"],
                                             "past-maintenance-adopt-001", INTENT)
    assert tuple(case.conn.execute("SELECT start_time,end_time FROM Schedule WHERE version=? AND op_id=?",
                                  (result["data"]["official_plan"]["version"], case.op_id)).fetchone()) == (
        "2026-09-09 08:00:00", "2026-09-09 10:00:00")


def _deactivate(case, change):
    if change == "machine":
        MachineService(case.conn).set_status("M1", "inactive")
    elif change == "operator":
        OperatorService(case.conn).set_status("O1", "inactive")
    elif change == "authorization":
        OperatorMachineService(case.conn).remove_link("O1", "M1")
    else:
        SupplierService(case.conn).update("S1", status="inactive")


def _historical_resource_route(case, piece, supplier, reported):
    if supplier:
        external_route(case, piece)
        ref = candidate(case)
        result = candidate_adoption(case.conn).adopt(ref, candidate_preview(case, ref), "resource-initial-adopt-001", candidate_intent)
        version = result["data"]["official_plan"]["version"]
        case.batch("B2")
        case.operation("B2", machine_id="M2", operator_id="O2")
        case.conn.commit()
    else:
        if piece:
            ids = split(case, common=False, quantity=1)
            case.conn.execute("UPDATE BatchOperations SET machine_id='M2',operator_id='O2' WHERE id=?", (ids["item-A", 30],))
            case.conn.commit()
        else:
            case.operation(seq=2, machine_id="M2", operator_id="O2")
        case.plan(1, [case.op_id])
        version = 1
    if reported:
        payload = case.values(1 if piece else 3)
        if supplier:
            payload.update(actual_machine_ref=None, actual_operator_ref=None)
        case.command("create", case.task(version, case.op_id), payload)
    else:
        case.conn.execute("UPDATE Schedule SET lock_status='locked' WHERE version=?", (version,))
        case.conn.commit()
    return case.settings("B1", "B2") if supplier else case.settings()


@pytest.mark.parametrize("piece", [False, True])
@pytest.mark.parametrize("change", ["machine", "operator", "authorization", "supplier"])
def test_actual_resource_identities_survive_current_qualification_changes(trial_case, piece, change):
    case = trial_case
    settings = _historical_resource_route(case, piece, change == "supplier", True)
    _deactivate(case, change)
    accepted = case.accept(key="historical-resource-run-001", settings=settings)
    run = WorkbenchRunWorker(case.conn).execute(accepted["run_ref"])
    assert run["state"] == "complete"
    ref = run["candidates"][0]["candidate_ref"]
    assert candidate_adoption(case.conn).preview(ref)["validation"]["can_adopt"]
    draft = create(case, {"base": {"candidate_ref": ref}})
    saved = _save(case, draft, "historical-resource")
    checked = adoption_service(case.conn).preview(saved["scenario_ref"])
    assert checked["validation"]["can_adopt"]
    result = adoption_service(case.conn).adopt(saved["scenario_ref"], checked["write_context"]["write_token"],
                                             "historical-resource-trial-001", INTENT)
    actual = case.conn.execute("SELECT machine_id,operator_id,start_time,end_time FROM Schedule WHERE version=? AND op_id=?",
                              (result["data"]["official_plan"]["version"], case.op_id)).fetchone()
    resources = (None, None) if change == "supplier" else ("M1", "O1")
    assert tuple(actual) == (*resources, "2026-09-09 08:00:00", "2026-09-09 10:00:00")


@pytest.mark.parametrize("piece", [False, True])
@pytest.mark.parametrize("change", ["machine", "operator", "authorization", "supplier"])
def test_unexecuted_locked_resources_still_require_current_qualifications(trial_case, piece, change):
    case = trial_case
    settings = _historical_resource_route(case, piece, change == "supplier", False)
    _deactivate(case, change)
    before = snapshot(case.conn)
    if change == "supplier":
        checked, _ = PreflightService(case.conn).evaluate(settings)
        assert checked["blockers"] and "supplier_missing" in {item["code"] for row in checked["tasks"] for item in row["issues"]}
    else:
        accepted = case.accept(key="locked-resource-run-001", settings=settings)
        if piece:
            with pytest.raises(Exception) as caught:
                WorkbenchRunWorker(case.conn).execute(accepted["run_ref"])
            assert caught.value.code == "piece_resource_invalid"
        else:
            run = WorkbenchRunWorker(case.conn).execute(accepted["run_ref"])
            checked = candidate_adoption(case.conn).preview(run["candidates"][0]["candidate_ref"])
            assert checked["validation"]["can_adopt"] is False
            assert checked["validation"]["issues"][0]["code"] == "candidate_resource_invalid"
        # Admission/failed-run bookkeeping may append; the executable history must not.
        assert snapshot(case.conn)["Schedule"] == before["Schedule"]
        assert snapshot(case.conn)["ScheduleHistory"] == before["ScheduleHistory"]


@pytest.mark.parametrize("piece", [False, True])
@pytest.mark.parametrize("base", ["official", "candidate"])
def test_actual_external_group_anchors_are_fixed_in_real_trial_contract(trial_case, piece, base):
    case = trial_case
    case.conn.execute("UPDATE BatchOperations SET unit_hours=0.25")
    case.conn.commit()
    version, copied, period = late_merged_actual(case, piece)
    if base == "official":
        value = {"base": {"plan_ref": case.plan_ref(version)}}
    else:
        _, refs = next_cycle_run(case, ("B1",))
        value = {"base": {"candidate_ref": refs[0]}}
    draft = create(case, value)
    derived = next(task for task in draft["tasks"] if (task.get("execution_anchor") or {}).get("basis") == "merged_external_actuals")
    assert not derived["edit_context"]["can_change"] and derived["locked"]
    before = snapshot(case.conn)
    index = next(index for index, task in enumerate(draft["tasks"]) if task["task_ref"] == derived["task_ref"])
    with pytest.raises(WorkbenchCommandRejected) as caught:
        change(case, draft, task=index, machine=None, operator=None)
    assert caught.value.code in ("task_locked", "execution_protected") and snapshot(case.conn) == before
    saved = _save(case, draft, "merged-external-cycle")
    _assert_public_contract(draft, saved)
    checked = adoption_service(case.conn).preview(saved["scenario_ref"])
    assert checked["validation"]["can_adopt"]
    result = adoption_service(case.conn).adopt(saved["scenario_ref"], checked["write_context"]["write_token"],
                                             "merged-external-cycle-adopt-001", INTENT)
    assert {tuple(datetime.fromisoformat(value) for value in row) for row in case.conn.execute(
        "SELECT start_time,end_time FROM Schedule WHERE version=? AND op_id IN (?,?)",
        (result["data"]["official_plan"]["version"], *copied))} == {period}


def _assert_public_contract(*workspaces):
    node = os.environ.get("WORKBENCH_NODE") or shutil.which("node")
    assert node, "Node is required for the actual trial DTO contract"
    source = Path(__file__).resolve().parents[2] / "frontend/workbench/app"
    script = """
const fs = require('fs'), path = require('path'), assert = require('assert');
global.window = {};
for (const name of ['PointContract.js', 'TrialContract.js']) require(path.join(process.argv[1], name));
for (const data of JSON.parse(fs.readFileSync(0, 'utf8'))) {
  window.TrialContract.workspace(data);
  assert(data.tasks.some(task => task.execution_anchor));
  const witnesses = new Map(data.tasks.filter(task => task.execution_anchor).map(task => [task.execution_anchor.basis, task.task_ref]));
  for (const [basis, ref] of witnesses) {
    for (const kind of ['start', 'editable', 'basis']) {
      const changed = JSON.parse(JSON.stringify(data));
      const task = changed.tasks.find(task => task.task_ref === ref);
      if (kind === 'start') task.execution_anchor.start = '2026-09-09T09:30:00';
      if (kind === 'editable') task.edit_context.can_change = true;
      if (kind === 'basis') task.execution_anchor.basis = 'guessed_actuals';
      assert.throws(() => window.TrialContract.workspace(changed));
    }
    if (basis === 'merged_external_actuals') {
      const changed = JSON.parse(JSON.stringify(data));
      changed.tasks.find(task => task.task_ref === ref).source = 'internal';
      assert.throws(() => window.TrialContract.workspace(changed));
    }
  }
}
"""
    result = subprocess.run([node, "-e", script, str(source)], input=json.dumps(workspaces),
                            text=True, capture_output=True, timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr


def _save(case, draft, suffix="anchor"):
    return trial_service(case.conn).save(draft["draft_ref"], {"name": "Actual anchors " + suffix},
        draft["write_context"]["write_token"], "trial-anchor-save-" + suffix)["data"]


def _completed(case, op_id, start="2026-09-09T09:00:00", end="2026-09-09T10:00:00"):
    return case.command("create", case.task(1, op_id), case.values(3,
        actual_start=start, actual_end=end, effective_processing_hours=0.5,
        actual_machine_ref=case.ref("machine", "M2"), actual_operator_ref=case.ref("operator", "O2")))["data"]["rows"][0]


def _two_tasks(case):
    value, second = full_plan(case)
    report = _completed(case, case.op_id)
    return value, second, report


def _assert_anchor(task, *, start, end, machine, operator, basis):
    expected = {"start": start, "end": end, "machine_ref": machine, "operator_ref": operator}
    assert {key: task[key] for key in PUBLIC_ARRANGEMENT} == expected
    assert {key: task["execution_anchor"][key] for key in PUBLIC_ARRANGEMENT} == expected
    assert task["execution_anchor"]["basis"] == basis
    assert task["execution_anchor"]["message"]
    assert task["locked"] and not task["edit_context"]["can_change"]
    assert "execution_protected" in {row["code"] for row in task["edit_context"]["blocked_reasons"]}


def _http_adopt_exact_saved(case, saved):
    client = api(case)
    path = BASE + saved["scenario_ref"]
    before = snapshot(case.conn)
    response = client.post(path + "/adopt-preview", json={})
    assert response.status_code == 200, response.get_json()
    checked = response.get_json()["data"]
    assert checked["validation"]["can_adopt"], checked
    assert snapshot(case.conn) == before
    response = client.post(path + "/adopt", json={"input": INTENT,
        "write_token": checked["write_context"]["write_token"], "request_key": "actual-anchor-adopt-0001"})
    assert response.status_code == 200, response.get_json()
    version = response.get_json()["data"]["official_plan"]["version"]
    actual = {row["op_id"]: row for row in case.conn.execute("SELECT * FROM Schedule WHERE version=?", (version,))}
    original_rows = load_draft(WorkbenchTrialRepository(case.conn), saved["draft_ref"])[1]
    op_ids = {row["operation_ref"]: row["original"]["operation"]["id"] for row in original_rows}
    assert len(actual) == len(saved["tasks"])
    for task in saved["tasks"]:
        row = actual[op_ids[task["operation_ref"]]]
        assert row["start_time"].replace(" ", "T") == task["start"]
        assert row["end_time"].replace(" ", "T") == task["end"]
        assert case.ref("machine", row["machine_id"]) == task["machine_ref"]
        assert case.ref("operator", row["operator_id"]) == task["operator_ref"]
    assert_retained(before, snapshot(case.conn))
    assert trial_service(case.conn).scenario(saved["scenario_ref"]) == saved


def test_completed_actuals_seed_new_trial_and_publish_exact_saved_arrangements(trial_case):
    case = trial_case
    value, second, report = _two_tasks(case)
    production = snapshot(case.conn)
    draft = create(case, value)
    first = next(task for task in draft["tasks"] if task["sequence"] == 1)
    _assert_anchor(first, start="2026-09-09T09:00:00", end="2026-09-09T10:00:00",
        machine=case.ref("machine", "M2"), operator=case.ref("operator", "O2"), basis="completed_actuals")
    assert first["original"] == {"start": "2026-09-09T08:00:00", "end": "2026-09-09T11:00:00",
        "machine_ref": case.ref("machine", "M1"), "operator_ref": case.ref("operator", "O1")}
    assert first["changed"]
    private = next(row for row in load_draft(WorkbenchTrialRepository(case.conn), draft["draft_ref"])[1]
                   if row["original"]["operation"]["id"] == case.op_id)
    assert private["original"]["arrangement"]["start"] == first["original"]["start"]
    assert private["original"]["execution_anchor"]["arrangement"] == private["current"]
    successor = next(index for index, task in enumerate(draft["tasks"]) if task["sequence"] == 2)
    draft = change(case, draft, task=successor, machine="M3", operator="O3")["data"]
    saved = _save(case, draft)
    _assert_public_contract(draft, saved)
    _http_adopt_exact_saved(case, saved)
    for table in ("WorkbenchProductionReports", "WorkbenchProductionReportRevisions", "OperationExecutionEvents"):
        assert snapshot(case.conn)[table] == production[table]
    for table in ("Schedule", "ScheduleHistory"):
        assert all(row in snapshot(case.conn)[table] for row in production[table])
    assert case.ledger.get_report(report["report_ref"]).recorded_against_task_ref == case.task(1, case.op_id)
    assert case.conn.execute("SELECT COUNT(*) FROM Schedule WHERE version=1").fetchone()[0] == 2


def test_started_legacy_anchor_keeps_original_plan_duration(trial_case):
    case = trial_case
    case.batch("UNSTARTED")
    second = case.operation("UNSTARTED")
    case.plan(1, [case.op_id, second], end="2026-09-09T11:00:00")
    case.conn.execute("UPDATE Schedule SET start_time='2026-09-09T13:00:00',end_time='2026-09-09T13:45:00' WHERE op_id=?", (second,))
    case.conn.commit()
    value = {"base": {"plan_ref": case.plan_ref(1)}}
    case.event(case.op_id, "start", time="2026-09-09T09:00:00")
    draft = create(case, value)
    first = next(task for task in draft["tasks"] if task["batch_id"] == "B1")
    _assert_anchor(first, start="2026-09-09T09:00:00", end="2026-09-09T12:00:00",
        machine=case.ref("machine", "M1"), operator=case.ref("operator", "O1"), basis="started_actuals")
    successor = next(index for index, task in enumerate(draft["tasks"]) if task["batch_id"] == "UNSTARTED")
    draft = change(case, draft, task=successor, machine="M3", operator="O3")["data"]
    _http_adopt_exact_saved(case, _save(case, draft))


def test_started_anchor_does_not_claim_completed_predecessor_for_downstream_work(trial_case):
    case = trial_case
    value, _ = full_plan(case)
    case.event(case.op_id, "start", time="2026-09-09T09:00:00")
    draft = create(case, value)
    successor = next(index for index, task in enumerate(draft["tasks"]) if task["sequence"] == 2)
    draft = change(case, draft, task=successor, machine="M3", operator="O3")["data"]
    saved = _save(case, draft)
    before = snapshot(case.conn)
    # Existing input policy excludes a successor whose protected predecessor
    # has no completion evidence. Anchoring must not silently loosen that rule.
    checked = adoption_service(case.conn).preview(saved["scenario_ref"])
    assert not checked["validation"]["can_adopt"]
    assert checked["write_context"]["write_token"] is None
    assert snapshot(case.conn) == before


def test_actual_anchor_cannot_be_changed_by_trial_command(trial_case):
    case = trial_case
    value, _, _ = _two_tasks(case)
    draft = create(case, value)
    first = next(index for index, task in enumerate(draft["tasks"]) if task["sequence"] == 1)
    before = snapshot(case.conn)
    with pytest.raises(WorkbenchCommandRejected) as error:
        change(case, draft, task=first, machine="M3", operator="O3")
    assert error.value.code == "execution_protected"
    assert snapshot(case.conn) == before


def test_old_saved_arrangement_is_rejected_without_silently_reanchoring(trial_case, monkeypatch):
    import core.services.workbench.trial.service as trial_module
    case = trial_case
    value, _, _ = _two_tasks(case)
    prepare = trial_module.prepare_base

    def legacy_prepare(conn, intent):
        admission, rows, live = prepare(conn, intent)
        for row in rows:
            row["original"].pop("execution_anchor", None)
            row["current"] = deepcopy(row["original"]["arrangement"])
        return admission, rows, live

    # Create a genuine saved envelope and receipts with the pre-fix row shape.
    with monkeypatch.context() as scoped:
        scoped.setattr(trial_module, "prepare_base", legacy_prepare)
        saved = _save(case, create(case, value))
    before = snapshot(case.conn)
    checked = adoption_service(case.conn).preview(saved["scenario_ref"])
    assert not checked["validation"]["can_adopt"]
    assert "scenario_execution_anchor_outdated" in {item["code"] for item in checked["validation"]["issues"]}
    assert checked["write_context"]["write_token"] is None
    assert trial_service(case.conn).scenario(saved["scenario_ref"]) == saved
    assert snapshot(case.conn) == before


@pytest.mark.parametrize("tamper", ["private_anchor", "report_drift"])
def test_saved_execution_anchor_tampering_and_report_drift_cannot_publish(trial_case, tamper):
    case = trial_case
    value, _, report = _two_tasks(case)
    saved = _save(case, create(case, value))
    checked = adoption_service(case.conn).preview(saved["scenario_ref"])
    assert checked["validation"]["can_adopt"], checked
    if tamper == "private_anchor":
        row = next(row for row in load_draft(WorkbenchTrialRepository(case.conn), saved["draft_ref"])[1]
                   if row["original"].get("execution_anchor"))
        original = deepcopy(row["original"])
        original["execution_anchor"]["arrangement"]["start"] = "2026-09-09T09:30:00"
        corrupt_update(case.conn, "WorkbenchTrialRows", "UPDATE WorkbenchTrialRows SET original_json=?,original_hash=? WHERE row_ref=?",
                       (dump(original), fingerprint(original), row["row_ref"]))
    else:
        case.command("correct", report["report_ref"], {
            "original_revision_ref": report["revision_ref"], "reason": "Verified finish correction",
            "actual_end": "2026-09-09T10:30:00"})
    before = snapshot(case.conn)
    with pytest.raises(WorkbenchCommandRejected):
        adoption_service(case.conn).adopt(saved["scenario_ref"], checked["write_context"]["write_token"],
                                         "anchor-drift-adopt-0001", INTENT)
    assert snapshot(case.conn) == before
    assert case.conn.execute("SELECT MAX(version) FROM ScheduleHistory").fetchone()[0] == 1


def test_five_completed_batches_and_three_changed_chains_publish_with_all_facts_retained(trial_case):
    case = trial_case
    case.conn.execute("UPDATE BatchOperations SET unit_hours=0.25")
    completed, successors, extra_chains = [case.op_id], [], []
    for index in range(5):
        batch = "B1" if index == 0 else "DONE" + str(index)
        if index:
            case.batch(batch)
            completed.append(case.operation(batch))
        successors.append(case.operation(batch, seq=2))
    for index in range(3):
        batch = "MOVE" + str(index)
        case.batch(batch)
        extra_chains.append([case.operation(batch), case.operation(batch, seq=2)])
    case.plan(1, completed + successors + [op for chain in extra_chains for op in chain])

    def arrange(op, start, machine="M1", operator="O1"):
        end = start + timedelta(minutes=45)
        case.conn.execute("UPDATE Schedule SET start_time=?,end_time=?,machine_id=?,operator_id=? WHERE op_id=?",
            (start.isoformat(), end.isoformat(), machine, operator, op))

    for index, op in enumerate(completed):
        arrange(op, datetime(2026, 9, 9, 8) + timedelta(minutes=45 * index))
        arrange(successors[index], datetime(2026, 9, 10, 8) + timedelta(minutes=45 * index))
    for chain in extra_chains:
        for index, op in enumerate(chain):
            arrange(op, datetime(2026, 9, 9, 9) + timedelta(minutes=45 * index), "M2", "O2")
    case.conn.commit()
    for index, op in enumerate(completed):
        start = datetime(2026, 9, 9, 9) + timedelta(minutes=45 * index)
        if index == 4:
            start = datetime(2026, 9, 9, 13)
        _completed(case, op, start.isoformat(), (start + timedelta(minutes=30)).isoformat())
    production = snapshot(case.conn)
    draft = create(case, {"base": {"plan_ref": case.plan_ref(1)}})
    assert sum(task.get("execution_anchor") is not None for task in draft["tasks"]) == 5
    assert draft["validation"]["constraints_status"] == "blocked"
    for chain_index, hour in enumerate((8, 10, 13)):
        for seq in (1, 2):
            index = next(index for index, task in enumerate(draft["tasks"])
                         if task["batch_id"] == "MOVE" + str(chain_index) and task["sequence"] == seq)
            start = datetime(2026, 9, 10, hour) + timedelta(minutes=45 * (seq - 1))
            draft = change(case, draft, task=index, start=start.isoformat(), machine="M3", operator="O3",
                key=f"anchor-move-chain-{chain_index}-{seq}")["data"]
    assert draft["validation"]["constraints_status"] == "valid", draft["validation"]
    assert len(draft["change_history"]) == 6
    saved = _save(case, draft, "five-batches")
    _http_adopt_exact_saved(case, saved)
    after = snapshot(case.conn)
    for table in ("WorkbenchProductionReports", "WorkbenchProductionReportRevisions", "OperationExecutionEvents"):
        assert after[table] == production[table]
    for table in ("Schedule", "ScheduleHistory"):
        assert all(row in after[table] for row in production[table])
    assert len(after["WorkbenchProductionReports"]) == 5
    assert case.conn.execute("SELECT COUNT(*) FROM Schedule WHERE version=1").fetchone()[0] == 16


def test_anchor_issue_describes_trial_draft_semantics_without_code_prefix():
    exc = AppError(ErrorCode.SCHEDULE_CONFLICT, "报工记录还没有准备好，系统无法确认排产约束。",
                   details={"reason": "execution_ledger_scope_missing"})
    actual = anchor_issue(exc)
    assert actual["code"] == "execution_anchor_unproven" and actual["severity"] == "blocker"
    assert "不阻止新增或保留试调草稿" in actual["message"]
    assert "当前不能正式采用" in actual["message"]
    assert "没有改动任何数据" not in actual["message"] and "[6003]" not in actual["message"]
    assert anchor_issue(KeyError("machine"))["message"] == "已开工工序的实际时间或资源不完整，请检查现场记录后重新发起试调。"


def test_execution_anchor_failure_commits_blocked_draft_with_scene_specific_message(trial_case, monkeypatch):
    import core.services.workbench.trial.execution_anchors as anchor_module

    case = trial_case

    def unavailable(*_args, **_kwargs):
        raise AppError(ErrorCode.SCHEDULE_CONFLICT, "报工记录还没有准备好，这次操作没有完成，没有改动任何数据。",
                       details={"reason": "execution_ledger_scope_missing"})

    monkeypatch.setattr(anchor_module, "execution_anchors", unavailable)
    draft = create(case)
    problem = next(row for row in draft["validation"]["issues"] if row["code"] == "execution_anchor_unproven")
    assert "不阻止新增或保留试调草稿" in problem["message"]
    assert "没有改动任何数据" not in problem["message"]
    assert draft["validation"]["constraints_status"] == "blocked"
    assert case.conn.execute("SELECT COUNT(*) FROM WorkbenchTrialDrafts WHERE draft_ref=?", (draft["draft_ref"],)).fetchone()[0] == 1
