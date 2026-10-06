"""回归测试：/reports/execution-review “计划和现场实际”页与 xlsx 导出——按计划身份精确匹配现场反馈，无反馈时显示“暂无现场反馈”，身份不匹配时忽略反馈，匹配时展示实际开工/完工偏差、暂停、异常、计划/实际资源等，且页面与工作簿都不泄漏 event_type/plan_role/source_table/schedule_id 等内部字段；含日期参数校验、报表索引/资源派工入口、场景导航禁用、流式导出与离线模板契约。"""

from __future__ import annotations

from io import BytesIO

import openpyxl
import pytest

from core.errors import ValidationError
from core.infrastructure.database import get_connection
from core.models.operation_execution_labels import action_to_event_type
from core.services.report import ReportEngine
from core.services.report.execution_review import _execution_scope
from core.services.report.exporters.xlsx import export_execution_review_xlsx
from data.repositories.operation_execution_event_repo import OperationExecutionEventRepo
from tests._support.paths import REPO_ROOT
from tests.operation_execution.operation_execution_feedback_test_support import _build_app
from tests.workbench.template_lineage_support import ledger_fixture as _ledger_fixture  # noqa: F401

EXPECTED_HEADERS = [
    "批次",
    "工序",
    "计划开始",
    "实际开始",
    "开工偏差",
    "计划结束",
    "实际结束",
    "完工偏差",
    "暂停时长",
    "异常原因",
    "严重程度",
    "预计影响时间",
    "影响设备",
    "影响人员",
    "处理状态",
    "是否建议重新排程",
    "计划资源",
    "实际资源",
    "现场反馈状态",
]

DEAD_EXECUTION_REVIEW_LABEL_KEYS = (
    "exception_affected_machine_identity_label",
    "exception_affected_machine_export_label",
    "exception_affected_operator_identity_label",
    "exception_affected_operator_export_label",
    "planned_resource_identity_label",
    "planned_resource_export_label",
    "actual_resource_identity_label",
    "actual_resource_export_label",
)


