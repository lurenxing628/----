"""Current report cohort, detail, export binding and standalone XLSX contracts."""

from __future__ import annotations

from datetime import datetime
from io import BytesIO

import openpyxl
import pytest

from core.errors import ValidationError
from core.infrastructure.transaction import TransactionManager
from core.services.report.date_range_limits import ensure_report_date_range_within_limit
from core.services.report.exporters.xlsx import export_execution_review_xlsx
from tests.workbench.execution_ledger_support import LedgerCase, current_database
from tests.workbench.plan_catalog_support import update_schedule_rows
from web.runtime_host import install_wall_clock


class _ReviewLedgerCase(LedgerCase):
    op_id: int


@pytest.fixture(name="ledger_case")
def _ledger_fixture(tmp_path):
    conn = current_database(tmp_path / "plan-vs-actual-review.sqlite")
    with TransactionManager(conn).transaction():
        conn.execute("INSERT INTO OpTypes(op_type_id,name) VALUES ('T1','Turning')")
        conn.execute("INSERT INTO Machines(machine_id,name) VALUES ('M1','Lathe')")
        conn.execute("INSERT INTO MachineOpTypes(machine_id,op_type_id) VALUES ('M1','T1')")
        conn.execute("INSERT INTO Operators(operator_id,name) VALUES ('O1','Operator')")
        conn.execute("INSERT INTO OperatorMachine(operator_id,machine_id) VALUES ('O1','M1')")
        conn.execute("INSERT INTO Parts(part_no,part_name) VALUES ('P1','Part')")
        conn.execute("INSERT INTO Batches(batch_id,part_no,quantity) VALUES ('B1','P1',10)")
        case = _ReviewLedgerCase(conn)
        case.op_id = case.op()
    case.plan(1, [case.op_id])
    try:
        yield case
    finally:
        conn.close()

EXPECTED_HEADERS = [
    "批次",
    "工序",
    "计划开始",
    "实际开始",
    "开工偏差",
    "计划结束",
    "实际结束",
    "完工偏差",
    "计划资源",
    "实际资源",
    "现场反馈状态",
]


