"""Actual HTTP writes and final-state batches over current-schema adopted routes."""

import json
from dataclasses import replace
from datetime import datetime, timedelta

import pytest

from core.infrastructure.transaction import TransactionManager
from core.models.workbench_command import WorkbenchCommandRejected
from core.services.scheduler.template_lineage import TemplateLineageWriter
from core.services.workbench.run.preflight import PreflightService
from core.services.workbench.run.worker import WorkbenchRunWorker
from tests.workbench.field_workspace_support import BASE, FieldAPI, success
from tests.workbench.piece_adoption_support import split
from tests.workbench.run_candidate_adoption_support import INTENT, KEY, preview, rewrite_candidate, service, snapshot
from tests.workbench.run_candidate_support import candidate_case as _case  # noqa: F401
from tests.workbench.run_candidate_support import compute


def adopt(case):
    _run, refs = compute(case)
    service(case.conn).adopt(refs[0], preview(case, refs[0]), KEY, INTENT)
    return case.conn.execute("SELECT max(version) FROM ScheduleHistory").fetchone()[0]


def ordinary_route(case):
    second = case.operation(seq=2)
    case.conn.execute("UPDATE BatchOperations SET unit_hours=1 WHERE id=?", (case.op_id,))
    case.conn.commit()
    return adopt(case), second


def task(api, version, operation):
    return api.read("/tasks/" + api.case.task(version, operation))["data"]["task"]


def values(case, start, end, quantity=3):
    return case.values(quantity, actual_start=start, actual_end=end,
        effective_processing_hours=(datetime.fromisoformat(end) - datetime.fromisoformat(start)).total_seconds() / 3600)


def create(api, version, operation, payload):
    row = task(api, version, operation)
    return api.client.post(BASE + "/tasks/" + row["task_ref"] + "/reports",
                           json=api.body(row["execution"]["write_context"], payload))


def correct(api, version, operation, patch):
    report = task(api, version, operation)["execution"]["reports"][0]
    return api.client.post(BASE + "/reports/" + report["report_ref"] + "/correct", json=api.body(report["write_context"],
        {"original_revision_ref": report["revision_ref"], "reason": "按原始生产记录核对", **patch}))


def reject_without_changes(case, call):
    before = snapshot(case.conn)
    response = call()
    assert response.status_code == 409, response.get_json()
    assert response.get_json()["committed"] is False
    assert response.get_json()["error"]["code"] == "constraint_conflict"
    assert snapshot(case.conn) == before


@pytest.mark.parametrize("reverse", [False, True])
def test_new_reports_check_known_actual_dependencies_in_both_entry_orders(candidate_case, reverse):
    case = candidate_case
    version, second = ordinary_route(case)
    api = FieldAPI(case)
    reports = [(case.op_id, values(case, "2026-09-09T08:00:00", "2026-09-09T10:00:00")),
               (second, values(case, "2026-09-09T09:00:00", "2026-09-09T10:30:00"))]
    if reverse:
        reports.reverse()
    assert create(api, version, *reports[0]).status_code == 200
    reject_without_changes(case, lambda: create(api, version, *reports[1]))


def test_correcting_successor_before_actual_predecessor_is_rejected_and_next_run_works(candidate_case):
    case = candidate_case
    version, second = ordinary_route(case)
    api = FieldAPI(case)
    assert create(api, version, case.op_id, values(case, "2026-09-09T08:00:00", "2026-09-09T09:00:00")).status_code == 200
    assert create(api, version, second, values(case, "2026-09-09T10:00:00", "2026-09-09T10:45:00")).status_code == 200
    assert correct(api, version, case.op_id, {"actual_end": "2026-09-09T09:45:00"}).status_code == 200
    reject_without_changes(case, lambda: correct(api, version, second, {"actual_start": "2026-09-09T09:30:00"}))
    assert task(api, version, second)["execution"]["first_actual_start"] == "2026-09-09T10:00:00"
    case.batch("B2")
    case.operation("B2")
    case.conn.commit()
    accepted = case.accept(key="dependency-replan-0001", settings=case.settings("B1", "B2"))
    run = WorkbenchRunWorker(case.conn).execute(accepted["run_ref"])
    assert run["state"] == "complete" and run["candidates"]


def report_plan(case, version, selected=None):
    rows = list(case.conn.execute("SELECT s.*,bo.piece_id FROM Schedule s JOIN BatchOperations bo ON bo.id=s.op_id "
                                 "WHERE s.version=? ORDER BY s.start_time,s.op_id", (version,)))
    for row in rows:
        if selected is None or row["op_id"] in selected:
            case.command("create", case.task(version, row["op_id"]), values(case,
                row["start_time"].replace(" ", "T"), row["end_time"].replace(" ", "T"), 3 if row["piece_id"] is None else 1))


@pytest.mark.parametrize("shape", ["fanout", "join"])
@pytest.mark.parametrize("produced", [False, True])
def test_void_crosses_common_and_piece_boundaries_before_any_write(candidate_case, shape, produced):
    case = candidate_case
    ids = split(case)
    if shape == "fanout":
        case.conn.execute("DELETE FROM BatchOperations WHERE id=?", (ids[None, 40],))
        case.conn.commit()
    target = ids[None, 10] if shape == "fanout" else ids["item-A", 30]
    dependent = ids["item-A", 20] if shape == "fanout" else ids[None, 40]
    version = adopt(case)
    report_plan(case, version, None if produced else {target})
    api = FieldAPI(case)
    report = task(api, version, target)["execution"]["reports"][0]
    payload = {"original_revision_ref": report["revision_ref"], "reason": "核对原始报工", "declared_operator": "班长"}
    before = snapshot(case.conn)
    checked = success(api.client.post(BASE + "/reports/" + report["report_ref"] + "/void-preview", json={"input": payload}))["data"]
    assert checked["can_confirm"] is False and checked["write_context"]["write_token"] is None
    dependent_ref = task(api, version, dependent)["operation_ref"]
    assert dependent_ref in {item["operation_ref"] for item in checked["downstream_impacts"]}
    with pytest.raises(WorkbenchCommandRejected):
        case.command("report_void", report["report_ref"], payload)
    assert snapshot(case.conn) == before


