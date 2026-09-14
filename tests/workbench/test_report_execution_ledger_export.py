"""Whole-snapshot exports retain each report, revision and original reference."""

import csv
import io
import json

import openpyxl
import pytest

from tests.workbench.plan_read_support import assert_error
from tests.workbench.report_execution_ledger_support import report_ledger_api as _fixture


@pytest.mark.parametrize("format_name", ["csv", "xlsx"])
def test_full_report_cohort_export_preserves_zero_null_revisions_and_refs(report_ledger_api, format_name):
    api = report_ledger_api
    first = api.create(api.values(None, effective_processing_hours=None, remark="=1+1"))
    api.revise(first, "supplement", completed_quantity=0, effective_processing_hours=0)
    for _ in range(11):
        api.create(api.values(0, effective_processing_hours=0))
    api.create(api.values(10))
    query = {"topic": "records", "size": 10, "plan_finish_date_from": "2026-09-09", "plan_finish_date_to": "2026-09-09"}
    reading = api.read(**query)
    assert len(reading["data"]["rows"]) == 10 and reading["data"]["page"]["total"] == 13
    snapshot = reading["meta"]["snapshot_ref"]
    before = api.state()
    response = api.get("/export", **query, snapshot_ref=snapshot, format=format_name)
    assert response.status_code == 200, response.get_json()
    assert response.headers["X-Workbench-Row-Count"] == "13"
    if format_name == "csv":
        rows = list(csv.reader(io.StringIO(response.data.decode("utf-8-sig"))))
    else:
        workbook = openpyxl.load_workbook(io.BytesIO(response.data), read_only=True)
        rows = list(workbook["范围全部结果"].values)
        assert dict(workbook["范围与计算方式"].values)["数据版本编号"] == snapshot
        workbook.close()
    assert len(rows) == 14
    values = [dict(zip(rows[0], row)) for row in rows[1:]]
    assert "实际记录时间" in rows[0] and "记录登记数量" in rows[0]
    exported = next(row for row in values if row["报工编号"] == first["report_ref"])
    assert exported["备注"] == "'=1+1"
    revisions = json.loads(exported["完整更正记录"])
    assert revisions[0]["after"]["completed_quantity"] is None
    assert revisions[1]["before"]["completed_quantity"] is None and revisions[1]["after"]["completed_quantity"] == 0
    assert str(exported["本次完成数量"]) == "0" and str(exported["有效加工工时（小时）"]) in ("0", "0.0")
    assert exported["原报工任务编号"] == api.task()["task_ref"]
    assert api.state() == before


def test_plan_finish_date_selects_whole_operation_not_event_time(report_ledger_api):
    api = report_ledger_api
    api.create(api.values(4, actual_start="2026-09-08T23:00:00", actual_end="2026-09-09T00:30:00"))
    first = api.read(topic="records", plan_finish_date_from="2026-09-09", plan_finish_date_to="2026-09-09")
    assert first["data"]["rows"][0]["actual_start"] == "2026-09-08T23:00:00"
    empty = api.read(topic="records", plan_finish_date_from="2026-09-08", plan_finish_date_to="2026-09-08")
    assert empty["data"]["rows"] == []
    assert_error(api.get("/export", topic="records", snapshot_ref=first["meta"]["snapshot_ref"],
        plan_finish_date_from="2026-09-08", plan_finish_date_to="2026-09-08"), "snapshot_stale")


def test_official_review_sheet_reads_new_completion_not_legacy_events(report_ledger_api):
    api = report_ledger_api
    api.create(api.values(10))
    reading = api.read()
    path = "/api/workbench/v1/reports/official-review/export"
    response = api.client.get(path, query_string={"snapshot_ref": reading["meta"]["snapshot_ref"]})
    assert response.status_code == 200, response.get_json()
    workbook = openpyxl.load_workbook(io.BytesIO(response.data), read_only=True)
    cells = [value for row in workbook["计划和现场实际"].values for value in row]
    assert "已完工" in cells and "2026-09-09T10:00:00" in cells
    assert "未确认整道完工" not in cells
    workbook.close()