def test_workbench_report_bounds_finish_cohort_before_detail_admission(ledger_case, monkeypatch):
    from flask import Blueprint, Flask, g

    from core.models.workbench_command import WorkbenchCommandRejected
    from core.models.workbench_plan_scope import PlanReadScope
    from core.models.workbench_report import ReportScope
    from core.services.workbench.plan import queries as plan_queries
    from core.services.workbench.report import facts as report_facts
    from web.routes.workbench.reports import register_report_routes

    case = ledger_case
    case.conn.execute("INSERT INTO Batches(batch_id,part_no,quantity) VALUES ('B2','P1',10)")
    case.conn.execute("INSERT INTO Machines(machine_id,name) VALUES ('M3','Other batch lathe')")
    case.conn.execute("INSERT INTO MachineOpTypes(machine_id,op_type_id) VALUES ('M3','T1')")
    others = [case.op('CROSS-' + str(index), batch='B2', seq=index) for index in (1, 2)]
    case.plan(2, [case.op_id] + others, end='2026-09-10 00:00:00')
    update_schedule_rows(case.conn, 2, where="op_id <> ?", params=(case.op_id,), machine_id='M3')
    update_schedule_rows(case.conn, 2, where="op_id = ?", params=(case.op_id,), end_time='2026-09-09T23:59:59.123456')
    case.conn.commit()
    monkeypatch.setattr(plan_queries, 'MAX_WINDOW_OPERATIONS', 2)
    monkeypatch.setattr(report_facts, 'MAX_WINDOW_OPERATIONS', 2)
    app = Flask('bounded-finish-report')
    install_wall_clock(app, datetime.now)
    app.config.update(TESTING=True, SECRET_KEY='bounded-finish-test')
    bp = Blueprint('bounded_finish_report', __name__)
    register_report_routes(bp)
    app.register_blueprint(bp)

    @app.before_request
    def database():
        g.db = case.conn

    client, url = app.test_client(), '/api/workbench/v1/analytics'
    whole = client.get(url)
    assert whole.status_code == 413 and whole.get_json()['error']['code'] == 'query_too_large'
    dates = {'plan_finish_date_from': '2026-09-09', 'plan_finish_date_to': '2026-09-09'}
    before = case.conn.total_changes
    resource_map_calls, original_maps = [], report_facts.WorkbenchReportFacts._resource_maps

    def captured_resources(plan_context, rows):
        resource_map_calls.append(rows)
        return original_maps(plan_context, rows)

    with monkeypatch.context() as patch:
        patch.setattr(report_facts.WorkbenchReportFacts, '_resource_maps', staticmethod(captured_resources))
        first = client.get(url, query_string=dates)
    assert len(resource_map_calls) == 1
    assert first.status_code == 200, first.get_data(as_text=True)
    payload = first.get_json()
    assert payload['data']['summary']['operations'] == 1
    assert payload['data']['rows'][0]['planned_end'] == '2026-09-09T23:59:59.123456'
    export_scope = {**dates, 'snapshot_ref': payload['meta']['snapshot_ref'], 'format': 'csv'}
    exported = client.get(url + '/export', query_string=export_scope)
    assert exported.status_code == 200 and exported.headers['X-Workbench-Row-Count'] == '1'
    for kind in ('utilization', 'downtime'):
        catalog = client.get('/api/workbench/v1/reports/' + kind, query_string={
            'window_date_from': '2026-09-09', 'window_date_to': '2026-09-09'})
        assert catalog.status_code == 200, catalog.get_data(as_text=True)
        assert catalog.get_json()['data']['scope']['selection'] == 'schedule_window_overlap'
    batch = client.get(url, query_string={'batch_ref': case.ref('batch', 'B1')})
    assert batch.status_code == 200 and batch.get_json()['data']['summary']['operations'] == 1
    choices = batch.get_json()['data']['choices']
    assert {row['label'] for row in choices['batch']} == {'B1', 'B2'}
    assert {row['label'] for row in choices['machine']} == {'Lathe', 'Other batch lathe'}
    other_ref = next(row['ref'] for row in choices['batch'] if row['label'] == 'B2')
    switched = client.get(url, query_string={'batch_ref': other_ref})
    assert switched.status_code == 200 and switched.get_json()['data']['summary']['operations'] == 2
    assert case.conn.total_changes == before
    case.conn.execute("UPDATE Machines SET name='Changed outside selected scope' WHERE machine_id='M3'")
    case.conn.commit()
    stale_choices = client.get(url + '/export', query_string=export_scope)
    assert stale_choices.status_code == 409 and stale_choices.get_json()['error']['code'] == 'snapshot_stale'
    case.conn.execute("INSERT INTO Machines(machine_id,name) VALUES ('M2','Historical lathe')")
    case.conn.execute("INSERT INTO MachineOpTypes(machine_id,op_type_id) VALUES ('M2','T1')")
    case.conn.execute("INSERT INTO OperatorMachine(operator_id,machine_id) VALUES ('O1','M2')")
    case.conn.commit()
    historical_ref = case.ref('machine', 'M2')
    case.command('create', case.task(2, case.op_id), case.values(10, actual_machine_ref=historical_ref))
    case.conn.execute("DELETE FROM OperatorMachine WHERE machine_id='M2'")
    case.conn.execute("DELETE FROM Machines WHERE machine_id='M2'")
    case.conn.commit()
    empty = client.get(url, query_string={'resource_type': 'machine', 'resource_ref': historical_ref,
        'plan_finish_date_from': '2026-09-20', 'plan_finish_date_to': '2026-09-20'})
    assert empty.status_code == 200 and empty.get_json()['data']['summary']['operations'] == 0
    case.command('create', case.task(2, others[0]), {'effective_processing_hours': 0})
    before = case.conn.total_changes
    uncertain = {'batch_ref': other_ref, 'resource_type': 'machine', 'resource_ref': historical_ref}
    planned = client.get(url, query_string={**uncertain, 'resource_ref': case.ref('machine', 'M3')})
    assert planned.status_code == 200 and planned.get_json()['data']['summary']['operations'] == 2
    unreported = client.get(url, query_string={**uncertain, 'focus': 'unreported'})
    assert unreported.status_code == 200 and unreported.get_json()['data']['summary']['operations'] == 0
    omitted = client.get(url, query_string={**uncertain, 'resource_ref': 'unassigned'})
    assert omitted.status_code == 200 and omitted.get_json()['data']['summary']['operations'] == 1
    assert case.conn.total_changes == before
    export_scope['snapshot_ref'] = client.get(url, query_string=dates).get_json()['meta']['snapshot_ref']
    reader = plan_queries.WorkbenchPlanQueryService(case.conn)
    with reader.read_snapshot() as context:
        selected, _ = context.selected(case.plan_ref(2))
        assert selected.can_view
        with pytest.raises(WorkbenchCommandRejected) as rejection:
            reader.workspace(context, PlanReadScope(case.plan_ref(2)))
    assert rejection.value.code == 'query_too_large'
    update_schedule_rows(case.conn, 2, where="op_id = ?", params=(case.op_id,), end_time='2026-09-09 23:59:59.234567')
    case.conn.commit()
    stale = client.get(url + '/export', query_string=export_scope)
    assert stale.status_code == 409 and stale.get_json()['error']['code'] == 'snapshot_stale'
    reused = report_facts.WorkbenchReportFacts(case.conn)
    scope = ReportScope(**dates)
    with reused.read_snapshot() as plan_context:
        assert len(reused.read(plan_context, scope, bind_snapshot=lambda _scope, _fp: None)['rows']) == 1

