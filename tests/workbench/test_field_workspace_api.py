"""Field route evidence against a real, isolated database and AJ's real ledger."""

from io import BytesIO

from flask import Blueprint
from openpyxl import load_workbook

from core.services.personnel.operator_machine_service import OperatorMachineService
from data.repositories.workbench_execution_report_repo import WorkbenchExecutionReportRepository, new_ref
from tests.workbench.execution_ledger_support import all_rows
from tests.workbench.field_workspace_support import BASE, FieldAPI, _ledger_fixture, success  # noqa: F401
from tests.workbench.field_workspace_support import field_api as _field_api  # noqa: F401
from web.routes.workbench.reports import register_report_routes


def test_unreported_null_zero_partial_finish_and_readonly(field_api):
    api = field_api
    before = all_rows(api.case.conn)
    task = api.task()
    assert task['execution']['execution_state'] == 'unreported'
    assert task['execution']['reports'] == []
    assert all_rows(api.case.conn) == before
    assert not any(sql.lstrip().split()[0].upper() in ('INSERT', 'UPDATE', 'DELETE', 'CREATE') for sql in api.app.ak_statements)
    api.create({'actual_start': '2026-09-01T08:00:00'})
    p = api.task()['execution']
    assert p['execution_state'] == 'started' and p['remaining_quantity'] is None
    record = p['reports'][0]
    body = api.body(record['write_context'], {'original_revision_ref': record['revision_ref'], 'reason': '核对现场记录',
        **api.case.values(0, actual_start='2026-09-01T08:00:00', actual_end='2026-09-01T10:00:00', effective_processing_hours=0)})
    success(api.client.post(BASE + '/reports/' + record['report_ref'] + '/supplement', json=body))
    assert api.task()['execution']['reports'][0]['completed_quantity'] == 0
    api.create(api.case.values(4, actual_start='2026-09-01T11:00:00', actual_end='2026-09-01T13:00:00'))
    assert api.task()['execution']['execution_state'] == 'partial'
    api.create(api.case.values(6, actual_start='2026-09-01T14:00:00', actual_end='2026-09-01T16:00:00'))
    p = api.task()['execution']
    assert p['execution_state'] == 'complete' and p['known_completed_quantity'] == 10 and p['remaining_quantity'] == 0
    assert api.case.conn.execute('SELECT count(*) FROM OperationExecutionEvents').fetchone()[0] == 0
    api.case.conn.execute("INSERT INTO Machines(machine_id,name,op_type_id) VALUES ('M2','Lathe','T1'),('M3','M1','T1')")
    api.case.conn.execute("INSERT INTO Operators(operator_id,name) VALUES ('O2','Operator'),('O3','O1')")
    api.case.conn.commit()
    reading = api.read()
    before = all_rows(api.case.conn)
    exported = api.client.get(BASE + '/files/export', query_string={**reading['data']['scope'],
        'snapshot_ref': reading['meta']['snapshot_ref']})
    assert exported.status_code == 200
    book = load_workbook(BytesIO(exported.data))
    assert [(row[7].value, row[8].value) for row in list(book.worksheets[0])[1:]] == [('M1', 'O1')] * 3
    checked = success(api.upload(exported.data, reading))['data']
    assert checked['can_confirm'] and checked['summary']['unchanged'] == 3 and checked['summary']['rejected'] == 0
    assert all_rows(api.case.conn) == before
    book.worksheets[0].cell(2, 8).value = 'Lathe'
    output = BytesIO()
    book.save(output)
    book.close()
    checked = success(api.upload(output.getvalue(), reading))['data']
    assert not checked['can_confirm'] and checked['summary']['rejected'] == 1
    assert all_rows(api.case.conn) == before


def test_missing_schema_is_unavailable_and_never_installed(request):
    case = request.getfixturevalue('ledger_case')
    api = FieldAPI(case)
    before = all_rows(case.conn)
    response = api.client.get(BASE + '/tasks')
    assert response.status_code == 409 and response.get_json()['error']['code'] == 'execution_ledger_unavailable'
    assert all_rows(case.conn) == before