def test_workbench_report_bounds_finish_cohort_before_detail_admission(ledger_case, monkeypatch):
    from flask import Blueprint, Flask, g

    from core.models.workbench_command import WorkbenchCommandRejected
    from core.models.workbench_report import ReportScope
    from core.services.workbench.plan import queries as plan_queries
    from core.services.workbench.report import facts as report_facts
    from web.routes.workbench.reports import register_report_routes

    case = ledger_case
    case.install()
    case.conn.execute("INSERT INTO Batches(batch_id,part_no,quantity) VALUES ('B2','P1',10)")
    case.conn.execute("INSERT INTO Machines(machine_id,name,op_type_id) VALUES ('M3','Other batch lathe','T1')")
    others = [case.op('CROSS-' + str(index), batch='B2', seq=index) for index in (1, 2)]
    case.plan(2, [case.op_id] + others, end='2026-09-10 00:00:00')
    case.conn.execute("UPDATE Schedule SET machine_id='M3' WHERE version=2 AND op_id<>?", (case.op_id,))
    case.conn.execute("UPDATE Schedule SET end_time='2026-09-09T23:59:59.123456' WHERE version=2 AND op_id=?", (case.op_id,))
    case.conn.commit()
    monkeypatch.setattr(plan_queries, 'MAX_PLAN_TASKS', 2)
    monkeypatch.setattr(report_facts, 'MAX_REPORT_OPERATIONS', 2)
    app = Flask('bounded-finish-report')
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
    first = client.get(url, query_string=dates)
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
    case.conn.execute("INSERT INTO Machines(machine_id,name,op_type_id) VALUES ('M2','Historical lathe','T1')")
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
    # A replacement with the same business code cannot identify which old
    # resource instance a preserved event actually used.
    case.conn.execute("INSERT INTO Machines(machine_id,name,op_type_id) VALUES ('M2','Replacement lathe','T1')")
    schedule_id = case.conn.execute('SELECT id FROM Schedule WHERE version=2 AND op_id=?', (others[0],)).fetchone()[0]
    case.conn.execute("""INSERT INTO OperationExecutionEvents
        (schedule_version,schedule_id,op_id,batch_id,source_table,effective_plan_role,event_type,reported_status,
         event_time,actual_machine_id,idempotency_key,request_fingerprint,previous_state_revision,created_by)
        VALUES (2,?,?,'B2','schedule','adopted','start','processing','2026-09-09T08:00:00',
                'M2','unresolved-resource-review','unresolved-resource-review',?,'old-operator')""",
        (schedule_id, others[0], str(others[0]) + ':0:0'))
    case.conn.commit()
    before = case.conn.total_changes
    uncertain = {'batch_ref': other_ref, 'resource_type': 'machine', 'resource_ref': historical_ref}
    unresolved = client.get(url, query_string=uncertain)
    assert unresolved.status_code == 409 and unresolved.get_json()['error']['code'] == 'execution_resource_unavailable'
    unresolved = client.get(url, query_string={**uncertain, 'resource_ref': 'unassigned'})
    assert unresolved.status_code == 409 and unresolved.get_json()['error']['code'] == 'execution_resource_unavailable'
    planned = client.get(url, query_string={**uncertain, 'resource_ref': case.ref('machine', 'M3')})
    assert planned.status_code == 200 and planned.get_json()['data']['summary']['operations'] == 2
    people = client.get(url, query_string={**uncertain, 'resource_type': 'operator', 'resource_ref': 'unassigned'})
    assert people.status_code == 200 and people.get_json()['data']['summary']['operations'] == 1
    unreported = client.get(url, query_string={**uncertain, 'focus': 'unreported'})
    assert unreported.status_code == 200 and unreported.get_json()['data']['summary']['operations'] == 0
    assert case.conn.total_changes == before
    case.command('create', case.task(2, others[0]), {'effective_processing_hours': 0})
    before = case.conn.total_changes
    omitted = client.get(url, query_string={**uncertain, 'resource_ref': 'unassigned'})
    assert omitted.status_code == 200 and omitted.get_json()['data']['summary']['operations'] == 1
    assert case.conn.total_changes == before
    export_scope['snapshot_ref'] = client.get(url, query_string=dates).get_json()['meta']['snapshot_ref']
    reader = plan_queries.WorkbenchPlanQueryService(case.conn)
    with pytest.raises(WorkbenchCommandRejected) as rejection, reader.read_snapshot():
        reader._selected(case.plan_ref(2))
    assert rejection.value.code == 'query_too_large'
    case.conn.execute("UPDATE Schedule SET end_time='2026-09-09 23:59:59.234567' WHERE version=2 AND op_id=?", (case.op_id,))
    case.conn.commit()
    stale = client.get(url + '/export', query_string=export_scope)
    assert stale.status_code == 409 and stale.get_json()['error']['code'] == 'snapshot_stale'
    reused = report_facts.WorkbenchReportFacts(case.conn)
    scope = ReportScope(**dates)
    with reused.read_snapshot():
        assert len(reused.read(scope)['rows']) == 1
    case.conn.execute("UPDATE Schedule SET end_time='invalid' WHERE version=2 AND op_id=?", (others[0],))
    case.conn.commit()
    with pytest.raises(WorkbenchCommandRejected) as rejection, reused.read_snapshot():
        reused.read(scope)
    assert rejection.value.code == 'plan_unavailable'
    invalid = client.get(url, query_string=dates)
    assert invalid.status_code == 409 and invalid.get_json()['error']['code'] == 'plan_unavailable'


