"""Actual HTTP writes and final-state batches over current-schema adopted routes."""

from datetime import datetime

import pytest

from core.infrastructure.transaction import TransactionManager
from core.models.workbench_command import WorkbenchCommandRejected
from core.services.scheduler.template_lineage import TemplateLineageWriter
from core.services.workbench.run.worker import WorkbenchRunWorker
from tests.workbench.field_workspace_support import BASE, FieldAPI, success
from tests.workbench.piece_adoption_support import split
from tests.workbench.run_candidate_adoption_support import INTENT, KEY, preview, service, snapshot
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


def test_merged_external_actuals_can_share_one_period(candidate_case):
    case = candidate_case
    case.conn.execute("UPDATE OpTypes SET category='both' WHERE op_type_id='T1'")
    case.conn.execute("INSERT INTO Suppliers(supplier_id,name,op_type_id) VALUES ('S1','供应商','T1')")
    case.conn.execute("INSERT INTO ExternalGroups(group_id,part_no,start_seq,end_seq,merge_mode,total_days,supplier_id) VALUES ('G','P1',2,3,'merged',1,'S1')")
    copied = []
    with TransactionManager(case.conn).transaction():
        for seq in (2, 3):
            cursor = case.conn.execute("INSERT INTO PartOperations(part_no,seq,op_type_id,op_type_name,source,supplier_id,ext_group_id,setup_hours,unit_hours) "
                                      "VALUES ('P1',?,'T1','Turning','external','S1','G',0,0)", (seq,))
            copied.append(TemplateLineageWriter(case.conn).copy_template("B1", cursor.lastrowid))
    case.conn.commit()
    version = adopt(case)
    report_plan(case, version, {case.op_id})
    api = FieldAPI(case)
    for operation in copied:
        payload = values(case, "2026-09-09T10:00:00", "2026-09-10T10:00:00")
        payload.update(actual_machine_ref=None, actual_operator_ref=None)
        response = create(api, version, operation, payload)
        assert response.status_code == 200, response.get_json()


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
def test_execution_resource_fix_does_not_relax_internal_or_discard_external_resources(candidate_case, external):
    from core.errors import AppError
    from core.services.scheduler.execution.execution_ledger_guard import ensure_ledger_execution_schedulable
    from tests.workbench.scheduler_execution_ledger_support import read_facts

    case = candidate_case
    if external:
        external_route(case)
    version = adopt(case)
    payload = case.values(3)
    if not external:
        payload.update(actual_machine_ref=None, actual_operator_ref=None)
    case.command("create", case.task(version, case.op_id), payload)
    before = snapshot(case.conn)
    facts = read_facts(case.conn, version)
    with pytest.raises(AppError) as caught:
        ensure_ledger_execution_schedulable(facts)
    expected = "execution_ledger_external_resource_conflict" if external else "execution_ledger_actual_resource_missing_or_multiple"
    assert expected in caught.value.details["data_gaps"]
    assert snapshot(case.conn) == before