def test_workbench_report_restores_second_page_once_and_keeps_export_binding(ledger_case, monkeypatch, record_property):
    from flask import Blueprint, Flask, g

    from core.services.workbench.report.facts import WorkbenchReportFacts
    from web.routes.workbench.reports import register_report_routes

    case = ledger_case
    others = [case.op('R18-' + str(index), seq=index) for index in range(2, 12)]
    case.plan(2, [case.op_id] + others)
    app = Flask('direct-report-page')
    install_wall_clock(app, datetime.now)
    app.config.update(TESTING=True, SECRET_KEY='temporary-direct-report-page')
    bp = Blueprint('direct_report_page', __name__)
    register_report_routes(bp)
    app.register_blueprint(bp)

    @app.before_request
    def database():
        g.db = case.conn

    original, calls = WorkbenchReportFacts.read, []

    def captured(reader, plan_context, scope, **kwargs):
        calls.append(scope)
        return original(reader, plan_context, scope, **kwargs)

    client, url, query = app.test_client(), '/api/workbench/v1/analytics', {'page': 2, 'size': 10}
    before = case.conn.total_changes
    with monkeypatch.context() as patch:
        patch.setattr(WorkbenchReportFacts, 'read', captured)
        response = client.get(url, query_string=query)
    assert response.status_code == 200, response.get_json()
    direct = response.get_json()
    assert len(calls) == 1 and direct['data']['page']['number'] == 2
    assert direct['data']['page']['total'] == 11 and len(direct['data']['rows']) == 1
    record_property('direct_page', 2)
    record_property('fact_query_calls', len(calls))
    record_property('data_fields', sorted(direct['data']))
    token = direct['meta']['snapshot_ref']
    from core.services.workbench.report import queries as report_queries

    def unwanted_workspace(*args, **kwargs):
        raise AssertionError('A detail read must not build the list workspace')

    detail_url = url + '/operations/' + direct['data']['rows'][0]['operation_ref']
    from core.models.workbench_execution import ExecutionProjection

    to_dict_calls, orig_to_dict = [], ExecutionProjection.to_dict

    def counted_to_dict(self):
        to_dict_calls.append(self.operation_ref)
        return orig_to_dict(self)

    with monkeypatch.context() as patch:
        patch.setattr(report_queries, 'summary', unwanted_workspace)
        patch.setattr(report_queries, 'charts', unwanted_workspace)
        patch.setattr(ExecutionProjection, 'to_dict', counted_to_dict)
        detail = client.get(detail_url, query_string={**query, 'snapshot_ref': token})
    assert detail.status_code == 200, detail.get_json()
    assert to_dict_calls == [direct['data']['rows'][0]['operation_ref']]
    assert set(detail.get_json()['data']) == {'plan', 'detail'}
    assert detail.get_json()['data']['detail']['operation'] == direct['data']['rows'][0]
    excluded_scope = {'query': 'no matching operation'}
    excluded = client.get(url, query_string=excluded_scope).get_json()
    outside = client.get(detail_url, query_string={**excluded_scope, 'snapshot_ref': excluded['meta']['snapshot_ref']})
    assert outside.status_code == 404 and outside.get_json()['error']['code'] == 'entity_not_found'
    repeated = client.get(url, query_string={**query, 'snapshot_ref': token}).get_json()
    assert repeated['data'] == direct['data'] and repeated['meta'].keys() == direct['meta'].keys()
    assert repeated['meta']['request_ref'] != direct['meta']['request_ref']
    assert all(repeated['meta'][key] == value for key, value in direct['meta'].items() if key != 'request_ref')
    for target in (url + '/export', url + '/operations/' + direct['data']['rows'][0]['operation_ref']):
        missing = client.get(target, query_string=query)
        assert missing.status_code == 400 and missing.get_json()['error']['code'] == 'snapshot_required'
        bound = client.get(target, query_string={**query, 'snapshot_ref': token})
        assert bound.status_code == 200, bound.get_json()
    changed = client.get(url, query_string={**query, 'batch_ref': case.ref('batch', 'B1'), 'snapshot_ref': token})
    assert changed.status_code == 409 and changed.get_json()['error']['code'] == 'snapshot_stale'
    assert case.conn.total_changes == before
    # Catalog pages use the same direct-page snapshot contract.
    from web.routes.workbench import reports_catalog

    for index, operation_id in enumerate(others, 2):
        machine_id = 'R18-CATALOG-' + str(index)
        case.conn.execute("INSERT INTO Machines(machine_id,name) VALUES (?,?)", (machine_id, 'Catalog machine ' + str(index)))
        case.conn.execute("INSERT INTO MachineOpTypes(machine_id,op_type_id) VALUES (?,'T1')", (machine_id,))
        update_schedule_rows(case.conn, 2, where="op_id = ?", params=(operation_id,), machine_id=machine_id, sync_history=False)
    case.conn.commit()
    catalog_calls, catalog_read = [], reports_catalog.catalog_facts

    def captured_catalog(reader, plan_context, scope, **kwargs):
        catalog_calls.append(scope)
        return catalog_read(reader, plan_context, scope, **kwargs)

    catalog_url = '/api/workbench/v1/reports/utilization'
    from contextlib import contextmanager

    admitted = []

    @contextmanager
    def catalog_slot():
        admitted.append(True)
        yield

    with monkeypatch.context() as patch:
        patch.setattr(reports_catalog.PLAN_READ_SLOTS, 'slot', catalog_slot)
        rejected = client.get(catalog_url, query_string={'snapshot_ref': 'invalid'})
        assert rejected.status_code == 409 and rejected.get_json()['error']['code'] == 'snapshot_stale'
        for invalid_page in ('１', '+1', '0'):
            rejected = client.get(catalog_url, query_string={'page': invalid_page})
            assert rejected.status_code == 400 and rejected.get_json()['error']['code'] == 'invalid_input'
    assert admitted == []
    before = case.conn.total_changes
    with monkeypatch.context() as patch:
        patch.setattr(reports_catalog, 'catalog_facts', captured_catalog)
        response = client.get(catalog_url, query_string=query)
    assert response.status_code == 200, response.get_json()
    direct_catalog = response.get_json()
    assert len(catalog_calls) == 1 and direct_catalog['data']['page']['number'] == 2
    assert direct_catalog['data']['page']['total'] == 12 and len(direct_catalog['data']['rows']) == 2
    record_property('catalog_direct_page_fact_calls', len(catalog_calls))
    catalog_token = direct_catalog['meta']['snapshot_ref']
    rebound = client.get(catalog_url, query_string={**query, 'snapshot_ref': catalog_token}).get_json()
    assert rebound['data'] == direct_catalog['data']
    missing = client.get(catalog_url + '/export', query_string={**query, 'format': 'csv'})
    assert missing.status_code == 400 and missing.get_json()['error']['code'] == 'snapshot_required'
    from core.services.workbench.report import exports as report_exports

    static_encodes, original_json = [], report_exports.canonical_json

    def capture_scope(value):
        if value is direct_catalog['data']['scope'] or isinstance(value, dict) and value.get('kind') == 'utilization':
            static_encodes.append(value)
        return original_json(value)

    with monkeypatch.context() as patch:
        patch.setattr(report_exports, 'canonical_json', capture_scope)
        exported = client.get(catalog_url + '/export', query_string={**query, 'snapshot_ref': catalog_token, 'format': 'csv'})
    assert len(static_encodes) == 1
    assert exported.status_code == 200 and exported.headers['X-Workbench-Row-Count'] == '12'
    assert case.conn.total_changes == before