def test_last_operation_of_unrelated_piece_can_still_be_voided(candidate_case):
    case = candidate_case
    ids = split(case, common=False)
    version = adopt(case)
    report_plan(case, version)
    api = FieldAPI(case)
    report = task(api, version, ids["item-A", 30])["execution"]["reports"][0]
    payload = {"original_revision_ref": report["revision_ref"], "reason": "本件记录重复", "declared_operator": "班长"}
    checked = success(api.client.post(BASE + "/reports/" + report["report_ref"] + "/void-preview", json={"input": payload}))["data"]
    assert checked["can_confirm"] is True and checked["downstream_impacts"] == []
    response = api.client.post(BASE + "/reports/" + report["report_ref"] + "/void", json=api.body(checked["write_context"], payload))
    assert response.status_code == 200, response.get_json()
    assert task(api, version, ids["item-B", 30])["execution"]["execution_state"] == "complete"


@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("valid", [False, True])
def test_batch_corrections_check_final_neighbours_and_are_atomic(candidate_case, reverse, valid):
    case = candidate_case
    version, second = ordinary_route(case)
    first = case.command("create", case.task(version, case.op_id), values(case, "2026-09-09T08:00:00", "2026-09-09T09:00:00"))["data"]["rows"][0]
    later = case.command("create", case.task(version, second), values(case, "2026-09-09T10:00:00", "2026-09-09T10:45:00"))["data"]["rows"][0]
    items = [{"action": "correct", "ref": row["report_ref"], "payload": {
        "original_revision_ref": row["revision_ref"], "reason": "整批核对时间", **patch}} for row, patch in (
            (first, {"actual_end": "2026-09-09T10:30:00"}),
            (later, {"actual_start": "2026-09-09T10:30:00" if valid else "2026-09-09T09:30:00", "effective_processing_hours": .25}))]
    if reverse:
        items.reverse()
    before = snapshot(case.conn)
    if valid:
        assert case.writer.preview_batch(items)["can_confirm"] is True
        assert snapshot(case.conn) == before
        result = case.writer.execute_batch(items, context_ref=case.plan_ref(version), request_key="dependency-batch-correct-001",
                                           validate_context=lambda *_: None)
        assert result["result"] == "committed"
    else:
        with pytest.raises(WorkbenchCommandRejected):
            case.writer.preview_batch(items)
        with pytest.raises(WorkbenchCommandRejected):
            case.writer.execute_batch(items, context_ref=case.plan_ref(version), request_key="dependency-batch-correct-001",
                                      validate_context=lambda *_: None)
        assert snapshot(case.conn) == before


def test_late_actual_does_not_use_unstarted_planned_successor_as_a_blocker(candidate_case):
    case = candidate_case
    version, second = ordinary_route(case)
    api = FieldAPI(case)
    assert create(api, version, case.op_id, values(case, "2026-09-09T08:00:00", "2026-09-09T12:00:00")).status_code == 200
    assert create(api, version, second, values(case, "2026-09-09T13:00:00", "2026-09-09T13:45:00")).status_code == 200


def merged_external_route(case, piece=False, members=2):
    case.conn.execute("UPDATE OpTypes SET category='both' WHERE op_type_id='T1'")
    case.conn.execute("INSERT INTO Suppliers(supplier_id,name,op_type_id) VALUES ('S1','供应商','T1')")
    case.conn.execute("INSERT INTO ExternalGroups(group_id,part_no,start_seq,end_seq,merge_mode,total_days,supplier_id) "
                      "VALUES ('G','P1',2,?,'merged',1,'S1')", (members + 1,))
    copied = []
    with TransactionManager(case.conn).transaction():
        for seq in range(2, members + 2):
            cursor = case.conn.execute("INSERT INTO PartOperations(part_no,seq,op_type_id,op_type_name,source,supplier_id,ext_group_id,setup_hours,unit_hours) "
                                      "VALUES ('P1',?,'T1','Turning','external','S1','G',0,0)", (seq,))
            copied.append(TemplateLineageWriter(case.conn).copy_template("B1", cursor.lastrowid))
    if piece:
        case.conn.execute("UPDATE Batches SET quantity=1 WHERE batch_id='B1'")
        case.conn.execute("UPDATE BatchOperations SET piece_id='unit-A' WHERE batch_id='B1'")
    case.conn.commit()
    return copied


def test_merged_external_actuals_can_share_one_period(candidate_case):
    case = candidate_case
    copied = merged_external_route(case)
    version = adopt(case)
    report_plan(case, version, {case.op_id})
    api = FieldAPI(case)
    for operation in copied:
        payload = values(case, "2026-09-09T10:00:00", "2026-09-10T10:00:00")
        payload.update(actual_machine_ref=None, actual_operator_ref=None)
        response = create(api, version, operation, payload)
        assert response.status_code == 200, response.get_json()


