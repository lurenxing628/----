"""Field route evidence against a real, isolated database and AJ's real ledger."""

from io import BytesIO

from flask import Blueprint
from openpyxl import load_workbook

from data.repositories.operator_machine_repo import OperatorMachineRepository
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
    book.worksheets[0].cell(2, 8, 'Lathe')
    output = BytesIO()
    book.save(output)
    book.close()
    checked = success(api.upload(output.getvalue(), reading))['data']
    assert not checked['can_confirm'] and checked['summary']['rejected'] == 1
    assert all_rows(api.case.conn) == before


def test_supplement_keeps_known_facts_through_correction(ledger_case):
    case = ledger_case
    api = FieldAPI(case)
    reports = Blueprint("report_hours", __name__)
    register_report_routes(reports)
    api.app.register_blueprint(reports)
    task = api.task()
    api.create(case.values(10, effective_processing_hours=None, actual_operator_ref=None), task)
    case.conn.execute("INSERT INTO Machines(machine_id,name,op_type_id) VALUES ('M2','New planned machine','T1')")
    case.plan(2, [case.op_id])
    case.conn.execute("UPDATE Schedule SET machine_id='M2' WHERE version=2")
    case.conn.commit()
    case.conn.execute("INSERT INTO OpTypes(op_type_id,name) VALUES ('T2','New craft')")
    case.conn.execute("UPDATE Machines SET op_type_id='T2' WHERE machine_id='M1'")
    OperatorMachineRepository(case.conn).remove("O1", "M1")
    case.conn.commit()
    task = api.task()
    assert task["planned_machine_ref"] == case.ref("machine", "M2")
    assert len(api.read(resource_type="machine", resource_ref=case.ref("machine", "M1"))["data"]["tasks"]) == 1
    assert len(api.read(query="Lathe")["data"]["tasks"]) == 1
    summary = api.read()["data"]["summary"]
    assert summary["effective_processing_hours"] is None and summary["unknown_hour_reports"] == 1
    record = task["execution"]["reports"][0]
    before = all_rows(case.conn)
    response = api.client.post(BASE + "/reports/" + record["report_ref"] + "/supplement", json=api.body(
        record["write_context"], {"original_revision_ref": record["revision_ref"], "reason": "不能用补齐覆盖原开工时间",
                                  "actual_start": "2026-09-09T09:00:00", "effective_processing_hours": 0.5}))
    assert response.status_code == 409 and all_rows(case.conn) == before
    success(api.client.post(BASE + "/reports/" + record["report_ref"] + "/supplement", json=api.body(
        record["write_context"], {"original_revision_ref": record["revision_ref"], "reason": "只补原记录缺少的工时",
                                  "effective_processing_hours": 1.5})))
    summary = api.read()["data"]["summary"]
    assert summary["effective_processing_hours"] == 1.5 and summary["unknown_hour_reports"] == 0
    report = success(api.client.get("/api/workbench/v1/analytics", query_string={"topic": "records"}))["data"]
    assert report["summary"]["production_reports"] == 1 and "records" not in report["summary"]
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
    # Maintaining hours/remark on an earlier plan's report preserves historical machine/operator actuals.
    with case.ledger.read_snapshot() as ledger_scope:
        original = case.ledger.load(ledger_scope, [record["operation_ref"]])["reports"][record["operation_ref"]][record["report_ref"]][-1]
    damaged = dict(original, revision_ref=new_ref(), sequence=3, previous_revision_ref=original["revision_ref"],
                   action="correct", reason="old accepted correction", values=dict(original["values"],
                   effective_processing_hours=0.5))
    request_key = case.conn.execute("SELECT request_key FROM WorkbenchProductionReportRevisions WHERE revision_ref=?",
                                   (original["revision_ref"],)).fetchone()[0]
    case.conn.execute("BEGIN")
    WorkbenchExecutionReportRepository(case.conn).append(damaged, request_key=request_key)
    case.conn.commit()
    assert api.read()["data"]["summary"]["effective_processing_hours"] == 0.5
    record = api.task()["execution"]["reports"][0]
    success(api.client.post(BASE + "/reports/" + record["report_ref"] + "/correct", json=api.body(
        record["write_context"], {"original_revision_ref": record["revision_ref"], "reason": "恢复核对后的有效工时",
                                "effective_processing_hours": 1.5})))
    execution = api.task()["execution"]
    assert execution["known_completed_quantity"] == 10 and execution["unknown_record_count"] == 0
    assert execution["reports"][0]["actual_start"] == "2026-09-09T08:00:00"
    assert api.read()["data"]["summary"]["effective_processing_hours"] == 1.5