def _all_workbook_values(wb) -> str:
    values = []
    for ws in wb.worksheets:
        values.append(ws.title)
        for row in ws.iter_rows():
            for cell in row:
                if cell.value is not None:
                    values.append(str(cell.value))
    return "\n".join(values)

def test_execution_review_xlsx_uses_canonical_labels_when_legacy_export_aliases_exist() -> None:
    row = {
        "batch_id_label": "B1",
        "operation_label": "OP10 / 车削",
        "planned_start_time_label": "2026-05-01 08:00:00",
        "actual_start_time_label": "2026-05-01 08:10:00",
        "start_deviation_label": "晚了 10 分钟",
        "planned_end_time_label": "2026-05-01 09:00:00",
        "actual_end_time_label": "2026-05-01 09:05:00",
        "end_deviation_label": "晚了 5 分钟",
        "planned_resource_label": "计划资源",
        "actual_resource_label": "实际资源",
        "feedback_status_label": "已完工",
        "planned_resource_export_label": "旧计划资源",
        "actual_resource_export_label": "旧实际资源",
    }

    wb = openpyxl.load_workbook(export_execution_review_xlsx([row], summary_rows=[["计划编号", "P1"]]), data_only=True)
    try:
        ws = wb["计划和现场实际"]
        assert [cell.value for cell in ws[1]] == EXPECTED_HEADERS
        assert ws["I2"].value == "计划资源"
        assert ws["J2"].value == "实际资源"
        all_values = _all_workbook_values(wb)
        for token in ("旧计划资源", "旧实际资源"):
            assert token not in all_values
    finally:
        wb.close()