@pytest.mark.parametrize("piece,all_members,locked,extra_hours,start_date", [
    pytest.param(False, False, False, 0, "2026-09-09", id="batch-one"),
    pytest.param(False, True, False, 0, "2026-09-09", id="batch-all"),
    pytest.param(True, False, False, 0, "2026-09-09", id="piece-one"),
    pytest.param(True, True, False, 0, "2026-09-09", id="piece-all"),
    pytest.param(False, False, True, 0, "2026-09-09", id="batch-one-locked"),
    pytest.param(False, False, False, 2, "2026-09-09", id="batch-actual-26-hours"),
    pytest.param(True, False, False, 2, "2026-09-09", id="piece-actual-26-hours"),
    pytest.param(False, False, False, 0, "2026-09-11", id="batch-actual-before-window"),
    pytest.param(True, False, False, 0, "2026-09-11", id="piece-actual-before-window"),
])
def test_merged_external_actuals_preserve_group_period_on_replan_and_adoption(candidate_case, piece, all_members, locked, extra_hours, start_date):
    case = candidate_case
    copied = merged_external_route(case, piece)
    version = adopt(case)
    original = {row["op_id"]: (row["start_time"], row["end_time"]) for row in case.conn.execute(
        "SELECT op_id,start_time,end_time FROM Schedule WHERE version=? AND op_id IN (?,?)", (version, *copied))}
    assert set(original) == set(copied) and len(set(original.values())) == 1
    report_plan(case, version, {case.op_id})
    api = FieldAPI(case)
    for operation in copied if all_members else copied[:1]:
        start, end = original[operation]
        actual_end = datetime.fromisoformat(end) + timedelta(hours=extra_hours)
        payload = values(case, start.replace(" ", "T"), actual_end.isoformat(), 1 if piece else 3)
        payload.update(actual_machine_ref=None, actual_operator_ref=None)
        assert case.writer.preview("create", case.task(version, operation), payload)["can_confirm"] is True
        assert success(create(api, version, operation, payload))["result"] == "committed"
    if locked:
        case.conn.execute("UPDATE Schedule SET lock_status='locked' WHERE version=? AND op_id=?", (version, copied[1]))
    case.batch("B2")
    case.operation("B2")
    case.conn.commit()
    accepted = case.accept(key="merged-actual-next-run-001", settings=case.settings("B1", "B2", start_date=start_date))
    run = WorkbenchRunWorker(case.conn).execute(accepted["run_ref"])
    assert run["state"] == "complete" and run["candidates"]
    expected = {op_id: (datetime.fromisoformat(period[0]), datetime.fromisoformat(period[1]) + timedelta(hours=extra_hours))
                for op_id, period in original.items()}
    for candidate in run["candidates"]:
        rows = (json.loads(row[0]) for row in case.conn.execute(
            "SELECT payload_json FROM WorkbenchRunCandidateTasks WHERE candidate_ref=?", (candidate["candidate_ref"],)))
        periods = {row["op_id"]: (datetime.fromisoformat(row["start_time"]), datetime.fromisoformat(row["end_time"]))
                   for row in rows if row["op_id"] in copied}
        assert periods == expected
    ref = run["candidates"][0]["candidate_ref"]
    result = service(case.conn).adopt(ref, preview(case, ref), "merged-actual-adopt-002", INTENT)
    assert result["result"] == "committed"
    stored = {row["op_id"]: (datetime.fromisoformat(row["start_time"]), datetime.fromisoformat(row["end_time"]))
              for row in case.conn.execute("SELECT op_id,start_time,end_time FROM Schedule WHERE version=? AND op_id IN (?,?)",
                                           (result["data"]["official_plan"]["version"], *copied))}
    assert stored == expected
    if locked:
        assert case.conn.execute("SELECT lock_status FROM Schedule WHERE version=? AND op_id=?",
                                 (result["data"]["official_plan"]["version"], copied[1])).fetchone()[0] == "locked"


def late_merged_actual(case, piece=False, member=0):
    copied = merged_external_route(case, piece)
    version = adopt(case)
    report_plan(case, version, {case.op_id})
    start, end = (datetime.fromisoformat(value) for value in case.conn.execute(
        "SELECT start_time,end_time FROM Schedule WHERE version=? AND op_id=?", (version, copied[member])).fetchone())
    end += timedelta(hours=2)
    payload = values(case, start.isoformat(), end.isoformat(), 1 if piece else 3)
    payload.update(actual_machine_ref=None, actual_operator_ref=None)
    case.command("create", case.task(version, copied[member]), payload)
    return version, copied, (start, end)


@pytest.mark.parametrize("piece", [False, True])
def test_actual_merged_cycle_only_ignores_later_ready_and_material_dates(candidate_case, piece):
    from core.services.workbench.batch.materials import WorkbenchBatchMaterialService
    from tests.workbench.test_material_stage_release import add_requirement
    from tests.workbench.trial_adoption_support import INTENT as trial_intent
    from tests.workbench.trial_adoption_support import preview as trial_preview
    from tests.workbench.trial_adoption_support import saved_scenario
    from tests.workbench.trial_adoption_support import service as trial_adoption

    case = candidate_case
    _, copied, period = late_merged_actual(case, piece)
    # The physical cycle is already in actual history. A later master-data
    # release date must not turn its remaining unreported member into new work.
    if not piece:
        add_requirement(case, copied[1], [{"arrival_date": "2030-01-01", "quantity": 3}])
        case.conn.execute("INSERT INTO WorkbenchCalendarDefaults(singleton,periods_json) VALUES (1,?)",
                          ('[{"start":"08:00","end":"16:00","day_offset":0}]',))
    else:
        case.conn.execute("INSERT INTO Materials(material_id,name,unit) VALUES ('STEEL','钢材','件')")
        case.conn.commit()
        with TransactionManager(case.conn).transaction():
            WorkbenchBatchMaterialService(case.conn).apply(case.ref("batch", "B1"), {"removed_keys": [], "rows": [{
                "row_key": None, "material_ref": case.ref("material", "STEEL"), "required_quantity": 1,
                "available_quantity": 0, "operation_ref": None,
                "arrivals": [{"arrival_date": "2030-01-01", "quantity": 1}]}]})
    case.conn.execute("UPDATE Batches SET ready_date='2026-09-20',ready_status='no' WHERE batch_id='B1'")
    case.conn.commit()
    settings = case.settings(material_strategy="stage", start_date="2026-09-11", end_date="2026-09-15")
    checked, _ = PreflightService(case.conn).evaluate(settings)
    assert checked["blockers"] == [] and checked["counts"]["eligible_tasks"] == 0
    assert checked["included_batches"] == [{"batch_ref": case.ref("batch", "B1"), "batch_id": "B1"}]
    assert all("op_id" not in row and "external_execution_cycle" not in row for row in checked["tasks"])
    accepted = case.accept(key="merged-cycle-only-run-001", settings=settings)
    run = WorkbenchRunWorker(case.conn).execute(accepted["run_ref"])
    assert run["state"] == "complete" and run["candidates"]
    ref = run["candidates"][0]["candidate_ref"]
    assert service(case.conn).preview(ref)["validation"]["can_adopt"]
    saved = saved_scenario(case, {"base": {"candidate_ref": ref}}, changed=False)
    result = trial_adoption(case.conn).adopt(saved["scenario_ref"], trial_preview(case, saved), "merged-cycle-only-trial-001", trial_intent)
    assert {tuple(datetime.fromisoformat(value) for value in row) for row in case.conn.execute(
        "SELECT start_time,end_time FROM Schedule WHERE version=? AND op_id IN (?,?)",
        (result["data"]["official_plan"]["version"], *copied))} == {period}