def _insert_event(repo: OperationExecutionEventRepo, **overrides) -> None:
    event_type = action_to_event_type(overrides.get("event_type") or "start")
    reported_status = {
        "start": "processing",
        "pause": "paused",
        "resume": "processing",
        "exception": "exception",
        "finish": "completed",
    }[event_type]
    payload = {
        "schedule_version": 1,
        "schedule_id": 101,
        "op_id": 10,
        "batch_id": "B1",
        "source_table": "schedule",
        "effective_plan_role": "adopted",
        "scenario_id": None,
        "event_type": event_type,
        "reported_status": reported_status,
        "event_time": "2026-05-01 08:10:00",
        "actual_machine_id": None,
        "actual_operator_id": None,
        "quantity_done": None,
        "quantity_scrapped": None,
        "reason_code": None,
        "reason_detail": None,
        "severity": None,
        "impact_minutes": None,
        "affected_machine_id": None,
        "affected_operator_id": None,
        "handling_status": None,
        "suggest_reschedule": 0,
        "remark": None,
        "created_by": "pytest",
        "idempotency_key": f"execution-review-{event_type}-{overrides.get('previous_state_revision')}",
        "request_fingerprint": f"execution-review-{event_type}-{overrides.get('previous_state_revision')}",
        "previous_state_revision": "10:0:0",
    }
    payload.update(overrides)
    payload["event_type"] = action_to_event_type(payload["event_type"])
    payload["reported_status"] = {
        "start": "processing",
        "pause": "paused",
        "resume": "processing",
        "exception": "exception",
        "finish": "completed",
    }[payload["event_type"]]
    repo.insert_event(payload)


def _seed_execution_events(db_path: str, **identity) -> None:
    conn = get_connection(db_path)
    try:
        repo = OperationExecutionEventRepo(conn)
        _insert_event(
            repo,
            **identity,
            event_type="start",
            event_time="2026-05-01 08:10:00",
            actual_machine_id="M2",
            actual_operator_id="O2",
            previous_state_revision="10:0:0",
        )
        _insert_event(
            repo,
            **identity,
            event_type="pause",
            event_time="2026-05-01 08:20:00",
            reason_code="equipment",
            remark="设备检查",
            previous_state_revision="10:1:1",
        )
        _insert_event(
            repo,
            **identity,
            event_type="resume",
            event_time="2026-05-01 08:35:00",
            remark="继续生产",
            previous_state_revision="10:2:2",
        )
        _insert_event(
            repo,
            **identity,
            event_type="exception",
            event_time="2026-05-01 08:45:00",
            reason_code="equipment",
            reason_detail="主轴异常",
            severity="high",
            impact_minutes=30,
            affected_machine_id="M2",
            affected_operator_id="O2",
            handling_status="checking",
            suggest_reschedule=1,
            remark="主轴异常",
            previous_state_revision="10:3:3",
        )
        _insert_event(
            repo,
            **identity,
            event_type="finish",
            event_time="2026-05-01 09:05:00",
            quantity_done=10,
            quantity_scrapped=0,
            remark="完成",
            previous_state_revision="10:4:4",
        )
        conn.commit()
    finally:
        conn.close()


def _all_workbook_values(wb) -> str:
    values = []
    for ws in wb.worksheets:
        values.append(ws.title)
        for row in ws.iter_rows():
            for cell in row:
                if cell.value is not None:
                    values.append(str(cell.value))
    return "\n".join(values)


def _assert_stream_export(db_path: str) -> None:
    conn = get_connection(db_path)
    try:
        engine = ReportEngine(conn)
        engine.EXPORT_DIRECT_MAX_ROWS = 0
        export = engine.export_execution_review_xlsx(2, date_from="2026-05-01", date_to="2026-05-01", batch_id="B1")
        assert export.mode == "stream"
        export.data.seek(0)
        wb = openpyxl.load_workbook(BytesIO(export.data.read()), data_only=True)
        try:
            assert "计划和现场实际" in wb.sheetnames
            ws = wb["计划和现场实际"]
            assert [cell.value for cell in ws[1]] == EXPECTED_HEADERS
            assert ws["R2"].value == "二号设备 / 李四"
        finally:
            wb.close()
    finally:
        conn.close()