def test_report_date_limit_and_offline_view_contract():
    from datetime import date

    with pytest.raises(ValidationError, match="日期范围不能超过 62 天"):
        ensure_report_date_range_within_limit(date(2026, 1, 1), date(2026, 4, 15))


def test_standalone_execution_xlsx_stream_keeps_canonical_headers():
    output = export_execution_review_xlsx(
        [
            {
                "batch_id_label": "B1",
                "operation_label": "OP10 / 车削",
                "planned_start_time_label": "2026-05-01 08:00:00",
                "actual_start_time_label": "2026-05-01 08:10:00",
                "start_deviation_label": "晚了 10 分钟",
                "planned_end_time_label": "2026-05-01 09:00:00",
                "actual_end_time_label": "2026-05-01 09:05:00",
                "end_deviation_label": "晚了 5 分钟",
                "planned_resource_label": "一号设备 / 张三",
                "actual_resource_label": "二号设备 / 李四",
                "feedback_status_label": "已完工",
            }
        ],
        summary_rows=[["计划编号", "P1"]], write_only=True)
    workbook = openpyxl.load_workbook(BytesIO(output.read()), data_only=True)
    try:
        sheet = workbook["计划和现场实际"]
        assert [cell.value for cell in sheet[1]] == EXPECTED_HEADERS
        assert sheet["J2"].value == "二号设备 / 李四"
    finally:
        workbook.close()