@pytest.mark.parametrize("member", [0, 1])
def test_actual_cycle_conflicts_with_existing_frozen_member_in_either_direction(candidate_case, member):
    from core.errors import AppError
    from core.services.scheduler.schedule_service import ScheduleService

    case = candidate_case
    late_merged_actual(case, member=member)
    case.batch("B2")
    case.operation("B2")
    case.conn.commit()
    case.config(freeze_window_enabled="yes", freeze_window_days=3)
    before = snapshot(case.conn)
    with pytest.raises(AppError) as caught:
        ScheduleService(case.conn).run_schedule(["B1", "B2"], start_dt=datetime(2026, 9, 9), end_date=datetime(2026, 9, 25).date())
    assert caught.value.details["reason"] == "execution_merged_group_split"
    assert snapshot(case.conn) == before


def test_persistence_guard_rejects_split_cycle_before_completed_later_member(candidate_case):
    from core.errors import AppError
    from core.services.scheduler.run.schedule_execution_persistence_guard import validate_execution_guard_before_persist
    from core.services.scheduler.run.schedule_payload_contract import build_validated_schedule_payload
    from core.services.scheduler.schedule_service import ScheduleService
    from core.services.workbench.run.compute import compute_candidate_run

    case = candidate_case
    _, copied, period = late_merged_actual(case, member=1)
    computation = compute_candidate_run(case.conn, case.settings(), case.projections())
    prepared = computation.schedule_input
    original = next(iter(computation.candidate_payloads.values()))
    rows = [replace(row, end_time=period[1] - timedelta(hours=2)) if row.op_id == copied[0] else row
            for row in original.schedule_rows]
    bad = build_validated_schedule_payload(rows, allowed_op_ids=original.scheduled_op_ids, operations=prepared.operations)
    before = snapshot(case.conn)
    with pytest.raises(AppError) as caught:
        validate_execution_guard_before_persist(ScheduleService(case.conn), validated_schedule_payload=bad,
            execution_guard_state_revisions=prepared.execution_guard_state_revisions, execution_facts=prepared.execution_facts,
            execution_fixed_op_ids=prepared.execution_fixed_op_ids, execution_completed_op_ids=prepared.execution_completed_op_ids,
            execution_snapshot_revision=prepared.execution_snapshot_revision, execution_snapshot_op_ids=prepared.execution_snapshot_op_ids,
            payload_validation_operations=prepared.operations)
    assert caught.value.details["reason"] == "execution_merged_group_split"
    assert snapshot(case.conn) == before


@pytest.mark.parametrize("other_actual_group", [False, True])
def test_unreported_group_cannot_borrow_another_cycles_actual_duration(candidate_case, other_actual_group):
    case = candidate_case
    if other_actual_group:
        late_merged_actual(case)
        case.batch("B2")
        case.operation("B2")
        templates = list(case.conn.execute("SELECT id FROM PartOperations WHERE part_no='P1' ORDER BY seq"))
        with TransactionManager(case.conn).transaction():
            for row in templates:
                TemplateLineageWriter(case.conn).copy_template("B2", row[0])
        selected = ("B1", "B2")
        target = {row[0] for row in case.conn.execute("SELECT id FROM BatchOperations WHERE batch_id='B2' AND source='external'")}
    else:
        target = set(merged_external_route(case))
        selected = ("B1",)
    case.conn.commit()
    _, refs = compute(case, case.settings(*selected)) if not other_actual_group else next_cycle_run(case, selected)
    ref = refs[0]
    rewrite_candidate(case, ref, lambda row: row.update(end_time=(datetime.fromisoformat(row["end_time"]) + timedelta(hours=2)).isoformat())
                      if row["op_id"] in target else None)
    checked = service(case.conn).preview(ref)
    assert checked["validation"]["can_adopt"] is False
    assert checked["validation"]["issues"][0]["code"] == "candidate_external_duration_conflict"


def next_cycle_run(case, selected):
    accepted = case.accept(key="other-cycle-run-000001", settings=case.settings(*selected))
    computed = WorkbenchRunWorker(case.conn).execute(accepted["run_ref"])
    return computed["run_ref"], [row["candidate_ref"] for row in computed["candidates"]]


def external_route(case, piece=False):
    case.conn.execute("UPDATE OpTypes SET category='both' WHERE op_type_id='T1'")
    case.conn.execute("INSERT INTO Suppliers(supplier_id,name,op_type_id) VALUES ('S1','供应商','T1')")
    case.conn.execute("INSERT INTO PartOperations(part_no,seq,op_type_id,op_type_name,source,supplier_id,ext_days) "
                      "VALUES ('P1',1,'T1','Turning','external','S1',2)")
    case.conn.execute("UPDATE BatchOperations SET source='external',supplier_id='S1',ext_days=2,machine_id=NULL,operator_id=NULL")
    if piece:
        case.conn.execute("UPDATE Batches SET quantity=1 WHERE batch_id='B1'")
        case.conn.execute("UPDATE BatchOperations SET piece_id='unit-A'")
    case.conn.commit()


@pytest.mark.parametrize("piece", [False, True])
@pytest.mark.parametrize("include_external", [False, True])
def test_external_completion_allows_other_work_and_preserves_actuals_in_trial(candidate_case, piece, include_external):
    from tests.workbench.trial_adoption_support import INTENT as trial_intent
    from tests.workbench.trial_adoption_support import preview as trial_preview
    from tests.workbench.trial_adoption_support import saved_scenario
    from tests.workbench.trial_adoption_support import service as trial_service

    case = candidate_case
    external_route(case, piece)
    version = adopt(case)
    api = FieldAPI(case)
    payload = values(case, "2026-09-09T08:00:00", "2026-09-09T10:00:00", 1 if piece else 3)
    payload.update(actual_machine_ref=None, actual_operator_ref=None)
    assert create(api, version, case.op_id, payload).status_code == 200
    case.batch("B2")
    internal = case.operation("B2")
    case.conn.commit()
    batches = ("B1", "B2") if include_external else ("B2",)
    accepted = case.accept(key="external-complete-next-run-001", settings=case.settings(*batches))
    run = WorkbenchRunWorker(case.conn).execute(accepted["run_ref"])
    assert run["state"] == "complete" and run["candidates"]
    if include_external:
        ref = run["candidates"][0]["candidate_ref"]
        adopted = service(case.conn).adopt(ref, preview(case, ref), "external-complete-adopt-002", INTENT)
        saved = saved_scenario(case, {"base": {"plan_ref": adopted["data"]["official_plan"]["plan_ref"]}}, changed=False)
        result = trial_service(case.conn).adopt(saved["scenario_ref"], trial_preview(case, saved),
            "external-complete-trial-adopt-001", trial_intent)
        assert result["result"] == "committed"
        latest = case.conn.execute("SELECT max(version) FROM ScheduleHistory").fetchone()[0]
        row = case.conn.execute("SELECT start_time,end_time,machine_id,operator_id FROM Schedule WHERE version=? AND op_id=?",
                                (latest, case.op_id)).fetchone()
        assert tuple(row) == ("2026-09-09 08:00:00", "2026-09-09 10:00:00", None, None)
        assert case.conn.execute("SELECT start_time FROM Schedule WHERE version=? AND op_id=?", (latest, internal)).fetchone()[0] == "2026-09-09 08:00:00"
    current_version = case.conn.execute("SELECT max(version) FROM ScheduleHistory").fetchone()[0]
    original = task(api, current_version, case.op_id)["execution"]["reports"][0]
    assert original["actual_machine_ref"] is None and original["actual_operator_ref"] is None
    assert original["actual_start"] == "2026-09-09T08:00:00" and original["actual_end"] == "2026-09-09T10:00:00"