def test_file_confirmation_retains_source_after_read_expiry_and_rechecks_write_expiry(field_api, monkeypatch):
    from datetime import datetime

    from core.services.workbench.commands import WorkbenchCommandService
    from core.services.workbench.execution.production_report import WorkbenchProductionReportService
    from web import public_token_registry
    from web.routes.workbench.execution_files import PREVIEW_NAMESPACE
    from web.routes.workbench.read_context import _SCOPE

    api = field_api
    api.create()
    reading = api.read()
    exported = api.client.get(BASE + '/files/export', query_string={**reading['data']['scope'],
        'snapshot_ref': reading['meta']['snapshot_ref']})
    assert exported.status_code == 200
    preview = success(api.upload(exported.data, reading))
    assert preview['data']['can_confirm']
    with api.app.app_context():
        public_token_registry._registry()[_SCOPE]['tokens'][reading['meta']['snapshot_ref']]['expires_at'] = 0
    confirmed = success(api.client.post(BASE + '/files/confirm', json=api.confirm_body(preview)))
    assert confirmed['result'] == 'unchanged'

    preview = success(api.upload(exported.data))
    ref, before = preview['data']['preview_ref'], all_rows(api.case.conn)
    execute = WorkbenchCommandService.execute

    def expired_after_prefetch(service, **kwargs):
        # The file has been prepared; the write-lock guard must still reject expiry.
        public_token_registry._registry()[PREVIEW_NAMESPACE]['tokens'][ref]['expires_at'] = 0
        return execute(service, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(WorkbenchCommandService, 'execute', expired_after_prefetch)
        response = api.client.post(BASE + '/files/confirm', json=api.confirm_body(preview))
    assert response.status_code == 409 and response.get_json()['error']['code'] == 'stale_write'
    assert all_rows(api.case.conn) == before

    orig_init = WorkbenchProductionReportService.__init__
    current_clock = datetime(2026, 9, 8, 12)

    def init_with_clock(self, conn, *, clock=None, **kwargs):
        orig_init(self, conn, clock=clock or (lambda: current_clock), **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(WorkbenchProductionReportService, '__init__', init_with_clock)
        rejected_preview = success(api.upload(exported.data))
        assert not rejected_preview['data']['can_confirm']
        current_clock = datetime(2026, 9, 10, 12)
        response = api.client.post(BASE + '/files/confirm', json=api.confirm_body(rejected_preview))
        assert response.status_code == 409 and response.get_json()['error']['code'] == 'stale_write'

        valid_preview = success(api.upload(exported.data))
        assert valid_preview['data']['can_confirm']
        current_clock = datetime(2026, 9, 8, 12)
        rollback_response = api.client.post(BASE + '/files/confirm', json=api.confirm_body(valid_preview))
        assert rollback_response.status_code == 409 and rollback_response.get_json()['error']['code'] == 'stale_write'
    assert all_rows(api.case.conn) == before


def test_field_workspace_pagination_rejects_oversized_non_ascii_and_leading_zero_inputs(field_api):
    import pytest

    from core.models.workbench_command import WorkbenchCommandRejected
    from core.services.workbench.execution.field_workspace_scope import page_input

    for bad_query in (
        {'page': '0'},
        {'page': '01'},
        {'page': '１'},
        {'page': '-1'},
        {'page': '100001'},
        {'page': '9' * 6000},
        {'size': '0'},
        {'size': '020'},
        {'size': '２０'},
        {'size': '101'},
        {'size': '9' * 6000},
    ):
        response = field_api.client.get(BASE + '/tasks', query_string=bad_query)
        assert response.status_code == 400
        assert response.get_json()['error']['code'] == 'invalid_input'

    for bad_raw in ({'page': 10 ** 5000}, {'page': True}, {'size': False}, {'size': 1.0}):
        with pytest.raises(WorkbenchCommandRejected) as exc_info:
            page_input(bad_raw)
        assert exc_info.value.status == 400 and exc_info.value.code == 'invalid_input'

    assert page_input({'page': '100000', 'size': '100'}) == (100000, 100)
    first_wide = field_api.read(page=1, size=100)['data']
    assert first_wide['page']['number'] == 1 and first_wide['page']['size'] == 100


def test_external_operation_template_preserves_incomplete_row_and_allocates_new_row_when_four_fields_complete(field_api):
    from tests.workbench.execution_ledger_support import publish_official_plan

    api = field_api
    conn = api.case.conn
    conn.execute("INSERT INTO OpTypes(op_type_id,name,category) VALUES ('T_EXT','热处理','external')")
    conn.execute("INSERT INTO Suppliers(supplier_id,name) VALUES ('S1','外协一厂')")
    ext_op_id = conn.execute(
        "INSERT INTO BatchOperations(op_code,batch_id,seq,op_type_id,op_type_name,source,supplier_id,ext_days) "
        "VALUES ('OP_EXT','B1',2,'T_EXT','热处理','external','S1',2)"
    ).lastrowid
    publish_official_plan(
        conn,
        2,
        [{"op_id": ext_op_id, "machine_id": None, "operator_id": None,
          "start_time": "2026-09-02T08:00:00", "end_time": "2026-09-04T08:00:00"}],
    )
    conn.commit()

    # ② 若已有外协报工缺必填项（如 actual_end 为空），/files/template 仍带出原报工单号供补齐。
    ext_task = api.task()
    assert ext_task['source'] == 'external'
    api.create(
        {'actual_start': '2026-09-02T08:00:00', 'completed_quantity': 4, 'effective_processing_hours': 8},
        ext_task,
    )
    first_report = api.task()['execution']['reports'][0]
    first_report_no = first_report['report_no']
    assert api.task()['execution']['records_complete'] is False

    reading = api.read()
    template_incomplete = api.client.get(
        BASE + '/files/template',
        query_string={**reading['data']['scope'], 'snapshot_ref': reading['meta']['snapshot_ref']},
    )
    assert template_incomplete.status_code == 200
    book = load_workbook(BytesIO(template_incomplete.data))
    sheet = book.worksheets[0]
    assert sheet.max_row == 2
    assert sheet.cell(2, 1).value == first_report_no
    assert sheet.cell(2, 4).value == '4'
    assert sheet.cell(2, 6).value is None
    sheet.cell(2, 6, '2026-09-03 08:00:00')
    supplement_buf = BytesIO()
    book.save(supplement_buf)
    book.close()

    supplement_preview = success(api.upload(supplement_buf.getvalue(), reading))
    assert supplement_preview['data']['can_confirm'] is True
    assert supplement_preview['data']['rows'][0]['result'] == 'supplement'
    confirmed_supplement = success(api.client.post(BASE + '/files/confirm', json=api.confirm_body(supplement_preview)))
    assert confirmed_supplement['result'] == 'committed'

    # ① 外协工序目标数量 10、已有一条四项齐全的完整报工（数量 4）时，下载 /files/template 生成全新 BG-T-... 单号空白行，
    # 填写本次数量 6 后经 /files/preview + /files/confirm 成功新增第 2 条外协报工且不触发 supplement 覆盖冲突。
    after_first = api.task()['execution']
    assert after_first['target_quantity'] == 10 and after_first['known_completed_quantity'] == 4
    assert after_first['records_complete'] is True and after_first['execution_state'] == 'partial'

    reading = api.read()
    template_complete = api.client.get(
        BASE + '/files/template',
        query_string={**reading['data']['scope'], 'snapshot_ref': reading['meta']['snapshot_ref']},
    )
    assert template_complete.status_code == 200
    book2 = load_workbook(BytesIO(template_complete.data))
    sheet2 = book2.worksheets[0]
    assert sheet2.max_row == 2
    second_report_no = sheet2.cell(2, 1).value
    assert isinstance(second_report_no, str) and second_report_no.startswith('BG-T-')
    assert second_report_no != first_report_no
    assert [sheet2.cell(2, col).value for col in range(4, 10)] == [None] * 6

    sheet2.cell(2, 4, 6)
    sheet2.cell(2, 5, '2026-09-03 09:00:00')
    sheet2.cell(2, 6, '2026-09-04 08:00:00')
    sheet2.cell(2, 7, 10)
    second_buf = BytesIO()
    book2.save(second_buf)
    book2.close()

    second_preview = success(api.upload(second_buf.getvalue(), reading))
    assert second_preview['data']['can_confirm'] is True
    assert second_preview['data']['rows'][0]['result'] == 'create'
    assert second_preview['data']['summary'] == {'total': 1, 'blank': 0, 'rejected': 0, 'changed': 1, 'unchanged': 0}
    confirmed_second = success(api.client.post(BASE + '/files/confirm', json=api.confirm_body(second_preview)))
    assert confirmed_second['result'] == 'committed'

    final_exec = api.task()['execution']
    assert final_exec['execution_state'] == 'complete'
    assert final_exec['known_completed_quantity'] == 10 and final_exec['remaining_quantity'] == 0
    assert final_exec['records_complete'] is True and final_exec['data_quality'] == 'complete'
    assert [(r['report_no'], r['completed_quantity']) for r in final_exec['reports']] == [
        (first_report_no, 4),
        (second_report_no, 6),
    ]


def test_void_preview_does_not_issue_write_tokens_for_downstream_operations(ledger_case):
    from web import public_token_registry
    from web.routes.workbench.write_context import _SCOPE as WRITE_SCOPE

    case = ledger_case
    downstream = case.op("OP2", seq=2)
    case.plan(2, [case.op_id, downstream])
    api = FieldAPI(case)
    first_task = next(row for row in api.read()["data"]["tasks"] if row["sequence"] == 1)
    api.create(case.values(4), first_task)
    report = next(row for row in api.read()["data"]["tasks"] if row["sequence"] == 1)["execution"]["reports"][0]

    with api.app.app_context():
        before_tokens = set(public_token_registry._registry().get(WRITE_SCOPE, {}).get("tokens", ()))

    preview = success(
        api.client.post(
            BASE + "/reports/" + report["report_ref"] + "/void-preview",
            json={
                "input": {
                    "original_revision_ref": report["revision_ref"],
                    "reason": "核对下游影响",
                    "declared_operator": "Foreman",
                }
            },
        )
    )["data"]

    with api.app.app_context():
        after_tokens = set(public_token_registry._registry()[WRITE_SCOPE]["tokens"])

    assert after_tokens - before_tokens == {preview["write_context"]["write_token"]}