def test_report_workspace_uses_lightweight_ledger_while_detail_and_records_export_load_target_history(
    ledger_case, monkeypatch
):
    import csv
    import json
    from io import StringIO

    from flask import Blueprint, Flask, g

    from core.models.workbench_execution import ExecutionProjection
    from core.services.execution import projection as exec_projection
    from core.services.workbench.report import facts as report_facts
    from web.routes.workbench.reports import register_report_routes

    case = ledger_case
    other_op_id = case.op("OP2", seq=2)
    case.plan(2, [case.op_id, other_op_id])
    created = case.command("create", case.task(2, other_op_id), case.values(5, remark="initial"))["data"]["rows"][0]
    first_report = case.report_projection(created["report_ref"])
    case.command(
        "correct",
        first_report.report_ref,
        {"original_revision_ref": first_report.revision_ref, "reason": "复核数量", "completed_quantity": 6},
    )

    app = Flask("lightweight-report-review")
    install_wall_clock(app, datetime.now)
    app.config.update(TESTING=True, SECRET_KEY="lightweight-report-review-test")
    bp = Blueprint("lightweight_report_review", __name__)
    register_report_routes(bp)
    app.register_blueprint(bp)

    @app.before_request
    def database():
        g.db = case.conn

    client, url = app.test_client(), "/api/workbench/v1/analytics"
    history_calls, orig_build_history = [], exec_projection.build_correction_history

    def counted_history(rows, *args, **kwargs):
        history_calls.append(len(rows))
        return orig_build_history(rows, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(exec_projection, "build_correction_history", counted_history)
        listing = client.get(url)
        records_listing = client.get(url, query_string={"topic": "records"})
    assert listing.status_code == 200, listing.get_json()
    assert records_listing.status_code == 200, records_listing.get_json()
    assert history_calls == []
    assert records_listing.get_json()["data"]["rows"][0]["revision_count"] == 2
    assert records_listing.get_json()["data"]["rows"][0]["completed_quantity"] == 6

    token = listing.get_json()["meta"]["snapshot_ref"]
    with monkeypatch.context() as patch:
        patch.setattr(exec_projection, "build_correction_history", counted_history)
        delivery_export = client.get(
            url + "/export", query_string={"topic": "delivery", "format": "csv", "snapshot_ref": token}
        )
    assert delivery_export.status_code == 200
    assert history_calls == []

    with monkeypatch.context() as patch:
        patch.setattr(exec_projection, "build_correction_history", counted_history)
        records_export = client.get(
            url + "/export", query_string={"topic": "records", "format": "csv", "snapshot_ref": token}
        )
    assert records_export.status_code == 200
    assert history_calls == [2]
    exported_rows = list(csv.DictReader(StringIO(records_export.data.decode("utf-8-sig"))))
    assert len(exported_rows) == 1
    exported_history = json.loads(exported_rows[0]["完整更正记录"])
    assert len(exported_history) == 2 and exported_history[1]["reason"] == "复核数量"

    healthy_ref = case.conn.execute(
        "SELECT ref FROM WorkbenchPlanSourceRefs WHERE kind='operation' AND source_key=? AND active=1",
        (str(case.op_id),),
    ).fetchone()[0]
    other_ref = case.conn.execute(
        "SELECT ref FROM WorkbenchPlanSourceRefs WHERE kind='operation' AND source_key=? AND active=1",
        (str(other_op_id),),
    ).fetchone()[0]

    history_calls.clear()
    to_dict_calls, orig_to_dict = [], ExecutionProjection.to_dict

    def counted_to_dict(self):
        to_dict_calls.append(self.operation_ref)
        return orig_to_dict(self)

    with monkeypatch.context() as patch:
        patch.setattr(exec_projection, "build_correction_history", counted_history)
        patch.setattr(ExecutionProjection, "to_dict", counted_to_dict)
        healthy_detail = client.get(f"{url}/operations/{healthy_ref}", query_string={"snapshot_ref": token})
    assert healthy_detail.status_code == 200, healthy_detail.get_json()
    assert to_dict_calls == [healthy_ref]
    assert history_calls == []

    other_detail = client.get(f"{url}/operations/{other_ref}", query_string={"snapshot_ref": token})
    assert other_detail.status_code == 200, other_detail.get_json()
    assert len(other_detail.get_json()["data"]["detail"]["records"][0]["correction_history"]) == 2

    with monkeypatch.context() as patch:
        patch.setattr(report_facts, "MAX_WINDOW_REPORTS", 1)
        too_many_list = client.get(url)
        too_many_detail = client.get(f"{url}/operations/{healthy_ref}", query_string={"snapshot_ref": token})
    assert too_many_list.status_code == 413 and too_many_list.get_json()["error"]["code"] == "query_too_large"
    assert too_many_detail.status_code == 413 and too_many_detail.get_json()["error"]["code"] == "query_too_large"


def test_unassigned_resource_never_collides_with_literal_none_resource_id_and_external_boundary_holds(ledger_case):
    from flask import Blueprint, Flask, g

    from tests.workbench.execution_ledger_support import END, START, publish_official_plan
    from web.routes.workbench.reports import register_report_routes

    case = ledger_case
    case.conn.execute("INSERT INTO Machines(machine_id,name) VALUES ('None','Literal None Machine')")
    case.conn.execute("INSERT INTO MachineOpTypes(machine_id,op_type_id) VALUES ('None','T1')")
    case.conn.execute("INSERT INTO Operators(operator_id,name) VALUES ('None','Literal None Operator')")
    case.conn.execute("INSERT INTO OperatorMachine(operator_id,machine_id) VALUES ('None','None')")
    case.conn.execute("INSERT INTO Batches(batch_id,part_no,quantity) VALUES ('B2','P1',10), ('B3','P1',10)")
    unassigned_op_id = case.op("OP-UNASSIGNED", batch="B2", seq=1)
    ext_op_id = case.conn.execute(
        """INSERT INTO BatchOperations(op_code,batch_id,seq,op_type_name,source,setup_hours,unit_hours,ext_days)
           VALUES ('OP-EXT','B3',1,'电镀','external',NULL,NULL,2)"""
    ).lastrowid
    publish_official_plan(
        case.conn,
        2,
        [
            {"op_id": case.op_id, "machine_id": "None", "operator_id": "None", "start_time": START, "end_time": END},
            {"op_id": unassigned_op_id, "machine_id": None, "operator_id": None, "start_time": START, "end_time": END},
            {"op_id": ext_op_id, "machine_id": None, "operator_id": None, "start_time": START, "end_time": END},
        ],
    )
    case.conn.commit()

    case.command(
        "create",
        case.task(2, case.op_id),
        case.values(
            10,
            actual_machine_ref=case.ref("machine", "None"),
            actual_operator_ref=case.ref("operator", "None"),
        ),
    )
    case.command(
        "create",
        case.task(2, ext_op_id),
        {
            "actual_start": START,
            "actual_end": END,
            "completed_quantity": 10,
            "effective_processing_hours": 2.0,
            "actual_machine_ref": None,
            "actual_operator_ref": None,
            "remark": "外协回厂",
        },
    )

    app = Flask("none-collision-and-external-boundary")
    install_wall_clock(app, datetime.now)
    app.config.update(TESTING=True, SECRET_KEY="none-collision-test")
    bp = Blueprint("none_collision_and_external_boundary", __name__)
    register_report_routes(bp)
    app.register_blueprint(bp)

    @app.before_request
    def database():
        g.db = case.conn

    client, url = app.test_client(), "/api/workbench/v1/analytics"
    delivery = client.get(url).get_json()["data"]
    assert delivery["summary"]["operations"] == 3
    assert delivery["summary"]["production_reports"] == 2
    # 汇总工时含外协报工（1.5 + 2.0）；资源工时只算自制工序，外协不进设备人员行。
    assert (delivery["summary"]["effective_processing_hours"], delivery["summary"]["unknown_hour_events"]) == (3.5, 0)
    assert [(row["resource_label"], row["effective_processing_hours"]) for row in delivery["resources"]["machines"]] == [
        ("Literal None Machine", 1.5)
    ]
    by_op_label = {row["operation_label"]: row for row in delivery["rows"]}
    assert by_op_label["OP1 / Turning"]["machine_label"] == "Literal None Machine"
    assert by_op_label["OP1 / Turning"]["operator_label"] == "Literal None Operator"
    assert by_op_label["OP-UNASSIGNED / Turning"]["machine_ref"] is None
    assert by_op_label["OP-UNASSIGNED / Turning"]["machine_label"] == "未填写"
    assert by_op_label["OP-UNASSIGNED / Turning"]["operator_ref"] is None
    assert by_op_label["OP-UNASSIGNED / Turning"]["operator_label"] == "未填写"
    assert by_op_label["OP-EXT / 电镀"]["operation_source"] == "external"
    assert by_op_label["OP-EXT / 电镀"]["machine_ref"] is None
    assert by_op_label["OP-EXT / 电镀"]["machine_label"] == "未填写"

    for topic in ("records", "quality"):
        topic_data = client.get(url, query_string={"topic": topic}).get_json()["data"]
        assert topic_data["summary"]["operations"] == 3
        assert topic_data["summary"]["production_reports"] == 2

    machines_data = client.get(url, query_string={"topic": "machines"}).get_json()["data"]
    assert [(r["resource_label"], r["production_reports"]) for r in machines_data["rows"]] == [
        ("Literal None Machine", 1)
    ]
    people_data = client.get(url, query_string={"topic": "people"}).get_json()["data"]
    assert [(r["resource_label"], r["production_reports"]) for r in people_data["rows"]] == [
        ("Literal None Operator", 1)
    ]

    unassigned_filtered = client.get(
        url, query_string={"resource_type": "machine", "resource_ref": "unassigned"}
    ).get_json()["data"]
    assert [row["operation_label"] for row in unassigned_filtered["rows"]] == ["OP-UNASSIGNED / Turning"]