@pytest.mark.parametrize("external", [False, True])
def test_execution_resource_fix_does_not_relax_internal_or_discard_external_resources(candidate_case, monkeypatch, external):
    from core.errors import AppError
    from core.services.scheduler.execution.execution_ledger_guard import ensure_ledger_execution_schedulable
    from core.services.workbench.execution import production_report_validation
    from tests.workbench.scheduler_execution_ledger_support import read_facts

    case = candidate_case
    if external:
        external_route(case)
    version = adopt(case)
    payload = case.values(3)
    if not external:
        payload.update(actual_machine_ref=None, actual_operator_ref=None)
    else:
        # 外协报工带本厂设备人员在入口就拒绝；下面绕过入口模拟修复前已写进库的旧记录，守卫仍不放行。
        before = snapshot(case.conn)
        with pytest.raises(WorkbenchCommandRejected) as rejected:
            case.command("create", case.task(version, case.op_id), payload)
        assert rejected.value.code == "constraint_conflict" and "经办人" in str(rejected.value)
        assert snapshot(case.conn) == before
        monkeypatch.setattr(production_report_validation, "_reject_external_resources", lambda operation, values: None)
    case.command("create", case.task(version, case.op_id), payload)
    before = snapshot(case.conn)
    facts = read_facts(case.conn, version)
    with pytest.raises(AppError) as caught:
        ensure_ledger_execution_schedulable(facts)
    expected = "execution_ledger_external_resource_conflict" if external else "execution_ledger_actual_resource_missing_or_multiple"
    assert expected in caught.value.details["data_gaps"]
    assert snapshot(case.conn) == before


@pytest.mark.parametrize("kind", ["machine", "operator"])
def test_old_external_report_holding_internal_resource_is_named_before_any_run(candidate_case, monkeypatch, kind):
    from core.services.workbench.execution import production_report_validation

    case = candidate_case
    external_route(case)
    version = adopt(case)
    payload = values(case, "2026-09-09T08:00:00", "2026-09-09T10:00:00")
    payload["actual_" + ("operator" if kind == "machine" else "machine") + "_ref"] = None
    monkeypatch.setattr(production_report_validation, "_reject_external_resources", lambda operation, values: None)
    report = case.command("create", case.task(version, case.op_id), payload)["data"]["rows"][0]
    monkeypatch.undo()
    case.batch("B2")
    case.operation("B2")
    case.conn.commit()
    # 只排无关批次也会被正式计划里的这条外协报工拦下：预检先指出是哪条报工、该怎么改。
    checked, _ = PreflightService(case.conn).evaluate(case.settings("B2"))
    assert checked["execution_projection_source"] == "execution_ledger"
    blocker = next(row for row in checked["blockers"] if row["code"] == "external_actual_resource_conflict")
    assert (blocker["operation_ref"], blocker["batch_id"]) == (report["operation_ref"], "B1")
    assert report["report_no"] in blocker["message"] and "更正" in blocker["message"]
    keep = {"original_revision_ref": report["revision_ref"], "reason": "按回厂单核对", "remark": "只改备注"}
    with pytest.raises(WorkbenchCommandRejected) as kept:
        case.command("correct", report["report_ref"], keep)
    assert "请用「更正」清除" in str(kept.value)
    case.command("correct", report["report_ref"], {**keep, "actual_machine_ref": None, "actual_operator_ref": None})
    checked, _ = PreflightService(case.conn).evaluate(case.settings("B2"))
    assert checked["blockers"] == []
    accepted = case.accept(key="external-resource-fixed-run-" + kind, settings=case.settings("B2"))
    assert WorkbenchRunWorker(case.conn).execute(accepted["run_ref"])["state"] == "complete"


def merged_member(case, start, end=None, quantity=3):
    payload = values(case, start, end, quantity) if end else {"actual_start": start, "remark": ""}
    payload.update(actual_machine_ref=None, actual_operator_ref=None)
    return payload


def test_merged_members_record_one_actual_period_on_create_and_supplement(candidate_case):
    case = candidate_case
    copied = merged_external_route(case)
    version = adopt(case)
    report_plan(case, version, {case.op_id})
    start, end = (value.replace(" ", "T") for value in case.conn.execute(
        "SELECT start_time,end_time FROM Schedule WHERE version=? AND op_id=?", (version, copied[0])).fetchone())
    later = (datetime.fromisoformat(end) + timedelta(minutes=5)).isoformat()
    case.command("create", case.task(version, copied[0]), merged_member(case, start, end))
    before = snapshot(case.conn)
    for call in (lambda: case.writer.preview("create", case.task(version, copied[1]), merged_member(case, start, later)),
                 lambda: case.command("create", case.task(version, copied[1]), merged_member(case, start, later))):
        with pytest.raises(WorkbenchCommandRejected) as caught:
            call()
        assert "同组第 2 道已登记" in str(caught.value) and end.replace("T", " ") in str(caught.value)
    assert snapshot(case.conn) == before
    started = case.command("create", case.task(version, copied[1]), merged_member(case, start))["data"]["rows"][0]
    patch = {"original_revision_ref": started["revision_ref"], "reason": "补回厂时间", "completed_quantity": 3,
             "effective_processing_hours": 1}
    with pytest.raises(WorkbenchCommandRejected):
        case.command("supplement", started["report_ref"], dict(patch, actual_end=later))
    assert case.command("supplement", started["report_ref"], dict(patch, actual_end=end))["result"] == "committed"


