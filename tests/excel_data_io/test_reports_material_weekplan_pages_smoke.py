"""
冒烟测试：报表、物料和周计划页面基础可用性。

旧的 smoke_* 脚本不会被 pytest 默认收集；这个 regression_* 文件保留同等保护，
并让全量 pytest 能自动覆盖这条入口。
"""

from __future__ import annotations


def _assert_status(resp, name: str, expect: int = 200) -> None:
    if resp.status_code != expect:
        body = resp.data.decode("utf-8", errors="ignore") if getattr(resp, "data", None) else ""
        raise RuntimeError(f"{name} 返回 {resp.status_code}，期望 {expect}，body={body[:500]}")


def test_reports_material_weekplan_pages_smoke(app_client) -> None:
    _assert_status(app_client.get("/reports/"), "GET /reports/")
    _assert_status(app_client.get("/reports/overdue"), "GET /reports/overdue")
    _assert_status(app_client.get("/reports/utilization"), "GET /reports/utilization")
    _assert_status(app_client.get("/reports/downtime"), "GET /reports/downtime")
    _assert_status(app_client.get("/material/materials"), "GET /material/materials")
    _assert_status(app_client.get("/material/batches"), "GET /material/batches")
    _assert_status(app_client.get("/scheduler/week-plan"), "GET /scheduler/week-plan")
