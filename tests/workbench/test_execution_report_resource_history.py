"""Historical actuals remain maintainable after genuine qualification changes."""

from uuid import uuid4

import pytest

from core.models.workbench_command import WorkbenchCommandRejected
from core.services.personnel.operator_machine_service import OperatorMachineService
from tests.workbench.execution_ledger_support import END, all_rows
from tests.workbench.execution_ledger_support import ledger_case as ledger_fixture
from tests.workbench.field_workspace_support import BASE, FieldAPI, success
from tests.workbench.resource_entity_support import run_resource


def revoke_qualification(case, kind="skills"):
    if kind == "machine":
        result = run_resource(case.conn, "machine", "update", {"relationships": {"op_type_refs": []}}, code="M1")
    elif kind == "skills":
        result = run_resource(case.conn, "operator", "update", {"relationships": {"skill_refs": []}}, code="O1")
    else:
        # This is the normal domain command used by the permission-maintenance flow.
        OperatorMachineService(case.conn).remove_link("O1", "M1")
        result = {"result": "committed"}
    assert result["result"] == "committed" and not case.conn.in_transaction


def revision(case, report_ref, **patch):
    return {"original_revision_ref": case.ledger.get_report(report_ref).revision_ref,
            "reason": "现场复核原始记录", **patch}


def correct_api(api, report_ref, action="correct", **patch):
    record = next(row for row in api.task()["execution"]["reports"] if row["report_ref"] == report_ref)
    return success(api.client.post(BASE + "/reports/" + report_ref + "/" + action,
        json=api.body(record["write_context"], revision(api.case, report_ref, **patch))))


@pytest.mark.parametrize("kind", ("machine", "skills", "permissions"))
def test_original_actuals_allow_api_maintenance_and_same_value_excel_roundtrip(ledger_case, kind):
    case = ledger_case
    case.install()
    api = FieldAPI(case)
    row = api.create(case.values(3, effective_processing_hours=None))["data"]["rows"][0]
    original = case.ledger.get_report(row["report_ref"])
    revoke_qualification(case, kind)
    assert correct_api(api, row["report_ref"], remark="核对完成")["result"] == "committed"
    assert correct_api(api, row["report_ref"], completed_quantity=4)["result"] == "committed"
    same = case.ledger.get_report(row["report_ref"])
    assert correct_api(api, row["report_ref"], completed_quantity=4)["result"] == "unchanged"
    assert case.ledger.get_report(row["report_ref"]).revision_ref == same.revision_ref
    assert correct_api(api, row["report_ref"], action="supplement", effective_processing_hours=1.25)["result"] == "committed"
    maintained = case.ledger.get_report(row["report_ref"])
    assert maintained.actual_start == original.actual_start and maintained.actual_end == original.actual_end
    assert maintained.actual_machine_ref == original.actual_machine_ref
    assert maintained.actual_operator_ref == original.actual_operator_ref
    assert maintained.completed_quantity == 4 and maintained.effective_processing_hours == 1.25
    assert len(maintained.correction_history) == 4
    reading = api.read()
    exported = api.client.get(BASE + "/files/export", query_string={
        **reading["data"]["scope"], "snapshot_ref": reading["meta"]["snapshot_ref"]})
    assert exported.status_code == 200
    before = all_rows(case.conn)
    preview = success(api.upload(exported.data))
    assert preview["data"]["can_confirm"] and preview["data"]["summary"]["unchanged"] == 1
    assert all_rows(case.conn) == before
    result = success(api.client.post(BASE + "/files/confirm", json=api.confirm_body(preview)))
    assert result["result"] == "unchanged"
    assert all_rows(case.conn)["WorkbenchProductionReportRevisions"] == before["WorkbenchProductionReportRevisions"]


@pytest.mark.parametrize("field", ("actual_start", "actual_end", "actual_machine_ref", "actual_operator_ref"))
def test_changed_actual_identity_or_interval_requires_current_qualification(ledger_case, field):
    case = ledger_case
    case.install()
    case.conn.execute("INSERT INTO Machines(machine_id,name,op_type_id) VALUES ('M2','Other lathe','T1')")
    case.conn.execute("INSERT INTO Operators(operator_id,name) VALUES ('O2','Other operator')")
    case.conn.commit()
    row = case.command("create", case.task(1, case.op_id), case.values(3))["data"]["rows"][0]
    revoke_qualification(case)
    changed = {"actual_start": "2026-09-09T07:59:00", "actual_end": "2026-09-09T10:01:00",
               "actual_machine_ref": case.ref("machine", "M2"), "actual_operator_ref": case.ref("operator", "O2")}
    before = all_rows(case.conn)
    with pytest.raises(WorkbenchCommandRejected) as error:
        case.command("correct", row["report_ref"], revision(case, row["report_ref"], **{field: changed[field]}))
    assert error.value.code == "constraint_conflict"
    assert all_rows(case.conn) == before