def test_merged_cycle_correction_moves_group_and_preflight_names_unfinished_moves(candidate_case):
    case = candidate_case
    copied = merged_external_route(case)
    version = adopt(case)
    report_plan(case, version, {case.op_id})
    start, end = (value.replace(" ", "T") for value in case.conn.execute(
        "SELECT start_time,end_time FROM Schedule WHERE version=? AND op_id=?", (version, copied[0])).fetchone())
    reports = [case.command("create", case.task(version, op), merged_member(case, start, end))["data"]["rows"][0] for op in copied]
    case.batch("B2")
    case.operation("B2")
    case.conn.commit()
    settings = case.settings("B1", "B2")
    moved = (datetime.fromisoformat(end) + timedelta(hours=1)).isoformat()

    def correct(report, actual_end):
        return case.command("correct", report["report_ref"], {"original_revision_ref": report["revision_ref"],
                                                              "reason": "按回厂单核对", "actual_end": actual_end})

    # 原本一致的整组可以逐道改到新时间；没改齐之前，排产检查明确指出是哪一组，而不是报“报工记录没准备好”。
    correct(reports[0], moved)
    checked, _ = PreflightService(case.conn).evaluate(settings)
    assert checked["execution_projection_source"] == "execution_ledger"
    split_cycle = next(row for row in checked["blockers"] if row["code"] == "external_cycle_actuals_differ")
    assert split_cycle["operation_ref"] == reports[0]["operation_ref"] and split_cycle["batch_id"] == "B1"
    assert "第 2 道" in split_cycle["message"] and "第 3 道" in split_cycle["message"]
    with pytest.raises(WorkbenchCommandRejected) as caught:
        correct(reports[1], (datetime.fromisoformat(moved) + timedelta(minutes=5)).isoformat())
    assert "同组第 2 道已登记" in str(caught.value)
    correct(reports[1], moved)
    checked, _ = PreflightService(case.conn).evaluate(settings)
    assert checked["blockers"] == []
    accepted = case.accept(key="merged-cycle-moved-run-0001", settings=settings)
    assert WorkbenchRunWorker(case.conn).execute(accepted["run_ref"])["state"] == "complete"


def merged_period(case, version, operation):
    return tuple(value.replace(" ", "T") for value in case.conn.execute(
        "SELECT start_time,end_time FROM Schedule WHERE version=? AND op_id=?", (version, operation)).fetchone())


def shifted(value, minutes):
    return (datetime.fromisoformat(value) + timedelta(minutes=minutes)).isoformat()


@pytest.mark.parametrize("first", [0, 1])
def test_merged_cycle_with_a_start_only_member_can_be_moved_from_either_member(candidate_case, first):
    case = candidate_case
    copied = merged_external_route(case)
    version = adopt(case)
    report_plan(case, version, {case.op_id})
    start, end = merged_period(case, version, copied[0])
    # 第 2 道已回厂，第 3 道只报了开工：两道开工一致，只是第 3 道还没填完工。
    reports = [case.command("create", case.task(version, copied[0]), merged_member(case, start, end))["data"]["rows"][0],
               case.command("create", case.task(version, copied[1]), merged_member(case, start))["data"]["rows"][0]]
    moved = shifted(start, 30)

    def correct(index, actual_start):
        patch = {"original_revision_ref": reports[index]["revision_ref"], "reason": "按送出单核对开工", "actual_start": actual_start}
        if index == 0:  # 已回厂那道开工改晚，有效加工小时跟着缩到新的起止时长
            patch["effective_processing_hours"] = (datetime.fromisoformat(end) - datetime.fromisoformat(actual_start)).total_seconds() / 3600
        return case.command("correct", reports[index]["report_ref"], patch)

    # 整组开工改晚半小时：先改哪一道都行（空着的完工不算对不上）；另一道只能跟着改到同一时间。
    assert correct(first, moved)["result"] == "committed"
    with pytest.raises(WorkbenchCommandRejected) as caught:
        correct(1 - first, shifted(moved, 5))
    assert "同组第 " + str(first + 2) + " 道已登记" in str(caught.value)
    assert correct(1 - first, moved)["result"] == "committed"
    api = FieldAPI(case)
    assert [task(api, version, op)["execution"]["first_actual_start"] for op in copied] == [moved, moved]


def test_merged_cycle_with_three_different_old_periods_can_be_corrected_one_by_one(candidate_case, monkeypatch):
    from core.services.workbench.execution import production_report_prepare

    case = candidate_case
    copied = merged_external_route(case, members=3)
    version = adopt(case)
    report_plan(case, version, {case.op_id})
    start, end = merged_period(case, version, copied[0])
    finishes = [shifted(end, minutes) for minutes in (0, 10, 20)]
    # 旧数据：同组三道的回厂时间各不相同（登记时还没有同组校验）。
    monkeypatch.setattr(production_report_prepare, "validate_merged_cycle", lambda *args: None)
    reports = [case.command("create", case.task(version, op), merged_member(case, start, finish))["data"]["rows"][0]
               for op, finish in zip(copied, finishes)]
    monkeypatch.undo()

    def correct(index, actual_end):
        report = reports[index]
        result = case.command("correct", report["report_ref"], {"original_revision_ref": report["revision_ref"], "reason": "按回厂单核对",
                                                                "actual_end": actual_end, "effective_processing_hours": 1})
        reports[index] = dict(report, revision_ref=result["data"]["rows"][0]["revision_ref"])
        return result

    def rejected(index, actual_end):
        before = snapshot(case.conn)
        with pytest.raises(WorkbenchCommandRejected) as caught:
            correct(index, actual_end)
        assert "同组第 " in str(caught.value) and snapshot(case.conn) == before

    # 改成和哪道都对不上的第四种时间，仍被拦下；改成和其中一道一致，就能逐道改齐。
    rejected(0, shifted(end, 30))
    assert correct(0, finishes[1])["result"] == "committed"
    # 其余两道已经一致：第 4 道要和两道都对上，改成别的时间仍被拦下。
    rejected(2, shifted(end, 30))
    assert correct(2, finishes[1])["result"] == "committed"
    checked, _ = PreflightService(case.conn).evaluate(case.settings())
    assert "external_cycle_actuals_differ" not in {row["code"] for row in checked["blockers"]}
    # 改齐后整组照常可以逐道挪；挪到一半时，另一道只能跟上，不能再改成第三种时间。
    moved = shifted(end, 40)
    assert correct(1, moved)["result"] == "committed"
    rejected(2, shifted(end, 50))
    assert correct(2, moved)["result"] == "committed"