def test_execution_review_rows_do_not_emit_dead_label_aliases(tmp_path, monkeypatch) -> None:
    _app, db_path = _build_app(tmp_path, monkeypatch)
    _seed_execution_events(db_path, schedule_version=2, schedule_id=100)
    conn = get_connection(db_path)
    try:
        report = ReportEngine(conn).execution_review(2, date_from="2026-05-01", date_to="2026-05-01", batch_id="B1")
    finally:
        conn.close()

    assert report["rows"]
    row = report["rows"][0]
    for key in DEAD_EXECUTION_REVIEW_LABEL_KEYS:
        assert key not in row
    assert row["planned_resource_label"] == "一号设备 / 张三"
    assert row["actual_resource_label"] == "二号设备 / 李四"


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
        "pause_duration_label": "15 分钟",
        "exception_reason_label": "设备问题",
        "exception_severity_label": "严重",
        "exception_impact_minutes_label": "预计影响 30 分钟",
        "exception_affected_machine_label": "影响设备",
        "exception_affected_operator_label": "影响人员",
        "exception_handling_status_label": "处理中",
        "exception_suggest_reschedule_label": "建议重新排程",
        "planned_resource_label": "计划资源",
        "actual_resource_label": "实际资源",
        "feedback_status_label": "已完工",
        "exception_affected_machine_export_label": "旧影响设备",
        "exception_affected_operator_export_label": "旧影响人员",
        "planned_resource_export_label": "旧计划资源",
        "actual_resource_export_label": "旧实际资源",
    }

    wb = openpyxl.load_workbook(export_execution_review_xlsx([row]), data_only=True)
    try:
        ws = wb["计划和现场实际"]
        assert [cell.value for cell in ws[1]] == EXPECTED_HEADERS
        assert ws["M2"].value == "影响设备"
        assert ws["N2"].value == "影响人员"
        assert ws["Q2"].value == "计划资源"
        assert ws["R2"].value == "实际资源"
        all_values = _all_workbook_values(wb)
        for token in ("旧影响设备", "旧影响人员", "旧计划资源", "旧实际资源"):
            assert token not in all_values
    finally:
        wb.close()


def test_execution_review_validation_and_offline_template_contract(tmp_path, monkeypatch) -> None:
    _app, _db_path = _build_app(tmp_path, monkeypatch)

    conn = get_connection(_db_path)
    try:
        with pytest.raises(ValidationError, match="日期范围不能超过 62 天"):
            ReportEngine(conn).execution_review(2, date_from="2026-01-01", date_to="2026-04-15")
    finally:
        conn.close()

    assert not (REPO_ROOT / "templates/reports/execution_review.html").exists()
    forbidden = ("http://", "https://", "cdn", "reason_code", "event_type", "report_exception", "text-meta")
    for relative in ("frontend/workbench/app/ReviewWorkspace.jsx", "frontend/workbench/app/ReportWorkspace.jsx",
                     "frontend/workbench/app/ReportTable.jsx"):
        source = (REPO_ROOT / relative).read_text(encoding="utf-8")
        for token in forbidden + DEAD_EXECUTION_REVIEW_LABEL_KEYS:
            assert token not in source


def test_execution_review_scope_fails_loudly_when_plan_identity_is_incomplete() -> None:
    with pytest.raises(ValidationError, match="计划数据缺少现场执行身份字段"):
        _execution_scope({"op_id": 10, "batch_id": "B1"}, 10)


def test_execution_review_stream_export_keeps_canonical_headers(tmp_path, monkeypatch) -> None:
    _app, db_path = _build_app(tmp_path, monkeypatch)
    _seed_execution_events(db_path, schedule_version=2, schedule_id=100)
    _assert_stream_export(db_path)