@pytest.mark.parametrize("kind,code", (("machine", "M2"), ("operator", "O2")))
def test_retired_actual_identity_cannot_be_rebound_to_recreated_business_code(ledger_case, kind, code):
    case = ledger_case
    case.install()
    run_resource(case.conn, "machine", "create", {"business_code": "M2", "label": "Actual lathe",
        "relationships": {"op_type_refs": [case.ref("op_type", "T1")]}})
    run_resource(case.conn, "operator", "create", {"business_code": "O2", "label": "Actual operator"})
    OperatorMachineService(case.conn).add_link("O2", "M2")
    actual_machine, actual_operator = case.ref("machine", "M2"), case.ref("operator", "O2")
    row = case.command("create", case.task(1, case.op_id), case.values(3,
        actual_machine_ref=actual_machine, actual_operator_ref=actual_operator))["data"]["rows"][0]
    retired_ref = case.ref(kind, code)
    run_resource(case.conn, kind, "delete", {}, code=code)
    run_resource(case.conn, kind, "create", {"business_code": code, "label": "New identity"})
    assert case.ref(kind, code) != retired_ref
    before = all_rows(case.conn)
    with pytest.raises(WorkbenchCommandRejected) as error:
        case.command("correct", row["report_ref"], revision(case, row["report_ref"], remark="不能把原实际改认成新身份"))
    assert error.value.code == "constraint_conflict"
    assert all_rows(case.conn) == before


@pytest.mark.parametrize("historical_first", (True, False))
def test_historical_row_never_qualifies_new_row_in_same_batch_and_rejection_rolls_back(ledger_case, historical_first):
    case = ledger_case
    case.install()
    task = case.task(1, case.op_id)
    row = case.command("create", task, case.values(3))["data"]["rows"][0]
    revoke_qualification(case)
    historical = {"action": "correct", "ref": row["report_ref"],
                  "payload": revision(case, row["report_ref"], remark="保留原设备人员和实际起止")}
    new = {"action": "create", "ref": task, "payload": case.values(1, source="excel", report_no="NEW-ACTUAL")}
    items = [historical, new] if historical_first else [new, historical]
    before = all_rows(case.conn)
    with pytest.raises(WorkbenchCommandRejected) as error:
        case.writer.execute_batch(items, context_ref=case.plan_ref(1), request_key="report-mixed-" + uuid4().hex,
                                  validate_context=lambda *_: None)
    assert error.value.code == "constraint_conflict" and error.value.row_number == (2 if historical_first else 1)
    assert all_rows(case.conn) == before


def test_preserved_actuals_still_enforce_quantity_and_adopted_plan_constraints(ledger_case):
    case = ledger_case
    case.install()
    row = case.command("create", case.task(1, case.op_id), case.values(3))["data"]["rows"][0]
    revoke_qualification(case)
    before = all_rows(case.conn)
    with pytest.raises(WorkbenchCommandRejected):
        case.command("correct", row["report_ref"], revision(case, row["report_ref"], completed_quantity=11))
    assert all_rows(case.conn) == before
    case.plan(2, [case.op_id])
    before = all_rows(case.conn)
    with pytest.raises(WorkbenchCommandRejected) as error:
        case.command("correct", row["report_ref"], revision(case, row["report_ref"], completed_quantity=4))
    assert "adopted_execution_basis_changed" in {item["code"] for item in error.value.conflicts}
    assert all_rows(case.conn) == before
    assert case.command("correct", row["report_ref"], revision(case, row["report_ref"], remark="核对原事实"))["result"] == "committed"


def test_legacy_first_supplement_has_no_existing_report_qualification_basis(ledger_case):
    case = ledger_case
    case.event(case.op_id, "start")
    case.event(case.op_id, "finish", quantity=10)
    case.install()
    task = case.task(1, case.op_id)
    legacy = case.ledger.get_task(task).legacy_facts[-1]["legacy_fact_ref"]
    revoke_qualification(case)
    before = all_rows(case.conn)
    with pytest.raises(WorkbenchCommandRejected) as error:
        case.command("create", task, case.values(10, legacy_fact_ref=legacy, reason="首次核对旧完工"))
    assert error.value.code == "constraint_conflict"
    assert all_rows(case.conn) == before


def test_preserved_actuals_still_protect_downstream_completion(ledger_case):
    case = ledger_case
    successor = case.op("NEXT", seq=2)
    case.plan(2, [case.op_id, successor], start=END, end="2026-09-09T12:00:00")
    case.install()
    row = case.command("create", case.task(2, case.op_id), case.values(10))["data"]["rows"][0]
    case.command("create", case.task(2, successor), {"actual_start": END, "completed_quantity": 0})
    revoke_qualification(case)
    before = all_rows(case.conn)
    with pytest.raises(WorkbenchCommandRejected) as error:
        case.command("correct", row["report_ref"], revision(case, row["report_ref"], completed_quantity=5))
    assert "downstream_requires_completion" in {item["code"] for item in error.value.conflicts}
    assert all_rows(case.conn) == before