def test_merged_cycle_corrections_never_part_from_agreeing_members():
    from core.services.workbench.execution import production_report_validation

    blocker = production_report_validation._cycle_blocker
    t = [datetime(2026, 9, 9, hour) for hour in range(8, 16)]
    apart = [("C", (t[1], t[3])), ("D", (t[2], t[4]))]
    # 其余各道本来就对不上：和其中一道对上就放行；对谁都对不上，或和原本一致的那道分开，都不放行。
    assert blocker(apart, (t[1], t[3]), (t[5], t[6]), True) is None
    assert blocker(apart, (t[5], t[7]), (t[5], t[6]), True) == apart[0]
    agreeing = [("B", (t[0], None))] + apart
    assert blocker(agreeing, (t[1], t[3]), (t[0], t[6]), True) == agreeing[0]
    # 补登不走更正放行：和任何一道对不上都拦下；只报开工、两边都填了的时间相同就算一致。
    assert blocker(agreeing, (t[1], t[3]), (None, None), False) == agreeing[0]
    assert blocker([("B", (t[0], None))], (t[0], t[6]), (None, None), False) is None


def test_locked_member_off_the_actual_cycle_is_a_preflight_blocker(candidate_case):
    from tests.workbench.run_jobs_support import service as run_service

    case = candidate_case
    version, copied, period = late_merged_actual(case, member=0)
    case.conn.execute("UPDATE Schedule SET lock_status='locked' WHERE version=? AND op_id=?", (version, copied[1]))
    case.conn.commit()
    checked, _ = PreflightService(case.conn).evaluate(case.settings())
    assert checked["execution_projection_source"] == "execution_ledger"
    locked = next(row for row in checked["blockers"] if row["code"] == "external_cycle_locked_conflict")
    assert locked["operation_ref"] == next(row["operation_ref"] for row in checked["tasks"] if row["sequence"] == 3)
    assert period[1].isoformat(sep=" ") in locked["message"] and "解锁" in locked["message"]
    reasons = run_service(case.conn).preview(case.preflight())["write_context"]["blocked_reasons"]
    assert "external_cycle_locked_conflict" in {row["code"] for row in reasons}
    assert "execution_ledger_unavailable" not in {row["code"] for row in reasons}
    case.conn.execute("UPDATE Schedule SET lock_status='unlocked' WHERE version=? AND op_id=?", (version, copied[1]))
    case.conn.commit()
    accepted = case.accept(key="locked-member-unlocked-run-01", settings=case.settings())
    assert WorkbenchRunWorker(case.conn).execute(accepted["run_ref"])["state"] == "complete"


def test_frozen_member_off_the_actual_cycle_is_a_preflight_blocker(candidate_case):
    """同组未报工成员的原安排落在不重排时段里（这里来自交付设置的「锁定近期排程」3 天），排产会原样保留它，和已报工的实际周期对不上：
    排产检查先拦下（冻结解不了锁，不提解锁），不再放行后让排产整次失败、把人引去核对现场记录。"""
    case = candidate_case
    _version, _copied, period = late_merged_actual(case, member=0)
    case.config(freeze_window_enabled="yes", freeze_window_days=3)
    checked, _ = PreflightService(case.conn).evaluate(case.settings())
    frozen = [row for row in checked["blockers"] if row["code"] == "external_cycle_locked_conflict"]
    assert [row["operation_ref"] for row in frozen] == [row["operation_ref"] for row in checked["tasks"] if row["sequence"] == 3]
    assert all(period[1].isoformat(sep=" ") in row["message"] and "不重排时段（2026-09-09 00:00 至 2026-09-12 00:00）" in row["message"]
               and "解锁" not in row["message"] for row in frozen)
    case.config(freeze_window_enabled="no")
    accepted = case.accept(key="frozen-member-unfrozen-run-1", settings=case.settings())
    assert WorkbenchRunWorker(case.conn).execute(accepted["run_ref"])["state"] == "complete"


def adopt_selected(case, key, *batches):
    accepted = case.accept(key=key + "-run", settings=case.settings(*batches))
    ref = WorkbenchRunWorker(case.conn).execute(accepted["run_ref"])["candidates"][0]["candidate_ref"]
    service(case.conn).adopt(ref, preview(case, ref), key + "-adopt", INTENT)


def make_external(case, op_id):
    # 升级前的守卫把外协也当自制、要求填设备人员；升级后这道工序按外协核对。
    case.conn.execute("INSERT INTO Suppliers(supplier_id,name,op_type_id) VALUES ('S1','供应商','T1')")
    case.conn.execute("UPDATE OpTypes SET category='both' WHERE op_type_id='T1'")
    case.conn.execute("UPDATE BatchOperations SET source='external',supplier_id='S1',ext_days=2 WHERE id=?", (op_id,))
    case.conn.commit()


