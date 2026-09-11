"""
冒烟测试：报表、物料和周计划页面基础可用性。

旧的 smoke_* 脚本不会被 pytest 默认收集；这个 regression_* 文件保留同等保护，
并让全量 pytest 能自动覆盖这条入口。
"""

from __future__ import annotations

from urllib.parse import parse_qs, urlsplit

from core.infrastructure.database import get_connection
from tests._support.legacy_http import LegacyHTML, assert_retired_response, canonical_navigation
from tests._support.sqlite_snapshot import table_rows


def _assert_status(resp, name: str, expect: int = 200) -> None:
    if resp.status_code != expect:
        body = resp.data.decode("utf-8", errors="ignore") if getattr(resp, "data", None) else ""
        raise RuntimeError(f"{name} 返回 {resp.status_code}，期望 {expect}，body={body[:500]}")


def test_reports_material_weekplan_pages_smoke(app_client) -> None:
    db_path = app_client.application.config["DATABASE_PATH"]
    conn = get_connection(db_path)
    try:
        conn.execute(
            "INSERT INTO ScheduleHistory(version,strategy,batch_count,op_count,result_status) VALUES(1,'EDD',0,0,'success')"
        )
        conn.commit()
        tables = ("ScheduleHistory", "WorkbenchPlanSourceRefs", "WorkbenchPlanIdentityClock",
                  "WorkbenchEntityRefs", "Materials", "BatchMaterials")
        before = {table: table_rows(conn, table) for table in tables}
    finally:
        conn.close()
    for path in ("/reports/", "/reports/overdue", "/reports/utilization", "/reports/downtime", "/scheduler/week-plan"):
        body = assert_retired_response(app_client.get(path))
        assert "<dt>排产版本</dt><dd>1</dd>" in body
        assert "<dt>方案</dt><dd>正式采用方案</dd>" in body
        assert "未改用新报表默认范围" in body
        if path in ("/reports/overdue", "/reports/utilization", "/reports/downtime"):
            links = [urlsplit(link) for link in LegacyHTML(body).links if urlsplit(link).path == path + "/export"]
            assert len(links) == 1
            assert not links[0].scheme and not links[0].netloc
            assert parse_qs(links[0].query) == {"version": ["1"], "plan_role": ["adopted"]}
    context = canonical_navigation(app_client, app_client.get("/material/materials"), "process")
    assert context == {"source": "production"}
    material_read = app_client.get("/api/workbench/v1/entities/material")
    _assert_status(material_read, "GET /api/workbench/v1/entities/material")
    assert material_read.get_json()["ok"] is True and material_read.get_json()["data"]["entities"] == []
    assert_retired_response(app_client.get("/material/batches"))
    conn = get_connection(db_path)
    try:
        assert before == {table: table_rows(conn, table) for table in tables}
    finally:
        conn.close()