def test_legacy_supplement_keeps_known_facts_through_correction(ledger_case):
    case = ledger_case
    case.event(case.op_id, "start", time="2026-09-09  08:00")
    case.event(case.op_id, "finish", quantity=10, time="2026-09-09  10:00")
    case.conn.execute("UPDATE OperationExecutionEvents SET actual_operator_id=NULL")
    case.conn.commit()
    case.conn.execute("INSERT INTO Machines(machine_id,name,op_type_id) VALUES ('M2','New planned machine','T1')")
    case.plan(2, [case.op_id])
    case.conn.execute("UPDATE Schedule SET machine_id='M2' WHERE version=2")
    case.conn.commit()
    case.install()
    case.conn.execute("INSERT INTO OpTypes(op_type_id,name) VALUES ('T2','New craft')")
    case.conn.execute("UPDATE Machines SET op_type_id='T2' WHERE machine_id='M1'")
    case.conn.commit()
    OperatorMachineService(case.conn).remove_link("O1", "M1")
    api = FieldAPI(case)
    reports = Blueprint("legacy_report_hours", __name__)
    register_report_routes(reports)
    api.app.register_blueprint(reports)
    task = api.task()
    assert task["planned_machine_ref"] == case.ref("machine", "M2")
    assert len(api.read(resource_type="machine", resource_ref=case.ref("machine", "M1"))["data"]["tasks"]) == 1
    assert len(api.read(query="Lathe")["data"]["tasks"]) == 1
    summary = api.read()["data"]["summary"]
    assert summary["effective_processing_hours"] is None and summary["unknown_hour_reports"] == 2
    legacy = task["execution"]["legacy_facts"][-1]
    source = all_rows(case.conn)["WorkbenchExecutionLegacyFacts"]
    payload = {"legacy_fact_ref": legacy["legacy_fact_ref"], "reason": "只补原记录缺少的工时",
               "effective_processing_hours": 1.5}
    before = all_rows(case.conn)
    response = api.client.post(BASE + "/tasks/" + task["task_ref"] + "/reports", json=api.body(
        task["execution"]["write_context"], {**payload, "completed_quantity": None}))
    assert response.status_code == 409 and all_rows(case.conn) == before
    response = api.client.post(BASE + "/tasks/" + task["task_ref"] + "/reports", json=api.body(
        task["execution"]["write_context"], {**payload, "actual_start": "2026-09-09T09:00:00", "effective_processing_hours": 0.5}))
    assert response.status_code == 409 and "不能覆盖原开工时间" in response.get_json()["error"]["message"]
    assert all_rows(case.conn) == before
    api.create(payload, task)
    summary = api.read()["data"]["summary"]
    assert summary["effective_processing_hours"] == 1.5 and summary["unknown_hour_reports"] == 0
    report = success(api.client.get("/api/workbench/v1/analytics", query_string={"topic": "records"}))["data"]
    assert report["summary"]["events"] == 2 and report["summary"]["production_reports"] == 1
    assert report["summary"]["effective_processing_hours"] == 1.5 and report["summary"]["unknown_hour_events"] == 0
    assert report["resources"]["machines"][0]["effective_processing_hours"] == 1.5
    assert report["resources"]["people"][0]["effective_processing_hours"] == 1.5
    execution = api.task()["execution"]
    record = execution["reports"][0]
    assert (record["actual_start"], record["actual_end"], record["completed_quantity"]) == (
        "2026-09-09T08:00:00", "2026-09-09T10:00:00", 10)
    assert record["actual_machine_ref"] == case.ref("machine", "M1") and record["actual_operator_ref"] is None
    assert execution["known_completed_quantity"] == 10 and execution["unknown_record_count"] == 0
    assert execution["data_quality"] == "incomplete"
    before = all_rows(case.conn)
    response = api.client.post(BASE + "/reports/" + record["report_ref"] + "/correct", json=api.body(
        record["write_context"], {"original_revision_ref": record["revision_ref"], "reason": "未知人员仍需当前资格",
                                "actual_operator_ref": case.ref("operator", "O1")}))
    assert response.status_code == 409 and all_rows(case.conn) == before
    # Repair an older release's admitted correction without erasing its history.
    original = case.ledger.load([record["operation_ref"]])["reports"][record["operation_ref"]][record["report_ref"]][-1]
    damaged = dict(original, revision_ref=new_ref(), sequence=2, previous_revision_ref=original["revision_ref"],
                   action="correct", reason="old accepted correction", values=dict(original["values"],
                   actual_start="2026-09-09T09:00:00", completed_quantity=None, effective_processing_hours=0.5))
    request_key = case.conn.execute("SELECT request_key FROM WorkbenchProductionReportRevisions WHERE revision_ref=?",
                                   (original["revision_ref"],)).fetchone()[0]
    case.conn.execute("BEGIN")
    WorkbenchExecutionReportRepository(case.conn).append(damaged, request_key=request_key)
    case.conn.commit()
    assert case.ledger.get_task(task["task_ref"]).known_completed_quantity == 10
    record = api.task()["execution"]["reports"][0]
    success(api.client.post(BASE + "/reports/" + record["report_ref"] + "/correct", json=api.body(
        record["write_context"], {"original_revision_ref": record["revision_ref"], "reason": "恢复已确认的原实际",
                                "actual_start": "2026-09-09T08:00:00", "completed_quantity": 10})))
    execution = api.task()["execution"]
    assert execution["known_completed_quantity"] == 10 and execution["unknown_record_count"] == 0
    assert execution["reports"][0]["actual_start"] == "2026-09-09T08:00:00"
    assert all_rows(case.conn)["WorkbenchExecutionLegacyFacts"] == source