def test_old_external_report_on_an_older_adopted_plan_can_still_be_cleared(candidate_case):
    case = candidate_case
    first = adopt(case)
    report = case.command("create", case.task(first, case.op_id),
                          values(case, "2026-09-09T08:00:00", "2026-09-09T10:00:00"))["data"]["rows"][0]
    case.batch("B2")
    case.operation("B2")
    case.conn.commit()
    adopt_selected(case, "older-plan-report-0001", "B1", "B2")
    make_external(case, case.op_id)
    clear = {"original_revision_ref": report["revision_ref"], "reason": "外协不占本厂资源", "actual_machine_ref": None, "actual_operator_ref": None}
    # 只清空设备人员不算改了采用依据；同时改数量等其他采用依据仍按原规则拒绝。
    with pytest.raises(WorkbenchCommandRejected) as changed:
        case.command("correct", report["report_ref"], dict(clear, completed_quantity=2))
    codes = {row["code"] for row in changed.value.conflicts}
    assert "adopted_execution_basis_changed" in codes and "adopted_actual_resource_changed" not in codes
    assert case.command("correct", report["report_ref"], clear)["result"] == "committed"
    checked, _ = PreflightService(case.conn).evaluate(case.settings("B2"))
    assert checked["blockers"] == []
    accepted = case.accept(key="older-plan-report-cleared-1", settings=case.settings("B2"))
    assert WorkbenchRunWorker(case.conn).execute(accepted["run_ref"])["state"] == "complete"


def test_cycle_check_failure_is_a_blocker_and_keeps_the_resource_report_named(candidate_case, monkeypatch):
    from core.services.workbench.execution import production_report_validation

    case = candidate_case
    copied = merged_external_route(case)
    version = adopt(case)
    report_plan(case, version, {case.op_id})
    start, end = (value.replace(" ", "T") for value in case.conn.execute(
        "SELECT start_time,end_time FROM Schedule WHERE version=? AND op_id=?", (version, copied[0])).fetchone())
    case.command("create", case.task(version, copied[0]), merged_member(case, start, end))
    monkeypatch.setattr(production_report_validation, "_reject_external_resources", lambda operation, values: None)
    held = case.command("create", case.task(version, copied[1]), values(case, start, end))["data"]["rows"][0]
    monkeypatch.undo()
    checked, _ = PreflightService(case.conn).evaluate(case.settings())
    # 周期核对不了不是“报工台账没准备好”；外协报工带本厂资源的具体提示照样列出。
    assert checked["execution_projection_source"] == "execution_ledger"
    codes = [row["code"] for row in checked["blockers"]]
    assert "external_execution_cycle_unproven" in codes and "external_actual_resource_conflict" in codes
    assert any(held["report_no"] in row["message"] for row in checked["blockers"])


@pytest.mark.parametrize("replanned", [False, True])
def test_old_external_events_holding_internal_resources_follow_the_guard_scope(candidate_case, replanned):
    from core.errors import AppError
    from core.services.workbench.run.compute import compute_candidate_run

    case = candidate_case
    first = adopt(case)
    start, end = case.conn.execute("SELECT start_time,end_time FROM Schedule WHERE version=? AND op_id=?", (first, case.op_id)).fetchone()
    case.event(case.op_id, "start", version=first, time=start)
    case.event(case.op_id, "finish", version=first, time=end, quantity=3)
    case.batch("B2")
    case.operation("B2")
    case.conn.commit()
    if replanned:
        adopt_selected(case, "old-events-replanned-0001", "B1", "B2")
    make_external(case, case.op_id)
    # 预检与守卫同口径：改过计划后要按记录核对，整次排产都拦；否则只有选上这批才拦。
    for batches, blocked in ((("B2",), replanned), (("B1", "B2"), True)):
        checked, _ = PreflightService(case.conn).evaluate(case.settings(*batches))
        found = [row for row in checked["blockers"] if row["code"] == "external_actual_resource_conflict"]
        assert bool(found) is blocked
        if found:
            assert "历史现场记录" in found[0]["message"] and "维护人员" in found[0]["message"]
            assert ("只排其他批次也一样" in found[0]["message"]) is replanned
            with pytest.raises(AppError):
                compute_candidate_run(case.conn, case.settings(*batches), case.projections(*batches))
        else:
            accepted = case.accept(key="old-events-other-batch-0001", settings=case.settings(*batches))
            assert WorkbenchRunWorker(case.conn).execute(accepted["run_ref"])["state"] == "complete"


def test_held_arrangement_before_a_late_actual_finish_is_named_before_the_run(candidate_case):
    """前道晚完工：后道按不重排时段保留的原安排早于前道实际完工，排产计算会整次拦下。
    排产检查事先指出是哪道、给出路（时段改短或不设）；就算绕过检查，排产记录里也说不重排时段，不说冻结窗口。"""
    from core.services.workbench.run import preflight as preflight_module

    case = candidate_case
    version, second = ordinary_route(case)
    case.operation(seq=3)  # 时段外还有要排的工序，排产不会因"全都保留"停下
    case.conn.commit()
    plan = {row["op_id"]: row for row in case.conn.execute("SELECT op_id,start_time FROM Schedule WHERE version=?", (version,))}
    start = datetime.fromisoformat(plan[second]["start_time"])
    finish = (start + timedelta(minutes=30)).isoformat()
    case.command("create", case.task(version, case.op_id), values(case, plan[case.op_id]["start_time"].replace(" ", "T"), finish))
    window = {"start": start.strftime("%Y-%m-%dT%H:%M"), "end": (start + timedelta(minutes=10)).strftime("%Y-%m-%dT%H:%M")}
    settings = case.settings(hold_window=window)
    checked, _ = PreflightService(case.conn).evaluate(settings)
    blocker = next(row for row in checked["blockers"] if row["code"] == "locked_predecessor_finish_conflict")
    assert blocker["operation_ref"] == next(row["operation_ref"] for row in checked["tasks"] if row["sequence"] == 2)
    assert "第 1 道" in blocker["message"] and finish.replace("T", " ") in blocker["message"] and "改短或不设" in blocker["message"]
    original = preflight_module.held_arrangement_reasons
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(preflight_module, "held_arrangement_reasons", lambda *args: (
            [row for row in original(*args)[0] if row["code"] != "locked_predecessor_finish_conflict"], [], {}))
        accepted = case.accept(key="late-finish-held-run-0001", settings=settings)
    with pytest.raises(Exception):
        WorkbenchRunWorker(case.conn).execute(accepted["run_ref"])
    error = json.loads(case.conn.execute("SELECT result_json FROM WorkbenchRunReceipts WHERE run_ref=?",
                                         (accepted["run_ref"],)).fetchone()[0])["error"]
    assert "已完工前道的实际完工" in error["message"] and "冻结" not in error["message"]
    cleared, _ = PreflightService(case.conn).evaluate(case.settings(hold_window=None))
    assert "locked_predecessor_finish_conflict" not in {row["code"] for row in cleared["blockers"]}
